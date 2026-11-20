"""5b.6 kill switch: CLI writes the flag with who and why, every change is audited, and a ticket already
past Route when the switch is flipped is not sent (it escalates with its answer kept as a draft)."""

import json

from evaluation import harness
from src import killswitch
from src.guardrails import GuardrailConfig, Validator
from src.ingest import normalise
from src.logging_store import DecisionLog
from src.route import automation_paused
from tests.test_a12 import components, ticket
from tests.test_generate import FakeClient, answer


def test_cli_on_off_audited(tmp_path, monkeypatch):
    rt = tmp_path / "runtime.json"
    rt.write_text('{"automation_paused": false}', encoding="utf-8")
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path / "s"))
    assert killswitch.main(["on", "--by", "Marcus", "--reason", "incident 1", "--file", str(rt)]) == 0
    assert automation_paused(rt) == (True, "")
    assert json.loads(rt.read_text())["changed_by"] == "Marcus"
    assert killswitch.main(["off", "--by", "Marcus", "--reason", "fixed", "--file", str(rt)]) == 0
    lines = [json.loads(x) for x in (tmp_path / "s" / "killswitch_audit.jsonl").read_text().splitlines()]
    assert [(x["before"], x["after"]) for x in lines] == [(False, True), (True, False)]


def test_cli_refuses_change_without_who_and_why(tmp_path):
    rt = tmp_path / "runtime.json"
    rt.write_text('{"automation_paused": false}', encoding="utf-8")
    assert killswitch.main(["on", "--file", str(rt)]) == 2
    assert automation_paused(rt) == (False, "")


def test_in_flight_ticket_not_sent_when_switch_flipped(tmp_path, fake_embedder):
    comp = components(tmp_path, FakeClient([answer()]),
                      validator=Validator(fake_embedder, GuardrailConfig(grounding_floor=0.0)))
    real = comp.generator.generate

    def flip_mid_flight(*a, **k):
        res = real(*a, **k)
        comp.router.runtime_path.write_text('{"automation_paused": true}', encoding="utf-8")
        return res

    comp.generator.generate = flip_mid_flight
    log = DecisionLog(tmp_path / "d.db", "r")
    r = harness.process_ticket(normalise(ticket(), 0), log, comp)
    assert r["route_action"] == "auto_respond"  # Route chose to answer before the flip
    assert r["action"] == "escalate" and r["rule_fired"] == "kill_switch_at_send" and r["reply"] is None
    assert r["escalation_package"]["draft"]  # the validated answer goes to the agent, not lost
    assert [x["stage"] for x in log.rows("T-1")].count("final") == 1


def test_trace_finds_sent_answers_and_ticket_rows(tmp_path, fake_embedder):
    from src import trace
    comp = components(tmp_path, FakeClient([answer()]),
                      validator=Validator(fake_embedder, GuardrailConfig(grounding_floor=0.0)))
    log = DecisionLog(tmp_path / "d.db", "r")
    harness.process_ticket(normalise(ticket(), 0), log, comp)
    log.close()
    con = trace.connect(tmp_path / "d.db")
    assert [r["stage"] for r in trace.ticket_rows(con, "T-1")][-1] == "final"
    hits = trace.sent(con, "2000-01-01", doc="DOC-API-001")
    assert [h["ticket_id"] for h in hits] == ["T-1"]
    assert trace.sent(con, "2000-01-01", doc="DOC-NONE") == []


def test_fail_closed_escalation_still_gets_holding_message(tmp_path):
    r = harness.process_ticket(normalise(ticket(body="", subject=""), 0), DecisionLog(tmp_path / "d.db", "r"),
                               components(tmp_path, FakeClient([])))
    assert r["action"] == "escalate" and r["customer_message"]


def test_repeat_ticket_in_same_run_fails_closed_with_holding_message(tmp_path, fake_embedder):
    comp = components(tmp_path, FakeClient([answer(), answer()]),
                      validator=Validator(fake_embedder, GuardrailConfig(grounding_floor=0.0)))
    log = DecisionLog(tmp_path / "d.db", "r")
    harness.process_ticket(normalise(ticket(), 0), log, comp)
    r = harness.process_ticket(normalise(ticket(), 0), log, comp)  # same (run, ticket): final row refused
    assert r["log_written"] is False and r["action"] == "escalate" and r["reply"] is None
    assert r["customer_message"]
