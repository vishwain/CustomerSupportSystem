"""FastAPI interface (5.15; PRD FR-29 live view, FR-31 kill switch visible in /health).

Start (repo root, virtual environment active):
    uvicorn src.api:app --port 8000

Endpoints
    POST /tickets   one ticket in, the outcome out: answered or escalated, the reason, the citations and
                    the decision ID of the final decision-log row. Runs the same pipeline as the harness
                    (Ingest, Classify, Retrieve, Route, Generate, Validate), so every request is logged.
    GET  /health    liveness plus which components loaded and whether the kill switch is on.
    GET  /metrics   Prometheus text format. Request and outcome counters now; wired to the full figure set
                    and Grafana at 5b.8.

Malformed input (missing or wrong-typed fields, empty body, unknown channel, broken JSON) is rejected with
HTTP 422 and a list of which field is wrong and why; it never reaches the pipeline and never crashes the
server. A pipeline failure on a valid ticket is not an error to the caller: the harness escalates it and
returns the reason (A11).

Every request gets its own run_id in one decision-log database (STORAGE_DIR/api/decisions.db), so the same
ticket_id can be sent twice and both decisions stay on record.
"""

from __future__ import annotations

import os
import threading
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.ingest import CHANNELS, MAX_TEXT_CHARS, normalise
from src.logging_store import DecisionLog
from src.route import automation_paused

API_VERSION = "api-1.0"
MAX_BODY_CHARS = 20_000  # far above any real ticket; Ingest truncates the cleaned text to MAX_TEXT_CHARS


class TicketIn(BaseModel):
    """One ticket in the pack schema. Unknown extra fields are ignored (the pipeline never reads them)."""

    model_config = ConfigDict(extra="ignore", str_strip_whitespace=False)

    ticket_id: str = Field(..., min_length=1, max_length=100, description="Caller's ticket id")
    channel: Literal["email", "chat", "docs_comment", "forum"]
    subject: str = Field("", max_length=1000)
    body: str = Field(..., max_length=MAX_BODY_CHARS)
    received_at: str | None = Field(None, description="ISO 8601; flagged, not rejected, if unparseable")
    customer_id: str | None = None
    customer_name: str | None = None

    @field_validator("ticket_id")
    @classmethod
    def _id_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("must not be blank")
        return v.strip()

    @field_validator("body")
    @classmethod
    def _body_has_text(cls, v: str) -> str:
        if not "".join(v.split()):
            raise ValueError("must contain text (empty or whitespace-only body)")
        return v


class Citation(BaseModel):
    passage_id: str
    doc_id: str
    title: str


class TicketOut(BaseModel):
    ticket_id: str
    outcome: Literal["answered", "escalated"]
    action: str  # auto_respond | escalate (decision-log value)
    reason: str
    rule_fired: str
    citations: list[Citation]
    reply: str | None  # the sent answer, when answered
    customer_message: str  # what the customer receives: the answer, or the holding message
    escalation_summary: str | None
    intent: str
    intent_confidence: float
    decision_id: str  # final decision-log row
    run_id: str
    latency_ms: int


class _State:
    comp = None
    db_path: Path = Path("storage/api/decisions.db")
    started = time.time()
    lock = threading.Lock()  # one ticket at a time: shared provider pacing, SQLite writes
    counts: dict[str, int] = {}
    latency_ms_sum = 0
    latency_n = 0


S = _State()


def _count(key: str, n: int = 1) -> None:
    S.counts[key] = S.counts.get(key, 0) + n


def load_components():
    """Same loading as the harness. API_NO_MODELS=1 / API_NO_LLM=1 start a degraded server (every ticket
    escalates), which is how the tests and a machine without the model run it."""
    from evaluation.harness import build_components

    return build_components(no_llm=os.getenv("API_NO_LLM") == "1", no_models=os.getenv("API_NO_MODELS") == "1")


@asynccontextmanager
async def lifespan(app: FastAPI):
    if S.comp is None:
        S.comp = load_components()
    S.db_path = Path(os.getenv("STORAGE_DIR", "storage")) / "api" / "decisions.db"
    S.db_path.parent.mkdir(parents=True, exist_ok=True)
    S.started = time.time()
    yield


app = FastAPI(title="CloudServe support pipeline", version=API_VERSION, lifespan=lifespan)


