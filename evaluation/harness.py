"""Evaluation harness (A9, A10; PRD FR-26, FR-27, FR-24).

One command, any ticket file, no hardcoded filename or ticket count:

    python -m evaluation.harness --input data/validation_tickets.json --output evaluation/results/<run-folder>

Per ticket: Ingest -> Route pre-rules -> Classify -> Retrieve -> Route -> Generate (PR-03, only when Route
chose auto_respond or draft_for_review) -> (Validate: 5.9, not built) -> final decision row (written BEFORE the
action) -> result line. Every stage writes its own row.
Validate (src/guardrails.py) checks every generated answer and draft before anything leaves: a block escalates
the ticket, leaves the draft out and logs a validation row. Only an answer that passes every blocking check is
sent (final action auto_respond). Without a validator nothing is sent.

Needs config/retrieval.json (docs/retrieval_experiment.py) and, for automatic answers, config/routing.json
(docs/routing_threshold.py). Without routing.json nothing is auto-answered. --no-models skips the
embedding model (classifier and retriever) for fast plumbing runs: every ticket then escalates as
classification_failed.

Writes to --output:
    results.jsonl              one line per ticket: action, route decision, intent, reason, error, latency
    escalation_queue.csv       every escalation with its package (FR-13), sorted by urgency then age (FR-06)
    reconcile.json             A8 check: final rows = tickets processed, no empty required field
    decision_log_extract.jsonl first 20 decision rows (A8 evidence; storage/ is not committed)
    metrics_report.md / .json  skeleton report (FR-27 fills the full figure groups later)
    run_info.json              run id, input hash, database path, runs on this input so far

Exit code: 0 = reconciled, 1 = reconcile failed, 2 = input file unreadable.
"""

from __future__ import annotations

import argparse
import csv
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
from src.classify import Classification, Classifier, build_classifier, fallback, log_classification
from src.generate import GenerationResult, Generator, compose_reply, load_messages, log_generation
from src.guardrails import GuardrailConfig, Validator, log_validation, private_terms_for
from src.ingest import INGEST_VERSION, InputFileError, TicketRecord, load
from src.retrieve import RetrievalResult, Retriever, SentenceTransformerEmbedder, build_retriever, log_retrieval
from src.route import RouteDecision, Router, log_routing
from src.logging_store import DecisionLog, LogWriteError, file_sha256, utc_now

HARNESS_VERSION = "harness-0.5-validate"
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
    generation: dict[str, Any] = field(default_factory=dict)
    customer_message: str = ""
    route_action: str = "none"
    intent: str = "unknown"
    intent_confidence: float = 0.0
    urgency: str = "unknown"


@dataclass
class Components:
    """Built once per run, shared by every ticket. None = component not available."""

    retriever: Retriever | None = None
    classifier: Classifier | None = None
    router: Router | None = None
    generator: Generator | None = None
    messages: dict[str, str] | None = None
    validator: Validator | None = None  # None = nothing is ever sent automatically
    private_terms: set[str] = field(default_factory=set)  # every customer name/id in the run (FR-22)


def escalation_package(record: TicketRecord, cls: Classification, res: RetrievalResult | None,
                       decision: RouteDecision, gen: GenerationResult | None = None, draft: str = "",
                       reason: str | None = None) -> dict[str, Any]:
    """FR-13. Without a model call: template summary, subject as restatement, route reason as unsure_about.
    With one: summary, restatement and unsure_about come from the PR-03 JSON; draft only if it passed checks."""
    subject = (record.subject or "").strip() or "(no subject)"
    passages = ([{"passage_id": p.passage_id, "doc_id": p.doc_id, "title": p.title, "score": p.score,
                  "reviewed": p.reviewed_label} for p in res.passages] if res and res.passages else "none found")
    template = f"{cls.intent} ({cls.intent_confidence:.2f}), {cls.urgency} urgency, {record.channel}: {subject}"
    why = reason or decision.reason
    model_ok = gen is not None and gen.error in ("none", "citation")
    return {
        "ticket_id": record.ticket_id,
        "summary": (gen.escalation_summary if model_ok and gen.escalation_summary else template),
        "restatement": (gen.restatement if model_ok and gen.restatement else subject),
        "intent": cls.intent, "intent_confidence": cls.intent_confidence,
        "alternatives": cls.intent_alternatives,
        "urgency": cls.urgency, "received_at": record.received_at,
        "passages": passages,
        "reason": why, "unsure_about": (gen.unsure_about if model_ok and gen.unsure_about else why),
        "draft": draft,
        "route_action": decision.action, "rule_fired": decision.rule_fired,
    }


