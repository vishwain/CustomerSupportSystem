"""Decision log (A8; PRD FR-24, NFR-05, section 10.5; Observations/DecisionLog_Design.md).

One SQLite table, `decisions`: one row per stage that runs, plus exactly one `final`
row per ticket, written BEFORE the action is taken. A second table, `runs`, records
each run (input file, hash, counts) so dev, validation and hidden runs stay apart and
the number of runs on a file can be reported.

Fail closed: if a write fails, the row goes to a fallback JSONL file next to the
database, an alert line is written, and LogWriteError is raised. The caller must then
send nothing and escalate (FR-24).

Never stored: customer_name, customer_id, tier, region, fluency, labels, history.
The evaluation layer joins those from the input file by ticket_id.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from src import pii

SCHEMA_VERSION = "decisionlog-1.0"
STAGES = ("ingest", "classification", "retrieval", "routing", "generation", "validation", "final")

# Allowed action_taken per stage. Final is the single action taken on the ticket.
ACTIONS = {
    "ingest": {"accept", "reject"},
    "classification": {"classify", "fallback"},
    "retrieval": {"passages_found", "no_passages"},
    "routing": {"auto_respond", "draft_for_review", "escalate"},
    "generation": {"answer", "draft", "cannot_answer", "failed"},
    "validation": {"pass", "block"},
    "final": {"auto_respond", "escalate"},
}

ERRORS = {
    "none", "malformed_input", "timeout", "rate_limit", "provider_down", "bad_output",
    "no_retrieval_hit", "log_write_failed", "classifier_error", "internal_error",
}

# Default requirement ids per stage (PRD 4a mapping). FR-24 is added to every row.
STAGE_FRS = {
    "ingest": ["FR-01", "FR-02", "FR-03"],
    "classification": ["FR-04", "FR-05"],
    "retrieval": ["FR-08", "FR-09", "FR-10", "FR-19"],
    "routing": ["FR-11", "FR-12", "FR-13", "FR-25", "FR-31"],
    "generation": ["FR-14", "FR-15", "FR-16", "FR-20"],
    "validation": ["FR-17", "FR-22", "FR-23"],
    "final": ["FR-24"],
}

SUMMARY_CHARS = 200  # PRD 10.5

# Columns that must never be NULL or empty (FR-24 acceptance: "No 10.5 field is empty").
# confidence and threshold_applied stay NULL when a stage has none, so calibration never
# mistakes "not applicable" for 0.
REQUIRED = (
    "decision_id", "timestamp", "run_id", "ticket_id", "stage", "input_summary", "input_sha256",
    "model_name", "model_version", "prompt_version", "action_taken", "reason", "requirement_ids",
    "rule_fired", "error",
)

DDL = f"""
CREATE TABLE IF NOT EXISTS decisions (
    decision_id        TEXT PRIMARY KEY,
    timestamp          TEXT NOT NULL,                -- UTC ISO 8601
    run_id             TEXT NOT NULL,
    ticket_id          TEXT NOT NULL CHECK (length(ticket_id) > 0),
    stage              TEXT NOT NULL CHECK (stage IN ({", ".join(repr(s) for s in STAGES)})),
    input_summary      TEXT NOT NULL,                -- first 200 chars after private-data scrub
    input_sha256       TEXT NOT NULL,                -- hash of the full cleaned text
    model_name         TEXT NOT NULL,
    model_version      TEXT NOT NULL,
    prompt_version     TEXT NOT NULL,                -- 'PR-xx vX.Y' or 'n/a'
    prediction         TEXT NOT NULL DEFAULT '{{}}', -- JSON
    confidence         REAL,                         -- NULL when the stage has no confidence
    alternatives       TEXT NOT NULL DEFAULT '[]',   -- JSON [{{value, confidence}}]
    sources_used       TEXT NOT NULL DEFAULT '[]',   -- JSON [{{doc_id, passage_id, score}}]
    doc_review_age     TEXT NOT NULL DEFAULT '{{}}', -- JSON {{doc_id: last_reviewed_days_ago}}
    threshold_applied  REAL,
    rule_fired         TEXT NOT NULL DEFAULT 'none',
    action_taken       TEXT NOT NULL,
    reason             TEXT NOT NULL CHECK (length(trim(reason)) > 0),
    guardrail_results  TEXT NOT NULL DEFAULT '{{}}', -- JSON {{pii, grounding, ...: pass|block}}
    requirement_ids    TEXT NOT NULL,                -- JSON list of FR ids
    error              TEXT NOT NULL DEFAULT 'none',
    degraded_mode      INTEGER NOT NULL DEFAULT 0,
    latency_ms         INTEGER NOT NULL DEFAULT 0,
    rate_limit_wait_ms INTEGER NOT NULL DEFAULT 0,
    requests           INTEGER NOT NULL DEFAULT 0,
    tokens_in          INTEGER NOT NULL DEFAULT 0,
    tokens_out         INTEGER NOT NULL DEFAULT 0,
    escalation_package TEXT NOT NULL DEFAULT '{{}}', -- JSON, final row only
    schema_version     TEXT NOT NULL DEFAULT '{SCHEMA_VERSION}'
);
CREATE INDEX IF NOT EXISTS ix_decisions_run_ticket ON decisions (run_id, ticket_id);
-- Exactly one final row per ticket per run, enforced by the database.
CREATE UNIQUE INDEX IF NOT EXISTS ux_one_final ON decisions (run_id, ticket_id) WHERE stage = 'final';

