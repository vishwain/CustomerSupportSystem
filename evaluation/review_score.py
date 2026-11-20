"""Human review scoring (5.18): per-assessor figures, agreement, disagreements, final figures.

Reads evaluation/results/human_review/assessor_A.csv and assessor_B.csv (rubric in RUBRIC.md), and, once
disagreements are settled, adjudication.csv (ticket_id, field, final_value, how_settled).

Writes in the same folder:
  review_results.md / .json   hallucination rate, citation accuracy, mean CSAT proxy, escalation and block
                              judgements, agreement between assessors, final figures
  disagreements.csv           every case to settle, with empty final_value / how_settled columns
                              (copy rows into adjudication.csv once settled)

Usage:
    python -m evaluation.review_score [--dir evaluation/results/human_review]
Exit 1 if a sheet is incomplete or out of range (the report lists what to fix).
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
from collections import Counter
from pathlib import Path
from typing import Any

YN = ("block_justified", "escalation_correct", "summary_accurate")
SCORES = ("correctness", "completeness", "tone")
FIELDS_BY_TYPE = {
    "answered": ("unsupported_sentences", "citations_supporting", *SCORES),
    "blocked": ("unsupported_sentences", "citations_supporting", "block_justified", *SCORES),
    "escalated": ("escalation_correct", "summary_accurate", *SCORES),
}


def read_sheet(p: Path) -> dict[str, dict[str, str]]:
    with open(p, encoding="utf-8-sig", newline="") as f:
        return {r["ticket_id"]: {k: (v or "").strip() for k, v in r.items()} for r in csv.DictReader(f)}


def check_sheet(rows: dict[str, dict[str, str]], who: str) -> list[str]:
    problems = []
    for tid, r in rows.items():
        t = r["item_type"]
        for f in FIELDS_BY_TYPE.get(t, ()):
            v = r.get(f, "")
            if v == "":
                problems.append(f"{who} {tid}: {f} is empty")
                continue
            if f in YN:
                if v.lower() not in ("y", "n"):
                    problems.append(f"{who} {tid}: {f} must be y or n, got {v!r}")
            elif f in SCORES:
                if v not in ("1", "2", "3", "4", "5"):
                    problems.append(f"{who} {tid}: {f} must be 1 to 5, got {v!r}")
            else:
                cap = int(r["sentences"] if f == "unsupported_sentences" else r["citations"])
                if not v.isdigit() or not 0 <= int(v) <= cap:
                    problems.append(f"{who} {tid}: {f} must be 0 to {cap}, got {v!r}")
    return problems


def kappa(a: list[Any], b: list[Any]) -> float | None:
    """Cohen's kappa for nominal labels."""
    n = len(a)
    if n == 0:
        return None
    po = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum(ca[k] * cb[k] for k in set(ca) | set(cb)) / (n * n)
    return 1.0 if pe == 1 else round((po - pe) / (1 - pe), 3)


def weighted_kappa(a: list[int], b: list[int], k: int = 5) -> float | None:
    """Quadratic-weighted kappa for ordinal 1..k scores."""
    n = len(a)
    if n == 0:
        return None
    w = lambda i, j: ((i - j) ** 2) / ((k - 1) ** 2)  # noqa: E731
    obs = sum(w(x, y) for x, y in zip(a, b)) / n
    ca, cb = Counter(a), Counter(b)
    exp = sum(ca[i] * cb[j] * w(i, j) for i in range(1, k + 1) for j in range(1, k + 1)) / (n * n)
    return 1.0 if exp == 0 else round(1 - obs / exp, 3)


def pct(k: int, n: int) -> float | None:
    return round(100 * k / n, 1) if n else None


