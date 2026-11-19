"""Retrieval experiment (checklist 5.2, A4; PRD FR-08, FR-09, AS-01, AS-08).

Answers three questions with dev data, then checks the answer on validation:
  1. Which chunking config finds the right article most often in the top 3?
     Measured on the dev TRAIN split, every answerable ticket (not a 20-30 sample).
     Rule fixed before running: highest top-3 hit rate; within 1 point, prefer `section`
     (PRD FR-08 design, citation ids are doc_id#section).
  2. What relevance cutoff? Scores of answerable vs not-answerable tickets, and of the right
     article vs the best wrong one, on the dev HOLD-OUT. Rule (FR-09): the highest cutoff that
     keeps the top-3 hit rate on answerable hold-out tickets at 85% or more (AS-01).
  3. Does it hold on validation (all 80, unseen texts apart), and for non-fluent wording (AS-08)?

language_fluency is read here, in docs/, for the AS-08 check only. src/ never reads it (FR-19).

Run from the repo root (first run downloads all-MiniLM-L6-v2 if it is not cached):
    python docs/retrieval_experiment.py                  # writes docs/retrieval_experiment.md/.json
    python docs/retrieval_experiment.py --write-config   # also writes config/retrieval.json
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import tempfile
from datetime import date
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.ingest import normalise  # noqa: E402
from src.retrieve import CONFIGS, Retriever  # noqa: E402
from src.splits import dev_holdout_split, text_key  # noqa: E402

TARGET_HIT = 0.85  # AS-01
TIE_POINTS = 0.01
PREFERRED = "section"
SWEEP = [round(i / 100, 2) for i in range(0, 91)]


def _load(path: str | Path) -> list[dict[str, Any]]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _prep(raw: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Ingest text plus the labels and fluency needed for scoring (labels never reach src/ components)."""
    out = []
    for i, t in enumerate(raw):
        r = normalise(t, i)
        lab = t.get("labels", {})
        out.append({
            "ticket_id": r.ticket_id, "text": r.text, "ok": r.ok,
            "answerable": bool(lab.get("answerable_from_docs")),
            "expected": set(lab.get("expected_doc_ids") or []),
            "intent": lab.get("intent"), "fluency": t.get("language_fluency", "unknown"),
            "key": text_key(t),
        })
    return out


def _rank_metrics(cands, expected: set[str]) -> dict[str, float]:
    """Doc-level metrics over ranked passages: hit@1/3/5 and reciprocal rank of the first right doc."""
    docs: list[str] = []
    for p in cands:
        if p.doc_id not in docs:
            docs.append(p.doc_id)
    first3 = {p.doc_id for p in cands[:3]}
    rank = next((i + 1 for i, d in enumerate(docs) if d in expected), None)
    return {
        "hit1": float(bool(cands) and cands[0].doc_id in expected),
        "hit3": float(bool(first3 & expected)),
        "hit5": float(bool({p.doc_id for p in cands[:5]} & expected)),
        "rr": 1.0 / rank if rank else 0.0,
    }


def _mean(xs) -> float:
    xs = list(xs)
    return round(sum(xs) / len(xs), 4) if xs else 0.0


def _dist(xs: list[float]) -> dict[str, float]:
    if not xs:
        return {"n": 0}
    s = sorted(xs)

    def q(p):
        return round(s[min(len(s) - 1, int(round(p * (len(s) - 1))))], 3)

    return {"n": len(s), "min": q(0), "p10": q(0.10), "p25": q(0.25), "median": q(0.5),
            "p75": q(0.75), "p90": q(0.90), "max": q(1.0), "mean": round(statistics.mean(s), 3)}


def _hit_at_cutoff(scored: list[dict[str, Any]], c: float) -> dict[str, float]:
    """scored rows hold top-5 (doc_id, score) for each ticket."""
    ans = [r for r in scored if r["answerable"]]
    una = [r for r in scored if not r["answerable"]]

    def kept(r):
        return [d for d, s in r["top5"] if s >= c]

    return {
        "cutoff": c,
        "hit3_answerable": _mean(float(bool(set(kept(r)[:3]) & r["expected"])) for r in ans),
        "answerable_empty": _mean(float(not kept(r)) for r in ans),
        "unanswerable_empty": _mean(float(not kept(r)) for r in una),
    }


