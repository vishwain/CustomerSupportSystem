"""Confidence calibration and the routing threshold (checklist 5.7; PRD NFR-10, FR-11, AS-05).

1. Data. Out-of-fold predictions for ALL 500 dev tickets: grouped 5-fold by distinct text, and C is
   re-tuned inside each outer fold, so no ticket's prediction comes from a model that was built or tuned
   on it (nested CV). The 85-ticket dev hold-out alone is below the 100-ticket minimum.
2. Bins. 0-0.5, 0.5-0.6, ..., 0.8-0.9, then the crowded top split as 0.9-0.95, 0.95-0.99, 0.99-1.0.
   Any bin under 10 tickets is merged into its smaller neighbour until none is. n is shown per bin.
3. Compare. Per bin: mean stated confidence, observed accuracy (with 95% Wilson interval), gap in points.
   NFR-10: |gap| <= 5 points.
4. Fix (rule fixed before running). If any bin fails, fit one temperature T on the dev out-of-fold
   predictions (minimum log-loss). Adopt T only if, on the dev hold-out with the deployed model, it
   lowers the expected calibration error and lowers the number of failing dev bins. Otherwise keep the
   raw confidence and report the failing bins as a known limit.
5. Threshold (rule fixed before running): the LOWEST t in 0.50..0.99 where
     a) intent accuracy of all tickets with confidence >= t is >= 95% (leaves room inside FR-11's 90%
        end-to-end target for answerability and Generate errors),
     b) no OVERCONFIDENT failing bin (gap > +5) lies at or above t (an underconfident bin is on the safe
        side; it is reported, not used to block),
     c) no must_not_auto_respond ticket would be answered automatically at t (NFR-09).
   If none: 1.01, nothing automatic.
6. Check. Deployed model on validation (never used above).

Run from the repo root:
    python docs/calibration.py                  # writes evaluation/results/<date>_calibration/
    python docs/calibration.py --write-config   # also config/routing.json threshold + config/calibration.json
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
import tempfile
from datetime import date
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.classify import LocalClassifier, apply_temperature  # noqa: E402
from src.ingest import normalise  # noqa: E402
from src.route import NEVER, Router, RoutingConfig  # noqa: E402
from src.splits import dev_holdout_split, text_key  # noqa: E402

EDGES = [0.0, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 0.99, 1.0000001]
MIN_BIN = 10
GAP_LIMIT = 5.0  # points, NFR-10
TARGET_ACC = 0.95
CANDIDATES = [round(0.50 + i / 100, 2) for i in range(50)]
FOLDS = 5


# ----------------------------------------------------------------------------- statistics

def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return 0.0, 1.0
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return round(max(0.0, c - h), 3), round(min(1.0, c + h), 3)


def bin_table(conf: list[float], correct: list[bool], edges=EDGES, min_n: int = MIN_BIN) -> list[dict[str, Any]]:
    bins = [{"lo": edges[i], "hi": edges[i + 1], "idx": []} for i in range(len(edges) - 1)]
    for i, c in enumerate(conf):
        for b in bins:
            if b["lo"] <= c < b["hi"]:
                b["idx"].append(i)
                break
    bins = [b for b in bins if b["idx"]] or bins[:1]
    while len(bins) > 1 and min(len(b["idx"]) for b in bins) < min_n:
        j = min(range(len(bins)), key=lambda k: (len(bins[k]["idx"]), k))
        if j == 0:
            k = 1
        elif j == len(bins) - 1:
            k = j - 1
        else:
            k = j - 1 if len(bins[j - 1]["idx"]) <= len(bins[j + 1]["idx"]) else j + 1
        a, b = sorted((j, k))
        bins[a] = {"lo": bins[a]["lo"], "hi": bins[b]["hi"], "idx": bins[a]["idx"] + bins[b]["idx"]}
        del bins[b]
    out = []
    for b in bins:
        n = len(b["idx"])
        k = sum(correct[i] for i in b["idx"])
        mc = sum(conf[i] for i in b["idx"]) / n if n else 0.0
        acc = k / n if n else 0.0
        gap = round((mc - acc) * 100, 1)
        out.append({"band": f"{b['lo']:.2f}-{min(b['hi'], 1.0):.2f}", "lo": b["lo"], "hi": min(b["hi"], 1.0), "n": n,
                    "mean_conf": round(mc, 3), "accuracy": round(acc, 3), "acc_95ci": wilson(k, n),
                    "gap_pts": gap, "pass": abs(gap) <= GAP_LIMIT and n >= min_n,
                    "direction": "over" if gap > 0 else "under"})
    return out


def ece(conf: list[float], correct: list[bool]) -> float:
    t = bin_table(conf, correct, min_n=1)
    n = sum(b["n"] for b in t) or 1
    return round(sum(b["n"] * abs(b["mean_conf"] - b["accuracy"]) for b in t) / n, 4)


def fit_temperature(probas, labels_idx) -> float:
    import numpy as np

    P = np.asarray(probas)
    y = np.asarray(labels_idx)
    best, best_t = float("inf"), 1.0
    for t in np.exp(np.linspace(math.log(0.1), math.log(10), 401)):
        q = apply_temperature(P, float(t))
        nll = -np.mean(np.log(np.clip(q[np.arange(len(y)), y], 1e-12, 1)))
        if nll < best:
            best, best_t = nll, float(t)
    return round(best_t, 3)


# ----------------------------------------------------------------------------- data

def out_of_fold(embedder, dev_raw: list[dict[str, Any]], folds: int = FOLDS) -> dict[str, Any]:
    """Nested grouped CV: per outer fold, pick C on the outer-train part only, fit, predict the held-out fold."""
    import numpy as np
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import GroupKFold

    recs = [(normalise(t, i), t) for i, t in enumerate(dev_raw)]
    recs = [(r, t) for r, t in recs if r.ok]
    X = np.asarray(embedder.encode([r.text for r, _ in recs]))
    y = np.asarray([t["labels"]["intent"] for _, t in recs])
    groups = [text_key(t) for _, t in recs]
    classes = sorted(set(y))
    cidx = {c: i for i, c in enumerate(classes)}
    P = np.zeros((len(recs), len(classes)))
    fold_of = np.zeros(len(recs), dtype=int)
    cs = []
    for f, (tr, te) in enumerate(GroupKFold(n_splits=folds).split(X, y, groups)):
        c, _ = LocalClassifier._pick_c(X[tr], y[tr], [groups[i] for i in tr])
        cs.append(c)
        m = LogisticRegression(C=c, max_iter=3000).fit(X[tr], y[tr])
        pp = m.predict_proba(X[te])
        for j, cl in enumerate(m.classes_):
            P[te, cidx[cl]] = pp[:, j]
        fold_of[te] = f
    return {"recs": recs, "P": P, "classes": classes, "y_idx": [cidx[v] for v in y], "fold": fold_of.tolist(),
            "C_per_fold": cs}


def deployed_probs(local: LocalClassifier, raw: list[dict[str, Any]]):
    """Deployed model's raw (T=1) intent probabilities, aligned to its own classes."""
    import numpy as np

    recs = [(normalise(t, i), t) for i, t in enumerate(raw)]
    recs = [(r, t) for r, t in recs if r.ok]
    P = local._intent.predict_proba(np.asarray(local.embedder.encode([r.text for r, _ in recs])))
    classes = [str(c) for c in local._intent.classes_]
    return recs, P, classes


