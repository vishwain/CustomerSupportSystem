"""PR-03 v1.0 vs v2.0 on the dev hold-out (checklist 5.8; PRD FR-11 revised, FR-15, FR-16, FR-20).

Why the dev hold-out and not validation: v2.0 was written after reading validation answers, so validation
is no longer a fair test of it. The hold-out was never used to design either prompt.

Tickets: dev hold-out tickets that the real pipeline (classifier + retrieval + routing config) sends to
auto_respond. Each arm sees what it would see in production:
  v1  = PR-03 v1.0 with the retrieved passages only (as in the 15-ticket validation run)
  v2  = PR-03 v2.0 with the retrieved passages plus the rest of those articles (retrieval context)

Measures per arm: send-ready answers (parsed, can_answer, every citation resolves); precision = share of
send-ready answers whose ticket is labelled expected_route = auto_respond (FR-11 target 90%); unanswerable
tickets refused; answerable tickets lost; citation failures; answers that cite at least one numbered step
("actionable"); sentence length (FR-20).

Adoption rule, fixed before running: v2 replaces v1 in config/generation.json if its precision is at least
v1's, its actionable share is at least v1's, and it loses at most 2 more answerable tickets than v1.

    LLM_CACHE=1 python docs/generate_eval.py                 # all hold-out auto tickets (~2 calls each)
    python docs/generate_eval.py --limit 25                  # quicker look
    python docs/generate_eval.py --write-config              # also writes config/generation.json
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import tempfile
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.ingest import normalise  # noqa: E402
from src.route import Router, RoutingConfig  # noqa: E402
from src.splits import dev_holdout_split  # noqa: E402

ARMS = {"v1": ("build/generate_v1.txt", False), "v2": ("build/generate_v2.txt", True)}
STEP = re.compile(r"(^|\s)\d\.\s")
PRECISION_TARGET = 0.90


def eligible(dev_raw, classifier, retriever, router: Router) -> list[dict[str, Any]]:
    _, hold = dev_holdout_split(dev_raw)
    hs = set(hold)
    out = []
    for i, t in enumerate(dev_raw):
        if t["ticket_id"] not in hs:
            continue
        rec = normalise(t, i)
        if not rec.ok:
            continue
        cls = classifier.classify(rec, allow_llm=False)
        res = retriever.retrieve(rec.text)
        d = router.decide(rec.text, cls, res)
        if d.action == "auto_respond":
            out.append({"rec": rec, "cls": cls, "res": res, "labels": t["labels"]})
    return out


def run_arm(generator, items, with_context: bool) -> list[dict[str, Any]]:
    rows = []
    for it in items:
        passages = it["res"].for_generation if with_context else it["res"].passages
        g = generator.generate(it["rec"], it["cls"].intent, passages, "answer")
        by_id = {p.passage_id: p for p in passages}
        words = [len(s["text"].split()) for s in g.sentences]
        rows.append({
            "ticket_id": it["rec"].ticket_id, "expected": it["labels"]["expected_route"],
            "answerable": it["labels"]["answerable_from_docs"], "intent": it["cls"].intent,
            "passages_shown": len(passages), "send_ready": g.usable, "can_answer": g.can_answer,
            "error": g.error, "citations_ok": g.citations_ok, "unresolved": g.unresolved, "cited": g.cited,
            "actionable": g.usable and any(STEP.search(by_id[c].text) for c in g.cited if c in by_id),
            "sentences": len(g.sentences), "avg_words": round(sum(words) / len(words), 1) if words else 0,
            "max_words": max(words) if words else 0, "requests": g.requests, "retries": g.retries,
            "wait_s": round(g.rate_limit_wait_ms / 1000, 1), "answer": " ".join(s["text"] for s in g.sentences),
            "unsure_about": g.unsure_about, "subject": it["rec"].subject, "body": it["rec"].body,
        })
    return rows


def summarise(rows: list[dict[str, Any]]) -> dict[str, Any]:
    sr = [r for r in rows if r["send_ready"]]
    exp_auto = [r for r in rows if r["expected"] == "auto_respond"]
    exp_esc = [r for r in rows if r["expected"] == "escalate"]
    words = [r["avg_words"] for r in sr]
    return {
        "tickets": len(rows), "send_ready": len(sr),
        "precision": round(sum(r["expected"] == "auto_respond" for r in sr) / len(sr), 4) if sr else None,
        "expected_escalate": len(exp_esc), "escalate_refused": sum(not r["send_ready"] for r in exp_esc),
        "expected_auto": len(exp_auto), "answerable_lost": sum(not r["send_ready"] for r in exp_auto),
        "cannot_answer": sum(r["error"] == "none" and not r["can_answer"] for r in rows),
        "citation_failures": sum(r["error"] == "citation" for r in rows),
        "other_errors": dict(Counter(r["error"] for r in rows if r["error"] not in ("none", "citation"))),
        "actionable_share": round(sum(r["actionable"] for r in sr) / len(sr), 4) if sr else None,
        "avg_sentences": round(sum(r["sentences"] for r in sr) / len(sr), 2) if sr else 0,
        "avg_words_per_sentence": round(sum(words) / len(words), 1) if words else 0,
        "max_sentence_words": max((r["max_words"] for r in sr), default=0),
        "requests": sum(r["requests"] for r in rows), "retries": sum(r["retries"] for r in rows),
        "rate_limit_wait_s": round(sum(r["wait_s"] for r in rows), 1),
    }


def decide(s1: dict[str, Any], s2: dict[str, Any]) -> tuple[bool, str]:
    p1, p2 = s1["precision"] or 0, s2["precision"] or 0
    a1, a2 = s1["actionable_share"] or 0, s2["actionable_share"] or 0
    ok = p2 >= p1 and a2 >= a1 and s2["answerable_lost"] <= s1["answerable_lost"] + 2
    why = (f"precision {p1:.1%} -> {p2:.1%}, actionable {a1:.1%} -> {a2:.1%}, answerable lost "
           f"{s1['answerable_lost']} -> {s2['answerable_lost']}")
    return ok, ("v2 adopted: " if ok else "v1 kept: ") + why


def to_markdown(r: dict[str, Any]) -> str:
    def pct(x):
        return "n/a" if x is None else f"{x:.1%}"

    s1, s2 = r["summary"]["v1"], r["summary"]["v2"]
    L = [f"# Generate: PR-03 v1.0 vs v2.0 ({r['run_date']})", "",
         f"Dev hold-out tickets the pipeline routes to auto_respond: {s1['tickets']}. Model `{r['model']}`. "
         "Generated by `docs/generate_eval.py`. v1 sees retrieved passages only; v2 also sees the rest of "
         "those articles.", "",
         "| Measure | v1.0 | v2.0 |", "| --- | --- | --- |"]
    for k, lab in (("send_ready", "Send-ready answers"), ("precision", "Precision (expected auto_respond)"),
                   ("escalate_refused", f"Expected-escalate tickets refused (of {s1['expected_escalate']})"),
                   ("answerable_lost", f"Expected-auto tickets lost (of {s1['expected_auto']})"),
                   ("cannot_answer", "can_answer = false"), ("citation_failures", "Citation failures"),
                   ("actionable_share", "Answers citing a numbered step"), ("avg_sentences", "Sentences per answer"),
                   ("avg_words_per_sentence", "Words per sentence (FR-20: 20)"),
                   ("max_sentence_words", "Longest sentence (limit 35)"), ("requests", "Provider requests"),
                   ("retries", "Retries"), ("rate_limit_wait_s", "Rate-limit wait (s)")):
        v1, v2 = s1[k], s2[k]
        if k in ("precision", "actionable_share"):
            v1, v2 = pct(v1), pct(v2)
        L.append(f"| {lab} | {v1} | {v2} |")
    L += ["", f"Other errors: v1 {s1['other_errors'] or 'none'}, v2 {s2['other_errors'] or 'none'}.", "",
          f"**Decision (rule fixed before running): {r['decision']}.**", "",
          f"FR-11 end-to-end target {PRECISION_TARGET:.0%}: v2 {pct(s2['precision'])}. About 8% of these tickets "
          "carry a route label that conflicts with an identical text elsewhere in the data, which caps any "
          "system's measured precision.", "",
          "Per-ticket answers for reading: `answers.csv` in this folder.", ""]
    return "\n".join(L)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dev", default="data/development_tickets.json")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--out-dir", default=None)
    ap.add_argument("--write-config", action="store_true")
    a = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    from src.classify import Classifier, LocalClassifier
    from src.generate import Generator
    from src.llm import client_from_env
    from src.retrieve import SentenceTransformerEmbedder, build_retriever

    emb = SentenceTransformerEmbedder()
    clf = Classifier(LocalClassifier(emb).load_or_train())
    ret = build_retriever(embedder=emb)
    dev = json.loads(Path(a.dev).read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory() as tmp:
        rt = Path(tmp) / "runtime.json"
        rt.write_text('{"automation_paused": false}', encoding="utf-8")
        items = eligible(dev, clf, ret, Router(RoutingConfig.load(), runtime_path=rt))
    if a.limit:
        items = items[: a.limit]
    client = client_from_env()
    print(f"{len(items)} hold-out tickets routed to auto_respond; ~{2 * len(items)} provider calls")
    rows, summary = {}, {}
    for arm, (path, ctx) in ARMS.items():
        rows[arm] = run_arm(Generator(client, prompt_path=path), items, ctx)
        summary[arm] = summarise(rows[arm])
        print(f"{arm}: {summary[arm]}")
    ok, why = decide(summary["v1"], summary["v2"])
    r = {"run_date": date.today().isoformat(), "model": client.model, "summary": summary, "decision": why,
         "v2_adopted": ok}
    out = Path(a.out_dir or f"evaluation/results/{r['run_date']}_generate_eval")
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "answers.csv", "w", newline="", encoding="utf-8") as f:
        fields = ["arm"] + list(rows["v1"][0].keys()) if rows["v1"] else ["arm"]
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for arm in ARMS:
            for row in rows[arm]:
                w.writerow({"arm": arm, **{k: (json.dumps(v) if isinstance(v, list) else v) for k, v in row.items()}})
    (out / "generate_eval.json").write_text(json.dumps(r, indent=2), encoding="utf-8")
    md = to_markdown(r)
    (out / "generate_eval.md").write_text(md, encoding="utf-8")
    print(md)
    if a.write_config:
        Path("config/generation.json").write_text(json.dumps({
            "prompt": ARMS["v2" if ok else "v1"][0], "set_on": r["run_date"], "why": why,
            "evidence": str(out / "generate_eval.md").replace("\\", "/")}, indent=2) + "\n", encoding="utf-8")
        print(f"\nwrote config/generation.json ({'v2' if ok else 'v1'})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
