"""5.18 review tooling: sample rule, sheet checks, figures, agreement, disagreements, adjudication."""

import csv

from evaluation import review_sample, review_score

F = review_sample.SHEET_FIELDS


def write(p, rows):
    with open(p, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=F)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in F})


def ans(tid, uns=0, sup=2, c=5, k=5, t=5, typ="answered", **o):
    return {"ticket_id": tid, "item_type": typ, "sentences": 2, "citations": 2, "unsupported_sentences": uns,
            "citations_supporting": sup, "correctness": c, "completeness": k, "tone": t, **o}


def esc(tid, ok="y", summ="y", c=5, k=4, t=5):
    return {"ticket_id": tid, "item_type": "escalated", "sentences": 0, "citations": 0, "escalation_correct": ok,
            "summary_accurate": summ, "correctness": c, "completeness": k, "tone": t}


def test_sample_takes_every_escalation_and_a_seeded_rest():
    res = [{"ticket_id": f"T{i:02d}", "action": "escalate" if i < 5 else "auto_respond",
            "rule_fired": "guardrail:grounding" if i == 0 else "none"} for i in range(20)]
    s1, s2 = review_sample.draw(res, 10), review_sample.draw(res, 10)
    assert s1 == s2 and len(s1["sample"]) == 10 and set(s1["escalated"]) <= set(s1["sample"])
    assert s1["blocked"] == ["T00"]


def test_scores_agreement_and_adjudication(tmp_path):
    A = [ans("V1"), ans("V2", uns=1, sup=1, c=2), ans("V3", typ="blocked", block_justified="n"), esc("V4"),
         esc("V5", ok="n", c=2)]
    B = [ans("V1", c=4), ans("V2", uns=0, sup=2, c=4), ans("V3", typ="blocked", block_justified="n"), esc("V4"),
         esc("V5", ok="y", c=5)]
    write(tmp_path / "assessor_A.csv", A)
    write(tmp_path / "assessor_B.csv", B)
    assert review_score.main(["--dir", str(tmp_path)]) == 0
    import json
    r = json.loads((tmp_path / "review_results.json").read_text(encoding="utf-8"))
    assert r["A"]["sent_hallucination_rate"] == 50.0 and r["B"]["sent_hallucination_rate"] == 0.0
    assert r["A"]["sent_citation_accuracy"] == 75.0
    fields = {(d["ticket_id"], d["field"]) for d in r["disagreements"]}
    assert ("V2", "unsupported_sentences") in fields and ("V5", "escalation_correct") in fields
    assert ("V1", "correctness") not in fields  # 5 vs 4: mean used, not a disagreement
    assert r["unsettled"]
    with open(tmp_path / "adjudication.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["ticket_id", "field", "final_value", "how_settled"])
        w.writeheader()
        for t, fld, v in (("V2", "unsupported_sentences", "1"), ("V2", "citations_supporting", "1"),
                          ("V2", "correctness", "3"), ("V5", "escalation_correct", "y"), ("V5", "correctness", "4")):
            w.writerow({"ticket_id": t, "field": fld, "final_value": v, "how_settled": "re-read vs rubric"})
    assert review_score.main(["--dir", str(tmp_path)]) == 0
    r = json.loads((tmp_path / "review_results.json").read_text(encoding="utf-8"))
    assert r["unsettled"] == [] and r["final"]["sent_hallucination_rate"] == 50.0
    assert r["final"]["hallucinating_items"] == ["V2"] and r["final"]["escalation_correct_rate"] == 100.0
    assert "re-read vs rubric" in (tmp_path / "review_results.md").read_text(encoding="utf-8")


def test_incomplete_sheet_is_reported(tmp_path):
    write(tmp_path / "assessor_A.csv", [ans("V1", c="")])
    write(tmp_path / "assessor_B.csv", [ans("V1", sup=3)])
    assert review_score.main(["--dir", str(tmp_path)]) == 1


def test_kappa_helpers():
    assert review_score.kappa(["y", "n", "y"], ["y", "n", "y"]) == 1.0
    assert review_score.weighted_kappa([5, 4, 3], [5, 4, 3]) == 1.0
    assert review_score.kappa(["y", "n"], ["n", "y"]) < 0
