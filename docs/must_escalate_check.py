"""5.10 evidence: must-not-auto-respond classes always escalate (FR-12, NFR-09, AS-06).

Three parts, all through the deployed classifier, retriever and Router (no model-provider call):

  A. Every labelled must-escalate ticket in the dev hold-out (classifier never saw them) and in the
     validation set: does it escalate, which rule fired, and which checks would have caught it on
     their own (intent rule, dispute list, risk terms, alternative guard).
  B. The alternative-guard floor, from data. "Must mass" = calibrated probability of every must-escalate
     class except the top one. Measured out-of-fold on all 500 dev tickets (5 grouped folds, same model
     recipe, deployed temperature), so every ticket is scored by a model that never saw its text.
     Rule: the smallest value on the 1-2-5 series above the largest must mass of any safe-labelled
     would-be automatic answer in the dev data (out-of-fold and the deployed model on the hold-out).
     Validation is the check, not the basis. A 1%-quantile rule was tried first (floor 0.0063): it cost
     0.6% out-of-fold but 4 of 58 on the hold-out with the deployed model, because the floor sat inside
     the dense top of the distribution and small model differences moved tickets across it.
     Note: an automatic answer has confidence >= threshold, so its must mass is at most 1 - threshold.
     A floor above that can never stop an automatic answer; it only turns drafts into escalations.
  C. tests/fixtures/must_escalate_tickets.json: one or more tickets per class, including mixed and
     disguised wording, which is how a risky ticket gets misclassified. Every one must escalate.

Usage (repo root):
    python docs/must_escalate_check.py                   # report only
    python docs/must_escalate_check.py --write-config    # also sets must_escalate_alt_floor in config/routing.json
Output: evaluation/results/<date>_must_escalate/must_escalate.md and .json
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import tempfile
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.ingest import normalise  # noqa: E402
from src.route import Router, RoutingConfig  # noqa: E402
from src.splits import dev_holdout_split  # noqa: E402

GRID = (0.001, 0.002, 0.005, 0.01, 0.02, 0.05, 0.10, 0.15)
DISPUTE = "billing_dispute"


def route_rows(raw: list[dict[str, Any]], classifier, retriever, router: Router, source: str) -> list[dict]:
    rows = []
    for i, t in enumerate(raw):
        rec = normalise(t, i)
        if not rec.ok:
            continue
        cls = classifier.classify(rec, allow_llm=False)
        q = (retriever.query_for(rec.text, rec.subject, None if cls.failed else cls.intent)[0]
             if hasattr(retriever, "query_for") else rec.text)
        res = retriever.retrieve(q)
        d = router.decide(rec.text, cls, res)
        lab = t.get("labels", {})
        rows.append({
            "ticket_id": rec.ticket_id, "source": source, "label": lab.get("intent", t.get("expect")),
            "kind": t.get("kind", ""), "pred": cls.intent, "conf": cls.intent_confidence,
            "action": d.action, "rule": d.rule_fired, "reason": d.reason, "layers": router.layers(rec.text, cls),
            "passages": len(res.passages), "text": rec.text,
        })
    return rows


def coverage_table(rows: list[dict], must: tuple[str, ...]) -> dict[str, Any]:
    by = defaultdict(list)
    for r in rows:
        by[r["label"]].append(r)
    out = {}
    for cls_name in [*must, DISPUTE]:
        rs = by.get(cls_name, [])
        if not rs:
            continue
        out[cls_name] = {
            "n": len(rs), "escalated": sum(r["action"] == "escalate" for r in rs),
            "not_escalated": [r["ticket_id"] for r in rs if r["action"] != "escalate"],
            "rules": dict(Counter(r["rule"] for r in rs)),
            "caught_by_intent_rule": sum(r["layers"]["intent_rule"] for r in rs),
            "caught_by_risk_terms": sum(bool(r["layers"]["risk_terms"]) for r in rs),
            "caught_by_dispute_list": sum(r["layers"]["dispute"] for r in rs),
            "caught_by_alternative_guard": sum(r["layers"]["alternative_guard"] for r in rs),
        }
    return out


def floor_table(rows: list[dict], must: tuple[str, ...]) -> list[dict[str, Any]]:
    """Safe-labelled tickets that reach auto_respond with the guard off: what each floor would cost."""
    safe = [r for r in rows if r["label"] not in must]
    autos = [r for r in safe if r["rule_guard_off"] == "auto"]
    drafts = [r for r in safe if r["rule_guard_off"] == "below_threshold"]
    table = []
    for f in GRID:
        hit = [r for r in autos if r["layers"]["alternative_mass"] >= f]
        dh = [r for r in drafts if r["layers"]["alternative_mass"] >= f]
        table.append({"floor": f, "would_be_auto": len(autos), "escalated_by_guard": len(hit),
                      "cost": round(len(hit) / len(autos), 4) if autos else 0.0,
                      "drafts": len(drafts), "drafts_escalated": len(dh),
                      "examples": [r["ticket_id"] for r in hit[:5]]})
    return table


def wilson_upper(k: int, n: int, z: float = 1.96) -> float:
    if n == 0:
        return 1.0
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    return round((c + z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5)) / d, 4)


def next_125(x: float) -> float:
    """Smallest value on the 1-2-5 series (..., 0.005, 0.01, 0.02, 0.05, ...) strictly above x."""
    e = math.floor(math.log10(x)) if x > 0 else -4
    for k in range(e, e + 2):
        for m in (1, 2, 5):
            v = round(m * 10 ** k, 10)
            if v > x:
                return v
    return round(10 ** (e + 2), 10)


def pick_floor(masses: list[float]) -> dict[str, Any]:
    """Next 1-2-5 value above the largest must mass of any safe would-be automatic answer."""
    n = len(masses)
    if n == 0:
        raise ValueError("no safe would-be automatic tickets to set the floor from")
    floor = next_125(max(masses))
    k_at = sum(m >= floor for m in masses)
    qs = sorted(masses)
    pctl = lambda q: round(qs[min(n - 1, int(q * n))], 5)  # noqa: E731
    return {"floor": round(floor, 4), "n": n, "escalated": k_at, "cost": round(k_at / n, 4),
            "cost_upper_95": wilson_upper(k_at, n),
            "mass_percentiles": {"p50": pctl(0.5), "p90": pctl(0.9), "p95": pctl(0.95), "p99": pctl(0.99),
                                 "max": round(qs[-1], 5)},
            "rule": "smallest 1-2-5 value above the largest must mass of any safe-labelled would-be automatic "
                    "answer in the dev data (out-of-fold on all 500, plus the deployed model on the hold-out); "
                    "validation is the check"}


def oof_rows(dev_raw, retriever, router_off: Router, temperature: float, oof_fn) -> list[dict[str, Any]]:
    """Out-of-fold classification of every dev ticket, routed with the guard off."""
    from src.classify import Classification, apply_temperature

    oof = oof_fn(dev_raw)
    Q = apply_temperature(oof["P"], temperature)
    classes = oof["classes"]
    rows = []
    for (rec, t), q in zip(oof["recs"], Q):
        k = int(q.argmax())
        dist = {c: float(x) for c, x in zip(classes, q)}
        order = q.argsort()[::-1]
        cls = Classification(classes[k], round(float(q[k]), 4),
                             [{"label": classes[i], "confidence": round(float(q[i]), 4)} for i in order[1:3]],
                             "medium", 0.0, [], "local", "oof", "oof", intent_distribution=dist)
        q = retriever.query_for(rec.text, rec.subject, cls.intent)[0] if hasattr(retriever, "query_for") else rec.text
        d = router_off.decide(rec.text, cls, retriever.retrieve(q))
        rows.append({"ticket_id": rec.ticket_id, "label": t["labels"]["intent"], "pred": cls.intent,
                     "conf": cls.intent_confidence, "rule_guard_off": "auto" if d.action == "auto_respond" else d.rule_fired,
                     "layers": router_off.layers(rec.text, cls)})
    return rows


def run(dev_raw, val_raw, fixtures, classifier, retriever, runtime_path, oof_fn=None,
        temperature: float = 1.0) -> dict[str, Any]:
    base = RoutingConfig.load()
    must = base.must_escalate_intents
    # Guard off (floor above any mass): tells which tickets would otherwise be answered automatically.
    off = Router(RoutingConfig(**{**base.__dict__, "must_escalate_alt_floor": 2.0}), runtime_path=runtime_path)
    live = Router(base, runtime_path=runtime_path)

    _, hold_ids = dev_holdout_split(dev_raw)
    hold = [t for t in dev_raw if t["ticket_id"] in set(hold_ids)]
    parts = {"dev_holdout": hold, "validation": val_raw}

    result: dict[str, Any] = {"run_date": date.today().isoformat(), "config": base.source,
                              "threshold": base.threshold, "floor_in_config": base.must_escalate_alt_floor,
                              "must_escalate_intents": list(must)}
    all_rows = {}
    for name, raw in parts.items():
        rows_off = route_rows(raw, classifier, retriever, off, name)
        rows = route_rows(raw, classifier, retriever, live, name)
        for r, ro in zip(rows, rows_off):
            r["rule_guard_off"] = "auto" if ro["action"] == "auto_respond" else ro["rule"]
        all_rows[name] = rows
        result[name] = {"n": len(rows), "coverage": coverage_table(rows, must),
                        "must_auto_or_draft": [r["ticket_id"] for r in rows
                                               if r["label"] in must and r["action"] != "escalate"],
                        "floor_table": floor_table(rows, must)}
    must_set = set(must)
    if oof_fn is not None:
        orow = oof_rows(dev_raw, retriever, off, temperature, oof_fn)
        result["dev_oof"] = {"n": len(orow), "floor_table": floor_table(orow, must)}
        basis = [r["layers"]["alternative_mass"] for r in orow + all_rows["dev_holdout"]
                 if r["label"] not in must_set and r["rule_guard_off"] == "auto"]
    else:  # tests without the OOF fit: fall back to the hold-out
        basis = [r["layers"]["alternative_mass"] for r in all_rows["dev_holdout"]
                 if r["label"] not in must_set and r["rule_guard_off"] == "auto"]
    result["floor_pick"] = pick_floor(basis)
    f = result["floor_pick"]["floor"]
    result["floor_pick"]["inert_above"] = round(1 - base.threshold, 4)
    for part in ("dev_holdout", "validation"):
        rows = all_rows[part]
        autos = [r for r in rows if r["label"] not in must_set and r["rule_guard_off"] == "auto"]
        drafts = [r for r in rows if r["label"] not in must_set and r["rule_guard_off"] == "below_threshold"]
        k = sum(r["layers"]["alternative_mass"] >= f for r in autos)
        result["floor_pick"][f"{part}_check"] = {
            "would_be_auto": len(autos), "escalated": k, "cost_upper_95": wilson_upper(k, len(autos)),
            "drafts": len(drafts), "drafts_escalated": sum(r["layers"]["alternative_mass"] >= f for r in drafts)}

    # Part C with the picked floor
    picked = Router(RoutingConfig(**{**base.__dict__, "must_escalate_alt_floor": f}), runtime_path=runtime_path)
    fx = route_rows(fixtures, classifier, retriever, picked, "fixtures")
    result["fixtures"] = [{k: r[k] for k in ("ticket_id", "label", "kind", "pred", "conf", "action", "rule")}
                          | {"mass": r["layers"]["alternative_mass"], "risk_terms": r["layers"]["risk_terms"],
                             "dispute": r["layers"]["dispute"]} for r in fx]
    result["fixtures_all_escalated"] = all(r["action"] == "escalate" for r in fx)
    return result


def pct(x: float) -> str:
    return f"{100 * x:.1f}%"


def to_markdown(r: dict[str, Any]) -> str:
    L = [f"# Must-not-auto-respond check (5.10), {r['run_date']}", "",
         f"Config {r['config']}, threshold {r['threshold']}. Must-escalate intents: "
         f"{', '.join(r['must_escalate_intents'])}, plus billing disputes (any intent). "
         "Generated by `docs/must_escalate_check.py`.", ""]
    for part in ("dev_holdout", "validation"):
        p = r[part]
        L += [f"## A. Labelled tickets: {part.replace('_', ' ')} ({p['n']} tickets)", "",
              "| Class | n | Escalated | Rules fired | Intent rule alone | Risk terms alone | Alternative guard alone |",
              "| --- | --- | --- | --- | --- | --- | --- |"]
        for c, v in p["coverage"].items():
            rules = ", ".join(f"{k} {n}" for k, n in v["rules"].items())
            L.append(f"| {c} | {v['n']} | {v['escalated']} | {rules} | {v['caught_by_intent_rule']} | "
                     f"{v['caught_by_risk_terms']} | {v['caught_by_alternative_guard']} |")
        L += ["", f"Must-escalate tickets answered or drafted: **{len(p['must_auto_or_draft'])}** "
              f"{p['must_auto_or_draft'] or ''}", ""]
    fp = r["floor_pick"]
    mp = fp["mass_percentiles"]
    L += ["## B. Alternative-guard floor", "",
          "Must mass = calibrated probability of every must-escalate class except the top one. Basis: "
          f"{fp['n']} safe-labelled dev ticket scores that would be answered automatically with the guard off "
          "(out-of-fold on all 500, so no ticket is scored by a model that saw its text, plus the deployed "
          "model on the hold-out).", "",
          f"Must mass on those tickets: median {mp['p50']:g}, p90 {mp['p90']:g}, p95 {mp['p95']:g}, "
          f"p99 {mp['p99']:g}, max {mp['max']:g}.", "",
          f"**Floor = {fp['floor']:g}**: {fp['rule']}. Cost {fp['escalated']} of {fp['n']} "
          f"in the dev basis ({pct(fp['cost'])}; Wilson 95% upper bound {pct(fp['cost_upper_95'])}).", ""]
    for part in ("dev_holdout", "validation"):
        c = fp[f"{part}_check"]
        L.append(f"- {part.replace('_', ' ')}, deployed model: {c['escalated']} of {c['would_be_auto']} would-be "
                 f"automatic answers escalated (upper 95% {pct(c['cost_upper_95'])}); "
                 f"{c['drafts_escalated']} of {c['drafts']} drafts escalated instead of drafted.")
    L += ["", f"An automatic answer has confidence >= {r['threshold']}, so its must mass is at most "
          f"{fp['inert_above']:g}. Any floor above that (the first policy value was 0.15) cannot stop an "
          "automatic answer; it only turns drafts into escalations.", "",
          "| Floor | OOF would-be auto escalated | Hold-out | Validation | Validation drafts escalated |",
          "| --- | --- | --- | --- | --- |"]
    oo = r.get("dev_oof", {}).get("floor_table") or r["dev_holdout"]["floor_table"]
    for o, h, v in zip(oo, r["dev_holdout"]["floor_table"], r["validation"]["floor_table"]):
        L.append(f"| {o['floor']:g} | {o['escalated_by_guard']} of {o['would_be_auto']} | "
                 f"{h['escalated_by_guard']} of {h['would_be_auto']} | {v['escalated_by_guard']} of "
                 f"{v['would_be_auto']} | {v['drafts_escalated']} of {v['drafts']} |")
    L += ["",
          "## C. Engineered tickets (tests/fixtures/must_escalate_tickets.json)", "",
          "| Ticket | Class | Wording | Predicted | Conf | Must mass | Action | Rule |", "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    for x in r["fixtures"]:
        L.append(f"| {x['ticket_id']} | {x['label']} | {x['kind']} | {x['pred']} | {x['conf']:.2f} | "
                 f"{x['mass']:.3f} | {x['action']} | {x['rule']} |")
    L += ["", "**All engineered tickets escalated.**" if r["fixtures_all_escalated"]
          else "**NOT ALL ENGINEERED TICKETS ESCALATED: see rows above.**", ""]
    return "\n".join(L)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dev", default="data/development_tickets.json")
    ap.add_argument("--validation", default="data/validation_tickets.json")
    ap.add_argument("--fixtures", default="tests/fixtures/must_escalate_tickets.json")
    ap.add_argument("--out-dir", default=None)
    ap.add_argument("--write-config", action="store_true")
    a = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    from src.classify import build_classifier
    from src.retrieve import SentenceTransformerEmbedder, build_retriever

    emb = SentenceTransformerEmbedder()
    classifier = build_classifier(emb, use_llm_fallback=False)
    retriever = build_retriever(embedder=emb)
    load = lambda p: json.loads(Path(p).read_text(encoding="utf-8"))  # noqa: E731
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        rt = Path(tmp) / "runtime.json"
        rt.write_text('{"automation_paused": false}', encoding="utf-8")  # the check ignores the live kill switch
        from docs.calibration import out_of_fold
        T = classifier.local.temperature if classifier.local is not None else 1.0
        r = run(load(a.dev), load(a.validation), load(a.fixtures), classifier, retriever, rt,
                oof_fn=lambda raw: out_of_fold(emb, raw), temperature=T)

    out = Path(a.out_dir or f"evaluation/results/{r['run_date']}_must_escalate")
    out.mkdir(parents=True, exist_ok=True)
    (out / "must_escalate.json").write_text(json.dumps(r, indent=2), encoding="utf-8")
    md = to_markdown(r)
    (out / "must_escalate.md").write_text(md, encoding="utf-8")
    print(md)
    if a.write_config:
        p = Path("config/routing.json")
        cfg = json.loads(p.read_text(encoding="utf-8"))
        cfg["must_escalate_alt_floor"] = r["floor_pick"]["floor"]
        cfg["must_escalate_alt_floor_rule"] = r["floor_pick"]["rule"]
        cfg["must_escalate_alt_floor_evidence"] = str(out / "must_escalate.md").replace("\\", "/")
        cfg["must_escalate_alt_floor_set_on"] = r["run_date"]
        p.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
        print(f"\nwrote {p} (must_escalate_alt_floor {r['floor_pick']['floor']:g})")
    bad = r["dev_holdout"]["must_auto_or_draft"] + r["validation"]["must_auto_or_draft"]
    return 0 if r["fixtures_all_escalated"] and not bad else 1


if __name__ == "__main__":
    raise SystemExit(main())
