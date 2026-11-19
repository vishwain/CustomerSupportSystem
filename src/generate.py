"""Generate (A6; PRD FR-07, FR-13, FR-14, FR-15, FR-16, FR-17, FR-18, FR-20). Prompt PR-03.

Runs only when Route chose auto_respond (mode 'answer') or draft_for_review (mode 'draft'). Route never
sends a ticket here when a hard rule fired or no passage passed the cutoff: those escalate with no model
call ("I don't know" behaviour, FR-11, FR-16).

Steps
  1. Render PR-03: ticket inside <<<TICKET>>>, passages inside <<<PASSAGES>>>, '<<<' and '>>>' removed from
     both first (FR-17). Passages shown as "[<passage_id>] <title> / <section>" then the text.
  2. One provider call (src/llm.py: timeouts, 429s, outage handled there).
  3. Parse: lenient JSON extraction, then src/schemas/answer.json. If it fails, one PR-04 repair call, then
     parse again. Still failing: escalate, error = bad_output (PRD 10.6).
  4. Citation check IN CODE (FR-15, FR-22 item 2): every sentence has at least one passage id, and every
     cited id is one of the passages retrieved and shown for THIS ticket. Any miss: escalate.
  5. Reply assembled by code, not the model (FR-18): automated label, greeting, the cited sentences, sign-off,
     then 'Sources:' with title, doc_id and review age (FR-10) of each cited article.

Validate (5.9: private data, grounding floor, commitments) runs after this and can still block.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.classify import _loads_lenient
from src.prompts import load_prompt, strip_delimiters

ANSWER_SCHEMA = Path("src/schemas/answer.json")
MESSAGES_CONFIG = Path("config/messages.json")
GENERATION_CONFIG = Path("config/generation.json")


def prompt_from_config(path: str | Path = GENERATION_CONFIG) -> str:
    """Which PR-03 file runs (config/generation.json, written by docs/generate_eval.py). Missing = v1."""
    p = Path(path)
    if not p.exists():
        return "build/generate_v1.txt"
    return json.loads(p.read_text(encoding="utf-8"))["prompt"]


@dataclass
class GenerationResult:
    mode: str  # answer | draft
    can_answer: bool = False
    sentences: list[dict[str, Any]] = field(default_factory=list)  # [{"text", "passage_ids"}]
    unsure_about: str = ""
    escalation_summary: str = ""
    restatement: str = ""
    error: str = "none"  # none | bad_output | citation | timeout | rate_limit | provider_down
    reason: str = ""
    citations_ok: bool = False
    unresolved: list[str] = field(default_factory=list)
    cited: list[str] = field(default_factory=list)  # distinct passage ids cited, in first-use order
    repairs: list[str] = field(default_factory=list)
    prompt_version: str = ""
    model: str = ""
    requests: int = 0
    retries: int = 0
    cached: bool = False  # every provider response for this ticket came from the cache
    rate_limit_wait_ms: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    latency_ms: int = 0
    degraded: bool = False
    raw: str = ""

    @property
    def usable(self) -> bool:
        """A grounded answer that passed the citation check. Validate still runs after this."""
        return self.error == "none" and self.can_answer and self.citations_ok and bool(self.sentences)

    @property
    def action(self) -> str:  # decision-log action for the generation stage
        if self.error not in ("none", "citation"):
            return "failed"
        if not self.can_answer:
            return "cannot_answer"
        if not self.citations_ok:
            return "failed"
        return "answer" if self.mode == "answer" else "draft"


def render_passages(passages) -> str:
    return "\n".join(f"[{p.passage_id}] {strip_delimiters(p.title)} / {strip_delimiters(p.section)}\n"
                     f"{strip_delimiters(p.text).strip()}" for p in passages)


def parse_answer(raw: str) -> tuple[dict[str, Any], list[str]]:
    """Raw model text -> schema-valid dict. Raises ValueError. Repairs listed (fences, chatter, commas)."""
    import jsonschema

    repairs: list[str] = []
    d = _loads_lenient(raw, repairs)
    if not isinstance(d, dict):
        raise ValueError("output is not a JSON object")
    if isinstance(d.get("can_answer"), str) and d["can_answer"].strip().lower() in ("true", "false"):
        d["can_answer"] = d["can_answer"].strip().lower() == "true"
        repairs.append("can_answer given as text")
    for s in d.get("answer_sentences") or []:
        if isinstance(s, dict) and isinstance(s.get("passage_ids"), str):
            s["passage_ids"] = [s["passage_ids"]]
            repairs.append("passage_ids given as a string")
        if isinstance(s, dict) and isinstance(s.get("passage_ids"), list):
            s["passage_ids"] = [str(x).strip().strip("[]") for x in s["passage_ids"]]
    schema = json.loads(ANSWER_SCHEMA.read_text(encoding="utf-8"))
    try:
        jsonschema.validate(d, schema)
    except jsonschema.ValidationError as e:
        raise ValueError(f"schema: {e.message[:200]}") from e
    return d, repairs


def check_citations(sentences: list[dict[str, Any]], allowed_ids: set[str]) -> tuple[bool, list[str], list[str]]:
    """(ok, unresolved_ids, cited_ids). ok needs every sentence cited and every id in allowed_ids."""
    unresolved, cited = [], []
    ok = bool(sentences)
    for s in sentences:
        ids = s.get("passage_ids") or []
        if not ids or not str(s.get("text", "")).strip():
            ok = False
        for pid in ids:
            if pid not in allowed_ids:
                ok = False
                if pid not in unresolved:
                    unresolved.append(pid)
            elif pid not in cited:
                cited.append(pid)
    return ok, unresolved, cited


def load_messages(path: str | Path = MESSAGES_CONFIG) -> dict[str, str]:
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    for k in ("automated_label", "greeting", "sign_off", "holding_message", "sources_heading"):
        if not str(d.get(k, "")).strip():
            raise ValueError(f"{path}: '{k}' missing or empty")
    return d


def compose_reply(g: GenerationResult, passages, messages: dict[str, str]) -> str:
    """FR-18: label first, Sources last. Only cited articles are listed, once each, in first-cited order."""
    by_id = {p.passage_id: p for p in passages}
    docs: list[Any] = []
    for pid in g.cited:
        p = by_id[pid]
        if p.doc_id not in [d.doc_id for d in docs]:
            docs.append(p)
    body = " ".join(s["text"].strip() for s in g.sentences)
    sources = "\n".join(f"- {p.title} ({p.doc_id}), {p.reviewed_label}" for p in docs)
    return (f"{messages['automated_label']}\n\n{messages['greeting']}\n\n{body}\n\n{messages['sign_off']}\n\n"
            f"{messages['sources_heading']}\n{sources}")


class Generator:
    def __init__(self, client, prompt_path: str | None = None,
                 repair_path: str = "build/json_repair_v1.txt"):
        self.client = client
        self.prompt = load_prompt(prompt_path or prompt_from_config())
        self.repair = load_prompt(repair_path)

    def generate(self, record, intent: str, passages, mode: str) -> GenerationResult:
        if mode not in ("answer", "draft"):
            raise ValueError(f"mode must be answer or draft, got {mode!r}")
        g = GenerationResult(mode=mode, prompt_version=self.prompt.version, model=self.client.model)
        if not passages:  # Route should never send this; refuse rather than answer from nothing
            g.error, g.reason = "none", "no passages given; nothing to answer from"
            return g
        t0 = time.perf_counter()
        system, user = self.prompt.render(
            mode=mode, intent=intent, channel=record.channel,
            subject=(record.subject or "").strip() or "(empty)", body=record.body or "",
            passages=render_passages(passages))
        r = self._call(g, system, user)
        if r is None:
            g.latency_ms = int((time.perf_counter() - t0) * 1000)
            return g
        try:
            d, g.repairs = parse_answer(r)
        except ValueError as first:
            g.raw = r[:2000]
            rs, ru = self.repair.render(raw_output=r)
            r2 = self._call(g, rs, ru, retry=True)
            if r2 is None:
                g.latency_ms = int((time.perf_counter() - t0) * 1000)
                return g
            g.prompt_version = f"{self.prompt.version}; {self.repair.version}"
            try:
                d, rep = parse_answer(r2)
                g.repairs = [f"PR-04 repair after: {first}"] + rep
            except ValueError as second:
                g.error = "bad_output"
                g.reason = f"model output failed the answer schema after one repair ({second})"
                g.latency_ms = int((time.perf_counter() - t0) * 1000)
                return g

        g.can_answer = bool(d["can_answer"])
        g.sentences = d["answer_sentences"]
        g.unsure_about, g.escalation_summary, g.restatement = d["unsure_about"], d["escalation_summary"], d["restatement"]
        if g.can_answer:
            g.citations_ok, g.unresolved, g.cited = check_citations(g.sentences, {p.passage_id for p in passages})
            if g.citations_ok:
                g.reason = (f"{len(g.sentences)} sentence(s), every one cited; cited {', '.join(g.cited)}; "
                            "all citations resolve to retrieved passages")
            else:
                g.error = "citation"
                g.reason = ("citation check failed: " + (f"ids not in the retrieved set {g.unresolved}" if g.unresolved
                                                         else "a sentence has no passage id or no text"))
        else:
            g.reason = f"model said it cannot answer from the passages: {g.unsure_about or 'no reason given'}"
        g.latency_ms = int((time.perf_counter() - t0) * 1000)
        return g

    def _call(self, g: GenerationResult, system: str, user: str, retry: bool = False) -> str | None:
        r = self.client.complete(system, user)
        g.cached = r.cached if g.requests == 0 else (g.cached and r.cached)
        g.requests += r.requests
        g.retries += r.retries + (1 if retry else 0)
        g.rate_limit_wait_ms += r.rate_limit_wait_ms
        g.tokens_in += r.tokens_in
        g.tokens_out += r.tokens_out
        g.degraded = g.degraded or r.degraded
        if not r.ok:
            g.error = r.error
            g.reason = (f"provider failed ({r.error}) after {r.requests} request(s): {r.detail or 'no detail'}; "
                        "escalated with a template summary")
            return None
        return r.text


def log_generation(log, ticket_id: str, text: str, g: GenerationResult, passages) -> None:
    score = {p.passage_id: p for p in passages}
    log.write(
        ticket_id=ticket_id, stage="generation", action_taken=g.action, reason=g.reason or g.action,
        input_text=text, model_name=f"llm:{g.model}", model_version=g.model, prompt_version=g.prompt_version or "n/a",
        prediction={"mode": g.mode, "can_answer": g.can_answer, "sentences": g.sentences, "cached": g.cached,
                    "citations_ok": g.citations_ok, "unresolved": g.unresolved, "unsure_about": g.unsure_about,
                    "restatement": g.restatement, **({"repairs": g.repairs} if g.repairs else {})},
        sources_used=[{"doc_id": score[pid].doc_id, "passage_id": pid, "score": score[pid].score}
                      for pid in g.cited if pid in score],
        doc_review_age={score[pid].doc_id: score[pid].last_reviewed_days_ago for pid in g.cited if pid in score},
        error=g.error if g.error != "citation" else "bad_output",
        degraded_mode=g.degraded, latency_ms=g.latency_ms, requests=g.requests,
        rate_limit_wait_ms=g.rate_limit_wait_ms, tokens_in=g.tokens_in, tokens_out=g.tokens_out,
    )