def rows_from(recs, P, classes, T: float, router: Router | None, retriever) -> list[dict[str, Any]]:
    Q = apply_temperature(P, T)
    out = []
    for (rec, t), q in zip(recs, Q):
        k = int(q.argmax())
        lab = t["labels"]
        row = {"ticket_id": rec.ticket_id, "pred": classes[k], "label": lab["intent"], "conf": round(float(q[k]), 4),
               "correct": classes[k] == lab["intent"], "must_not": bool(lab.get("must_not_auto_respond")),
               "expected": lab.get("expected_route")}
        if router is not None:
            from src.classify import Classification
            order = q.argsort()[::-1]
            cls = Classification(classes[k], row["conf"],
                                 [{"label": classes[i], "confidence": round(float(q[i]), 4)} for i in order[1:3]],
                                 "medium", 0.0, [], "local", "calibration", "oof")
            res = retriever.retrieve(rec.text) if retriever is not None else None
            d = router.decide(rec.text, cls, res)  # router threshold is 0: tells eligibility only
            row["eligible"] = d.rule_fired == "none"
            row["rule"] = d.rule_fired
        out.append(row)
    return out


def threshold_table(rows: list[dict[str, Any]], bins: list[dict[str, Any]]) -> tuple[list[dict], dict]:
    table = []
    n_all = len(rows)
    for t in CANDIDATES:
        above = [r for r in rows if r["conf"] >= t]
        auto = [r for r in above if r.get("eligible")]
        elig = [r for r in rows if r.get("eligible")]
        over_fail = [b for b in bins if b["hi"] > t and not b["pass"] and b["direction"] == "over"]
        table.append({
            "threshold": t, "n_above": len(above),
            "acc_above": round(sum(r["correct"] for r in above) / len(above), 4) if above else None,
            "auto": len(auto), "draft": len(elig) - len(auto), "auto_rate": round(len(auto) / n_all, 4) if n_all else 0,
            "auto_wrong_intent": sum(not r["correct"] for r in auto),
            "auto_expected_precision": round(sum(r["expected"] == "auto_respond" for r in auto) / len(auto), 4)
            if auto else None,
            "must_not_auto": sum(r["must_not"] for r in auto),
            "overconfident_failing_bins_above": [b["band"] for b in over_fail],
        })
    ok = [s for s in table if s["acc_above"] is not None and s["acc_above"] >= TARGET_ACC
          and not s["overconfident_failing_bins_above"] and s["must_not_auto"] == 0]
    if ok:
        pick = min(ok, key=lambda s: s["threshold"])
    else:
        pick = {"threshold": NEVER, "note": "no candidate met all three conditions"}
    return table, pick


