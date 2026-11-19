"""Query experiment (5.13 follow-up, NFR-06): does adding the predicted intent's description to the
retrieval query close the gap for tickets without a subject (every chat ticket)?

The gate run showed chat tickets (no subject) at 46% top-3 hit rate against 95% for tickets with a subject.
The PRD (Section 10) designed the query as ticket text plus the predicted intent's description; it was
built as text only. This compares three query modes on the dev HOLD-OUT (the classifier never saw these
tickets; the predicted intent comes from the deployed classifier, not the label):

  text                   ticket text only (current)
  intent                 intent description, then the ticket text, for every ticket
  intent_if_no_subject   the same, only for tickets without a subject

For each mode the cutoff is chosen with the same rule as 5.2 (highest cutoff keeping hold-out top-3 hit
rate on answerable tickets at 85% or more, AS-01). Rule for the mode, fixed before the run: the mode with
the smallest gap between tickets with and without a subject, among modes whose overall hold-out hit rate
at their cutoff is within 1 point of the best; ties go to the simpler mode (text, then
intent_if_no_subject, then intent). Validation is the check, never the basis.

Usage (repo root):
    python docs/query_experiment.py                 # report only
    python docs/query_experiment.py --write-config  # also sets query_mode and cutoff in config/retrieval.json
Output: evaluation/results/<date>_query_experiment/query_experiment.md and .json
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.ingest import normalise  # noqa: E402
from src.retrieve import QUERY_MODES, build_query  # noqa: E402
from src.splits import dev_holdout_split, text_key  # noqa: E402

TARGET = 0.85
TIE = 0.01
SWEEP = [round(i / 100, 2) for i in range(0, 91)]
SIMPLICITY = {"text": 0, "intent_if_no_subject": 1, "intent": 2}


def prep(raw: list[dict[str, Any]], classifier) -> list[dict[str, Any]]:
    out = []
    for i, t in enumerate(raw):
        rec = normalise(t, i)
        if not rec.ok:
            continue
        cls = classifier.classify(rec, allow_llm=False)
        lab = t.get("labels", {})
        out.append({"ticket_id": rec.ticket_id, "text": rec.text, "subject": rec.subject,
                    "has_subject": bool((rec.subject or "").strip()), "channel": rec.channel,
                    "pred_intent": None if cls.failed else cls.intent,
                    "answerable": bool(lab.get("answerable_from_docs")),
                    "expected": set(lab.get("expected_doc_ids") or []), "key": text_key(t)})
    return out


def score(tickets: list[dict[str, Any]], retriever, mode: str) -> list[dict[str, Any]]:
    rows = []
    for t in tickets:
        q, expanded = build_query(t["text"], t["subject"], t["pred_intent"], mode)
        top = retriever.score_all(q)[:5]
        rows.append({**t, "expanded": expanded, "top5": [(p.doc_id, p.score) for p in top]})
    return rows


def at_cutoff(rows: list[dict[str, Any]], c: float) -> dict[str, Any]:
    def kept(r):
        return [d for d, s in r["top5"] if s >= c]

    def hit(rs):
        rs = [r for r in rs if r["answerable"] and r["expected"]]
        return (round(sum(bool(set(kept(r)[:3]) & r["expected"]) for r in rs) / len(rs), 4) if rs else None), len(rs)

    allh, n = hit(rows)
    subj, ns = hit([r for r in rows if r["has_subject"]])
    nosubj, nn = hit([r for r in rows if not r["has_subject"]])
    una = [r for r in rows if not r["answerable"]]
    return {"cutoff": c, "hit3": allh, "n": n, "hit3_subject": subj, "n_subject": ns,
            "hit3_no_subject": nosubj, "n_no_subject": nn,
            "gap_pts": round(100 * abs(subj - nosubj), 1) if subj is not None and nosubj is not None else None,
            "unanswerable_empty": round(sum(not kept(r) for r in una) / len(una), 4) if una else None}


def pick_cutoff(rows: list[dict[str, Any]]) -> dict[str, Any]:
    sweep = [at_cutoff(rows, c) for c in SWEEP]
    ok = [s for s in sweep if s["hit3"] is not None and s["hit3"] >= TARGET]
    if ok:
        return max(ok, key=lambda s: s["cutoff"]) | {"as01": True}
    base = sweep[0]["hit3"]
    keep = [s for s in sweep if s["hit3"] >= base - 0.01]
    return max(keep, key=lambda s: s["cutoff"]) | {"as01": False}


def run(dev_raw, val_raw, classifier, retriever) -> dict[str, Any]:
    _, hold_ids = dev_holdout_split(dev_raw)
    hs = set(hold_ids)
    hold = prep([t for t in dev_raw if t["ticket_id"] in hs], classifier)
    val = prep(val_raw, classifier)
    dev_keys = {text_key(t) for t in dev_raw}
    modes = {}
    for m in QUERY_MODES:
        hrows = score(hold, retriever, m)
        pick = pick_cutoff(hrows)
        vrows = score(val, retriever, m)
        modes[m] = {"holdout": pick, "holdout_no_cutoff": at_cutoff(hrows, 0.0),
                    "validation": at_cutoff(vrows, pick["cutoff"]),
                    "validation_unseen": at_cutoff([r for r in vrows if r["key"] not in dev_keys], pick["cutoff"]),
                    "validation_chat": at_cutoff([r for r in vrows if r["channel"] == "chat"], pick["cutoff"]),
                    "expanded_share_holdout": round(sum(r["expanded"] for r in hrows) / len(hrows), 3)}
    best = max(v["holdout"]["hit3"] for v in modes.values())
    near = [m for m, v in modes.items() if v["holdout"]["hit3"] >= best - TIE]
    chosen = min(near, key=lambda m: ((modes[m]["holdout"]["gap_pts"] if modes[m]["holdout"]["gap_pts"]
                                       is not None else 999), SIMPLICITY[m]))
    return {"run_date": date.today().isoformat(), "holdout_n": len(hold), "validation_n": len(val),
            "modes": modes, "chosen": chosen,
            "rule": ("smallest subject / no-subject gap among modes within 1 point of the best hold-out hit rate "
                     "at their own cutoff; ties to the simpler mode")}


def to_markdown(r: dict[str, Any]) -> str:
    def p(x):
        return "n/a" if x is None else f"{100 * x:.1f}%"

    L = [f"# Query experiment (intent-expanded query), {r['run_date']}", "",
         f"Dev hold-out {r['holdout_n']} tickets (basis), validation {r['validation_n']} (check). Predicted intent "
         "from the deployed classifier. Generated by `docs/query_experiment.py`.", "",
         "| Mode | Cutoff | Hold-out hit@3 | With subject (n) | No subject (n) | Gap | Unanswerable stopped | "
         "Validation hit@3 | Validation chat hit@3 (n) | Validation unseen |",
         "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for m, v in r["modes"].items():
        h, va, ch, un = v["holdout"], v["validation"], v["validation_chat"], v["validation_unseen"]
        L.append(f"| {m} | {h['cutoff']} | {p(h['hit3'])} | {p(h['hit3_subject'])} ({h['n_subject']}) | "
                 f"{p(h['hit3_no_subject'])} ({h['n_no_subject']}) | {h['gap_pts']} pts | {p(h['unanswerable_empty'])} | "
                 f"{p(va['hit3'])} | {p(ch['hit3'])} ({ch['n']}) | {p(un['hit3'])} |")
    L += ["", "Without any cutoff (ranking quality only):", "",
          "| Mode | Hold-out hit@3 | With subject | No subject |", "| --- | --- | --- | --- |"]
    for m, v in r["modes"].items():
        h = v["holdout_no_cutoff"]
        L.append(f"| {m} | {p(h['hit3'])} | {p(h['hit3_subject'])} | {p(h['hit3_no_subject'])} |")
    c = r["modes"][r["chosen"]]["holdout"]
    L += ["", f"**Chosen: {r['chosen']}, cutoff {c['cutoff']}.** Rule: {r['rule']}."
          + ("" if c["as01"] else " AS-01 (85%) not met at any cutoff for this mode: fallback cutoff."), ""]
    return "\n".join(L)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dev", default="data/development_tickets.json")
    ap.add_argument("--validation", default="data/validation_tickets.json")
    ap.add_argument("--config-path", default="config/retrieval.json")
    ap.add_argument("--write-config", action="store_true")
    a = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    from src.classify import build_classifier
    from src.retrieve import SentenceTransformerEmbedder, build_retriever

    emb = SentenceTransformerEmbedder()
    classifier = build_classifier(emb, use_llm_fallback=False)
    retriever = build_retriever(a.config_path, embedder=emb)
    load = lambda x: json.loads(Path(x).read_text(encoding="utf-8"))  # noqa: E731
    r = run(load(a.dev), load(a.validation), classifier, retriever)
    out = Path(f"evaluation/results/{r['run_date']}_query_experiment")
    out.mkdir(parents=True, exist_ok=True)
    (out / "query_experiment.json").write_text(json.dumps(r, indent=2, default=list), encoding="utf-8")
    md = to_markdown(r)
    (out / "query_experiment.md").write_text(md, encoding="utf-8")
    print(md)
    if a.write_config:
        p = Path(a.config_path)
        cfg = json.loads(p.read_text(encoding="utf-8"))
        h = r["modes"][r["chosen"]]["holdout"]
        cfg.update({"query_mode": r["chosen"], "cutoff": h["cutoff"],
                    "query_mode_rule": r["rule"], "query_mode_set_on": r["run_date"],
                    "query_mode_evidence": str(out / "query_experiment.md").replace("\\", "/")})
        p.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
        print(f"\nwrote {p}: query_mode {r['chosen']}, cutoff {h['cutoff']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
