"""Evaluation harness (A9, A10; PRD FR-26, FR-27, FR-24).

One command, any ticket file, no hardcoded filename or ticket count:

    python -m evaluation.harness --input data/validation_tickets.json --output evaluation/results/<run-folder>

Per ticket: Ingest -> pipeline -> final decision row (written BEFORE the action) -> result line.
Today the pipeline is a placeholder that escalates every accepted ticket. Classify, Retrieve,
Route, Generate and Validate plug into `run_pipeline` later; the harness does not change.

Writes to --output:
    results.jsonl              one line per ticket: action, reason, error, latency
    reconcile.json             A8 check: final rows = tickets processed, no empty required field
    decision_log_extract.jsonl first 20 decision rows (A8 evidence; storage/ is not committed)
    metrics_report.md / .json  skeleton report (FR-27 fills the full figure groups later)
    run_info.json              run id, input hash, database path, runs on this input so far

Exit code: 0 = reconciled, 1 = reconcile failed, 2 = input file unreadable.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import traceback
import uuid
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src import pii
from src.ingest import INGEST_VERSION, InputFileError, TicketRecord, load
from src.logging_store import DecisionLog, LogWriteError, file_sha256, utc_now

HARNESS_VERSION = "harness-0.1-skeleton"
EXTRACT_ROWS = 20


@dataclass
class Outcome:
    """What the pipeline decided for one ticket. The harness logs it as the final row, then acts."""

    action: str  # auto_respond | escalate
    reason: str
    error: str = "none"
    reply: str | None = None
    escalation_package: dict[str, Any] = field(default_factory=dict)
    rule_fired: str = "none"
    degraded_mode: bool = False
    placeholder: bool = False


def run_pipeline(record: TicketRecord, log: DecisionLog) -> Outcome:
    """Classify -> Retrieve -> Route -> Generate -> Validate. Each component writes its own stage row.

    Placeholder until those components exist: escalate, which is the safe default.
    """
    return Outcome(
        action="escalate",
        reason="Pipeline components not built yet (harness skeleton); ticket escalated to a person.",
        escalation_package={"summary": "skeleton run: no classification or retrieval yet",
                            "channel": record.channel},
        placeholder=True,
    )


def process_ticket(record: TicketRecord, log: DecisionLog) -> dict[str, Any]:
    t0 = time.perf_counter()
    ingest_model = {"model_name": "rules:ingest", "model_version": INGEST_VERSION}

    try:
        # 1. Ingest decision row.
        log.write(
            ticket_id=record.ticket_id, stage="ingest",
            action_taken="accept" if record.ok else "reject",
            reason=record.ingest_reason if record.ok else f"Malformed input: {record.ingest_reason}.",
            input_text=record.text, error=record.ingest_error or "none",
            prediction={"channel": record.channel, "flags": record.flags}, **ingest_model,
        )
        # 2. Pipeline, or straight to escalation for malformed input (FR-02).
        if record.ok:
            outcome = run_pipeline(record, log)
        else:
            outcome = Outcome(action="escalate", error="malformed_input",
                              reason=f"Malformed input ({record.ingest_reason}); escalated without a model call.",
                              escalation_package={"summary": "unreadable or empty ticket"})
    except LogWriteError as e:
        outcome = Outcome(action="escalate", error="log_write_failed",
                          reason=f"Decision log write failed before acting ({e}); fail closed, nothing sent.")
    except Exception as e:  # any component crash: escalate, keep the run going (A11)
        msg = pii.scrub(str(e))[:200]
        outcome = Outcome(action="escalate", error="internal_error",
                          reason=f"Pipeline error {type(e).__name__}: {msg}; escalated.")
        traceback.print_exc(file=sys.stderr)

    latency_ms = int((time.perf_counter() - t0) * 1000)

    # 3. Final row BEFORE acting. If it cannot be written: send nothing, escalate (fail closed).
    log_written = True
    try:
        log.write(
            ticket_id=record.ticket_id, stage="final", action_taken=outcome.action,
            reason=outcome.reason, input_text=record.text, error=outcome.error,
            rule_fired=outcome.rule_fired, degraded_mode=outcome.degraded_mode,
            latency_ms=latency_ms, escalation_package=outcome.escalation_package,
            model_name="harness", model_version=HARNESS_VERSION,
        )
    except (LogWriteError, ValueError) as e:
        log_written = False
        print(f"ALERT: final log write failed for {record.ticket_id}: {e}", file=sys.stderr)
        outcome = Outcome(action="escalate", error="log_write_failed",
                          reason="Final decision row could not be written; fail closed, nothing sent.")

    # 4. Act. Today: record the result. Later: send reply or push to escalation queue.
    return {
        "run_id": log.run_id,
        "ticket_id": record.ticket_id,
        "channel": record.channel,
        "action": outcome.action,
        "reason": outcome.reason,
        "error": outcome.error,
        "rule_fired": outcome.rule_fired,
        "reply": outcome.reply if (outcome.action == "auto_respond" and log_written) else None,
        "latency_ms": latency_ms,
        "log_written": log_written,
        "placeholder": outcome.placeholder,
        "ingest_flags": record.flags,
    }


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def skeleton_metrics(results: list[dict[str, Any]], rec: dict[str, Any], run: dict[str, Any]) -> dict[str, Any]:
    lat = sorted(r["latency_ms"] for r in results)

    def pct(p: float) -> int:
        return lat[min(len(lat) - 1, int(round(p * (len(lat) - 1))))] if lat else 0

    return {
        "run_id": run["run_id"],
        "input": run["input_name"],
        "run_date_utc": run["finished_at"],
        "runs_on_this_input": run["runs_on_this_input"],
        "tickets_in": len(results),
        "by_channel": dict(Counter(r["channel"] for r in results)),
        "by_action": dict(Counter(r["action"] for r in results)),
        "by_error": dict(Counter(r["error"] for r in results)),
        "latency_ms_p50": pct(0.50),
        "latency_ms_p95": pct(0.95),
        "decision_log_coverage_ok": rec["ok"],
        "final_rows": rec["final_rows"],
        "note": "Skeleton report. Business, technical, governance and segment figures added with FR-27.",
    }


def metrics_markdown(m: dict[str, Any]) -> str:
    lines = [f"# Metrics report: {m['run_id']}", "",
             f"Input: `{m['input']}`. Finished {m['run_date_utc']}. Runs on this input so far: {m['runs_on_this_input']}.",
             "", "| Figure | Value |", "| --- | --- |"]
    for k in ("tickets_in", "final_rows", "decision_log_coverage_ok", "latency_ms_p50", "latency_ms_p95"):
        lines.append(f"| {k} | {m[k]} |")
    for group in ("by_channel", "by_action", "by_error"):
        for k, v in sorted(m[group].items()):
            lines.append(f"| {group}: {k} | {v} |")
    lines += ["", m["note"], ""]
    return "\n".join(lines)


def registry_count(registry: Path, input_sha: str) -> int:
    if not registry.exists():
        return 0
    with open(registry, encoding="utf-8") as f:
        return sum(1 for line in f if line.strip() and json.loads(line).get("input_sha256") == input_sha)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Run every ticket in a file through the system, unattended.")
    ap.add_argument("--input", required=True, help="ticket file: .json list or .jsonl")
    ap.add_argument("--output", required=True, help="folder for results, reconcile and metrics files")
    ap.add_argument("--run-id", help="default: <UTC time>_<input name>_<random>")
    ap.add_argument("--db", help="decision log path; default <storage>/runs/<run_id>/decisions.db")
    ap.add_argument("--storage", default=os.getenv("STORAGE_DIR", "storage"),
                    help="runtime folder, never committed (default: storage, or $STORAGE_DIR)")
    ap.add_argument("--quiet", action="store_true", help="no per-ticket lines")
    a = ap.parse_args(argv)

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    in_path = Path(a.input)
    out_dir = Path(a.output)
    storage = Path(a.storage)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_id = a.run_id or f"{stamp}_{in_path.stem}_{uuid.uuid4().hex[:4]}"
    db_path = Path(a.db) if a.db else storage / "runs" / run_id / "decisions.db"

    # Read the file first. A file we cannot read at all is the only case that stops the run.
    try:
        input_sha = file_sha256(in_path)
        records = load(in_path)
    except (InputFileError, OSError) as e:
        print(f"ERROR: input file unreadable: {e}", file=sys.stderr)
        return 2

    out_dir.mkdir(parents=True, exist_ok=True)
    storage.mkdir(parents=True, exist_ok=True)
    registry = storage / "run_registry.jsonl"
    prior_runs = registry_count(registry, input_sha)

    log = DecisionLog(db_path, run_id)
    log.start_run(in_path.name, input_sha, notes=HARNESS_VERSION)
    print(f"run {run_id}: {len(records)} tickets from {in_path} (runs on this file before: {prior_runs})")

    results = []
    for rec in records:
        r = process_ticket(rec, log)
        results.append(r)
        if not a.quiet:
            print(f"  {r['ticket_id']:<12} {r['channel']:<13} {r['action']:<12} {r['error']}")

    ticket_ids = [r.ticket_id for r in records]
    reconcile = log.reconcile(ticket_ids)
    log.finish_run(len(records), len(results), "completed" if reconcile["ok"] else "failed")
    extract = log.rows(limit=EXTRACT_ROWS)
    log.close()

    finished = utc_now()
    run_info = {
        "run_id": run_id, "input_path": str(in_path), "input_name": in_path.name,
        "input_sha256": input_sha, "tickets_in": len(records), "db_path": str(db_path),
        "harness_version": HARNESS_VERSION, "finished_at": finished,
        "runs_on_this_input": prior_runs + 1,
    }
    with open(registry, "a", encoding="utf-8") as f:
        f.write(json.dumps({k: run_info[k] for k in ("run_id", "input_name", "input_sha256", "finished_at")}) + "\n")

    metrics = skeleton_metrics(results, reconcile, run_info)
    write_jsonl(out_dir / "results.jsonl", results)
    write_jsonl(out_dir / "decision_log_extract.jsonl", extract)
    (out_dir / "reconcile.json").write_text(json.dumps(reconcile, indent=2), encoding="utf-8")
    (out_dir / "run_info.json").write_text(json.dumps(run_info, indent=2), encoding="utf-8")
    (out_dir / "metrics_report.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    (out_dir / "metrics_report.md").write_text(metrics_markdown(metrics), encoding="utf-8")

    status = "RECONCILED" if reconcile["ok"] else "RECONCILE FAILED"
    print(f"{status}: {reconcile['final_rows']} final rows for {len(records)} tickets; "
          f"actions {reconcile['final_actions']}; rows by stage {reconcile['rows_by_stage']}; "
          f"empty required fields {reconcile['rows_with_empty_required_field']}.")
    print(f"outputs in {out_dir}; decision log at {db_path}")
    return 0 if reconcile["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
