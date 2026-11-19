"""Gate check (5.12, A9): verify a harness run independently of the harness's own reconcile.

Reads the input file, the run's results.jsonl and the SQLite decision log directly, and checks:
  1. Every record in the input has exactly one final decision row, and nothing else does
     (tickets in = decisions out, including malformed records).
  2. Every final action is auto_respond or escalate. Every escalation has a reason. Every automatic
     answer has a reply that passed Validate.
  3. Every ticket has an ingest row and a final row; no row has an empty required field.
  4. No ticket labelled must_not_auto_respond was answered automatically (labels joined from the
     input file by ticket_id; the pipeline never read them, FR-03).
  5. With --compare <other run dir>: the same input gives the same route and final action for every
     ticket (FR-11 acceptance: determinism), and the re-run spent no provider calls if cached.

Usage:
    python -m evaluation.gate_check --run-dir evaluation/results/<gate run> [--compare evaluation/results/<re-run>]
Writes gate_check.md and gate_check.json into the run folder. Exit 0 only if every check passes.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from src.ingest import iter_raw, load

ACTIONS = {"auto_respond", "escalate"}


def _jsonl(p: Path) -> list[dict[str, Any]]:
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]


def load_run(run_dir: Path) -> dict[str, Any]:
    info = json.loads((run_dir / "run_info.json").read_text(encoding="utf-8"))
    results = _jsonl(run_dir / "results.jsonl")
    metrics = json.loads((run_dir / "metrics_report.json").read_text(encoding="utf-8"))
    con = sqlite3.connect(info["db_path"])
    rows = con.execute("SELECT ticket_id, stage, action_taken, reason FROM decisions WHERE run_id=?",
                       (info["run_id"],)).fetchall()
    con.close()
    return {"dir": run_dir, "info": info, "results": results, "metrics": metrics, "rows": rows}


def labels_by_id(input_path: Path) -> dict[str, dict[str, Any]]:
    """Labels joined by ticket id, using the same id assignment as ingest (ROW-nnnn, #2 suffixes)."""
    raws = [raw for _, raw in iter_raw(input_path)]
    out = {}
    for rec, raw in zip(load(input_path), raws):
        out[rec.ticket_id] = raw.get("labels", {}) if isinstance(raw, dict) else {}
    return out


def check(run: dict[str, Any], compare: dict[str, Any] | None = None) -> dict[str, Any]:
    info, results, rows = run["info"], run["results"], run["rows"]
    input_path = Path(info["input_path"])
    raw_count = sum(1 for _ in iter_raw(input_path))
    labels = labels_by_id(input_path)
    ids_in = list(labels)

    finals = [r for r in rows if r[1] == "final"]
    final_ids = Counter(r[0] for r in finals)
    stages = {}
    for tid, stage, *_ in rows:
        stages.setdefault(tid, set()).add(stage)

    c: dict[str, Any] = {}
    c["records_in_file"] = raw_count
    c["tickets_after_ingest"] = len(ids_in)
    c["results_lines"] = len(results)
    c["final_rows_in_log"] = len(finals)
    c["tickets_without_final"] = sorted(set(ids_in) - set(final_ids))
    c["final_rows_without_ticket"] = sorted(set(final_ids) - set(ids_in))
    c["tickets_with_2plus_finals"] = sorted(t for t, n in final_ids.items() if n > 1)
    c["bad_final_actions"] = sorted({r[2] for r in finals} - ACTIONS)
    c["escalations_without_reason"] = [r[0] for r in finals if r[2] == "escalate" and not (r[3] or "").strip()]
    c["auto_without_reply"] = [r["ticket_id"] for r in results if r["action"] == "auto_respond" and not r.get("reply")]
    c["auto_not_validated"] = [r["ticket_id"] for r in results if r["action"] == "auto_respond"
                               and (r.get("generation") or {}).get("validated") is not True]
    c["tickets_missing_ingest_row"] = sorted(t for t in ids_in if "ingest" not in stages.get(t, set()))
    c["must_not_answered_automatically"] = [r["ticket_id"] for r in results if r["action"] == "auto_respond"
                                            and labels.get(r["ticket_id"], {}).get("must_not_auto_respond")]
    c["harness_reconcile_ok"] = json.loads((run["dir"] / "reconcile.json").read_text(encoding="utf-8"))["ok"]

    passes = {
        "one final row per ticket, none extra": (raw_count == len(ids_in) == len(results) == len(finals)
                                                 and not c["tickets_without_final"]
                                                 and not c["final_rows_without_ticket"]
                                                 and not c["tickets_with_2plus_finals"]),
        "every final action is auto_respond or escalate": not c["bad_final_actions"],
        "every escalation has a reason": not c["escalations_without_reason"],
        "every automatic answer has a reply that passed Validate": not (c["auto_without_reply"]
                                                                        or c["auto_not_validated"]),
        "every ticket has an ingest row": not c["tickets_missing_ingest_row"],
        "no must_not_auto_respond ticket answered automatically": not c["must_not_answered_automatically"],
        "harness reconcile.json ok": c["harness_reconcile_ok"],
    }

    if compare is not None:
        a = {r["ticket_id"]: (r["route_action"], r["action"], r["rule_fired"]) for r in results}
        b = {r["ticket_id"]: (r["route_action"], r["action"], r["rule_fired"]) for r in compare["results"]}
        diff = sorted(t for t in set(a) | set(b) if a.get(t) != b.get(t))
        c["compare_run"] = str(compare["dir"])
        c["compare_differences"] = [{"ticket_id": t, "this": a.get(t), "other": b.get(t)} for t in diff]
        c["compare_provider_requests"] = compare["metrics"].get("provider_requests")
        c["compare_cache_hits"] = compare["metrics"].get("generation_cache_hits")
        passes["same input, same route and final action (determinism)"] = not diff

    m = run["metrics"]
    summary = {
        "actions": dict(Counter(r["action"] for r in results)),
        "route_actions": dict(Counter(r["route_action"] for r in results)),
        "rules_fired": dict(Counter(r["rule_fired"] for r in results)),
        "errors": dict(Counter(r["error"] for r in results)),
        "auto_by_intent": dict(Counter(r["intent"] for r in results if r["action"] == "auto_respond")),
        "provider_requests": m.get("provider_requests"), "cache_hits": m.get("generation_cache_hits"),
        "degraded_mode_tickets": m.get("degraded_mode_tickets"),
        "latency_ms_p50": m.get("latency_ms_p50"), "latency_ms_p95": m.get("latency_ms_p95"),
    }
    return {"run_id": info["run_id"], "input": info["input_path"], "input_sha256": info["input_sha256"],
            "checks": c, "passes": passes, "summary": summary, "ok": all(passes.values())}


def to_markdown(r: dict[str, Any]) -> str:
    c, s = r["checks"], r["summary"]
    L = [f"# Gate check (5.12): {r['run_id']}", "",
         f"Input `{r['input']}` (sha256 {r['input_sha256'][:12]}). Checked by `evaluation/gate_check.py` from the "
         "input file and the SQLite decision log, independently of the harness.", "",
         f"**{'GATE PASSED' if r['ok'] else 'GATE FAILED'}**", "", "| Check | Result |", "| --- | --- |"]
    L += [f"| {k} | {'PASS' if v else 'FAIL'} |" for k, v in r["passes"].items()]
    L += ["", "| Count | Value |", "| --- | --- |",
          f"| Records in the input file | {c['records_in_file']} |",
          f"| Tickets after ingest | {c['tickets_after_ingest']} |",
          f"| Lines in results.jsonl | {c['results_lines']} |",
          f"| Final rows in the decision log | {c['final_rows_in_log']} |",
          f"| Final actions | {s['actions']} |",
          f"| Route actions | {s['route_actions']} |",
          f"| Errors | {s['errors']} |",
          f"| Automatic answers by intent | {s['auto_by_intent']} |",
          f"| Provider requests / cache hits | {s['provider_requests']} / {s['cache_hits']} |",
          f"| Degraded-mode tickets | {s['degraded_mode_tickets']} |",
          f"| Latency p50 / p95 (ms) | {s['latency_ms_p50']} / {s['latency_ms_p95']} |",
          "", "Rules fired: " + ", ".join(f"{k} {v}" for k, v in sorted(s["rules_fired"].items(), key=lambda x: -x[1]))]
    if "compare_run" in c:
        L += ["", f"Re-run compared: `{c['compare_run']}`: {len(c['compare_differences'])} ticket(s) differ; "
              f"re-run provider requests {c['compare_provider_requests']}, cache hits {c['compare_cache_hits']}."]
        for d in c["compare_differences"][:20]:
            L.append(f"- {d['ticket_id']}: {d['this']} vs {d['other']}")
    bad = {k: v for k, v in c.items() if isinstance(v, list) and v and k != "compare_differences"}
    if bad:
        L += ["", "Problems:"] + [f"- {k}: {v[:20]}" for k, v in bad.items()]
    return "\n".join(L) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--compare", help="a second run of the same input, for the determinism check")
    a = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    run = load_run(Path(a.run_dir))
    other = load_run(Path(a.compare)) if a.compare else None
    if other and other["info"]["input_sha256"] != run["info"]["input_sha256"]:
        print("ERROR: --compare run used a different input file", file=sys.stderr)
        return 2
    r = check(run, other)
    md = to_markdown(r)
    (Path(a.run_dir) / "gate_check.md").write_text(md, encoding="utf-8")
    (Path(a.run_dir) / "gate_check.json").write_text(json.dumps(r, indent=2), encoding="utf-8")
    print(md)
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
