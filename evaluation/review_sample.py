"""Human review sample (5.18): draw the sample and build the review packet and blank scoring sheets.

Sample rule (fixed before anyone scores): every escalated ticket in the run (this includes every
guardrail-blocked one), plus a seeded random sample of the automatic answers, seed 42, enough to reach
the target size. The rule, the seed and the ticket list are written to SAMPLE.md.

Outputs in --out (default evaluation/results/human_review):
  SAMPLE.md           how the sample was drawn, and the ticket list
  review_packet.md    what the assessors read: ticket, the sent answer (or blocked draft, or escalation
                      package and holding message), numbered sentences with their citations, and the text
                      of every cited or retrieved passage
  assessor_A.csv, assessor_B.csv   blank sheets, one row per sampled ticket (rubric in RUBRIC.md)

No pipeline code, prompt or response is changed: everything is read from the run folder and its log.

Usage:
    python -m evaluation.review_sample --run-dir evaluation/results/validation_5.17_official
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from pathlib import Path
from typing import Any

from src import pii
from src.ingest import load
from src.logging_store import DecisionLog
from src.retrieve import CONFIGS, chunk_docs, load_config, load_docs

SEED = 42
SHEET_FIELDS = ("ticket_id", "item_type", "sentences", "citations",
                "unsupported_sentences", "citations_supporting", "block_justified",
                "escalation_correct", "summary_accurate",
                "correctness", "completeness", "tone", "notes")


def draw(results: list[dict[str, Any]], target: int, seed: int = SEED) -> dict[str, Any]:
    escalated = sorted(r["ticket_id"] for r in results if r["action"] == "escalate")
    blocked = sorted(r["ticket_id"] for r in results if str(r.get("rule_fired", "")).startswith("guardrail:"))
    auto = sorted(r["ticket_id"] for r in results if r["action"] == "auto_respond")
    k = max(0, min(len(auto), target - len(escalated)))
    picked = sorted(random.Random(seed).sample(auto, k))
    return {"escalated": escalated, "blocked": blocked, "auto_pool": len(auto), "auto_sampled": picked,
            "sample": sorted(escalated + picked), "seed": seed, "target": target}


def item_type(r: dict[str, Any]) -> str:
    if str(r.get("rule_fired", "")).startswith("guardrail:"):
        return "blocked"
    return "answered" if r["action"] == "auto_respond" else "escalated"


def build(run_dir: Path, out: Path, target: int) -> dict[str, Any]:
    info = json.loads((run_dir / "run_info.json").read_text(encoding="utf-8"))
    results = {json.loads(x)["ticket_id"]: json.loads(x)
               for x in (run_dir / "results.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()}
    log = DecisionLog(info["db_path"], info["run_id"])
    rows = log.rows()
    log.close()
    gen = {r["ticket_id"]: r for r in rows if r["stage"] == "generation"}
    ret = {r["ticket_id"]: r for r in rows if r["stage"] == "retrieval"}
    texts = {rec.ticket_id: rec.text for rec in load(info["input_path"])}
    passages = {p.passage_id: p for p in chunk_docs(load_docs(), CONFIGS[load_config().chunking])}
    s = draw(list(results.values()), target)
    out.mkdir(parents=True, exist_ok=True)

    # ---- SAMPLE.md
    (out / "SAMPLE.md").write_text("\n".join([
        "# Human review sample (5.18)", "",
        f"Run `{info['run_id']}` (5.17 official run), input `{info['input_path']}`.", "",
        "How it was drawn (rule fixed before scoring, script `evaluation/review_sample.py`):", "",
        f"1. Every escalated ticket: {len(s['escalated'])}. This includes every guardrail-blocked ticket "
        f"({len(s['blocked'])}: {', '.join(s['blocked']) or 'none'}), whose blocked draft is reviewed.",
        f"2. A random sample of the automatic answers: {len(s['auto_sampled'])} of {s['auto_pool']}, "
        f"`random.Random({s['seed']}).sample(sorted ids, {len(s['auto_sampled'])})`, to reach {s['target']} items.",
        f"3. Total: **{len(s['sample'])}** of {len(results)} responses.", "",
        "Automatic answers sampled: " + ", ".join(s["auto_sampled"]), "",
        "Escalated: " + ", ".join(s["escalated"]), ""]), encoding="utf-8")

    # ---- packet + sheets
    L = ["# Review packet (5.18)", "",
         "Read RUBRIC.md first. Score each item in your own sheet only; do not open the other assessor's sheet.",
         "Ticket text has private data replaced by [REDACTED:...]. Sentence numbers match the sheet counts.", ""]
    sheet_rows = []
    for n, tid in enumerate(s["sample"], 1):
        r = results[tid]
        kind = item_type(r)
        L += ["---", "", f"## {n}. {tid} ({kind})", "",
              f"Channel {r['channel']}; predicted intent {r['intent']} ({r['intent_confidence']:.2f}); "
              f"route {r['route_action']}; final {r['action']}; rule `{r['rule_fired']}`.", "",
              "**Ticket**", "", "> " + pii.scrub(texts.get(tid, "")).replace("\n", "\n> "), ""]
        sentences, cited_ids = [], []
        if kind in ("answered", "blocked"):
            g = gen.get(tid) or {}
            sentences = (g.get("prediction") or {}).get("sentences") or []
            if kind == "answered":
                L += ["**Sent to the customer**", "", "```", r.get("reply") or "", "```", ""]
            else:
                L += [f"**Blocked draft (never sent).** Block reason: {r['reason']}", ""]
            L += ["**Answer sentences and their citations**", ""]
            for i, snt in enumerate(sentences, 1):
                ids = snt.get("passage_ids") or []
                cited_ids += [x for x in ids if x not in cited_ids]
                L.append(f"{i}. {snt.get('text', '')}  [cites: {', '.join(ids) or 'none'}]")
            L += ["", "**Cited passages**", ""]
            for pid in cited_ids:
                p = passages.get(pid)
                L += [f"*{pid}* ({p.title if p else 'not found'})", "", "> " + (p.text if p else "(text not found)")
                      .replace("\n", "\n> "), ""]
        else:
            pkg = r.get("escalation_package") or {}
            L += ["**Customer received (holding message)**", "", "```", r.get("customer_message") or "", "```", "",
                  "**Escalation package for the agent**", "",
                  f"- Summary: {pkg.get('summary', '')}", f"- Restatement: {pkg.get('restatement', '')}",
                  f"- Reason: {pkg.get('reason', '')}", ""]
            top = [x["passage_id"] for x in ((ret.get(tid) or {}).get("sources_used") or [])][:3]
            L += ["**Sources retrieved for the agent**" + ("" if top else ": none passed the cutoff"), ""]
            for pid in top:
                p = passages.get(pid)
                L += [f"*{pid}* ({p.title if p else 'not found'})", "", "> " + (p.text if p else "").replace(
                    "\n", "\n> "), ""]
        n_cit = sum(len(x.get("passage_ids") or []) for x in sentences)
        sheet_rows.append({"ticket_id": tid, "item_type": kind, "sentences": len(sentences), "citations": n_cit})
    (out / "review_packet.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    for who in ("A", "B"):
        p = out / f"assessor_{who}.csv"
        if p.exists():
            continue  # never overwrite a sheet that may already hold scores
        with open(p, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=SHEET_FIELDS)
            w.writeheader()
            for row in sheet_rows:
                w.writerow(row)
    return s


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--out", default="evaluation/results/human_review")
    ap.add_argument("--target", type=int, default=59)
    a = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    s = build(Path(a.run_dir), Path(a.out), a.target)
    print(f"sample: {len(s['sample'])} items ({len(s['escalated'])} escalated incl. {len(s['blocked'])} blocked, "
          f"{len(s['auto_sampled'])} of {s['auto_pool']} automatic answers, seed {s['seed']}) -> {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
