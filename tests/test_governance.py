"""5b: fairness interval maths and the guardrail-evidence case loader."""
import importlib.util
from pathlib import Path

from evaluation.fairness_audit import gap_interval, wilson


def test_wilson_bounds():
    lo, hi = wilson(19, 21)
    assert 0.6 < lo < 0.9047 < hi <= 1.0
    assert wilson(0, 0) == (0.0, 1.0)


def test_gap_interval_contains_point_and_flags_small_samples():
    d, lo, hi = gap_interval(19, 21, 15, 19)
    assert lo < d < hi
    assert lo < 5 < hi  # an 11.5-pt gap at n=19-21 is not established


def test_guardrail_demo_cases_load():
    p = Path("docs/guardrail_evidence.py")
    spec = importlib.util.spec_from_file_location("ge", p)
    ge = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ge)
    cs = ge.demo_cases()
    assert {"B-pii", "E-unsupported", "H-low-confidence"} <= set(cs)