def run_experiment(embedder, dev_raw, val_raw, docs_path="data/documentation.json",
                   chroma_path: str | None = None, target: float = TARGET_HIT) -> dict[str, Any]:
    dev, val = _prep(dev_raw), _prep(val_raw)
    train_ids, hold_ids = dev_holdout_split(dev_raw)
    train_ids, hold_ids = set(train_ids), set(hold_ids)
    train = [t for t in dev if t["ticket_id"] in train_ids and t["ok"]]
    hold = [t for t in dev if t["ticket_id"] in hold_ids and t["ok"]]
    dev_keys = {t["key"] for t in dev}
    chroma_path = chroma_path or tempfile.mkdtemp(prefix="chroma_exp_")

    # 1. Chunking comparison on train answerable tickets (cutoff 0 = pure ranking quality).
    retrievers, comparison = {}, []
    for name, cfg in CONFIGS.items():
        r = Retriever(embedder, cfg, cutoff=0.0, top_k=5, docs_path=docs_path, chroma_path=chroma_path)
        retrievers[name] = r
        rows = [(t, _rank_metrics(r.retrieve(t["text"]).candidates, t["expected"]))
                for t in train if t["answerable"]]
        by_fl = {fl: _mean(m["hit3"] for t, m in rows if t["fluency"] == fl)
                 for fl in sorted({t["fluency"] for t, _ in rows})}
        comparison.append({
            "config": name, "describe": cfg.describe(), "passages": len(r.passages),
            "avg_passage_chars": round(statistics.mean(len(p.text) for p in r.passages)),
            "n_tickets": len(rows),
            "hit1": _mean(m["hit1"] for _, m in rows), "hit3": _mean(m["hit3"] for _, m in rows),
            "hit5": _mean(m["hit5"] for _, m in rows), "mrr": _mean(m["rr"] for _, m in rows),
            "hit3_by_fluency": by_fl,
        })

    best = max(comparison, key=lambda c: (c["hit3"], c["mrr"]))
    pref = next(c for c in comparison if c["config"] == PREFERRED)
    chosen = pref if best["hit3"] - pref["hit3"] <= TIE_POINTS else best
    why = (f"{chosen['config']} has the highest top-3 hit rate on train ({chosen['hit3']:.1%})."
           if chosen is best else
           f"{best['config']} leads on train top-3 hit rate ({best['hit3']:.1%}) but {PREFERRED} is within "
           f"{TIE_POINTS:.0%} ({pref['hit3']:.1%}); the pre-set rule prefers {PREFERRED} (doc_id#section citations).")
    ret = retrievers[chosen["config"]]

    # 2. Scores on the hold-out: answerable vs not, right article vs best wrong article.
    def score_rows(tickets):
        out = []
        for t in tickets:
            allp = ret.score_all(t["text"])
            right = [p.score for p in allp if p.doc_id in t["expected"]]
            wrong = [p.score for p in allp if p.doc_id not in t["expected"]]
            out.append({**t, "top1": allp[0].score if allp else 0.0,
                        "best_right": max(right) if right else None,
                        "best_wrong": max(wrong) if wrong else None,
                        "top5": [(p.doc_id, p.score) for p in allp[:5]]})
        return out

    hold_scored = score_rows(hold)
    ans = [r for r in hold_scored if r["answerable"]]
    una = [r for r in hold_scored if not r["answerable"]]
    distributions = {
        "top1_answerable": _dist([r["top1"] for r in ans]),
        "top1_not_answerable": _dist([r["top1"] for r in una]),
        "best_right_article": _dist([r["best_right"] for r in ans if r["best_right"] is not None]),
        "best_wrong_article_on_answerable": _dist([r["best_wrong"] for r in ans if r["best_wrong"] is not None]),
    }
    intents_una = {}
    for r in una:
        intents_una.setdefault(r["intent"], []).append(r["top1"])
    una_by_intent = {k: {"n": len(v), "median_top1": round(statistics.median(v), 3)}
                     for k, v in sorted(intents_una.items(), key=lambda kv: -statistics.median(kv[1]))}

    # 3. Cutoff sweep and rule.
    sweep = [_hit_at_cutoff(hold_scored, c) for c in SWEEP]
    base = sweep[0]["hit3_answerable"]
    ok = [s for s in sweep if s["hit3_answerable"] >= target]
    if ok:
        pick, as01 = max(ok, key=lambda s: s["cutoff"]), True
        rule = f"highest cutoff keeping hold-out top-3 hit rate on answerable tickets >= {target:.0%} (FR-09, AS-01)"
    else:  # AS-01 fails even with no cutoff: do not trade away more hits, flag it.
        keep = [s for s in sweep if s["hit3_answerable"] >= base - 0.01]
        pick, as01 = max(keep, key=lambda s: s["cutoff"]), False
        rule = (f"AS-01 NOT MET: hit rate is {base:.1%} even with no cutoff. Fallback: highest cutoff losing "
                f"at most 1 point of hit rate; record in the PRD revision log")
    cutoff = pick["cutoff"]

    # 4. Validation check at the chosen config and cutoff (never used to choose anything).
    val_ok = [t for t in val if t["ok"]]
    val_scored = score_rows(val_ok)
    val_unseen = [r for r in val_scored if r["key"] not in dev_keys]
    validation = {
        "all": _hit_at_cutoff(val_scored, cutoff) | {"n": len(val_scored)},
        "unseen_texts": _hit_at_cutoff(val_unseen, cutoff) | {"n": len(val_unseen)},
    }
    pooled = hold_scored + val_scored
    fluency = {fl: _hit_at_cutoff([r for r in pooled if r["fluency"] == fl], cutoff)
               | {"n_answerable": sum(1 for r in pooled if r["fluency"] == fl and r["answerable"])}
               for fl in sorted({r["fluency"] for r in pooled})}
    hits = [v["hit3_answerable"] for v in fluency.values()]
    as08_gap = round(max(hits) - min(hits), 4) if len(hits) > 1 else 0.0

    return {
        "run_date": date.today().isoformat(),
        "embedding_model": embedder.name,
        "split": {"train_tickets": len(train), "holdout_tickets": len(hold),
                  "holdout_answerable": len(ans), "holdout_not_answerable": len(una)},
        "comparison": comparison,
        "chosen_config": chosen["config"], "chosen_why": why,
        "distributions_holdout": distributions,
        "not_answerable_by_intent": una_by_intent,
        "sweep_holdout": sweep,
        "cutoff": cutoff, "cutoff_rule": rule, "as01_met": as01, "at_cutoff_holdout": pick,
        "validation": validation,
        "fluency_pooled_holdout_validation": fluency, "as08_gap": as08_gap, "as08_met": as08_gap <= 0.05,
    }


