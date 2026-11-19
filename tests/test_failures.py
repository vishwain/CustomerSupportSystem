"""5.11 failure handling (A11): every forced failure ends in an escalation with a logged reason, never a
crash, and the run still reconciles (tickets in = final rows out). No network: scripted transports."""

import json

from evaluation import harness
from src.generate import Generator, load_messages
from src.ingest import load, normalise
from src.llm import LLMClient, ProviderError
from src.logging_store import DecisionLog
from src.route import Router, RoutingConfig
from tests.test_generate import PASSAGES, StubClassifier, StubRetriever, answer


def ticket(**over):
    t = {"ticket_id": "T-1", "channel": "email", "subject": "429s", "body": "Every call returns 429.",
         "received_at": "2026-11-19T09:00:00Z", "customer_id": "CUST-1", "customer_name": "N"}
    t.update(over)
    return normalise(t, 0)


class ScriptedTransport:
    """Raises or returns in order; counts calls."""

    def __init__(self, script):
        self.script, self.calls = list(script), 0

    def __call__(self, system, user, timeout_s):
        self.calls += 1
        step = self.script.pop(0) if self.script else self.script_last
        if isinstance(step, Exception):
            raise step
        return step, 10, 10

    script_last = ProviderError("timeout", "still down")


def client(script, cache_dir=None):
    t = ScriptedTransport(script)
    c = LLMClient(transport=t, model="fake/model:free", timeout_s=0.01, min_interval_s=0, retries=2,
                  cache_dir=cache_dir, sleep=lambda s: None)
    return c, t


def comp(tmp_path, llm, passages=PASSAGES):
    rt = tmp_path / "runtime.json"
    rt.write_text('{"automation_paused": false}', encoding="utf-8")
    return harness.Components(retriever=StubRetriever(passages), classifier=StubClassifier("rate_limit", 0.99),
                              router=Router(RoutingConfig(threshold=0.95), runtime_path=rt),
                              generator=Generator(llm), messages=load_messages())


def finals(log, tid):
    return [r for r in log.rows(tid) if r["stage"] == "final"]


# ------------------------------------------------------------------ 1. no retrieval hit

def test_no_supporting_passage_escalates_without_draft_or_call(tmp_path):
    llm, t = client([answer()])
    log = DecisionLog(tmp_path / "d.db", "r")
    r = harness.process_ticket(ticket(), log, comp(tmp_path, llm, passages=[]))
    assert r["action"] == "escalate" and r["rule_fired"] == "no_retrieval_hit" and t.calls == 0
    assert "no supporting passage" in r["reason"] and r["escalation_package"]["draft"] == ""
    assert len(finals(log, "T-1")) == 1


# ------------------------------------------------------------------ 2. timeout / outage / bad key

def test_timeout_retries_then_escalates_with_provider_reason(tmp_path):
    llm, t = client([ProviderError("timeout", "read timed out")] * 3)
    log = DecisionLog(tmp_path / "d.db", "r")
    r = harness.process_ticket(ticket(), log, comp(tmp_path, llm))
    assert t.calls == 3  # 1 + 2 retries, then stop
    assert r["action"] == "escalate" and r["error"] == "timeout" and r["rule_fired"] == "provider_timeout"
    assert "provider failed (timeout) after 3 request(s)" in r["reason"]
    gen_row = [x for x in log.rows("T-1") if x["stage"] == "generation"][0]
    assert gen_row["error"] == "timeout" and gen_row["requests"] == 3


def test_bad_key_does_not_retry_and_opens_the_circuit(tmp_path):
    llm, t = client([ProviderError("provider_config", "AuthenticationError (status 401)")])
    log = DecisionLog(tmp_path / "d.db", "r")
    c = comp(tmp_path, llm)
    r1 = harness.process_ticket(ticket(ticket_id="T-1"), log, c)
    r2 = harness.process_ticket(ticket(ticket_id="T-2"), log, c)
    assert t.calls == 1  # no retry on a permanent error, and no request for the next ticket
    for r in (r1, r2):
        assert r["action"] == "escalate" and r["error"] == "provider_down" and r["degraded_mode"]
        assert r["rule_fired"] == "provider_down"
    assert "401" in r1["reason"] and "circuit open" in r2["reason"]


def test_outage_opens_circuit_after_five_failures_and_run_continues(tmp_path):
    llm, t = client([ProviderError("provider_error", "503")] * 10)
    log = DecisionLog(tmp_path / "d.db", "r")
    c = comp(tmp_path, llm)
    rs = [harness.process_ticket(ticket(ticket_id=f"T-{i}"), log, c) for i in range(4)]
    assert all(r["action"] == "escalate" for r in rs)
    assert t.calls == 5  # 3 for the first ticket, 2 more open the circuit, then no requests at all
    assert rs[-1]["error"] == "provider_down"


# ------------------------------------------------------------------ 3. rate limit + cache

def test_rate_limit_backs_off_then_succeeds(tmp_path):
    llm, t = client([ProviderError("rate_limit", "429", retry_after=2), ProviderError("rate_limit", "429", 2),
                     answer()])
    r = harness.process_ticket(ticket(), DecisionLog(tmp_path / "d.db", "r"), comp(tmp_path, llm))
    assert t.calls == 3 and r["generation"]["gen_action"] == "answer"


def test_rate_limit_past_the_wait_budget_escalates(tmp_path):
    llm, t = client([ProviderError("rate_limit", "429", retry_after=90)])
    r = harness.process_ticket(ticket(), DecisionLog(tmp_path / "d.db", "r"), comp(tmp_path, llm))
    assert r["action"] == "escalate" and r["error"] == "rate_limit" and t.calls == 1