@app.exception_handler(RequestValidationError)
async def invalid_ticket(request: Request, exc: RequestValidationError) -> JSONResponse:
    _count("invalid")
    details = []
    for e in exc.errors():
        loc = [str(x) for x in e.get("loc", [])]
        if loc and loc[0] == "body":  # FastAPI prefixes the request body; keep the field name itself
            loc = loc[1:]
        details.append({"field": ".".join(loc) or "(request body)", "problem": e.get("msg", "invalid"),
                        **({"allowed": list(CHANNELS)} if loc == ["channel"] else {})})
    return JSONResponse(status_code=422, content={
        "error": "invalid ticket", "details": details,
        "expected": {"ticket_id": "string", "channel": list(CHANNELS), "subject": "string (optional)",
                     "body": "non-empty string", "received_at": "ISO 8601 (optional)"}})


def _citations(rows: list[dict[str, Any]]) -> list[Citation]:
    gen = next((r for r in rows if r["stage"] == "generation"), None)
    if not gen:
        return []
    titles = {}
    retr = getattr(S.comp, "retriever", None)
    by_id = getattr(retr, "_by_id", {}) if retr is not None else {}
    for s in gen.get("sources_used", []):
        p = by_id.get(s["passage_id"])
        titles[s["passage_id"]] = Citation(passage_id=s["passage_id"], doc_id=s["doc_id"],
                                           title=p.title if p else s["doc_id"])
    return list(titles.values())


@app.post("/tickets", response_model=TicketOut)
def post_ticket(t: TicketIn) -> TicketOut:
    from evaluation.harness import process_ticket

    run_id = f"api-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:6]}"
    rec = normalise(t.model_dump(), 0)
    with S.lock:
        log = DecisionLog(S.db_path, run_id)
        try:
            log.start_run(f"api:{rec.ticket_id}", "api-request", notes=API_VERSION)
            r = process_ticket(rec, log, S.comp)
            rows = log.rows(rec.ticket_id)
            log.finish_run(1, 1, "completed")
        finally:
            log.close()
    final = next(x for x in rows if x["stage"] == "final")
    answered = r["action"] == "auto_respond"
    _count("answered" if answered else "escalated")
    _count(f"rule:{r['rule_fired']}")
    S.latency_ms_sum += r["latency_ms"]
    S.latency_n += 1
    pkg = r.get("escalation_package") or {}
    return TicketOut(
        ticket_id=rec.ticket_id, outcome="answered" if answered else "escalated", action=r["action"],
        reason=r["reason"], rule_fired=r["rule_fired"], citations=_citations(rows) if answered else [],
        reply=r["reply"] if answered else None, customer_message=r.get("customer_message") or "",
        escalation_summary=None if answered else pkg.get("summary"),
        intent=r["intent"], intent_confidence=float(r["intent_confidence"]),
        decision_id=final["decision_id"], run_id=run_id, latency_ms=r["latency_ms"])


@app.get("/health")
def health() -> dict[str, Any]:
    c = S.comp
    loaded = {k: getattr(c, k, None) is not None for k in ("classifier", "retriever", "generator", "validator")}
    paused, why = automation_paused()
    status = "ok" if all(loaded.values()) else "degraded"
    return {"status": status, "version": API_VERSION, "uptime_s": int(time.time() - S.started),
            "components": loaded, "automation_paused": paused, **({"pause_note": why} if why else {}),
            "can_answer_automatically": all(loaded.values()) and not paused,
            "tickets_processed": S.counts.get("answered", 0) + S.counts.get("escalated", 0)}


@app.get("/metrics", response_class=PlainTextResponse)
def metrics() -> str:
    """Prometheus text exposition. Stub until 5b.8 (prometheus_client, latency histogram, confidence)."""
    L = ["# HELP support_tickets_total Tickets processed by outcome.", "# TYPE support_tickets_total counter"]
    for o in ("answered", "escalated"):
        L.append(f'support_tickets_total{{outcome="{o}"}} {S.counts.get(o, 0)}')
    L += ["# HELP support_rule_fired_total Final rule per ticket (none = no rule).",
          "# TYPE support_rule_fired_total counter"]
    for k, v in sorted(S.counts.items()):
        if k.startswith("rule:"):
            L.append(f'support_rule_fired_total{{rule="{k[5:]}"}} {v}')
    L += ["# HELP support_invalid_requests_total Requests rejected as malformed (HTTP 422).",
          "# TYPE support_invalid_requests_total counter", f"support_invalid_requests_total {S.counts.get('invalid', 0)}",
          "# HELP support_latency_ms_sum Total ingest-to-final latency.", "# TYPE support_latency_ms_sum counter",
          f"support_latency_ms_sum {S.latency_ms_sum}", "# TYPE support_latency_ms_count counter",
          f"support_latency_ms_count {S.latency_n}",
          "# HELP support_automation_paused Kill switch state (1 = paused).", "# TYPE support_automation_paused gauge",
          f"support_automation_paused {int(automation_paused()[0])}"]
    return "\n".join(L) + "\n"


__all__ = ["app", "MAX_TEXT_CHARS"]
