"""Routing threshold study (checklist 5.6, A5; PRD FR-11, NFR-09). 5.7 extends it with calibration.

On the dev HOLD-OUT (NFR-03 split; the local classifier never trained on it):
  - run the real Router with the threshold at 0 to see, per ticket, whether a hard rule fired, whether a
    passage passed the retrieval cutoff, and the intent confidence;
  - sweep the threshold 0.00..1.00. A ticket is answered automatically at threshold t when no rule fired,
    a passage passed, and confidence >= t;
  - rule (FR-11): the LOWEST t where >= 90% of automatic answers have expected_route = auto_respond AND
    zero automatic answers are must_not_auto_respond. Lowest = most automation that still meets both.
    If no t meets both, the threshold stays above 1.0 (nothing automatic) and the report says so.
Then the chosen t is checked on validation (nothing chosen there).

Run from the repo root after docs/retrieval_experiment.py:
    python docs/routing_threshold.py                  # writes docs/routing_threshold.md/.json
    python docs/routing_threshold.py --write-config   # also writes config/routing.json
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.ingest import normalise  # noqa: E402
from src.route import NEVER, Router, RoutingConfig  # noqa: E402
from src.splits import dev_holdout_split, text_key  # noqa: E402

PRECISION_TARGET = 0.90
SWEEP = [round(i / 100, 2) for i in range(0, 101)]


def _load(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def score_tickets(raw: list[dict[str, Any]], classifier, retriever, router: Router) -> list[dict[str, Any]]:
    out = []
    for i, t in enumerate(raw):
        rec = normalise(t, i)
        lab = t.get("labels", {})
        if not rec.ok:
            continue
        cls = classifier.classify(rec, allow_llm=False)
        res = retriever.retrieve(rec.text) if retriever else None
        d = router.decide(rec.text, cls, res)
        out.append({
            "ticket_id": rec.ticket_id, "key": text_key(t),
            "intent_true": lab.get("intent"), "intent_pred": cls.intent, "conf": cls.intent_confidence,
            "correct": cls.intent == lab.get("intent"),
            "rule": d.rule_fired if d.rule_fired not in ("none", "below_threshold", "no_retrieval_hit") else None,
            "passage": bool(res and res.passages),
            "expected": lab.get("expected_route"), "must_not": bool(lab.get("must_not_auto_respond")),
        })
    return out


def at_threshold(rows: list[dict[str, Any]], t: float) -> dict[str, Any]:
    auto = [r for r in rows if r["rule"] is None and r["passage"] and r["conf"] >= t]
    draft = [r for r in rows if r["rule"] is None and r["passage"] and r["conf"] < t]
    exp_auto = [r for r in rows if r["expected"] == "auto_respond"]
    good = sum(r["expected"] == "auto_respond" for r in auto)
    return {
        "threshold": t, "auto": len(auto), "draft": len(draft), "escalate": len(rows) - len(auto) - len(draft),
        "auto_rate": round(len(auto) / len(rows), 4) if rows else 0.0,
        "precision": round(good / len(auto), 4) if auto else None,
        "must_not_auto": sum(r["must_not"] for r in auto),
        "expected_auto_answered": round(good / len(exp_auto), 4) if exp_auto else 0.0,
        "auto_wrong_intent": sum(not r["correct"] for r in auto),
    }


def run_study(classifier, retriever, dev_raw, val_raw, alt_floor: float = 0.15) -> dict[str, Any]:
    _, hold_ids = dev_holdout_split(dev_raw)
    hold_set = set(hold_ids)
    hold_raw = [t for t in dev_raw if t["ticket_id"] in hold_set]

    with tempfile.TemporaryDirectory() as tmp:
        rt = Path(tmp) / "runtime.json"
        rt.write_text('{"automation_paused": false}', encoding="utf-8")  # the study ignores the live kill switch
        router = Router(RoutingConfig(threshold=0.0, must_escalate_alt_floor=alt_floor), runtime_path=rt)
        hold = score_tickets(hold_raw, classifier, retriever, router)
        val = score_tickets(val_raw, classifier, retriever, router)

    sweep = [at_threshold(hold, t) for t in SWEEP]
    ok = [s for s in sweep if s["auto"] > 0 and s["precision"] is not None
          and s["precision"] >= PRECISION_TARGET and s["must_not_auto"] == 0]
    if ok:
        pick = min(ok, key=lambda s: s["threshold"])
        threshold, met = pick["threshold"], True
        rule = (f"lowest threshold where >= {PRECISION_TARGET:.0%} of automatic answers on the dev hold-out "
                "have expected_route = auto_respond and none is must_not_auto_respond (FR-11, NFR-09)")
    else:
        pick, threshold, met = at_threshold(hold, NEVER), NEVER, False
        rule = "NO threshold met FR-11 on the dev hold-out: nothing is answered automatically; record in the PRD revision log"

    must_not = [r for r in hold + val if r["must_not"]]
    rules = Counter(r["rule"] or ("no passage" if not r["passage"] else "eligible") for r in hold)
    alt_fired = [r for r in hold if (r["rule"] or "").startswith("must_escalate_alternative")]
    conf_ok = sorted(r["conf"] for r in hold if r["correct"])
    conf_bad = sorted(r["conf"] for r in hold if not r["correct"])
    dev_keys = {text_key(t) for t in dev_raw}
    return {
        "run_date": date.today().isoformat(),
        "classifier": f"{classifier.local.name if hasattr(classifier, 'local') else classifier.name}",
        "holdout_n": len(hold), "validation_n": len(val),
        "intent_accuracy_holdout": round(sum(r["correct"] for r in hold) / len(hold), 4) if hold else 0.0,
        "intent_accuracy_validation": round(sum(r["correct"] for r in val) / len(val), 4) if val else 0.0,
        "intent_accuracy_validation_unseen": (lambda u: round(sum(r["correct"] for r in u) / len(u), 4)
                                              if u else 0.0)([r for r in val if r["key"] not in dev_keys]),
        "confidence_correct": {"n": len(conf_ok), "median": conf_ok[len(conf_ok) // 2] if conf_ok else None},
        "confidence_wrong": {"n": len(conf_bad), "median": conf_bad[len(conf_bad) // 2] if conf_bad else None,
                             "max": conf_bad[-1] if conf_bad else None},
        "route_outcomes_holdout": dict(rules),
        "alt_floor": alt_floor,
        "alt_guard_fired_holdout": {"n": len(alt_fired), "must_not": sum(r["must_not"] for r in alt_fired),
                                    "expected_escalate": sum(r["expected"] == "escalate" for r in alt_fired)},
        "must_not_tickets_by_rule": dict(Counter(r["rule"] or "NO RULE" for r in must_not)),
        "sweep_holdout": sweep,
        "threshold": threshold, "threshold_rule": rule, "fr11_met": met, "at_threshold_holdout": pick,
        "at_threshold_validation": at_threshold(val, threshold),
    }


def to_markdown(r: dict[str, Any]) -> str:
    def pct(x):
        return "n/a" if x is None else f"{x:.1%}"

    L = [f"# Routing threshold study ({r['run_date']})", "",
         f"Classifier `{r['classifier']}` (trained on dev train split only). Generated by "
         "`docs/routing_threshold.py`; rerun to reproduce.", "",
         "## Classifier on held-out data", "",
         f"Intent accuracy: dev hold-out {pct(r['intent_accuracy_holdout'])} (n={r['holdout_n']}), validation "
         f"{pct(r['intent_accuracy_validation'])} (n={r['validation_n']}), validation texts not in dev "
         f"{pct(r['intent_accuracy_validation_unseen'])}.", "",
         f"Confidence when right: n={r['confidence_correct']['n']}, median {r['confidence_correct']['median']}. "
         f"When wrong: n={r['confidence_wrong']['n']}, median {r['confidence_wrong']['median']}, "
         f"max {r['confidence_wrong']['max']}. (Calibration bands: 5.7.)", "",
         "## What Route did on the dev hold-out before any threshold", "",
         "| Outcome | Tickets |", "| --- | --- |"]
    L += [f"| {k} | {v} |" for k, v in sorted(r["route_outcomes_holdout"].items(), key=lambda kv: -kv[1])]
    g = r["alt_guard_fired_holdout"]
    L += ["", f"Alternative guard (floor {r['alt_floor']}): fired on {g['n']} hold-out tickets, "
          f"{g['must_not']} must_not_auto_respond, {g['expected_escalate']} expected escalate.", "",
          "must_not_auto_respond tickets (hold-out + validation) by the rule that stopped them:", "",
          "| Rule | Tickets |", "| --- | --- |"]
    L += [f"| {k} | {v} |" for k, v in sorted(r["must_not_tickets_by_rule"].items())]
    L += ["", "## Threshold sweep (dev hold-out)", "",
          "| Threshold | Auto | Draft | Escalate | Auto rate | Precision (expected auto) | must_not auto | "
          "Expected-auto answered | Auto with wrong intent |",
          "| --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for s in r["sweep_holdout"]:
        if round(s["threshold"] * 100) % 5 == 0 or s["threshold"] == r["threshold"]:
            mark = " **<- chosen**" if s["threshold"] == r["threshold"] else ""
            L.append(f"| {s['threshold']:.2f}{mark} | {s['auto']} | {s['draft']} | {s['escalate']} | "
                     f"{pct(s['auto_rate'])} | {pct(s['precision'])} | {s['must_not_auto']} | "
                     f"{pct(s['expected_auto_answered'])} | {s['auto_wrong_intent']} |")
    h, v = r["at_threshold_holdout"], r["at_threshold_validation"]
    L += ["", f"**Threshold {r['threshold']}.** Rule: {r['threshold_rule']}. FR-11 met: {r['fr11_met']}.", "",
          "| Set | Auto | Draft | Escalate | Precision | must_not auto | Expected-auto answered |",
          "| --- | --- | --- | --- | --- | --- | --- |",
          f"| Dev hold-out | {h['auto']} | {h['draft']} | {h['escalate']} | {pct(h['precision'])} | "
          f"{h['must_not_auto']} | {pct(h['expected_auto_answered'])} |",
          f"| Validation (check only) | {v['auto']} | {v['draft']} | {v['escalate']} | {pct(v['precision'])} | "
          f"{v['must_not_auto']} | {pct(v['expected_auto_answered'])} |", ""]
    return "\n".join(L)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dev", default="data/development_tickets.json")
    ap.add_argument("--validation", default="data/validation_tickets.json")
    ap.add_argument("--retrieval-config", default="config/retrieval.json")
    ap.add_argument("--alt-floor", type=float, default=0.15)
    ap.add_argument("--out", default="docs/routing_threshold")
    ap.add_argument("--write-config", action="store_true")
    ap.add_argument("--config-path", default="config/routing.json")
    a = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    from src.classify import Classifier, LocalClassifier
    from src.retrieve import SentenceTransformerEmbedder, build_retriever

    emb = SentenceTransformerEmbedder()
    clf = Classifier(LocalClassifier(emb).load_or_train())
    ret = build_retriever(a.retrieval_config, embedder=emb)
    r = run_study(clf, ret, _load(a.dev), _load(a.validation), a.alt_floor)
    r["classifier"] = f"{clf.local.name} {clf.local.version}"

    out = Path(a.out)
    out.with_suffix(".json").write_text(json.dumps(r, indent=2), encoding="utf-8")
    md = to_markdown(r)
    out.with_suffix(".md").write_text(md, encoding="utf-8")
    print(md)
    if a.write_config:
        cfg = {"threshold": r["threshold"], "must_escalate_alt_floor": a.alt_floor, "set_on": r["run_date"],
               "rule": r["threshold_rule"], "classifier_version": clf.local.version,
               "evidence": {"report": str(out.with_suffix(".md")).replace("\\", "/"),
                            "holdout": r["at_threshold_holdout"], "validation": r["at_threshold_validation"]}}
        p = Path(a.config_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        current = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
        if current.get("set_by") == "calibration":  # 5.7 owns the threshold: keep it, attach this study
            current["fr11_route_study"] = {k: cfg[k] for k in ("threshold", "set_on", "rule", "evidence")}
            p.write_text(json.dumps(current, indent=2) + "\n", encoding="utf-8")
            print(f"\n{p}: threshold kept at {current['threshold']} (set by calibration); study attached")
        else:
            p.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
            print(f"\nwrote {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
