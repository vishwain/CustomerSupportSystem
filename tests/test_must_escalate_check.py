"""Plumbing test for docs/must_escalate_check.py (5.10). Real numbers come from the real model."""

import importlib.util
import json

import pytest
from pathlib import Path

from src.classify import Classification
from src.retrieve import Passage, RetrievalResult

spec = importlib.util.spec_from_file_location("mec", Path("docs/must_escalate_check.py"))
mec = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mec)

P = Passage("DOC-API-001#c00", "DOC-API-001", "t", "s", "x", "x", 0, 0.7)


class OracleClassifier:
    """Predicts the label (or 'rate_limit' for fixtures), with a little must-escalate mass."""

    def __init__(self, labels):
        self.labels = labels

    def classify(self, rec, allow_llm=False):
        lab = self.labels.get(rec.ticket_id, "rate_limit")
        dist = {lab: 0.97, "security_incident" if lab != "security_incident" else "rate_limit": 0.03}
        return Classification(lab, 0.97, [{"label": k, "confidence": v} for k, v in dist.items() if k != lab],
                              "medium", 0.5, [], "local", "oracle", "t", intent_distribution=dist)


class HitRetriever:
    def retrieve(self, text):
        return RetrievalResult([P], [P], 0.47, 0.7, "found")


def test_run_reports_coverage_floor_and_fixtures(tmp_path):
    load = lambda p: json.loads(Path(p).read_text(encoding="utf-8"))  # noqa: E731
    dev, val = load("data/development_tickets.json"), load("data/validation_tickets.json")
    fx = load("tests/fixtures/must_escalate_tickets.json")
    labels = {t["ticket_id"]: t["labels"]["intent"] for t in dev + val}
    rt = tmp_path / "runtime.json"
    rt.write_text('{"automation_paused": false}', encoding="utf-8")
    r = mec.run(dev, val, fx, OracleClassifier(labels), HitRetriever(), rt)
    for part in ("dev_holdout", "validation"):
        assert r[part]["must_auto_or_draft"] == []  # oracle intent: the intent rule catches every one
        assert {t["floor"] for t in r[part]["floor_table"]} == set(mec.GRID)
    # every safe ticket carries mass 0.03, so the lowest floor costing <= 1% sits just above it
    assert r["floor_pick"]["floor"] == 0.05 and r["floor_pick"]["escalated"] == 0
    by = {x["ticket_id"]: x for x in r["fixtures"]}
    # fixtures are classified rate_limit here, so only text rules can catch them
    assert by["MUST-DSP-03"]["rule"] == "billing_dispute"
    assert by["MUST-SEC-02"]["rule"] == "risk_terms:security"
    assert by["MUST-CMP-02"]["rule"] == "risk_terms:legal"
    assert by["MUST-RES-02"]["rule"] == "risk_terms:residency"
    assert by["MUST-FEA-02"]["action"] == "auto_respond"  # no keyword: depends on the real classifier
    md = mec.to_markdown(r)
    assert "Floor = 0.05" in md and "NOT ALL ENGINEERED TICKETS ESCALATED" in md


def test_pick_floor_sits_above_every_safe_mass():
    fp = mec.pick_floor([0.0001] * 190 + [0.002] * 8 + [0.0062, 0.0088])
    assert fp["floor"] == 0.01 and fp["escalated"] == 0
    assert fp["mass_percentiles"]["max"] == 0.0088


@pytest.mark.parametrize("x,want", [(0.0088, 0.01), (0.01, 0.02), (0.03, 0.05), (0.0, 0.0001), (0.004, 0.005)])
def test_next_125(x, want):
    assert mec.next_125(x) == want


def test_wilson_upper_bound_is_informative_when_nothing_fires():
    assert 0.06 < mec.wilson_upper(0, 58) < 0.07  # 0 of 58 still allows ~6%
    assert mec.wilson_upper(0, 343) < 0.012


def test_oof_rows_route_with_the_full_distribution(tmp_path):
    import numpy as np
    from src.ingest import normalise
    from src.route import Router, RoutingConfig
    dev = json.loads(Path("data/development_tickets.json").read_text(encoding="utf-8"))[:3]
    classes = ["feature_request", "rate_limit", "security_incident"]
    P = np.array([[0.02, 0.97, 0.01], [0.10, 0.85, 0.05], [0.0, 0.0, 1.0]])

    def oof_fn(raw):
        return {"recs": [(normalise(t, i), t) for i, t in enumerate(raw)], "P": P, "classes": classes}

    rt = tmp_path / "runtime.json"
    rt.write_text('{"automation_paused": false}', encoding="utf-8")
    off = Router(RoutingConfig(threshold=0.95, must_escalate_alt_floor=2.0), runtime_path=rt)
    rows = mec.oof_rows(dev, HitRetriever(), off, 1.0, oof_fn)
    assert [r["layers"]["alternative_mass"] for r in rows] == [0.03, 0.15, 0.0]  # top class excluded
    assert rows[2]["rule_guard_off"] == "must_escalate_intent:security_incident"


def test_run_with_oof_basis(tmp_path):
    import numpy as np
    from src.ingest import normalise
    load = lambda p: json.loads(Path(p).read_text(encoding="utf-8"))  # noqa: E731
    dev, val = load("data/development_tickets.json"), load("data/validation_tickets.json")
    labels = {t["ticket_id"]: t["labels"]["intent"] for t in dev + val}
    classes = sorted({t["labels"]["intent"] for t in dev})

    def oof_fn(raw):
        recs = [(normalise(t, i), t) for i, t in enumerate(raw)]
        P = np.full((len(recs), len(classes)), 0.0)
        for j, (_, t) in enumerate(recs):
            P[j, classes.index(t["labels"]["intent"])] = 0.99
            P[j, classes.index("feature_request" if t["labels"]["intent"] != "feature_request" else "rate_limit")] = 0.01
        return {"recs": recs, "P": P, "classes": classes}

    rt = tmp_path / "runtime.json"
    rt.write_text('{"automation_paused": false}', encoding="utf-8")
    r = mec.run(dev, val, [], OracleClassifier(labels), HitRetriever(), rt, oof_fn=oof_fn)
    assert r["dev_oof"]["n"] == 500 and r["floor_pick"]["floor"] == 0.05  # basis max 0.03 (hold-out oracle), OOF stub 0.01
    assert "OOF would-be auto" in mec.to_markdown(r)