def run_pipeline(record: TicketRecord, log: DecisionLog, comp: Components | None = None) -> Outcome:
    """Route pre-rules -> Classify -> Retrieve -> Route. Generate and Validate are not built yet,
    so the final action is escalate whatever Route chose; the routing row records Route's choice."""
    comp = comp or Components()
    router = comp.router or Router()

    # Text-only rules first (kill switch, instruction integrity): when they fire, no model call may happen.
    pre = router.pre_rules(record.text)

    if comp.classifier is not None:
        cls = comp.classifier.classify(record, allow_llm=pre is None)
    else:
        cls = fallback("classification failed: classifier not loaded (--no-models or load error)")
    log_classification(log, record.ticket_id, record.text, cls)

    res = None
    if comp.retriever is not None:
        t0 = time.perf_counter()
        res = comp.retriever.retrieve(record.text)
        log_retrieval(log, record.ticket_id, record.text, comp.retriever, res,
                      latency_ms=int((time.perf_counter() - t0) * 1000))

    decision = router.decide(record.text, cls, res)
    log_routing(log, record.ticket_id, record.text, decision, cls, router.cfg)

    messages = comp.messages or load_messages()
    gen: GenerationResult | None = None
    if decision.action in ("auto_respond", "draft_for_review") and comp.generator is not None and res and res.passages:
        gen = comp.generator.generate(record, cls.intent, res.for_generation,
                                      "answer" if decision.action == "auto_respond" else "draft")
        log_generation(log, record.ticket_id, record.text, gen, res.for_generation)

    draft, would_send, error, rule = "", False, (cls.error if cls.failed else "none"), decision.rule_fired
    validated: bool | None = None
    gen_for_package = gen
    if decision.action == "escalate":
        reason = decision.reason
    elif gen is None:
        reason = f"Route: {decision.action} ({decision.reason}). Generate unavailable (no provider config); escalated."
    elif gen.error in ("timeout", "rate_limit", "provider_down"):
        reason, error = f"Generate failed: {gen.reason}", gen.error
    elif gen.error in ("bad_output", "citation"):
        reason, error = f"Generate output rejected: {gen.reason}; escalated, nothing sent.", "bad_output"
        rule = "citation_check" if gen.error == "citation" else "bad_output"
    elif not gen.can_answer:
        reason, rule = f"Model cannot answer from the passages (FR-16): {gen.unsure_about or gen.reason}", "cannot_answer"
    else:
        candidate = compose_reply(gen, res.for_generation, messages)
        kind = "answer" if gen.mode == "answer" else "draft"
        if comp.validator is None:
            draft, would_send = candidate, gen.mode == "answer"
            reason = f"{kind.capitalize()} passed the citation check, but Validate is unavailable, so nothing is sent."
        else:
            terms = comp.private_terms | {v for v in (record.held_for_validate or {}).values() if v}
            v = comp.validator.validate(
                ticket_text=record.text, sentences=gen.sentences,
                extra_texts=[gen.restatement, gen.escalation_summary, gen.unsure_about, candidate],
                passages=res.for_generation, mode=gen.mode, confidence=cls.intent_confidence,
                threshold=router.cfg.threshold, private_terms=terms)
            log_validation(log, record.ticket_id, record.text, v, gen.mode, comp.validator.cfg)
            validated = v.passed
            if not v.passed:
                rule = "guardrail:" + ",".join(v.blocked_by)
                reason = (f"Validate blocked the {kind} ({v.reason}). Escalated; the {kind} is left out and the "
                          "customer gets the holding message.")
                if "private_data" in v.blocked_by:
                    gen_for_package = None  # model text may hold the private data: template summary instead
            elif gen.mode == "draft":
                draft = candidate
                reason = f"Draft for an agent (FR-14): {decision.reason}. Passed Validate ({v.reason})."
            else:
                draft, would_send = candidate, True
                reason = f"Automatic answer: {decision.reason}. Passed Validate ({v.reason})."
    action = "auto_respond" if (would_send and validated) else "escalate"
    gen_info = {} if gen is None else {
        "gen_action": gen.action, "mode": gen.mode, "can_answer": gen.can_answer, "citations_ok": gen.citations_ok,
        "cited": gen.cited, "unresolved": gen.unresolved, "would_send": would_send, "validated": validated,
        "draft": draft,
        "requests": gen.requests, "prompt_version": gen.prompt_version}
    return Outcome(
        action=action, reason=reason, error=error,
        reply=draft if action == "auto_respond" else None,
        escalation_package=escalation_package(record, cls, res, decision, gen_for_package,
                                              draft if action == "escalate" else "", reason),
        rule_fired=rule, degraded_mode=cls.degraded or bool(gen and gen.degraded),
        placeholder=False,
        route_action=decision.action, intent=cls.intent, intent_confidence=cls.intent_confidence,
        urgency=cls.urgency, generation=gen_info,
        customer_message=draft if action == "auto_respond" else messages["holding_message"],
    )