CREATE TABLE IF NOT EXISTS runs (
    run_id            TEXT PRIMARY KEY,
    started_at        TEXT NOT NULL,
    finished_at       TEXT,
    input_name        TEXT NOT NULL,
    input_sha256      TEXT NOT NULL,
    tickets_in        INTEGER,
    tickets_processed INTEGER,
    status            TEXT NOT NULL DEFAULT 'running',  -- running | completed | failed
    notes             TEXT NOT NULL DEFAULT ''
);
"""

JSON_COLS = (
    "prediction", "alternatives", "sources_used", "doc_review_age", "guardrail_results",
    "requirement_ids", "escalation_package",
)


class LogWriteError(Exception):
    """A decision row could not be written to the database. Caller must fail closed."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def summarise_input(text: str) -> tuple[str, str]:
    """(input_summary, input_sha256). Scrub first, then cut, so no half-pattern survives."""
    text = text or ""
    summary = pii.scrub(text)[:SUMMARY_CHARS]
    return (summary or "[empty]"), hashlib.sha256(text.encode("utf-8")).hexdigest()


def file_sha256(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


class DecisionLog:
    def __init__(self, db_path: str | Path, run_id: str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.run_id = run_id
        self.fallback_path = self.db_path.with_name(self.db_path.stem + "_fallback.jsonl")
        self.alert_path = self.db_path.with_name("alerts.log")
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(DDL)
        self._conn.commit()

    # -- runs ---------------------------------------------------------------
    def start_run(self, input_name: str, input_sha256: str, notes: str = "") -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO runs (run_id, started_at, input_name, input_sha256, notes) VALUES (?,?,?,?,?)",
                (self.run_id, utc_now(), input_name, input_sha256, notes),
            )
            self._conn.commit()

    def finish_run(self, tickets_in: int, tickets_processed: int, status: str = "completed") -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE runs SET finished_at=?, tickets_in=?, tickets_processed=?, status=? WHERE run_id=?",
                (utc_now(), tickets_in, tickets_processed, status, self.run_id),
            )
            self._conn.commit()

    def runs_on_input(self, input_sha256: str) -> int:
        """How many runs this database has seen on the same input file (hidden set: once only)."""
        row = self._conn.execute("SELECT COUNT(*) FROM runs WHERE input_sha256=?", (input_sha256,)).fetchone()
        return int(row[0])

    # -- decisions ----------------------------------------------------------
    def build_row(self, *, ticket_id: str, stage: str, action_taken: str, reason: str,
                  input_text: str = "", model_name: str = "none", model_version: str = "n/a",
                  prompt_version: str = "n/a", requirement_ids: Iterable[str] | None = None,
                  error: str = "none", **extra: Any) -> dict[str, Any]:
        """Build and check one row. Raises ValueError on a programming error (bad stage, empty reason)."""
        if stage not in STAGES:
            raise ValueError(f"unknown stage {stage!r}")
        if action_taken not in ACTIONS[stage]:
            raise ValueError(f"action {action_taken!r} not allowed for stage {stage!r}")
        if not (reason or "").strip():
            raise ValueError("reason must not be empty")
        if error not in ERRORS:
            raise ValueError(f"unknown error code {error!r}")
        unknown = set(extra) - {
            "prediction", "confidence", "alternatives", "sources_used", "doc_review_age",
            "threshold_applied", "rule_fired", "guardrail_results", "degraded_mode", "latency_ms",
            "rate_limit_wait_ms", "requests", "tokens_in", "tokens_out", "escalation_package",
        }
        if unknown:
            raise ValueError(f"unknown fields {sorted(unknown)}")

        frs = list(requirement_ids) if requirement_ids else list(STAGE_FRS[stage])
        if "FR-24" not in frs:
            frs.append("FR-24")
        summary, digest = summarise_input(input_text)
        row: dict[str, Any] = {
            "decision_id": str(uuid.uuid4()),
            "timestamp": utc_now(),
            "run_id": self.run_id,
            "ticket_id": ticket_id,
            "stage": stage,
            "input_summary": summary,
            "input_sha256": digest,
            "model_name": model_name,
            "model_version": model_version,
            "prompt_version": prompt_version,
            "prediction": extra.get("prediction", {}),
            "confidence": extra.get("confidence"),
            "alternatives": extra.get("alternatives", []),
            "sources_used": extra.get("sources_used", []),
            "doc_review_age": extra.get("doc_review_age", {}),
            "threshold_applied": extra.get("threshold_applied"),
            "rule_fired": extra.get("rule_fired") or "none",
            "action_taken": action_taken,
            "reason": reason.strip(),
            "guardrail_results": extra.get("guardrail_results", {}),
            "requirement_ids": frs,
            "error": error,
            "degraded_mode": int(bool(extra.get("degraded_mode", False))),
            "latency_ms": int(extra.get("latency_ms", 0)),
            "rate_limit_wait_ms": int(extra.get("rate_limit_wait_ms", 0)),
            "requests": int(extra.get("requests", 0)),
            "tokens_in": int(extra.get("tokens_in", 0)),
            "tokens_out": int(extra.get("tokens_out", 0)),
            "escalation_package": extra.get("escalation_package", {}),
        }
        return row

    def write(self, **fields: Any) -> dict[str, Any]:
        """Build, check and commit one row. On a database error: fallback file, alert, LogWriteError."""
        row = self.build_row(**fields)
        db_row = {k: (json.dumps(v, ensure_ascii=False, sort_keys=True) if k in JSON_COLS else v)
                  for k, v in row.items()}
        cols = ", ".join(db_row)
        marks = ", ".join("?" for _ in db_row)
        try:
            with self._lock:
                self._conn.execute(f"INSERT INTO decisions ({cols}) VALUES ({marks})", tuple(db_row.values()))
                self._conn.commit()
        except sqlite3.Error as e:
            self._fail(row, e)
            raise LogWriteError(f"{row['stage']} row for {row['ticket_id']}: {e}") from e
        return row

    def _fail(self, row: dict[str, Any], exc: Exception) -> None:
        """Best effort: keep the row and raise an alert. Never raises itself."""
        try:
            with open(self.fallback_path, "a", encoding="utf-8") as f:
                f.write(json.dumps({**row, "write_error": str(exc)}, ensure_ascii=False) + "\n")
        except OSError:
            pass
        try:
            with open(self.alert_path, "a", encoding="utf-8") as f:
                f.write(f"{utc_now()} ALERT decision log write failed run={self.run_id} "
                        f"ticket={row.get('ticket_id')} stage={row.get('stage')}: {exc}\n")
        except OSError:
            pass

    # -- checks -------------------------------------------------------------
    def reconcile(self, ticket_ids: list[str]) -> dict[str, Any]:
        """A8 / NFR-05 check: one final row per ticket processed, no empty required field."""
        q = self._conn.execute
        expected = set(ticket_ids)
        finals = [r[0] for r in q(
            "SELECT ticket_id FROM decisions WHERE run_id=? AND stage='final'", (self.run_id,))]
        final_set = set(finals)
        empty_checks = " OR ".join(f"{c} IS NULL OR trim({c}) = ''" for c in REQUIRED)
        empty = q(f"SELECT COUNT(*) FROM decisions WHERE run_id=? AND ({empty_checks})",
                  (self.run_id,)).fetchone()[0]
        by_stage = {r[0]: r[1] for r in q(
            "SELECT stage, COUNT(*) FROM decisions WHERE run_id=? GROUP BY stage", (self.run_id,))}
        by_action = {r[0]: r[1] for r in q(
            "SELECT action_taken, COUNT(*) FROM decisions WHERE run_id=? AND stage='final' "
            "GROUP BY action_taken", (self.run_id,))}
        fallback_rows = 0
        if self.fallback_path.exists():
            with open(self.fallback_path, encoding="utf-8") as f:
                fallback_rows = sum(1 for line in f if f'"run_id": "{self.run_id}"' in line)
        missing = sorted(expected - final_set)
        unexpected = sorted(final_set - expected)
        result = {
            "run_id": self.run_id,
            "tickets_processed": len(ticket_ids),
            "distinct_ticket_ids": len(expected),
            "final_rows": len(finals),
            "final_actions": by_action,
            "rows_by_stage": by_stage,
            "rows_total": sum(by_stage.values()),
            "missing_final": missing[:50],
            "missing_final_count": len(missing),
            "unexpected_final": unexpected[:50],
            "duplicate_final": len(finals) - len(final_set),
            "rows_with_empty_required_field": empty,
            "fallback_rows": fallback_rows,
        }
        result["ok"] = (
            len(finals) == len(ticket_ids) == len(expected)
            and not missing and not unexpected and empty == 0 and fallback_rows == 0
        )
        return result

    def rows(self, ticket_id: str | None = None, limit: int | None = None) -> list[dict[str, Any]]:
        sql = "SELECT * FROM decisions WHERE run_id=?"
        args: list[Any] = [self.run_id]
        if ticket_id:
            sql += " AND ticket_id=?"
            args.append(ticket_id)
        sql += " ORDER BY rowid"
        if limit:
            sql += f" LIMIT {int(limit)}"
        out = []
        for r in self._conn.execute(sql, args):
            d = dict(r)
            for c in JSON_COLS:
                d[c] = json.loads(d[c])
            out.append(d)
        return out

    def close(self) -> None:
        self._conn.close()