def figures(rows: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Figures from one set of per-item values (an assessor's sheet, or the final values)."""
    def num(r, f):
        return float(r[f])

    sent = [r for r in rows.values() if r["item_type"] == "answered"]
    blk = [r for r in rows.values() if r["item_type"] == "blocked"]
    esc = [r for r in rows.values() if r["item_type"] == "escalated"]
    out: dict[str, Any] = {"items": len(rows), "sent_answers": len(sent), "blocked": len(blk), "escalated": len(esc)}
    for name, grp in (("sent", sent), ("blocked", blk)):
        sent_n = sum(int(r["sentences"]) for r in grp)
        cit_n = sum(int(r["citations"]) for r in grp)
        out[f"{name}_hallucination_rate"] = pct(sum(num(r, "unsupported_sentences") > 0 for r in grp), len(grp))
        out[f"{name}_unsupported_sentence_rate"] = pct(round(sum(num(r, "unsupported_sentences") for r in grp)), sent_n)
        out[f"{name}_citation_accuracy"] = pct(round(sum(num(r, "citations_supporting") for r in grp)), cit_n)
        out[f"{name}_sentences"], out[f"{name}_citations"] = sent_n, cit_n
    out["escalation_correct_rate"] = pct(sum(r["escalation_correct"] == "y" for r in esc), len(esc))
    out["summary_accurate_rate"] = pct(sum(r["summary_accurate"] == "y" for r in esc), len(esc))
    out["block_justified"] = f"{sum(r['block_justified'] == 'y' for r in blk)} of {len(blk)}"
    means = {t: [statistics.mean(num(r, f) for f in SCORES) for r in rows.values() if r["item_type"] == t]
             for t in FIELDS_BY_TYPE}
    allm = [x for v in means.values() for x in v]
    out["csat_mean"] = round(statistics.mean(allm), 2) if allm else None
    out["csat_mean_by_type"] = {t: (round(statistics.mean(v), 2) if v else None) for t, v in means.items()}
    out["csat_mean_by_dimension"] = {f: round(statistics.mean(num(r, f) for r in rows.values()), 2) for f in SCORES}
    out["hallucinating_items"] = sorted(r["ticket_id"] for r in sent + blk if num(r, "unsupported_sentences") > 0)
    return out


def agreement(A: dict, B: dict) -> dict[str, Any]:
    ids = sorted(set(A) & set(B))
    res: dict[str, Any] = {}
    gen = [t for t in ids if A[t]["item_type"] in ("answered", "blocked")]
    fa = [int(A[t]["unsupported_sentences"]) > 0 for t in gen]
    fb = [int(B[t]["unsupported_sentences"]) > 0 for t in gen]
    res["hallucination_flag"] = {"n": len(gen), "agree_pct": pct(sum(x == y for x, y in zip(fa, fb)), len(gen)),
                                 "kappa": kappa(fa, fb)}
    ca = [A[t]["citations_supporting"] for t in gen]
    cb = [B[t]["citations_supporting"] for t in gen]
    res["citations_supporting_exact"] = {"n": len(gen), "agree_pct": pct(sum(x == y for x, y in zip(ca, cb)), len(gen))}
    for f in YN:
        sub = [t for t in ids if A[t][f] and B[t][f]]
        a, b = [A[t][f].lower() for t in sub], [B[t][f].lower() for t in sub]
        res[f] = {"n": len(sub), "agree_pct": pct(sum(x == y for x, y in zip(a, b)), len(sub)), "kappa": kappa(a, b)}
    for f in SCORES:
        a, b = [int(A[t][f]) for t in ids], [int(B[t][f]) for t in ids]
        res[f] = {"n": len(ids), "exact_pct": pct(sum(x == y for x, y in zip(a, b)), len(ids)),
                  "within_1_pct": pct(sum(abs(x - y) <= 1 for x, y in zip(a, b)), len(ids)),
                  "weighted_kappa": weighted_kappa(a, b)}
    return res


def disagreements(A: dict, B: dict) -> list[dict[str, str]]:
    out = []
    for t in sorted(set(A) & set(B)):
        a, b = A[t], B[t]
        if a["item_type"] in ("answered", "blocked"):
            if (int(a["unsupported_sentences"]) > 0) != (int(b["unsupported_sentences"]) > 0) or \
                    a["unsupported_sentences"] != b["unsupported_sentences"]:
                out.append({"ticket_id": t, "field": "unsupported_sentences", "A": a["unsupported_sentences"],
                            "B": b["unsupported_sentences"]})
            if a["citations_supporting"] != b["citations_supporting"]:
                out.append({"ticket_id": t, "field": "citations_supporting", "A": a["citations_supporting"],
                            "B": b["citations_supporting"]})
        for f in YN:
            if a[f] and b[f] and a[f].lower() != b[f].lower():
                out.append({"ticket_id": t, "field": f, "A": a[f], "B": b[f]})
        for f in SCORES:
            if abs(int(a[f]) - int(b[f])) >= 2:
                out.append({"ticket_id": t, "field": f, "A": a[f], "B": b[f]})
    for d in out:
        d.update({"A_notes": A[d["ticket_id"]].get("notes", ""), "B_notes": B[d["ticket_id"]].get("notes", ""),
                  "final_value": "", "how_settled": ""})
    return out


def final_values(A: dict, B: dict, adj: dict[tuple[str, str], dict[str, str]]) -> tuple[dict, list[str]]:
    final, unsettled = {}, []
    for t in sorted(set(A) & set(B)):
        a, b = A[t], B[t]
        r = {"ticket_id": t, "item_type": a["item_type"], "sentences": a["sentences"], "citations": a["citations"]}
        for f in FIELDS_BY_TYPE[a["item_type"]]:
            if (t, f) in adj:
                r[f] = adj[(t, f)]["final_value"]
            elif a[f].lower() == b[f].lower():
                r[f] = a[f].lower()
            elif f in SCORES and abs(int(a[f]) - int(b[f])) == 1:
                r[f] = str((int(a[f]) + int(b[f])) / 2)
            else:
                r[f] = a[f]
                unsettled.append(f"{t} {f}")
        final[t] = r
    return final, unsettled


def to_markdown(r: dict[str, Any]) -> str:
    def row(label, key, unit="%"):
        vals = [r[k].get(key) if r.get(k) else None for k in ("A", "B", "final")]
        return f"| {label} | " + " | ".join("n/a" if v is None else f"{v}{unit if isinstance(v, (int, float)) else ''}"
                                             for v in vals) + " |"

    L = ["# Human review results (5.18)", "",
         f"Sample: {r['A']['items']} items ({r['A']['sent_answers']} sent answers, {r['A']['blocked']} blocked "
         f"drafts, {r['A']['escalated']} escalations); see SAMPLE.md. Rubric: RUBRIC.md.", "",
         f"Assessor A: {r['assessors']['A']}. Assessor B: {r['assessors']['B']}. Scored independently; neither "
         "saw the other's sheet before finishing.", "",
         "| Figure | Assessor A | Assessor B | Final (agreed + adjudicated) |", "| --- | --- | --- | --- |",
         row("Hallucination rate, sent answers (any unsupported sentence)", "sent_hallucination_rate"),
         row("Unsupported sentences, sent answers", "sent_unsupported_sentence_rate"),
         row("Citation accuracy, sent answers (supporting links)", "sent_citation_accuracy"),
         row("Mean CSAT proxy (1 to 5), all items", "csat_mean", ""),
         row("Escalation was the right call", "escalation_correct_rate"),
         row("Escalation summary accurate (no added facts)", "summary_accurate_rate"),
         row("Blocked drafts: block justified", "block_justified", ""),
         row("Blocked drafts: hallucination rate", "blocked_hallucination_rate"),
         row("Blocked drafts: citation accuracy", "blocked_citation_accuracy"), "",
         f"NFR-08 targets: hallucination 5% or less, citation accuracy 95% or more (final: "
         f"{r['final'].get('sent_hallucination_rate')}% / {r['final'].get('sent_citation_accuracy')}%).", "",
         "Mean CSAT proxy by item type (final): " + ", ".join(f"{k} {v}" for k, v in
                                                            r["final"]["csat_mean_by_type"].items()),
         "", "Hallucinating items (final): " + (", ".join(r["final"]["hallucinating_items"]) or "none"),
         "", "## Agreement between assessors", "", "| Judgement | n | Agreement | Kappa |", "| --- | --- | --- | --- |"]
    g = r["agreement"]
    L.append(f"| Hallucination flag | {g['hallucination_flag']['n']} | {g['hallucination_flag']['agree_pct']}% | "
             f"{g['hallucination_flag']['kappa']} |")
    L.append(f"| citations_supporting count (exact) | {g['citations_supporting_exact']['n']} | "
             f"{g['citations_supporting_exact']['agree_pct']}% | |")
    for f in YN:
        L.append(f"| {f} | {g[f]['n']} | {g[f]['agree_pct']}% | {g[f]['kappa']} |")
    for f in SCORES:
        L.append(f"| {f} (1 to 5) | {g[f]['n']} | exact {g[f]['exact_pct']}%, within 1 {g[f]['within_1_pct']}% | "
                 f"weighted {g[f]['weighted_kappa']} |")
    L += ["", "Kappa is undefined-but-reported-as-1.0 when both assessors give the same single value to every item.",
          "", f"## Disagreements ({len(r['disagreements'])})", "",
          "| Ticket | Field | A | B | Final | How settled |", "| --- | --- | --- | --- | --- | --- |"]
    for d in r["disagreements"]:
        L.append(f"| {d['ticket_id']} | {d['field']} | {d['A']} | {d['B']} | {d.get('final_value') or 'unsettled'} | "
                 f"{(d.get('how_settled') or '').replace('|', '/')} |")
    if r["unsettled"]:
        L += ["", f"**{len(r['unsettled'])} disagreement(s) not settled yet**: final figures use assessor A's value "
              "for them until adjudication.csv has a row."]
    return "\n".join(L) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dir", default="evaluation/results/human_review")
    ap.add_argument("--assessor-a", default="the project author (human, FDE role)")
    ap.add_argument("--assessor-b", default="see ASSESSORS.md")
    a = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    d = Path(a.dir)
    A, B = read_sheet(d / "assessor_A.csv"), read_sheet(d / "assessor_B.csv")
    problems = check_sheet(A, "A") + check_sheet(B, "B")
    if set(A) != set(B):
        problems.append(f"sheets cover different tickets: {sorted(set(A) ^ set(B))}")
    if problems:
        print("Sheets are not complete; fix these and re-run:\n" + "\n".join(f"- {p}" for p in problems))
        return 1
    adj = {}
    if (d / "adjudication.csv").exists():
        with open(d / "adjudication.csv", encoding="utf-8-sig", newline="") as f:
            adj = {(x["ticket_id"], x["field"]): x for x in csv.DictReader(f) if (x.get("final_value") or "").strip()}
    dis = disagreements(A, B)
    for x in dis:
        if (x["ticket_id"], x["field"]) in adj:
            x["final_value"] = adj[(x["ticket_id"], x["field"])]["final_value"]
            x["how_settled"] = adj[(x["ticket_id"], x["field"])].get("how_settled", "")
    final, unsettled = final_values(A, B, adj)
    who = {"A": a.assessor_a, "B": a.assessor_b}
    if (d / "ASSESSORS.md").exists():
        for line in (d / "ASSESSORS.md").read_text(encoding="utf-8").splitlines():
            for k in ("A", "B"):
                if line.startswith(f"Assessor {k}:"):
                    who[k] = line.split(":", 1)[1].strip()
    r = {"assessors": who, "A": figures(A), "B": figures(B), "final": figures(final),
         "agreement": agreement(A, B), "disagreements": dis, "unsettled": unsettled}
    (d / "review_results.json").write_text(json.dumps(r, indent=2), encoding="utf-8")
    (d / "review_results.md").write_text(to_markdown(r), encoding="utf-8")
    with open(d / "disagreements.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["ticket_id", "field", "A", "B", "A_notes", "B_notes", "final_value",
                                          "how_settled"])
        w.writeheader()
        w.writerows(dis)
    print(to_markdown(r))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
