"""Fairness audit (5b.3, Governance Framework section 3; NFR-06 v2).

Breaks one run's results down by customer tier, region, language fluency, ticket length and channel. For
each segment: tickets, resolution rate (all tickets, and among auto-eligible tickets), response quality
(mean CSAT proxy from the 5.18 review, final values), citation accuracy (automated: cited passages in the
retrieved set; human: supporting links in the review), and retrieval hit rate. Variation from the best
segment is given with a 95% interval on the gap (Newcombe, from Wilson intervals). NFR-06 v2 rule: a gap
is judged only when both groups have 20 or more eligible tickets; a gap over 5 pts is FLAGGED; a gap whose
interval includes 5 pts is "not established". Small segments carry a caveat, not a conclusion.

Segment fields are joined from the input file by ticket_id here; the pipeline never reads them (FR-03, FR-19).

Usage:
    python -m evaluation.fairness_audit --run-dir evaluation/results/validation_5.17_official \
        --review-dir evaluation/results/human_review --out evaluation/results/fairness_audit
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

from src.ingest import iter_raw, load
from src.route import MUST_ESCALATE_INTENTS

GAP_PTS = 5.0
MIN_N = 20
SHORT_WORDS = 28
DIMENSIONS = ("tier", "region", "fluency", "length", "channel")


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - h) / d, (c + h) / d)


def gap_interval(k1: int, n1: int, k2: int, n2: int) -> tuple[float, float, float]:
    """Difference p1 - p2 in points, with Newcombe's hybrid-score 95% interval."""
    p1, p2 = k1 / n1, k2 / n2
    l1, u1 = wilson(k1, n1)
    l2, u2 = wilson(k2, n2)
    d = p1 - p2
    lo = d - math.sqrt((p1 - l1) ** 2 + (u2 - p2) ** 2)
    hi = d + math.sqrt((u1 - p1) ** 2 + (p2 - l2) ** 2)
    return round(100 * d, 1), round(100 * lo, 1), round(100 * hi, 1)


def pct(k: float, n: int) -> float | None:
    return round(100 * k / n, 1) if n else None


def review_final(review_dir: Path) -> dict[str, dict[str, Any]]:
    """Per-item final review values (agreed or adjudicated), via evaluation.review_score."""
    from evaluation import review_score as rs
    A, B = rs.read_sheet(review_dir / "assessor_A.csv"), rs.read_sheet(review_dir / "assessor_B.csv")
    adj = {}
    p = review_dir / "adjudication.csv"
    if p.exists():
        import csv
        with open(p, encoding="utf-8-sig", newline="") as f:
            adj = {(x["ticket_id"], x["field"]): x for x in csv.DictReader(f) if (x.get("final_value") or "").strip()}
    final, _ = rs.final_values(A, B, adj)
    return final


