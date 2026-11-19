"""Read a run's decision log as text, one block per ticket (checklist 5.6: "read the log yourself").

    python -m evaluation.show_log --run-dir evaluation/results/<run-folder>          # first 20 tickets
    python -m evaluation.show_log --run-dir <folder> --ticket VAL-0012
    python -m evaluation.show_log --db storage/runs/<run_id>/decisions.db --limit 0  # all tickets
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path


def _short(row: sqlite3.Row) -> str:
    stage, act = row["stage"], row["action_taken"]
    conf = f" conf={row['confidence']:.2f}" if row["confidence"] is not None else ""
    thr = f" thr={row['threshold_applied']:.2f}" if row["threshold_applied"] is not None else ""
    extra = ""
    pred = json.loads(row["prediction"] or "{}")
    if stage == "classification":
        alts = json.loads(row["alternatives"] or "[]")
        extra = (f" intent={pred.get('intent')} urgency={pred.get('urgency')} via {pred.get('source')} "
                 f"alts={[(a['value'], a['confidence']) for a in alts]}")
    elif stage == "retrieval":
        src = json.loads(row["sources_used"] or "[]")
        extra = f" passages={[(s['passage_id'], s['score']) for s in src]}"
    rule = f" rule={row['rule_fired']}" if row["rule_fired"] != "none" else ""
    err = f" error={row['error']}" if row["error"] != "none" else ""
    return (f"  {stage:<15}{act:<17}{conf}{thr}{rule}{err}{extra}\n"
            f"  {'':<15}reason: {row['reason']}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--run-dir", help="harness --output folder (reads run_info.json)")
    g.add_argument("--db", help="decisions.db path")
    ap.add_argument("--ticket", help="one ticket id")
    ap.add_argument("--limit", type=int, default=20, help="tickets to show (0 = all)")
    a = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    db = Path(a.db) if a.db else Path(json.loads((Path(a.run_dir) / "run_info.json").read_text())["db_path"])
    con = sqlite3.connect(str(db))
    con.row_factory = sqlite3.Row
    run_id = con.execute("SELECT run_id FROM runs ORDER BY started_at DESC LIMIT 1").fetchone()[0]
    ids = [r[0] for r in con.execute(
        "SELECT ticket_id FROM decisions WHERE run_id=? AND stage='ingest' ORDER BY rowid", (run_id,))]
    if a.ticket:
        ids = [a.ticket]
    elif a.limit:
        ids = ids[: a.limit]
    print(f"run {run_id}, {db}\n")
    for tid in ids:
        rows = con.execute("SELECT * FROM decisions WHERE run_id=? AND ticket_id=? ORDER BY rowid",
                           (run_id, tid)).fetchall()
        if not rows:
            print(f"{tid}: no rows")
            continue
        print(f"{tid}  | {rows[0]['input_summary'][:110]!r}")
        for r in rows:
            print(_short(r))
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
