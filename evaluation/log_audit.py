"""Decision-log audit (5b.1, Governance Framework section 1): minimum record fields and coverage.

Checks one run's SQLite decision log, independently of the harness:
  1. Fields: every row carries the framework's minimum record (decision_id, timestamp, ticket_id, stage,
     input_summary, model name and version, prediction, alternatives, sources_used, threshold_applied,
     action_taken, reason, guardrail_results, prompt_version, requirement_ids). Fields that only apply to one
     stage are checked on that stage: confidence and alternatives on classification, threshold on routing,
     guardrail results on validation, the escalation package on escalated final rows, the generated sentences
     and citations on answered tickets.
  2. Coverage: final rows = tickets in the input (a --limit run counts the tickets it processed), no ticket
     without a final row, no duplicate final row, and every ticket has ingest, classification, retrieval and
     routing rows (malformed records stop after ingest by design).

Usage:  python -m evaluation.log_audit --run-dir evaluation/results/validation_5.17_official
Writes log_audit.md and log_audit.json into the run folder. Exit 0 only if every check passes.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from src.ingest import iter_raw, load
from src.logging_store import REQUIRED, DecisionLog

FRAMEWORK_FIELDS = {  # Governance Framework minimum record -> decision-log column
    "decision_id": "decision_id", "timestamp": "timestamp", "ticket_id": "ticket_id", "stage": "stage",
    "input_summary": "input_summary", "model.name": "model_name", "model.version": "model_version",
    "prediction": "prediction", "alternatives": "alternatives", "sources_used": "sources_used",
    "threshold_applied": "threshold_applied", "action_taken": "action_taken", "reason": "reason",
    "guardrail_results": "guardrail_results", "prompt_version": "prompt_version",
    "requirement_ids": "requirement_ids",
}
ALWAYS = ("decision_id", "timestamp", "ticket_id", "stage", "input_summary", "model_name", "model_version",
          "prompt_version", "action_taken", "reason", "requirement_ids")
PIPELINE = ("ingest", "classification", "retrieval", "routing")


def empty(v: Any) -> bool:
    return v is None or (isinstance(v, str) and not v.strip()) or (isinstance(v, (list, dict)) and not v)


def audit(rows: list[dict[str, Any]], ticket_ids: list[str]) -> dict[str, Any]:
    by = defaultdict(dict)
    dup_stage = []
    for r in rows:
        if r["stage"] in by[r["ticket_id"]] and r["stage"] != "final":
            dup_stage.append((r["ticket_id"], r["stage"]))
        by[r["ticket_id"]].setdefault(r["stage"], r)
    problems: list[str] = []

    # ---- 1. fields
    for r in rows:
        for c in ALWAYS + REQUIRED:
            if empty(r.get(c)):
                problems.append(f"{r['ticket_id']} {r['stage']}: {c} empty")
        s = r["stage"]
        if s == "classification" and (r.get("prediction") or {}).get("intent") not in (None, "unknown"):
            if r.get("confidence") is None:
                problems.append(f"{r['ticket_id']} classification: confidence missing")
            if empty(r.get("alternatives")):
                problems.append(f"{r['ticket_id']} classification: alternatives missing")
        if s == "routing" and r.get("threshold_applied") is None:
            problems.append(f"{r['ticket_id']} routing: threshold_applied missing")
        if s == "validation" and empty(r.get("guardrail_results")):
            problems.append(f"{r['ticket_id']} validation: guardrail_results missing")
        if s == "retrieval" and not r.get("sources_used") and "no" not in r["reason"].lower() \
                and "cutoff" not in r["reason"].lower():
            problems.append(f"{r['ticket_id']} retrieval: no sources and the reason does not say why")
    field_rows = Counter(r["stage"] for r in rows)

    # ---- response or escalation, per ticket
    resp = Counter()
    for tid, st in by.items():
        fin = st.get("final")
        if not fin:
            continue
        if fin["action_taken"] == "escalate":
            ok = not empty(fin.get("escalation_package"))
            resp["escalation package on final row"] += ok
            if not ok:
                problems.append(f"{tid} final: escalate without an escalation package")
        else:
            g, v = st.get("generation"), st.get("validation")
            ok = bool(g and (g.get("prediction") or {}).get("sentences") and g.get("sources_used")
                      and v and v["action_taken"] == "pass")
            resp["answered: generated sentences, citations and a Validate pass"] += ok
            if not ok:
                problems.append(f"{tid} final: auto_respond without logged sentences, citations and a Validate pass")

    # ---- 2. coverage
    finals = Counter(r["ticket_id"] for r in rows if r["stage"] == "final")
    want = set(ticket_ids)
    malformed = {t for t, st in by.items() if (st.get("ingest") or {}).get("error") == "malformed_input"}
    missing_stage = sorted(f"{t}:{s}" for t in want - malformed for s in PIPELINE if s not in by.get(t, {}))
    cov = {
        "tickets_in": len(ticket_ids),
        "final_rows": sum(finals.values()),
        "tickets_without_final": sorted(want - set(finals)),
        "final_rows_without_ticket": sorted(set(finals) - want),
        "duplicate_final_rows": sorted(t for t, n in finals.items() if n > 1),
        "duplicate_stage_rows": dup_stage,
        "duplicate_ticket_ids_in_input": sorted(t for t, n in Counter(ticket_ids).items() if n > 1),
        "tickets_missing_a_pipeline_row": missing_stage,
        "malformed_tickets": sorted(malformed),
    }
    cov_ok = (cov["final_rows"] == cov["tickets_in"] and not cov["tickets_without_final"]
              and not cov["final_rows_without_ticket"] and not cov["duplicate_final_rows"]
              and not dup_stage and not missing_stage and not cov["duplicate_ticket_ids_in_input"])
    present = {k: all(c in rows[0] for c in [v]) for k, v in FRAMEWORK_FIELDS.items()} if rows else {}
    return {"rows": len(rows), "rows_by_stage": dict(field_rows), "framework_fields_present": present,
            "field_problems": problems, "responses": dict(resp), "coverage": cov,
            "fields_ok": not problems and all(present.values()), "coverage_ok": cov_ok,
            "ok": not problems and cov_ok and all(present.values())}


def to_markdown(r: dict[str, Any], info: dict[str, Any]) -> str:
    c = r["coverage"]
    L = [f"# Decision-log audit (5b.1): {info['run_id']}", "",
         f"Input `{info['input_path']}`; log `{info['db_path']}`. Checked by `evaluation/log_audit.py` against the "
         "Governance Framework minimum record.", "",
         f"**{'PASS' if r['ok'] else 'FAIL'}**: fields {'complete' if r['fields_ok'] else 'INCOMPLETE'}, coverage "
         f"{'reconciles exactly' if r['coverage_ok'] else 'DOES NOT RECONCILE'}.", "",
         "## 1. Minimum record fields", "", "| Framework field | Column | Present |", "| --- | --- | --- |"]
    for k, v in FRAMEWORK_FIELDS.items():
        L.append(f"| {k} | `{v}` | {'yes' if r['framework_fields_present'].get(k) else 'NO'} |")
    L += ["", f"{r['rows']} rows checked: {r['rows_by_stage']}. Rows with a missing or empty required field: "
          f"**{len(r['field_problems'])}**.", "",
          "Stage-specific checks: classification rows carry confidence and alternatives; routing rows carry the "
          "threshold applied; validation rows carry every guardrail result; retrieval rows with no sources say why.",
          "", "Response or escalation, per ticket: " + "; ".join(f"{k}: {v}" for k, v in r["responses"].items())
          + ". The exact text sent to the customer is in results.jsonl; the log holds the generated sentences "
          "(redacted), their citations and the Validate result it was built from.", "",
          "## 2. Coverage", "", "| Check | Result |", "| --- | --- |",
          f"| Tickets in the input | {c['tickets_in']} |", f"| Final decision rows | {c['final_rows']} |",
          f"| Tickets without a final row | {len(c['tickets_without_final'])} |",
          f"| Final rows without a ticket | {len(c['final_rows_without_ticket'])} |",
          f"| Duplicate final rows | {len(c['duplicate_final_rows'])} |",
          f"| Duplicate stage rows | {len(c['duplicate_stage_rows'])} |",
          f"| Duplicate ticket ids in the input | {len(c['duplicate_ticket_ids_in_input'])} |",
          f"| Tickets missing an ingest, classification, retrieval or routing row | "
          f"{len(c['tickets_missing_a_pipeline_row'])} |"]
    if r["field_problems"]:
        L += ["", "Problems:"] + [f"- {p}" for p in r["field_problems"][:30]]
    return "\n".join(L) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--run-dir", required=True)
    a = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    d = Path(a.run_dir)
    info = json.loads((d / "run_info.json").read_text(encoding="utf-8"))
    log = DecisionLog(info["db_path"], info["run_id"])
    rows = log.rows()
    log.close()
    n = int(info.get("tickets_in") or 0) or sum(1 for _ in iter_raw(info["input_path"]))
    ids = [rec.ticket_id for rec in load(info["input_path"])][:n]
    r = audit(rows, ids)
    (d / "log_audit.json").write_text(json.dumps(r, indent=2), encoding="utf-8")
    md = to_markdown(r, info)
    (d / "log_audit.md").write_text(md, encoding="utf-8")
    print(md)
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