# ----------------------------------------------------------------------------- run

def run(embedder, retriever, dev_raw, val_raw, local: LocalClassifier) -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as tmp:
        rt = Path(tmp) / "runtime.json"
        rt.write_text('{"automation_paused": false}', encoding="utf-8")
        router = Router(RoutingConfig(threshold=0.0), runtime_path=rt)

        oof = out_of_fold(embedder, dev_raw)
        raw_rows = rows_from(oof["recs"], oof["P"], oof["classes"], 1.0, router, retriever)
        raw_bins = bin_table([r["conf"] for r in raw_rows], [r["correct"] for r in raw_rows])
        failing_raw = [b for b in raw_bins if not b["pass"]]

        # Fix by temperature only if a bin fails; adopt only if it helps on the dev hold-out (deployed model).
        _, hold_ids = dev_holdout_split(dev_raw)
        hs = set(hold_ids)
        h_recs, h_P, h_cls = deployed_probs(local, [t for t in dev_raw if t["ticket_id"] in hs])
        T, adopted, why = 1.0, False, "no bin failed; confidence used as computed"
        T_fit = None
        if failing_raw:
            T_fit = fit_temperature(oof["P"], oof["y_idx"])
            s_rows = rows_from(oof["recs"], oof["P"], oof["classes"], T_fit, None, None)
            s_bins = bin_table([r["conf"] for r in s_rows], [r["correct"] for r in s_rows])
            h_raw = rows_from(h_recs, h_P, h_cls, 1.0, None, None)
            h_s = rows_from(h_recs, h_P, h_cls, T_fit, None, None)
            e_raw = ece([r["conf"] for r in h_raw], [r["correct"] for r in h_raw])
            e_s = ece([r["conf"] for r in h_s], [r["correct"] for r in h_s])
            fewer = sum(not b["pass"] for b in s_bins) < len(failing_raw)
            if e_s <= e_raw and fewer:
                T, adopted = T_fit, True
                why = (f"T={T_fit} adopted: dev hold-out ECE {e_raw:.3f} -> {e_s:.3f}, failing dev bins "
                       f"{len(failing_raw)} -> {sum(not b['pass'] for b in s_bins)}")
            else:
                why = (f"T={T_fit} fitted but NOT adopted: dev hold-out ECE {e_raw:.3f} -> {e_s:.3f}, failing dev "
                       f"bins {len(failing_raw)} -> {sum(not b['pass'] for b in s_bins)}. Failing bins reported as a "
                       "known limit")

        rows = raw_rows if T == 1.0 else rows_from(oof["recs"], oof["P"], oof["classes"], T, router, retriever)
        bins = raw_bins if T == 1.0 else bin_table([r["conf"] for r in rows], [r["correct"] for r in rows])
        table, pick = threshold_table(rows, bins)

        # Checks with the deployed model (nothing chosen here except T adoption above, on the hold-out).
        hold_rows = rows_from(h_recs, h_P, h_cls, T, None, None)
        v_recs, v_P, v_cls = deployed_probs(local, val_raw)
        val_rows = rows_from(v_recs, v_P, v_cls, T, router, retriever)
        thr = pick["threshold"]
        val_auto = [r for r in val_rows if r.get("eligible") and r["conf"] >= thr]

    return {
        "run_date": date.today().isoformat(), "classifier_version": local.version,
        "embedding_model": embedder.name, "folds": FOLDS, "C_per_fold": oof["C_per_fold"],
        "n_oof": len(rows), "accuracy_oof": round(sum(r["correct"] for r in rows) / len(rows), 4),
        "bins_raw": raw_bins, "failing_raw": [b["band"] for b in failing_raw],
        "temperature_fitted": T_fit, "temperature": T, "temperature_adopted": adopted, "temperature_why": why,
        "bins": bins, "ece_oof": ece([r["conf"] for r in rows], [r["correct"] for r in rows]),
        "threshold_table": table, "threshold": thr, "pick": pick,
        "holdout_check": {"n": len(hold_rows), "bins": bin_table([r["conf"] for r in hold_rows],
                                                                 [r["correct"] for r in hold_rows])},
        "validation_check": {"n": len(val_rows),
                             "bins": bin_table([r["conf"] for r in val_rows], [r["correct"] for r in val_rows]),
                             "auto": len(val_auto), "auto_wrong_intent": sum(not r["correct"] for r in val_auto),
                             "must_not_auto": sum(r["must_not"] for r in val_auto),
                             "auto_expected_precision": round(sum(r["expected"] == "auto_respond" for r in val_auto)
                                                              / len(val_auto), 4) if val_auto else None},
        "rows": rows,
    }