def process_ticket(record: TicketRecord, log: DecisionLog, comp: Components | None = None) -> dict[str, Any]:
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
            outcome = run_pipeline(record, log, comp)
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
        "route_action": outcome.route_action,
        "intent": outcome.intent,
        "intent_confidence": outcome.intent_confidence,
        "urgency": outcome.urgency,
        "received_at": record.received_at,
        "reason": outcome.reason,
        "error": outcome.error,
        "rule_fired": outcome.rule_fired,
        "reply": outcome.reply if (outcome.action == "auto_respond" and log_written) else None,
        "latency_ms": latency_ms,
        "log_written": log_written,
        "placeholder": outcome.placeholder,
        "ingest_flags": record.flags,
        "escalation_package": outcome.escalation_package if outcome.action == "escalate" else {},
        "generation": outcome.generation,
        "customer_message": outcome.customer_message,
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
        "by_route_action": dict(Counter(r["route_action"] for r in results)),
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
    for group in ("by_channel", "by_action", "by_route_action", "by_error"):
        for k, v in sorted(m[group].items()):
            lines.append(f"| {group}: {k} | {v} |")
    lines += ["", m["note"], ""]
    return "\n".join(lines)


QUEUE_FIELDS = ("ticket_id", "urgency", "received_at", "summary", "restatement", "intent", "intent_confidence",
                "alternatives", "passages", "reason", "unsure_about", "draft", "route_action", "rule_fired")
URGENCY_ORDER = {"high": 0, "unknown": 0, "medium": 1, "low": 2}