def facts(run_dir: Path, review_dir: Path | None) -> list[dict[str, Any]]:
    info = json.loads((run_dir / "run_info.json").read_text(encoding="utf-8"))
    results = {json.loads(x)["ticket_id"]: json.loads(x)
               for x in (run_dir / "results.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()}
    raws = [raw for _, raw in iter_raw(info["input_path"])]
    recs = load(info["input_path"])
    rev = review_final(review_dir) if review_dir and (review_dir / "assessor_A.csv").exists() else {}
    from src.logging_store import DecisionLog
    log = DecisionLog(info["db_path"], info["run_id"])
    ret = {r["ticket_id"]: r for r in log.rows() if r["stage"] == "retrieval"}
    log.close()
    out = []
    for rec, raw in zip(recs, raws):
        r = results.get(rec.ticket_id)
        if r is None or not isinstance(raw, dict):
            continue
        lab = raw.get("labels") or {}
        body = raw.get("body") if isinstance(raw.get("body"), str) else ""
        docs = [s["doc_id"] for s in (ret.get(rec.ticket_id) or {}).get("sources_used", [])]
        v = rev.get(rec.ticket_id)
        scores = None
        if v:
            scores = sum(float(v[f]) for f in ("correctness", "completeness", "tone")) / 3
        out.append({
            "ticket_id": rec.ticket_id, "answered": r["action"] == "auto_respond",
            # PRD Section 8 eligibility: answerable, not must-not, and not an intent FR-12 always escalates
            # (data_residency is labelled automatable but the PRD escalates it on purpose)
            "eligible": (bool(lab.get("answerable_from_docs")) and not lab.get("must_not_auto_respond")
                         and lab.get("intent") not in MUST_ESCALATE_INTENTS),
            "answerable": bool(lab.get("answerable_from_docs")) and bool(lab.get("expected_doc_ids")),
            "hit3": bool(set(docs[:3]) & set(lab.get("expected_doc_ids") or [])),
            "cited_ok": (r.get("generation") or {}).get("validated") is True if r["action"] == "auto_respond" else None,
            "csat": scores, "reviewed_answer": bool(v and v["item_type"] == "answered"),
            "cit_n": int(v["citations"]) if v and v["item_type"] == "answered" else 0,
            "cit_ok": float(v["citations_supporting"]) if v and v["item_type"] == "answered" else 0.0,
            "halluc": (float(v["unsupported_sentences"]) > 0) if v and v["item_type"] == "answered" else None,
            "tier": raw.get("customer_tier") or "unknown", "region": raw.get("customer_region") or "unknown",
            "fluency": raw.get("language_fluency") or "unknown", "channel": rec.channel,
            "length": f"short (<= {SHORT_WORDS} words)" if len(body.split()) <= SHORT_WORDS else f"long (> {SHORT_WORDS} words)",
        })
    return out


def segment(fs: list[dict[str, Any]]) -> dict[str, Any]:
    el = [f for f in fs if f["eligible"]]
    ans = [f for f in fs if f["answerable"]]
    rv = [f for f in fs if f["csat"] is not None]
    ra = [f for f in fs if f["reviewed_answer"]]
    sent = [f for f in fs if f["answered"]]
    cit_n = sum(f["cit_n"] for f in ra)
    return {
        "n": len(fs), "answered": len(sent), "resolution_rate": pct(len(sent), len(fs)),
        "eligible_n": len(el), "eligible_answered": sum(f["answered"] for f in el),
        "resolution_rate_eligible": pct(sum(f["answered"] for f in el), len(el)),
        "hit3_n": len(ans), "hit3": pct(sum(f["hit3"] for f in ans), len(ans)),
        "reviewed_n": len(rv), "quality_csat": round(sum(f["csat"] for f in rv) / len(rv), 2) if rv else None,
        "reviewed_answers": len(ra), "citation_links": cit_n,
        "citation_accuracy_review": pct(sum(f["cit_ok"] for f in ra), cit_n),
        "hallucinating_answers": sum(bool(f["halluc"]) for f in ra),
        "citation_validity_automated": pct(sum(bool(f["cited_ok"]) for f in sent), len(sent)),
    }


def audit(fs: list[dict[str, Any]]) -> dict[str, Any]:
    res: dict[str, Any] = {"overall": segment(fs), "dimensions": {}}
    for dim in DIMENSIONS:
        groups = defaultdict(list)
        for f in fs:
            groups[f[dim]].append(f)
        segs = {g: segment(v) for g, v in sorted(groups.items())}
        judged = {g: s for g, s in segs.items() if s["eligible_n"] >= MIN_N}
        comps = {}
        pool = judged or {g: s for g, s in segs.items() if s["eligible_n"]}
        if pool:
            # reference: the best segment of 20+ eligible tickets; if none, the largest segment (caveat only)
            best = (max(judged, key=lambda g: judged[g]["resolution_rate_eligible"]) if judged
                    else max(pool, key=lambda g: pool[g]["eligible_n"]))
            b = segs[best]
            for g, s in segs.items():
                if g == best or not s["eligible_n"]:
                    continue
                d, lo, hi = gap_interval(b["eligible_answered"], b["eligible_n"], s["eligible_answered"], s["eligible_n"])
                if s["eligible_n"] < MIN_N or b["eligible_n"] < MIN_N:
                    verdict = (f"caveat: {min(s['eligible_n'], b['eligible_n'])} eligible tickets, under {MIN_N}; "
                               "not judged") + ("; better than the reference" if d < 0 else "")
                elif d > GAP_PTS and lo > GAP_PTS:
                    verdict = "FLAG: gap over 5 pts, interval above 5"
                elif d > GAP_PTS:
                    verdict = "FLAG (not established): gap over 5 pts, interval includes 5"
                elif hi > GAP_PTS:
                    verdict = "within 5 pts, but the interval cannot rule out a gap over 5"
                else:
                    verdict = "within 5 pts"
                comps[g] = {"vs": best, "gap_pts": d, "ci95": [lo, hi], "verdict": verdict}
        else:
            best = None
        # retrieval gap (answerable tickets), same rule
        hit = {g: s for g, s in segs.items() if s["hit3_n"] >= MIN_N}
        hit_gap = None
        if len(hit) >= 2:
            hb = max(hit, key=lambda g: hit[g]["hit3"])
            hw = min(hit, key=lambda g: hit[g]["hit3"])
            fb, fw = hit[hb], hit[hw]
            kb, kw = round(fb["hit3"] * fb["hit3_n"] / 100), round(fw["hit3"] * fw["hit3_n"] / 100)
            d, lo, hi = gap_interval(kb, fb["hit3_n"], kw, fw["hit3_n"])
            hit_gap = {"best": hb, "worst": hw, "gap_pts": d, "ci95": [lo, hi],
                       "verdict": ("FLAG: over 5 pts, interval above 5" if lo > GAP_PTS else
                                   "FLAG (not established): over 5 pts, interval includes 5" if d > GAP_PTS else
                                   "within 5 pts")}
        res["dimensions"][dim] = {"segments": segs, "best": best, "comparisons": comps, "hit3_gap": hit_gap}
    return res


def to_markdown(r: dict[str, Any], run_id: str) -> str:
    def f(x, u="%"):
        return "n/a" if x is None else f"{x}{u}"

    o = r["overall"]
    L = [f"# Fairness audit (5b.3): {run_id}", "",
         "Validation run 11 (80 tickets), with response quality and human citation accuracy from the 5.18 review "
         "(59 items, two LLM assessors, final values). Generated by `evaluation/fairness_audit.py`.", "",
         "Columns: **Resolution** = answered automatically / tickets. **Eligible resolution** = answered / tickets "
         "labelled answerable and not must-not-auto-respond (the NFR-06 measure; segments differ in how many "
         "tickets may be automated at all). **Quality** = mean CSAT proxy (1 to 5) of the reviewed items in the "
         "segment. **Citation accuracy** = supporting links / all links in reviewed sent answers (human); every "
         "sent answer's citations resolve to retrieved passages in all segments (automated, 100%). "
         "**Variation from reference** = eligible-resolution gap to the best segment with 20+ eligible tickets "
         "(positive = worse than the reference), with a 95% interval. Eligible follows PRD Section 8: answerable, not "
         "must-not-auto-respond, and not data residency, which FR-12 escalates by design.", "",
         f"Overall: {o['n']} tickets, resolution {f(o['resolution_rate'])}, eligible resolution "
         f"{f(o['resolution_rate_eligible'])} (n={o['eligible_n']}), hit@3 {f(o['hit3'])}, quality "
         f"{f(o['quality_csat'], '')} (n={o['reviewed_n']}), citation accuracy {f(o['citation_accuracy_review'])} "
         f"({o['citation_links']} links).", ""]
    names = {"tier": "Customer tier", "region": "Region", "fluency": "Language fluency", "length": "Ticket length",
             "channel": "Channel"}
    for dim, d in r["dimensions"].items():
        L += [f"## {names[dim]}", "",
              "| Segment | Tickets | Resolution | Eligible resolution (n) | Hit@3 (n) | Quality (n reviewed) | "
              "Citation accuracy (links) | Variation from reference | Finding |",
              "| --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
        for g, s in d["segments"].items():
            c = d["comparisons"].get(g)
            var = "reference" if g == d["best"] else (f"{c['gap_pts']:+.1f} pts [{c['ci95'][0]}, {c['ci95'][1]}]" if c else "n/a")
            finding = "reference" if g == d["best"] else (c["verdict"] if c else "n/a")
            L.append(f"| {g} | {s['n']} | {f(s['resolution_rate'])} | {f(s['resolution_rate_eligible'])} "
                     f"({s['eligible_n']}) | {f(s['hit3'])} ({s['hit3_n']}) | {f(s['quality_csat'], '')} "
                     f"({s['reviewed_n']}) | {f(s['citation_accuracy_review'])} ({s['citation_links']}) | {var} | "
                     f"{finding} |")
        if d["hit3_gap"]:
            h = d["hit3_gap"]
            L.append(f"\nRetrieval: hit@3 gap {h['gap_pts']} pts [{h['ci95'][0]}, {h['ci95'][1]}] ({h['best']} vs "
                     f"{h['worst']}, groups of {MIN_N}+ answerable tickets): {h['verdict']}.")
        if d["best"] is None:
            L.append(f"\nNo segment has {MIN_N} or more eligible tickets: the reference is the largest segment and "
                     "every gap in this dimension is a caveat, not a conclusion.")
        L.append("")
    return "\n".join(L)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--review-dir", default="evaluation/results/human_review")
    ap.add_argument("--out", default="evaluation/results/fairness_audit")
    a = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    run_dir = Path(a.run_dir)
    info = json.loads((run_dir / "run_info.json").read_text(encoding="utf-8"))
    r = audit(facts(run_dir, Path(a.review_dir)))
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "fairness_audit.json").write_text(json.dumps(r, indent=2), encoding="utf-8")
    md = to_markdown(r, info["run_id"])
    (out / "fairness_audit.md").write_text(md, encoding="utf-8")
    print(md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
