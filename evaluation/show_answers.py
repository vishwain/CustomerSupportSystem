"""Read Generate's output for a run, side by side with the ticket and the cited passage text (checklist 5.8:
"read the outputs yourself"). For each generated ticket: the ticket, Route's choice, the answer or the
cannot-answer reason, each sentence with its citations, and the text of every cited passage, so you can
check that each sentence is really supported.

    python -m evaluation.show_answers --run-dir evaluation/results/<run-folder>
    python -m evaluation.show_answers --run-dir <folder> --ticket VAL-0012
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import textwrap
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--ticket")
    ap.add_argument("--retrieval-config", default="config/retrieval.json")
    a = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    from src.ingest import load
    from src.retrieve import CONFIGS, chunk_docs, load_config, load_docs

    run_dir = Path(a.run_dir)
    info = json.loads((run_dir / "run_info.json").read_text(encoding="utf-8"))
    tickets = {r.ticket_id: r for r in load(info["input_path"])}
    passages = {p.passage_id: p for p in chunk_docs(load_docs(), CONFIGS[load_config(a.retrieval_config).chunking])}
    con = sqlite3.connect(info["db_path"])
    con.row_factory = sqlite3.Row
    results = [json.loads(x) for x in (run_dir / "results.jsonl").read_text(encoding="utf-8").splitlines()]
    shown = 0
    for r in results:
        if a.ticket and r["ticket_id"] != a.ticket:
            continue
        if not r.get("generation"):
            continue
        shown += 1
        t = tickets.get(r["ticket_id"])
        row = con.execute("SELECT * FROM decisions WHERE ticket_id=? AND stage='generation' ORDER BY rowid DESC",
                          (r["ticket_id"],)).fetchone()
        pred = json.loads(row["prediction"]) if row else {}
        g = r["generation"]
        print("=" * 100)
        print(f"{r['ticket_id']}  intent={r['intent']} ({r['intent_confidence']:.2f})  route={r['route_action']}  "
              f"generate={g['gen_action']}  citations_ok={g['citations_ok']}  send-ready={g['would_send']}  "
              f"[{g['prompt_version']}]")
        if t:
            print(f"SUBJECT: {t.subject or '(empty)'}")
            print("BODY:    " + textwrap.fill(t.body, 96, subsequent_indent="         "))
        print(f"FINAL:   {r['action']} - {r['reason']}")
        if pred.get("restatement"):
            print(f"RESTATED: {pred['restatement']}")
        for i, s in enumerate(pred.get("sentences") or [], 1):
            print(f"  [{i}] {s['text']}")
            print(f"      cites {s['passage_ids']}")
        if pred.get("unsure_about"):
            print(f"UNSURE:  {pred['unsure_about']}")
        if g.get("unresolved"):
            print(f"UNRESOLVED CITATIONS: {g['unresolved']}")
        for pid in g.get("cited") or []:
            p = passages.get(pid)
            if p:
                print(f"  --- {pid} | {p.title} / {p.section}")
                print(textwrap.indent(textwrap.fill(p.text.replace("\n", " "), 94), "      "))
        if g.get("draft"):
            print("REPLY AS IT WOULD BE SENT:")
            print(textwrap.indent(g["draft"], "  | "))
    if not shown:
        print("no generated tickets in this run")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
