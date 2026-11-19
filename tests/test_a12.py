"""A12 acceptance: one test per required area, end to end through the harness where it matters.
Model calls are scripted (FakeClient, scripted transports, FakeEmbedder): no API key, no network.
The detailed tests for each area live in the other test files; README "Tests" maps them."""

import json

import pytest

from evaluation import gate_check, harness
from src.classify import Classification
from src.generate import Generator, load_messages
from src.guardrails import GuardrailConfig, Validator
from src.ingest import CHANNELS, load, normalise
from src.llm import LLMClient, ProviderError
from src.logging_store import DecisionLog
from src.route import MUST_ESCALATE_INTENTS, Router, RoutingConfig
from tests.test_generate import PASSAGES, FakeClient, StubRetriever, answer


def ticket(tid="T-1", channel="email", **over):
    t = {"ticket_id": tid, "channel": channel, "subject": "429s", "body": "Every call returns 429.",
         "received_at": "2026-11-19T09:00:00Z", "customer_id": "CUST-1", "customer_name": "Ana Lima"}
    t.update(over)
    return t


class Classifier:
    def __init__(self, intent="rate_limit", conf=0.99):
        self.intent, self.conf = intent, conf

    def classify(self, t, allow_llm=True):
        return Classification(self.intent, self.conf, [{"label": "api_key_issue", "confidence": 0.001}],
                              "medium", 0.6, [], "local", "stub", "v")


def components(tmp_path, llm, intent="rate_limit", validator=None, passages=PASSAGES):
    rt = tmp_path / "runtime.json"
    rt.write_text('{"automation_paused": false}', encoding="utf-8")
    return harness.Components(retriever=StubRetriever(passages), classifier=Classifier(intent),
                              router=Router(RoutingConfig(threshold=0.95), runtime_path=rt),
                              generator=Generator(llm), messages=load_messages(), validator=validator)


def stages(log, tid):
    return [r["stage"] for r in log.rows(tid)]


# 1. Ingest normalisation for each channel ------------------------------------------------------

@pytest.mark.parametrize("channel", CHANNELS)
def test_ingest_normalises_each_channel(channel):
    r = normalise(ticket(channel=channel.upper() + " ", subject="  Help ", body="Line one\r\nline two\x07"), 0)
    assert r.ok and r.channel == channel
    assert r.text == "Help\n\nLine one\nline two"  # trimmed, CRLF folded, control character removed
    assert set(r.model_view()) == {"ticket_id", "channel", "subject", "body", "received_at", "text"}
    assert "Ana Lima" not in json.dumps(r.model_view())  # customer name held for Validate only (FR-03)


# 2. Routing rule, including must_not_auto_respond ----------------------------------------------

@pytest.mark.parametrize("intent", MUST_ESCALATE_INTENTS)
def test_must_not_auto_respond_class_escalates_with_no_model_call(tmp_path, intent):
    llm = FakeClient([answer()])
    log = DecisionLog(tmp_path / "d.db", "r")
    r = harness.process_ticket(normalise(ticket(), 0), log, components(tmp_path, llm, intent=intent))
    assert r["action"] == "escalate" and r["rule_fired"] == f"must_escalate_intent:{intent}"
    assert llm.calls == [] and "generation" not in stages(log, "T-1")
    assert r["escalation_package"]["passages"] != "none found"  # the agent still gets the sources


def test_safe_class_above_threshold_routes_to_auto(tmp_path):
    rt = tmp_path / "runtime.json"
    rt.write_text('{"automation_paused": false}', encoding="utf-8")
    d = Router(RoutingConfig(threshold=0.95), runtime_path=rt).decide(
        "Every call returns 429.", Classifier().classify(None), StubRetriever(PASSAGES).retrieve("x"))
    assert d.action == "auto_respond" and d.rule_fired == "none"


# 3. A guardrail that blocks --------------------------------------------------------------------

