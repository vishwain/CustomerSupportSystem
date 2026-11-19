"""Calibration tests (5.7, NFR-10): binning, temperature, threshold rule, config writing."""

import importlib.util
import json

import numpy as np
import pytest

from src.classify import LocalClassifier, apply_temperature, load_temperature

spec = importlib.util.spec_from_file_location("cal", "docs/calibration.py")
cal = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cal)


def test_apply_temperature_properties():
    p = np.array([[0.7, 0.2, 0.1], [0.4, 0.35, 0.25]])
    assert np.allclose(apply_temperature(p, 1.0), p)
    sharp, soft = apply_temperature(p, 0.5), apply_temperature(p, 2.0)
    assert (sharp.argmax(1) == p.argmax(1)).all() and (soft.argmax(1) == p.argmax(1)).all()
    assert (sharp.max(1) > p.max(1)).all() and (soft.max(1) < p.max(1)).all()
    assert np.allclose(sharp.sum(1), 1) and np.allclose(soft.sum(1), 1)


def test_temperature_config_used_only_when_adopted(tmp_path):
    p = tmp_path / "c.json"
    assert load_temperature(p) == 1.0
    p.write_text(json.dumps({"adopted": False, "intent_temperature": 0.5}))
    assert load_temperature(p) == 1.0
    p.write_text(json.dumps({"adopted": True, "intent_temperature": 0.5}))
    assert load_temperature(p) == 0.5
    p.write_text(json.dumps({"adopted": True, "intent_temperature": 99}))
    with pytest.raises(ValueError):
        load_temperature(p)


def test_bins_merge_small_and_keep_every_ticket():
    rng = np.random.default_rng(0)
    conf = list(np.r_[rng.uniform(0.5, 0.6, 3), rng.uniform(0.6, 0.7, 4), rng.uniform(0.9, 1.0, 50)])
    correct = [True] * len(conf)
    t = cal.bin_table(conf, correct)
    assert all(b["n"] >= cal.MIN_BIN for b in t) and sum(b["n"] for b in t) == len(conf)
    assert all(t[i]["hi"] <= t[i + 1]["lo"] + 1e-9 for i in range(len(t) - 1))


def test_gap_sign_and_pass():
    t = cal.bin_table([0.95] * 20 + [0.65] * 20, [True] * 20 + [False] * 8 + [True] * 12)
    hi = next(b for b in t if b["lo"] >= 0.9)
    lo = next(b for b in t if b["hi"] <= 0.7)
    assert hi["gap_pts"] == -5.0 and hi["pass"]  # exactly on the limit passes
    assert lo["accuracy"] == 0.6 and lo["gap_pts"] == 5.0 and lo["pass"]


def test_wilson_interval():
    lo, hi = cal.wilson(10, 10)
    assert hi == 1.0 and 0.6 < lo < 0.8


def _rows(n, conf, correct=True, eligible=True, must_not=False):
    return [{"conf": conf, "correct": correct, "eligible": eligible, "must_not": must_not,
             "expected": "auto_respond"} for _ in range(n)]


def test_threshold_rule_accuracy_target():
    rows = _rows(50, 0.97) + _rows(10, 0.62, correct=False) + _rows(10, 0.62)
    bins = cal.bin_table([r["conf"] for r in rows], [r["correct"] for r in rows])
    _, pick = cal.threshold_table(rows, bins)
    # 0.6-0.7 bin: 62% stated, 50% right -> overconfident failing bin, so t must clear the whole bin
    assert pick["threshold"] == 0.70


def test_threshold_rule_must_not_blocks():
    rows = _rows(50, 0.97) + _rows(1, 0.80, must_not=True)
    _, pick = cal.threshold_table(rows, [])
    assert pick["threshold"] == 0.81


def test_overconfident_bin_blocks_underconfident_does_not():
    over = [{"band": "0.90-0.95", "lo": 0.9, "hi": 0.95, "pass": False, "direction": "over"}]
    under = [{"band": "0.90-0.95", "lo": 0.9, "hi": 0.95, "pass": False, "direction": "under"}]
    rows = _rows(60, 0.97)
    assert cal.threshold_table(rows, under)[1]["threshold"] == 0.50
    assert cal.threshold_table(rows, over)[1]["threshold"] == 0.95


def test_end_to_end_with_fake_model(fake_embedder, tmp_path):
    from src.retrieve import CONFIGS, Retriever
    dev = json.load(open("data/development_tickets.json", encoding="utf-8"))
    val = json.load(open("data/validation_tickets.json", encoding="utf-8"))
    local = LocalClassifier(fake_embedder, model_dir=tmp_path / "m", temperature=1.0).load_or_train()
    r = cal.run(fake_embedder, Retriever(fake_embedder, CONFIGS["chars800"], 0.3), dev, val, local)
    assert r["n_oof"] == 500 and sum(b["n"] for b in r["bins"]) == 500
    routing = tmp_path / "routing.json"
    routing.write_text(json.dumps({"threshold": 1.01, "must_escalate_alt_floor": 0.15}))
    cal.write_outputs(r, tmp_path / "out", True, routing, tmp_path / "calibration.json")
    cfg = json.loads(routing.read_text())
    assert cfg["set_by"] == "calibration" and cfg["must_escalate_alt_floor"] == 0.15
    assert cfg["threshold"] == r["threshold"]
    assert (tmp_path / "out" / "calibration.md").exists() and (tmp_path / "out" / "predictions_oof.csv").exists()
