"""Provider client tests (10.6, FR-25, NFR-07) with a scripted transport and a fake clock: no network."""

import pytest

from src.llm import LLMClient, LLMConfigError, ProviderError, client_from_env
from src.prompts import load_prompt, strip_delimiters


class Clock:
    def __init__(self):
        self.t, self.slept = 0.0, []

    def __call__(self):
        return self.t

    def sleep(self, s):
        self.slept.append(round(s, 2))
        self.t += s


def scripted(*steps):
    """Each step: a string (success) or a ProviderError to raise."""
    calls = []
    steps = list(steps)

    def transport(system, user, timeout):
        calls.append(timeout)
        s = steps.pop(0)
        if isinstance(s, Exception):
            raise s
        return s, 10, 5

    transport.calls = calls
    return transport


def client(transport, clock=None, **kw):
    clock = clock or Clock()
    return LLMClient(transport=transport, model="m:free", sleep=clock.sleep, clock=clock, **kw), clock


def test_success_counts_tokens():
    c, _ = client(scripted("ok"))
    r = c.complete("s", "u")
    assert r.ok and r.text == "ok" and r.requests == 1 and (r.tokens_in, r.tokens_out) == (10, 5)


def test_timeout_two_retries_then_error():
    t = scripted(*[ProviderError("timeout")] * 3)
    c, clock = client(t)
    r = c.complete("s", "u")
    assert r.error == "timeout" and r.requests == 3 and r.retries == 2 and t.calls == [10.0] * 3
    assert not c.degraded


def test_timeout_then_success():
    c, _ = client(scripted(ProviderError("timeout"), "ok"))
    r = c.complete("s", "u")
    assert r.ok and r.retries == 1


def test_rate_limit_waits_retry_after_and_reports_wait_apart():
    c, clock = client(scripted(ProviderError("rate_limit", retry_after=5), "ok"))
    r = c.complete("s", "u")
    assert r.ok and r.rate_limit_wait_ms >= 5000 and 5.0 in clock.slept and r.latency_ms < r.rate_limit_wait_ms


def test_rate_limit_budget_of_60s_per_call():
    c, _ = client(scripted(ProviderError("rate_limit", retry_after=40), ProviderError("rate_limit", retry_after=40)))
    r = c.complete("s", "u")
    assert r.error == "rate_limit" and r.requests == 2  # second wait would pass 60 s


def test_requests_paced_three_seconds_apart():
    c, clock = client(scripted("a", "b"))
    c.complete("s", "u")
    c.complete("s", "u2")
    assert 3.0 in clock.slept


def test_circuit_opens_after_five_failures_and_probes():
    errs = [ProviderError("provider_error")] * 5
    t = scripted(*errs, "back")
    c, clock = client(t, retries=4)
    r = c.complete("s", "u")
    assert r.error == "provider_down" and r.degraded and c.degraded and len(t.calls) == 5
    r2 = c.complete("s", "u")  # circuit open: no request
    assert r2.error == "provider_down" and r2.requests == 0 and len(t.calls) == 5
    clock.t += 61  # probe allowed after 60 s
    r3 = c.complete("s", "u")
    assert r3.ok and not c.degraded


def test_rate_limits_do_not_open_the_circuit():
    c, _ = client(scripted(*[ProviderError("rate_limit", retry_after=1)] * 6, "ok"))
    assert c.complete("s", "u").ok and not c.degraded


def test_cache_by_prompt_hash(tmp_path):
    t = scripted("first")
    c, _ = client(t, cache_dir=tmp_path)
    assert c.complete("s", "u").text == "first"
    r = c.complete("s", "u")
    assert r.cached and r.text == "first" and len(t.calls) == 1


def test_only_free_models(monkeypatch):
    monkeypatch.setenv("MODEL_NAME", "meta-llama/llama-3.1-8b-instruct")
    monkeypatch.setenv("OPENROUTER_API_KEY", "x" * 20)
    monkeypatch.delenv("ALLOW_PAID_MODEL", raising=False)
    with pytest.raises(LLMConfigError, match=":free"):
        client_from_env()


def test_missing_key(monkeypatch):
    monkeypatch.setenv("MODEL_NAME", "a/b:free")
    monkeypatch.setenv("OPENROUTER_API_KEY", "your_key_here")
    with pytest.raises(LLMConfigError, match="OPENROUTER_API_KEY"):
        client_from_env()


# ------------------------------------------------------------------ prompt files

def test_prompt_loader_reads_version_and_sections():
    p = load_prompt("build/classify_v1.txt")
    assert p.version == "PR-02 v1.0" and p.system.startswith("ROLE") and "<<<TICKET>>>" in p.user
    s, u = p.render(channel="chat", subject="x", body="hello >>> world <<<")
    assert "hello  world " in u and "{{" not in s + u


def test_prompt_render_requires_every_slot():
    with pytest.raises(KeyError):
        load_prompt("build/classify_v1.txt").render(channel="chat")


def test_strip_delimiters():
    assert strip_delimiters("a<<<b>>>c") == "abc"