def to_markdown(r: dict[str, Any]) -> str:
    pct = lambda x: f"{x:.1%}"  # noqa: E731
    L = [f"# Retrieval experiment ({r['run_date']})", "",
         f"Embedding model `{r['embedding_model']}`, Chroma cosine similarity. Generated by "
         "`docs/retrieval_experiment.py`; rerun to reproduce.", "",
         f"Dev split (NFR-03, seed 42, by distinct text): {r['split']['train_tickets']} train tickets, "
         f"{r['split']['holdout_tickets']} hold-out ({r['split']['holdout_answerable']} answerable, "
         f"{r['split']['holdout_not_answerable']} not).", "",
         "## 1. Chunking configs (dev train, answerable tickets, no cutoff)", "",
         "Hit@k: a right article (expected_doc_ids) is among the articles of the first k passages.", "",
         "| Config | Passages | Avg chars | n | Hit@1 | Hit@3 | Hit@5 | MRR | Hit@3 fluent / non-fluent |",
         "| --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for c in r["comparison"]:
        fl = " / ".join(pct(v) for _, v in sorted(c["hit3_by_fluency"].items()))
        L.append(f"| `{c['config']}` ({c['describe']}) | {c['passages']} | {c['avg_passage_chars']} | {c['n_tickets']} | "
                 f"{pct(c['hit1'])} | **{pct(c['hit3'])}** | {pct(c['hit5'])} | {c['mrr']:.3f} | {fl} |")
    L += ["", f"**Chosen: `{r['chosen_config']}`.** {r['chosen_why']}", "",
          "## 2. Scores: relevant vs irrelevant (dev hold-out, chosen config)", "",
          "| Score set | n | min | p10 | p25 | median | p75 | p90 | max |", "| --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    labels = {"top1_answerable": "Top-1 score, answerable tickets",
              "top1_not_answerable": "Top-1 score, not-answerable tickets",
              "best_right_article": "Best passage of the right article",
              "best_wrong_article_on_answerable": "Best passage of a wrong article (answerable tickets)"}
    for k, lab in labels.items():
        d = r["distributions_holdout"][k]
        if d.get("n"):
            L.append(f"| {lab} | {d['n']} | {d['min']} | {d['p10']} | {d['p25']} | {d['median']} | "
                     f"{d['p75']} | {d['p90']} | {d['max']} |")
    L += ["", "Not-answerable hold-out tickets by intent (highest median top-1 first; these are the ones a cutoff cannot stop):", "",
          "| Intent | n | Median top-1 |", "| --- | --- | --- |"]
    L += [f"| {k} | {v['n']} | {v['median_top1']} |" for k, v in r["not_answerable_by_intent"].items()]
    L += ["", "## 3. Cutoff sweep (dev hold-out)", "",
          "| Cutoff | Hit@3 answerable | Answerable with no passage | Not-answerable with no passage |",
          "| --- | --- | --- | --- |"]
    for s in r["sweep_holdout"]:
        if round(s["cutoff"] * 100) % 5 == 0 or s["cutoff"] == r["cutoff"]:
            mark = " **<- chosen**" if s["cutoff"] == r["cutoff"] else ""
            L.append(f"| {s['cutoff']:.2f}{mark} | {pct(s['hit3_answerable'])} | {pct(s['answerable_empty'])} | "
                     f"{pct(s['unanswerable_empty'])} |")
    p = r["at_cutoff_holdout"]
    L += ["", f"**Cutoff {r['cutoff']:.2f}.** Rule: {r['cutoff_rule']}. At this cutoff on the hold-out: hit@3 "
          f"{pct(p['hit3_answerable'])}; {pct(p['unanswerable_empty'])} of not-answerable tickets get no passage; "
          f"{pct(p['answerable_empty'])} of answerable tickets lose all passages. AS-01 met: {r['as01_met']}.", "",
          "## 4. Check on validation and by fluency (nothing chosen here)", "",
          "| Set | n | Hit@3 answerable | Answerable with no passage | Not-answerable with no passage |",
          "| --- | --- | --- | --- | --- |"]
    for k, lab in (("all", "Validation, all"), ("unseen_texts", "Validation, texts not in dev")):
        v = r["validation"][k]
        L.append(f"| {lab} | {v['n']} | {pct(v['hit3_answerable'])} | {pct(v['answerable_empty'])} | "
                 f"{pct(v['unanswerable_empty'])} |")
    L += ["", "Pooled dev hold-out + validation (NFR-06), at the chosen cutoff:", "",
          "| Fluency | Answerable n | Hit@3 |", "| --- | --- | --- |"]
    L += [f"| {fl} | {v['n_answerable']} | {pct(v['hit3_answerable'])} |"
          for fl, v in r["fluency_pooled_holdout_validation"].items()]
    L += ["", f"AS-08 gap {pct(r['as08_gap'])} (limit 5 points). Met: {r['as08_met']}.", ""]
    return "\n".join(L)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dev", default="data/development_tickets.json")
    ap.add_argument("--validation", default="data/validation_tickets.json")
    ap.add_argument("--docs", default="data/documentation.json")
    ap.add_argument("--out", default="docs/retrieval_experiment", help="path stem for .md and .json")
    ap.add_argument("--write-config", action="store_true", help="write config/retrieval.json")
    ap.add_argument("--config-path", default="config/retrieval.json")
    a = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    from src.retrieve import SentenceTransformerEmbedder
    emb = SentenceTransformerEmbedder()
    with tempfile.TemporaryDirectory(prefix="chroma_exp_", ignore_cleanup_errors=True) as tmp:
        r = run_experiment(emb, _load(a.dev), _load(a.validation), a.docs, chroma_path=tmp)

    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.with_suffix(".json").write_text(json.dumps(r, indent=2, default=list), encoding="utf-8")
    md = to_markdown(r)
    out.with_suffix(".md").write_text(md, encoding="utf-8")
    print(md)

    if a.write_config:
        cfg = {
            "chunking": r["chosen_config"], "cutoff": r["cutoff"], "top_k": 5,
            "embedding_model": r["embedding_model"], "set_on": r["run_date"], "rule": r["cutoff_rule"],
            "evidence": {"report": str(out.with_suffix(".md")).replace("\\", "/"),
                         "holdout_hit3": r["at_cutoff_holdout"]["hit3_answerable"],
                         "holdout_unanswerable_empty": r["at_cutoff_holdout"]["unanswerable_empty"],
                         "validation_hit3": r["validation"]["all"]["hit3_answerable"]},
        }
        p = Path(a.config_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
        print(f"\nwrote {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
