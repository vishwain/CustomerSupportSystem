"""PR-03 v2 support: whole-article retrieval context, prompt selection, and the v1-vs-v2 evaluation logic."""

import importlib.util
import json

from src.generate import Generator, prompt_from_config
from src.llm import LLMResult
from src.prompts import load_prompt
from src.retrieve import CONFIGS, Retriever
from tests.test_generate import FakeClient, answer, ticket

spec = importlib.util.spec_from_file_location("geval", "docs/generate_eval.py")
geval = importlib.util.module_from_spec(spec)
spec.loader.exec_module(geval)


def test_context_adds_rest_of_article_without_changing_hits(fake_embedder):
    plain = Retriever(fake_embedder, CONFIGS["chars800"], cutoff=0.3)
    ctx = Retriever(fake_embedder, CONFIGS["chars800"], cutoff=0.3, expand_docs=2)
    q = "container health check timeout rolls back after deployment"
    a, b = plain.retrieve(q), ctx.retrieve(q)
    assert [p.passage_id for p in a.passages] == [p.passage_id for p in b.passages]  # Route sees the same
    assert a.context == [] and b.context
    top_docs = []
    for p in b.passages:
        if p.doc_id not in top_docs:
            top_docs.append(p.doc_id)
    assert {p.doc_id for p in b.context} <= set(top_docs[:2])
    assert not {p.passage_id for p in b.context} & {p.passage_id for p in b.passages}
    assert all(p.score is not None for p in b.context)


def test_no_context_when_nothing_passes(fake_embedder):
    r = Retriever(fake_embedder, CONFIGS["chars800"], cutoff=0.99, expand_docs=2).retrieve("dark mode please")
    assert r.passages == [] and r.context == []


def test_context_passages_are_citable(fake_embedder):
    ret = Retriever(fake_embedder, CONFIGS["chars800"], cutoff=0.3, expand_docs=2)
    res = ret.retrieve("container health check timeout rolls back after deployment")
    pid = res.context[0].passage_id
    g = Generator(FakeClient([answer(ids=(pid,)).replace("DOC-API-001#c01", pid)])).generate(
        ticket(), "deployment_failure", res.for_generation, "answer")
    assert g.citations_ok and pid in g.cited


def test_v2_prompt_loads_and_renders():
    p = load_prompt("build/generate_v2.txt")
    assert p.version == "PR-03 v2.0" and "WHAT AN ANSWER IS" in p.system and "up to nine" in p.system
    s, u = p.render(mode="answer", intent="x", channel="chat", subject="(empty)", body="b", passages="[A#c00] t / s\ntext")
    assert "{{" not in s + u


def test_prompt_selection_from_config(tmp_path):
    assert prompt_from_config(tmp_path / "missing.json") == "build/generate_v1.txt"
    p = tmp_path / "g.json"
    p.write_text(json.dumps({"prompt": "build/generate_v2.txt"}))
    assert prompt_from_config(p) == "build/generate_v2.txt"
    assert Generator(FakeClient([]), prompt_path="build/generate_v2.txt").prompt.version == "PR-03 v2.0"


def _row(expected, send_ready, actionable=False, error="none", can_answer=True):
    return {"expected": expected, "send_ready": send_ready, "actionable": actionable, "error": error,
            "can_answer": can_answer, "avg_words": 12.0, "max_words": 20, "sentences": 3, "requests": 1,
            "retries": 0, "wait_s": 0.0}


def test_summary_and_decision_rule():
    v1 = [_row("auto_respond", True), _row("auto_respond", True), _row("escalate", True), _row("escalate", True)]
    v2 = [_row("auto_respond", True, True), _row("auto_respond", True, True), _row("escalate", False, can_answer=False),
          _row("escalate", True, True)]
    s1, s2 = geval.summarise(v1), geval.summarise(v2)
    assert s1["precision"] == 0.5 and round(s2["precision"], 3) == 0.667 and s2["escalate_refused"] == 1
    ok, why = geval.decide(s1, s2)
    assert ok and why.startswith("v2 adopted")
    v2_bad = [_row("auto_respond", False, can_answer=False)] * 2 + [_row("escalate", True, True)] * 2
    assert not geval.decide(s1, geval.summarise(v2_bad))[0]


def test_run_arm_uses_context_only_for_v2(fake_embedder):
    ret = Retriever(fake_embedder, CONFIGS["chars800"], cutoff=0.3, expand_docs=2)
    res = ret.retrieve("container health check timeout rolls back after deployment")
    item = {"rec": ticket(), "cls": type("C", (), {"intent": "deployment_failure"})(), "res": res,
            "labels": {"expected_route": "auto_respond", "answerable_from_docs": True}}
    pid = res.passages[0].passage_id
    out = answer(ids=(pid,)).replace("DOC-API-001#c01", pid)
    r1 = geval.run_arm(Generator(FakeClient([out]), prompt_path="build/generate_v1.txt"), [item], False)
    r2 = geval.run_arm(Generator(FakeClient([out]), prompt_path="build/generate_v2.txt"), [item], True)
    assert r1[0]["passages_shown"] == len(res.passages) < r2[0]["passages_shown"] == len(res.for_generation)
    assert r1[0]["send_ready"] and r2[0]["send_ready"]


def test_provider_error_counts_as_not_send_ready(fake_embedder):
    ret = Retriever(fake_embedder, CONFIGS["chars800"], cutoff=0.3)
    res = ret.retrieve("container health check timeout rolls back after deployment")
    item = {"rec": ticket(), "cls": type("C", (), {"intent": "x"})(), "res": res,
            "labels": {"expected_route": "auto_respond", "answerable_from_docs": True}}
    rows = geval.run_arm(Generator(FakeClient([LLMResult(text=None, error="timeout")])), [item], False)
    s = geval.summarise(rows)
    assert s["send_ready"] == 0 and s["answerable_lost"] == 1 and s["other_errors"] == {"timeout": 1}