def test_guardrail_blocks_private_data_and_nothing_is_sent(tmp_path, fake_embedder):
    leak = answer(answer_sentences=[{"text": "Ana Lima, your limit is per organisation.",
                                     "passage_ids": ["DOC-API-001#c01"]}])
    v = Validator(fake_embedder, GuardrailConfig(grounding_floor=0.0))
    log = DecisionLog(tmp_path / "d.db", "r")
    r = harness.process_ticket(normalise(ticket(), 0), log, components(tmp_path, FakeClient([leak]), validator=v))
    assert r["action"] == "escalate" and r["reply"] is None and r["rule_fired"] == "guardrail:private_data"
    val = [x for x in log.rows("T-1") if x["stage"] == "validation"][0]
    assert val["action_taken"] == "block" and val["guardrail_results"]["private_data"] == "block"
    assert "Ana Lima" not in json.dumps(log.rows("T-1"))  # the leaked value is not written to the log


# 4. Failure handling ---------------------------------------------------------------------------

def test_provider_timeout_escalates_with_reason_and_log_row(tmp_path):
    calls = []

    def transport(system, user, timeout_s):
        calls.append(1)
        raise ProviderError("timeout", "read timed out")

    llm = LLMClient(transport=transport, model="test/model:free", min_interval_s=0, sleep=lambda s: None)
    log = DecisionLog(tmp_path / "d.db", "r")
    r = harness.process_ticket(normalise(ticket(), 0), log, components(tmp_path, llm))
    assert len(calls) == 3 and r["action"] == "escalate" and r["error"] == "timeout"
    assert "provider failed (timeout)" in r["reason"]
    assert stages(log, "T-1")[-1] == "final"


def test_empty_ticket_escalates_without_a_model_call(tmp_path):
    llm = FakeClient([answer()])
    log = DecisionLog(tmp_path / "d.db", "r")
    r = harness.process_ticket(normalise(ticket(body="   "), 0), log, components(tmp_path, llm))
    assert r["action"] == "escalate" and r["error"] == "malformed_input" and llm.calls == []


# 5. Citation resolution ------------------------------------------------------------------------

def test_citations_resolve_to_retrieved_passages(tmp_path, fake_embedder):
    v = Validator(fake_embedder, GuardrailConfig(grounding_floor=0.0))
    r = harness.process_ticket(normalise(ticket(), 0), DecisionLog(tmp_path / "d.db", "r"),
                               components(tmp_path, FakeClient([answer()]), validator=v))
    assert r["action"] == "auto_respond" and r["generation"]["cited"] == ["DOC-API-001#c01"]
    assert "(DOC-API-001)" in r["reply"]  # the source list is built from the resolved passage


def test_citation_to_an_unretrieved_passage_escalates(tmp_path, fake_embedder):
    bad = FakeClient([answer(ids=("DOC-SEC-001#c00",)), answer(ids=("DOC-SEC-001#c00",))])
    v = Validator(fake_embedder, GuardrailConfig(grounding_floor=0.0))
    r = harness.process_ticket(normalise(ticket(), 0), DecisionLog(tmp_path / "d.db", "r"),
                               components(tmp_path, bad, validator=v))
    assert r["action"] == "escalate" and r["rule_fired"] == "citation_check" and r["reply"] is None


# 6. Decision-log coverage ----------------------------------------------------------------------

def test_every_ticket_has_exactly_one_final_row(tmp_path):
    p = tmp_path / "mixed.jsonl"
    lines = [json.dumps(ticket("A-1")), "{broken", json.dumps(ticket("A-2", body="")),
             json.dumps(ticket("A-1")), json.dumps(ticket("A-3", channel="forum"))]
    p.write_text("\n".join(lines), encoding="utf-8")
    out = tmp_path / "out"
    assert harness.main(["--input", str(p), "--output", str(out), "--storage", str(tmp_path / "s"),
                         "--quiet", "--no-models", "--no-llm"]) == 0
    rec = json.loads((out / "reconcile.json").read_text(encoding="utf-8"))
    assert rec["ok"] and rec["final_rows"] == 5 and rec["rows_with_empty_required_field"] == 0
    assert gate_check.main(["--run-dir", str(out)]) == 0  # independent check from the SQLite log
    assert len(load(p)) == 5


def test_redact_removes_names_and_patterns():
    from src.pii import redact
    assert redact("Hi ana lima, mail ana@x.io", {"Ana Lima"}) == "Hi [REDACTED:customer], mail [REDACTED:email]"