def write_escalation_queue(path: Path, results: list[dict[str, Any]]) -> int:
    """FR-13 file, sorted per FR-06: high and unknown first, then medium, then low; oldest first within."""
    rows = []
    for r in results:
        if r["action"] != "escalate":
            continue
        pkg = r.get("escalation_package") or {}
        row = {k: pkg.get(k, "") for k in QUEUE_FIELDS}
        row.update(ticket_id=r["ticket_id"], urgency=pkg.get("urgency") or "unknown",
                   received_at=r.get("received_at", ""), reason=pkg.get("reason") or r["reason"],
                   unsure_about=pkg.get("unsure_about") or r["reason"],
                   summary=pkg.get("summary") or f"unknown (0.00), unknown urgency, {r['channel']}: (no subject)",
                   intent=pkg.get("intent", "unknown"), restatement=pkg.get("restatement") or "(no subject)",
                   passages=pkg.get("passages") or "none found", route_action=pkg.get("route_action", "escalate"),
                   rule_fired=r.get("rule_fired", "none"), intent_confidence=pkg.get("intent_confidence", 0.0),
                   alternatives=pkg.get("alternatives", []))
        for k in ("alternatives", "passages"):
            if not isinstance(row[k], str):
                row[k] = json.dumps(row[k], ensure_ascii=False)
        rows.append(row)
    rows.sort(key=lambda x: (URGENCY_ORDER.get(x["urgency"], 0), x["received_at"] or "9999"))
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=QUEUE_FIELDS)
        w.writeheader()
        w.writerows(rows)
    return len(rows)


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
    ap.add_argument("--no-models", action="store_true",
                    help="skip the embedding model (classifier, retriever): fast plumbing runs and tests")
    ap.add_argument("--no-llm", action="store_true", help="no provider calls: no Generate, no PR-02 fallback")
    ap.add_argument("--limit", type=int, default=0, help="process only the first N tickets (0 = all)")
    ap.add_argument("--retrieval-config", default="config/retrieval.json")
    ap.add_argument("--routing-config", default="config/routing.json")
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
        if a.limit > 0:
            records = records[: a.limit]
    except (InputFileError, OSError) as e:
        print(f"ERROR: input file unreadable: {e}", file=sys.stderr)
        return 2

    out_dir.mkdir(parents=True, exist_ok=True)
    storage.mkdir(parents=True, exist_ok=True)
    registry = storage / "run_registry.jsonl"
    prior_runs = registry_count(registry, input_sha)

    from src.route import RoutingConfig
    comp = Components(router=Router(RoutingConfig.load(a.routing_config)))
    print(f"routing: threshold {comp.router.cfg.threshold} from {comp.router.cfg.source}")
    comp.messages = load_messages()
    llm_client = None
    if not a.no_llm:
        try:
            from src.llm import client_from_env
            llm_client = client_from_env()
            comp.generator = Generator(llm_client)
            print(f"generate: {comp.generator.prompt.version} on {llm_client.model}")
        except Exception as e:  # noqa: BLE001 - no key or paid model id: run continues, nothing generated
            print(f"WARNING: Generate unavailable ({type(e).__name__}: {e}); auto/draft tickets escalate",
                  file=sys.stderr)
    if not a.no_models:
        try:
            emb = SentenceTransformerEmbedder()
        except Exception as e:  # noqa: BLE001
            emb = None
            print(f"WARNING: embedding model unavailable ({type(e).__name__}: {e})", file=sys.stderr)
        if emb is not None:
            try:
                comp.classifier = build_classifier(emb, use_llm_fallback=llm_client is not None, llm_client=llm_client)
                print(f"classifier: {comp.classifier.local.name} {comp.classifier.local.version}"
                      f"{' + PR-02 fallback' if comp.classifier.llm else ''}")
            except Exception as e:  # noqa: BLE001 - every ticket then escalates as classification_failed
                print(f"WARNING: classifier unavailable ({type(e).__name__}: {e})", file=sys.stderr)
            if comp.generator is not None:
                try:
                    gcfg = GuardrailConfig.load()
                    comp.validator = Validator(emb, gcfg, prompt_system=comp.generator.prompt.system)
                    print(f"validate: grounding floor {gcfg.grounding_floor} from {gcfg.source}"
                          + ("" if gcfg.grounding_floor is not None else " (NOT SET: every answer will be blocked)"))
                except Exception as e:  # noqa: BLE001 - no validator: nothing is sent
                    print(f"WARNING: Validate unavailable ({type(e).__name__}: {e}); nothing will be sent",
                          file=sys.stderr)
            try:
                comp.retriever = build_retriever(a.retrieval_config, embedder=emb)
                print(f"retrieval: {comp.retriever.model_version}, cutoff {comp.retriever.cutoff}")
            except Exception as e:  # noqa: BLE001 - no passages: Route escalates
                print(f"WARNING: retrieval unavailable ({type(e).__name__}: {e})", file=sys.stderr)

    comp.private_terms = private_terms_for(records)
    log = DecisionLog(db_path, run_id)
    log.start_run(in_path.name, input_sha, notes=HARNESS_VERSION)
    print(f"run {run_id}: {len(records)} tickets from {in_path} (runs on this file before: {prior_runs})")

    results = []
    for rec in records:
        r = process_ticket(rec, log, comp)
        results.append(r)
        if not a.quiet:
            g = r["generation"]
            gtxt = (f" gen={g['gen_action']}{' SENT' if r['action'] == 'auto_respond' else ''}"
                    f"{' BLOCKED' if g.get('validated') is False else ''}" if g else "")
            print(f"  {r['ticket_id']:<12} {r['channel']:<13} {r['intent']:<24} {r['intent_confidence']:.2f}  "
                  f"route={r['route_action']:<16}{gtxt:<28} final={r['action']:<9} {r['rule_fired']}")

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
    n_queue = write_escalation_queue(out_dir / "escalation_queue.csv", results)
    (out_dir / "reconcile.json").write_text(json.dumps(reconcile, indent=2), encoding="utf-8")
    (out_dir / "run_info.json").write_text(json.dumps(run_info, indent=2), encoding="utf-8")
    (out_dir / "metrics_report.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    (out_dir / "metrics_report.md").write_text(metrics_markdown(metrics), encoding="utf-8")

    status = "RECONCILED" if reconcile["ok"] else "RECONCILE FAILED"
    print(f"{status}: {reconcile['final_rows']} final rows for {len(records)} tickets; "
          f"actions {reconcile['final_actions']}; rows by stage {reconcile['rows_by_stage']}; "
          f"empty required fields {reconcile['rows_with_empty_required_field']}.")
    gens = [r["generation"] for r in results if r["generation"]]
    print(f"route decisions {dict(Counter(r['route_action'] for r in results))}; generation "
          f"{dict(Counter(g['gen_action'] for g in gens))}; blocked by Validate "
          f"{sum(g.get('validated') is False for g in gens)}; sent {sum(r['action'] == 'auto_respond' for r in results)}; "
          f"{n_queue} rows in escalation_queue.csv")
    if gens:
        print(f"read the answers: python -m evaluation.show_answers --run-dir {out_dir}")
    print(f"outputs in {out_dir}; decision log at {db_path}")
    print(f"read the log: python -m evaluation.show_log --run-dir {out_dir}")
    return 0 if reconcile["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
