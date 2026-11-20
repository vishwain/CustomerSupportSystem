"""Incident lookup in the decision log (Governance Framework sections 1 and 5). Read-only.

    python -m src.trace ticket VAL-0039                       every row for one ticket, every run, in order
    python -m src.trace sent --since 2026-11-20T00:00         answers sent since a time (who may be affected)
    python -m src.trace sent --since 2026-11-20 --doc DOC-SSO-001   ... only answers citing one article
    python -m src.trace sent --since 2026-11-20 --intent billing_query

--db defaults to the API log (STORAGE_DIR/api/decisions.db); pass a run's decisions.db for a harness run.
Prints no customer text: input_summary is already redacted in the log, and replies are not stored there.
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path


def default_db() -> Path:
    return Path(os.getenv("STORAGE_DIR", "storage")) / "api" / "decisions.db"


def connect(db: str | Path) -> sqlite3.Connection:
    p = Path(db)
    if not p.exists():
        raise SystemExit(f"no decision log at {p}")
    con = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    return con


def _j(x):
    try:
        return json.loads(x) if x else None
    except ValueError:
        return x


def ticket_rows(con, ticket_id: str) -> list[dict]:
    q = ("SELECT timestamp, run_id, stage, action_taken, rule_fired, confidence, threshold_applied, reason, "
         "sources_used, guardrail_results, prompt_version, decision_id FROM decisions WHERE ticket_id = ? "
         "ORDER BY timestamp, rowid")
    return [dict(r) for r in con.execute(q, (ticket_id,))]


def sent(con, since: str, doc: str | None = None, intent: str | None = None) -> list[dict]:
    finals = con.execute("SELECT run_id, ticket_id, timestamp, decision_id FROM decisions WHERE stage = 'final' "
                         "AND action_taken = 'auto_respond' AND timestamp >= ? ORDER BY timestamp", (since,)).fetchall()
    out = []
    for f in finals:
        key = (f["run_id"], f["ticket_id"])
        gen = con.execute("SELECT sources_used FROM decisions WHERE run_id=? AND ticket_id=? AND stage='generation'",
                          key).fetchone()
        cls = con.execute("SELECT prediction FROM decisions WHERE run_id=? AND ticket_id=? AND stage='classification'",
                          key).fetchone()
        docs = sorted({s.get("doc_id", "") for s in (_j(gen["sources_used"]) or [])}) if gen else []
        it = (_j(cls["prediction"]) or {}).get("intent") if cls else None
        if doc and doc not in docs:
            continue
        if intent and it != intent:
            continue
        out.append({"timestamp": f["timestamp"], "ticket_id": f["ticket_id"], "run_id": f["run_id"],
                    "intent": it, "cited_docs": docs, "final_decision_id": f["decision_id"]})
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Look up decisions for an incident (read-only).")
    sub = ap.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("ticket")
    t.add_argument("ticket_id")
    s = sub.add_parser("sent")
    s.add_argument("--since", required=True, help="ISO time, UTC, e.g. 2026-11-20T00:00")
    s.add_argument("--doc")
    s.add_argument("--intent")
    for p in (t, s):
        p.add_argument("--db", default=None)
    a = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    con = connect(a.db or default_db())
    if a.cmd == "ticket":
        rows = ticket_rows(con, a.ticket_id)
        if not rows:
            print(f"no rows for {a.ticket_id}")
            return 1
        for r in rows:
            print(f"{r['timestamp']}  {r['stage']:<14} {r['action_taken']:<16} {r['rule_fired']:<28} "
                  f"run={r['run_id']}\n    reason: {r['reason'][:300]}")
            if r["guardrail_results"] and r["stage"] == "validation":
                print(f"    guardrails: {r['guardrail_results']}")
            if r["sources_used"] and r["stage"] in ("retrieval", "generation"):
                print(f"    sources: {[x.get('passage_id', x.get('doc_id')) for x in (_j(r['sources_used']) or [])][:5]}")
    else:
        rows = sent(con, a.since, a.doc, a.intent)
        for r in rows:
            print(f"{r['timestamp']}  {r['ticket_id']:<12} {str(r['intent']):<24} {','.join(r['cited_docs'])}  run={r['run_id']}")
        print(f"{len(rows)} answer(s) sent since {a.since}" + (f" citing {a.doc}" if a.doc else "")
              + (f" with intent {a.intent}" if a.intent else ""))
    con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