def _bin_md(bins: list[dict[str, Any]]) -> list[str]:
    L = ["| Confidence bin | n | Mean confidence | Observed accuracy (95% CI) | Gap (pts) | Within 5 pts |",
         "| --- | --- | --- | --- | --- | --- |"]
    for b in bins:
        verdict = "yes" if b["pass"] else f"**NO** ({b['direction']}confident)"
        L.append(f"| {b['band']} | {b['n']} | {b['mean_conf']:.3f} | {b['accuracy']:.3f} "
                 f"({b['acc_95ci'][0]:.2f}-{b['acc_95ci'][1]:.2f}) | {b['gap_pts']:+.1f} | {verdict} |")
    return L


def to_markdown(r: dict[str, Any]) -> str:
    def pct(x):
        return "n/a" if x is None else f"{x:.1%}"

    L = [f"# Confidence calibration and routing threshold ({r['run_date']})", "",
         f"Local classifier `{r['classifier_version']}` ({r['embedding_model']} + logistic regression). "
         "Generated by `docs/calibration.py`; rerun to reproduce.", "",
         "## 1. Data", "",
         f"{r['n_oof']} dev tickets, each predicted by a model that never saw it: grouped {r['folds']}-fold by "
         f"distinct text, with C re-tuned inside each fold (C per fold: {r['C_per_fold']}). Out-of-fold intent "
         f"accuracy {pct(r['accuracy_oof'])}.", "",
         "## 2-3. Calibration table (raw confidence)", "",
         f"Bins under {MIN_BIN} tickets merged into a neighbour. Limit: |gap| <= {GAP_LIMIT:g} points (NFR-10). "
         "Gap = mean confidence minus accuracy; negative = underconfident.", ""]
    L += _bin_md(r["bins_raw"])
    L += ["", "## 4. Fix", "", r["temperature_why"] + "."]
    if r["temperature_adopted"]:
        L += ["", f"Calibration table with T = {r['temperature']} (same out-of-fold data T was fitted on, so "
              "optimistic; the deployed-model checks in section 6 are the independent view):", ""] + _bin_md(r["bins"])
    fails = [b for b in r["bins"] if not b["pass"]]
    L += ["", f"Expected calibration error (out-of-fold, as used): {r['ece_oof']:.3f}.", "",
          "**Known limits:** " + ("none; every bin is within 5 points." if not fails else
                                  "; ".join(f"bin {b['band']} (n={b['n']}) gap {b['gap_pts']:+.1f} pts, "
                                            f"{b['direction']}confident" for b in fails) + "."), "",
          "## 5. Threshold", "",
          f"Rule: lowest t where intent accuracy at or above t >= {TARGET_ACC:.0%}, no overconfident failing bin "
          "at or above t, and no must_not_auto_respond ticket answered automatically. Auto = no Route rule fired, "
          "a passage passed the cutoff, confidence >= t. Out-of-fold dev data.", "",
          "| t | Tickets >= t | Accuracy >= t | Auto | Draft | Auto rate (all) | Auto, wrong intent | "
          "Auto, expected auto_respond | must_not auto |", "| --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for s in r["threshold_table"]:
        if round(s["threshold"] * 100) % 5 == 0 or s["threshold"] == r["threshold"] or s["threshold"] == 0.99:
            mark = " **<- chosen**" if s["threshold"] == r["threshold"] else ""
            L.append(f"| {s['threshold']:.2f}{mark} | {s['n_above']} | {pct(s['acc_above'])} | {s['auto']} | "
                     f"{s['draft']} | {pct(s['auto_rate'])} | {s['auto_wrong_intent']} | "
                     f"{pct(s['auto_expected_precision'])} | {s['must_not_auto']} |")
    L += ["", f"**Chosen threshold: {r['threshold']}.**", "",
          "**Trade-off.** Raising the threshold moves tickets from automatic answers to drafts for an agent: fewer "
          "wrong-intent answers, more agent work. Lowering it automates more and risks answering on a wrong intent. "
          "The table shows the cost at each step. Intent errors are only one source of wrong answers: tickets the "
          "docs cannot answer still pass this threshold (see 'Auto, expected auto_respond'), so the end-to-end 90% "
          "check (FR-11, revised) runs after Generate (5.8).", "",
          "## 6. Checks with the deployed model", "",
          f"Dev hold-out (n={r['holdout_check']['n']}; used only to decide whether to adopt T):", ""]
    L += _bin_md(r["holdout_check"]["bins"])
    v = r["validation_check"]
    L += ["", f"Validation (n={v['n']}; never used to choose anything):", ""] + _bin_md(v["bins"])
    L += ["", f"At the chosen threshold on validation: {v['auto']} automatic, {v['auto_wrong_intent']} with a wrong "
          f"intent, {v['must_not_auto']} must_not_auto_respond, {pct(v['auto_expected_precision'])} expected "
          "auto_respond.", ""]
    return "\n".join(L)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dev", default="data/development_tickets.json")
    ap.add_argument("--validation", default="data/validation_tickets.json")
    ap.add_argument("--retrieval-config", default="config/retrieval.json")
    ap.add_argument("--out-dir", default=None, help="default evaluation/results/<date>_calibration")
    ap.add_argument("--write-config", action="store_true")
    a = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    from src.retrieve import SentenceTransformerEmbedder, build_retriever

    emb = SentenceTransformerEmbedder()
    local = LocalClassifier(emb, temperature=1.0).load_or_train()  # raw model; T is decided here
    ret = build_retriever(a.retrieval_config, embedder=emb)
    dev = json.loads(Path(a.dev).read_text(encoding="utf-8"))
    val = json.loads(Path(a.validation).read_text(encoding="utf-8"))
    r = run(emb, ret, dev, val, local)
    write_outputs(r, Path(a.out_dir or f"evaluation/results/{r['run_date']}_calibration"), a.write_config)
    return 0


def write_outputs(r: dict[str, Any], out: Path, write_config: bool,
                  routing_path: Path = Path("config/routing.json"),
                  calibration_path: Path = Path("config/calibration.json")) -> None:
    out.mkdir(parents=True, exist_ok=True)
    rows = r.pop("rows")
    with open(out / "predictions_oof.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    (out / "calibration.json").write_text(json.dumps(r, indent=2), encoding="utf-8")
    md = to_markdown(r)
    (out / "calibration.md").write_text(md, encoding="utf-8")
    print(md)
    if not write_config:
        return
    report = str(out / "calibration.md").replace("\\", "/")
    calibration_path.parent.mkdir(parents=True, exist_ok=True)
    calibration_path.write_text(json.dumps({
        "adopted": r["temperature_adopted"], "intent_temperature": r["temperature"],
        "fitted_temperature": r["temperature_fitted"], "set_on": r["run_date"], "why": r["temperature_why"],
        "evidence": report}, indent=2) + "\n", encoding="utf-8")
    cfg = json.loads(routing_path.read_text(encoding="utf-8")) if routing_path.exists() else {}
    pick = r["pick"]
    cfg.update({
        "threshold": r["threshold"], "set_on": r["run_date"], "set_by": "calibration",
        "rule": (f"lowest confidence where out-of-fold intent accuracy at or above it >= {TARGET_ACC:.0%}, no "
                 "overconfident failing calibration bin above it, zero must_not_auto_respond automatic (5.7)"),
        "classifier_version": r["classifier_version"], "intent_temperature": r["temperature"],
        "evidence": {"report": report, "at_threshold_dev_oof": {k: pick.get(k) for k in
                     ("auto", "auto_rate", "acc_above", "auto_wrong_intent", "auto_expected_precision",
                      "must_not_auto")},
                     "validation": {k: v for k, v in r["validation_check"].items() if k != "bins"}},
    })
    routing_path.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
    print(f"\nwrote {routing_path} (threshold {r['threshold']}) and {calibration_path}")


if __name__ == "__main__":
    raise SystemExit(main())
