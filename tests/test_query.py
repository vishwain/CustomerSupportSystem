"""Intent-expanded query (5.13 follow-up): build_query, harness wiring, and the experiment's plumbing."""

import importlib.util
import json
from pathlib import Path

import pytest

from evaluation import harness
from src.classify import Classification
from src.ingest import normalise
from src.logging_store import DecisionLog
from src.retrieve import CONFIGS, Retriever, build_query, intent_descriptions

spec = importlib.util.spec_from_file_location("qe", Path("docs/query_experiment.py"))
qe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(qe)


def test_descriptions_cover_every_intent():
    from src.classify import INTENTS
    assert set(intent_descriptions()) == set(INTENTS)


@pytest.mark.parametrize("mode,subject,expanded", [
    ("text", "", False), ("intent", "Subject", True), ("intent", "", True),
    ("intent_if_no_subject", "Subject", False), ("intent_if_no_subject", "  ", True),
])
def test_build_query_modes(mode, subject, expanded):
    q, e = build_query("Every call returns 429.", subject, "rate_limit", mode)
    assert e is expanded
    assert q.startswith("rate limit: ") == expanded and q.endswith("Every call returns 429.")


def test_no_expansion_without_a_known_intent():
    assert build_query("x", "", None, "intent") == ("x", False)
    assert build_query("x", "", "unknown", "intent") == ("x", False)
    with pytest.raises(ValueError):
        build_query("x", "", "rate_limit", "bogus")


class StubClassifier:
    def __init__(self, intent="rate_limit"):
        self.intent = intent

    def classify(self, t, allow_llm=True):
        return Classification(self.intent, 0.99, [], "medium", 0.5, [], "local", "stub", "v")


def test_harness_logs_query_mode_and_intent(fake_embedder, tmp_path):
    r = Retriever(fake_embedder, CONFIGS["chars800"], 0.0)
    r.query_mode = "intent_if_no_subject"
    rt = tmp_path / "runtime.json"
    rt.write_text('{"automation_paused": false}', encoding="utf-8")
    from src.route import Router, RoutingConfig
    comp = harness.Components(retriever=r, classifier=StubClassifier(),
                              router=Router(RoutingConfig(threshold=0.95), runtime_path=rt))
    log = DecisionLog(tmp_path / "d.db", "r")
    for i, subj in enumerate(("", "Rate limits")):
        rec = normalise({"ticket_id": f"T-{i}", "channel": "chat", "subject": subj, "body": "429 everywhere"}, i)
        harness.process_ticket(rec, log, comp)
    rows = {x["ticket_id"]: x for x in log.rows() if x["stage"] == "retrieval"}
    assert rows["T-0"]["prediction"]["query_mode"] == "intent_if_no_subject"
    assert rows["T-0"]["prediction"]["query_intent"] == "rate_limit"
    assert rows["T-1"]["prediction"]["query_intent"] is None  # had a subject: not expanded
    assert rows["T-0"]["input_summary"].startswith("429")  # the log keeps the ticket text, not the query


class OracleClassifier:
    def __init__(self, labels):
        self.labels = labels

    def classify(self, rec, allow_llm=False):
        return Classification(self.labels.get(rec.ticket_id, "unknown"), 0.99, [], "medium", 0.5, [],
                              "local", "oracle", "v")


def test_experiment_runs_and_picks_a_mode(fake_embedder):
    load = lambda p: json.loads(Path(p).read_text(encoding="utf-8"))  # noqa: E731
    dev, val = load("data/development_tickets.json"), load("data/validation_tickets.json")
    labels = {t["ticket_id"]: t["labels"]["intent"] for t in dev + val}
    r = qe.run(dev, val, OracleClassifier(labels), Retriever(fake_embedder, CONFIGS["chars800"], 0.0))
    assert r["chosen"] in ("text", "intent", "intent_if_no_subject")
    h = r["modes"]["intent_if_no_subject"]
    assert 0 < h["expanded_share_holdout"] < 1  # only the tickets without a subject
    assert r["modes"]["intent"]["expanded_share_holdout"] == 1.0
    md = qe.to_markdown(r)
    assert "Chosen:" in md and "No subject" in md