def test_rerun_hits_the_cache_and_spends_no_calls(tmp_path):
    cache = tmp_path / "cache"
    llm1, t1 = client([answer()], cache_dir=cache)
    r1 = harness.process_ticket(ticket(), DecisionLog(tmp_path / "a.db", "a"), comp(tmp_path, llm1))
    llm2, t2 = client([], cache_dir=cache)  # would time out if it were called
    r2 = harness.process_ticket(ticket(), DecisionLog(tmp_path / "b.db", "b"), comp(tmp_path, llm2))
    assert t1.calls == 1 and t2.calls == 0 and r2["generation"]["cached"]
    assert r1["generation"]["draft"] == r2["generation"]["draft"]


def test_cache_misses_when_ticket_text_changes(tmp_path):
    cache = tmp_path / "cache"
    llm1, _ = client([answer()], cache_dir=cache)
    harness.process_ticket(ticket(), DecisionLog(tmp_path / "a.db", "a"), comp(tmp_path, llm1))
    llm2, t2 = client([answer()], cache_dir=cache)
    harness.process_ticket(ticket(body="Every call returns 429 since noon."), DecisionLog(tmp_path / "b.db", "b"),
                           comp(tmp_path, llm2))
    assert t2.calls == 1


def test_corrupt_cache_entry_is_ignored(tmp_path):
    cache = tmp_path / "cache"
    llm1, _ = client([answer()], cache_dir=cache)
    harness.process_ticket(ticket(), DecisionLog(tmp_path / "a.db", "a"), comp(tmp_path, llm1))
    for f in cache.glob("*.json"):
        f.write_text("{not json", encoding="utf-8")
    llm2, t2 = client([answer()], cache_dir=cache)
    r = harness.process_ticket(ticket(), DecisionLog(tmp_path / "b.db", "b"), comp(tmp_path, llm2))
    assert t2.calls == 1 and r["generation"]["gen_action"] == "answer"


# ------------------------------------------------------------------ 4. malformed input and output

def test_broken_model_json_escalates_as_bad_output(tmp_path):
    llm, _ = client(["{not json", "still {not json"])
    r = harness.process_ticket(ticket(), DecisionLog(tmp_path / "d.db", "r"), comp(tmp_path, llm))
    assert r["action"] == "escalate" and r["error"] == "bad_output"


def test_failure_fixture_file_reconciles(tmp_path):
    out = tmp_path / "out"
    code = harness.main(["--input", "tests/fixtures/failure_tickets.json", "--output", str(out),
                         "--storage", str(tmp_path / "s"), "--quiet", "--no-models", "--no-llm"])
    rec = json.loads((out / "reconcile.json").read_text(encoding="utf-8"))
    res = [json.loads(x) for x in (out / "results.jsonl").read_text(encoding="utf-8").splitlines()]
    raw = json.loads(open("tests/fixtures/failure_tickets.json", encoding="utf-8").read())
    assert code == 0 and rec["ok"] and rec["final_rows"] == len(raw) == len(res)
    assert all(r["action"] == "escalate" and r["reason"] for r in res)
    by = {r["ticket_id"]: r for r in res}
    for tid in ("FAIL-EMPTY", "FAIL-SPACES", "FAIL-NOBODY", "FAIL-NULLBODY", "FAIL-ZEROWIDTH", "FAIL-GARBLED"):
        assert by[tid]["error"] == "malformed_input", tid


def test_non_utf8_file_is_read_with_flags_not_rejected(tmp_path):
    p = tmp_path / "cp1252.json"
    body_ok = "Caf\xe9 billing question: why is the invoice higher this month?"  # one bad byte
    garbled = "\xe9\xe8\xe0\xf9\xe7\xe9\xe8\xe0"  # nothing but undecodable bytes
    data = json.dumps([{"ticket_id": "A", "channel": "email", "body": body_ok},
                       {"ticket_id": "B", "channel": "email", "body": garbled}], ensure_ascii=False)
    p.write_bytes(data.encode("cp1252"))
    a, b = load(p)
    assert a.ok and a.flags.get("replacement_chars")
    assert not b.ok and "unreadable" in b.ingest_reason


def test_utf16_file_with_bom_is_read(tmp_path):
    p = tmp_path / "u16.json"
    p.write_bytes(json.dumps([{"ticket_id": "A", "channel": "chat", "body": "hello"}]).encode("utf-16"))
    (a,) = load(p)
    assert a.ok and a.body == "hello"


def test_failure_drill_report_from_harness_outputs(tmp_path):
    """The drill's report and checks run on real harness output (no models, no provider)."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("drill", "docs/failure_drill.py")
    drill = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(drill)
    out = tmp_path / "out"
    harness.main(["--input", drill.FIXTURE, "--output", str(out), "--storage", str(tmp_path / "s"),
                  "--quiet", "--no-models", "--no-llm"])
    res = [json.loads(x) for x in (out / "results.jsonl").read_text(encoding="utf-8").splitlines()]
    met = json.loads((out / "metrics_report.json").read_text(encoding="utf-8"))
    runs = [{"name": n, "exit": 0, "wall_s": 1.0, "reconcile_ok": True, "final_rows": len(res), "results": res,
             "metrics": met, "stderr_tail": []} for n in ("normal", "rerun", "bad_key", "timeout")]
    md, ok = drill.to_markdown(runs)
    assert ok and "PASS: rerun spends no provider calls" in md and "FAIL-NODOCS-1" in md
