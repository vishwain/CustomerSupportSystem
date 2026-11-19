"""Retrieve tests (A4, FR-08, FR-09, FR-10) and the dev split. Offline: FakeEmbedder, in-memory Chroma."""

import importlib.util
import json

import pytest

from evaluation import harness
from src.ingest import normalise
from src.logging_store import DecisionLog
from src.retrieve import CONFIGS, Retriever, chunk_docs, load_config, load_docs
from src.splits import dev_holdout_split, text_key

DOCS = load_docs()
DOC_TEXT = {d["doc_id"]: d["content"] for d in DOCS}


@pytest.mark.parametrize("name", list(CONFIGS))
def test_every_passage_traces_to_its_source_article(name):
    passages = chunk_docs(DOCS, CONFIGS[name])
    assert len({p.passage_id for p in passages}) == len(passages)
    for p in passages:
        assert p.passage_id.startswith(p.doc_id + "#")
        assert p.text.strip() and p.text in DOC_TEXT[p.doc_id]  # FR-08: id resolves to real text


def test_section_config_gives_four_passages_per_article():
    passages = chunk_docs(DOCS, CONFIGS["section"])
    assert len(passages) == 4 * len(DOCS) == 116
    assert {p.section for p in passages} == {"Symptoms", "Common causes", "Resolution", "Notes"}
    assert "DOC-AUTH-001#resolution" in {p.passage_id for p in passages}


def test_char_configs_differ_in_size():
    big, small = (chunk_docs(DOCS, CONFIGS[n]) for n in ("chars800", "chars400"))
    assert len(small) > len(big) and max(len(p.text) for p in small) <= 400


def test_retrieve_ranks_and_carries_review_age(fake_embedder):
    r = Retriever(fake_embedder, CONFIGS["section"], cutoff=0.0, top_k=5)
    res = r.retrieve("container health check timeout rolls back after deployment")
    assert res.hit and len(res.passages) == 5
    assert res.passages[0].doc_id == "DOC-DEPLOY-001"
    scores = [p.score for p in res.passages]
    assert scores == sorted(scores, reverse=True)
    assert res.passages[0].public()["reviewed_label"] == "reviewed today"  # FR-10 (all 29 articles have 0)


def test_nothing_returned_when_no_passage_clears_cutoff(fake_embedder):
    r = Retriever(fake_embedder, CONFIGS["section"], cutoff=0.99)
    res = r.retrieve("please add a dark mode to the console")
    assert not res.hit and res.passages == [] and res.candidates  # candidates kept for the log
    assert "No passage at or above cutoff 0.99" in res.reason


def test_empty_text_returns_nothing(fake_embedder):
    assert not Retriever(fake_embedder, CONFIGS["section"], cutoff=0.0).retrieve("   ").hit


def test_persistent_index_rebuilt_only_when_needed(fake_embedder, tmp_path):
    Retriever(fake_embedder, CONFIGS["section"], 0.2, chroma_path=tmp_path)
    calls = []
    orig = fake_embedder.encode
    fake_embedder.encode = lambda texts: calls.append(len(texts)) or orig(texts)
    Retriever(fake_embedder, CONFIGS["section"], 0.2, chroma_path=tmp_path)
    assert calls == []  # same docs, config, model: no re-embedding


def test_retrieval_row_logged_for_hit_and_miss(fake_embedder, tmp_path):
    from src.retrieve import log_retrieval
    log = DecisionLog(tmp_path / "d.db", "r")
    r = Retriever(fake_embedder, CONFIGS["section"], cutoff=0.0)
    log_retrieval(log, "T-1", "webhook signature fails", r, r.retrieve("webhook signature fails"))
    log_retrieval(log, "T-2", "xyz", r, r.retrieve("xyz", cutoff=0.99))
    hit, miss = log.rows("T-1")[0], log.rows("T-2")[0]
    assert hit["action_taken"] == "passages_found" and hit["sources_used"][0]["passage_id"].startswith("DOC-")
    assert hit["threshold_applied"] == 0.0 and hit["model_version"].endswith("|section")
    assert miss["action_taken"] == "no_passages" and miss["error"] == "no_retrieval_hit"
    assert miss["sources_used"] == []


def test_config_missing_gives_clear_message(tmp_path):
    with pytest.raises(FileNotFoundError, match="retrieval_experiment.py"):
        load_config(tmp_path / "none.json")


def test_harness_writes_retrieval_row(fake_embedder, tmp_path):
    comp = harness.Components(retriever=Retriever(fake_embedder, CONFIGS["section"], cutoff=0.0))
    log = DecisionLog(tmp_path / "d.db", "r")
    t = {"ticket_id": "N-1", "channel": "chat", "subject": "", "body": "Getting 429 rate limit on search",
         "received_at": "2026-03-02T08:32:00Z"}
    res = harness.process_ticket(normalise(t, 0), log, comp)
    assert [x["stage"] for x in log.rows("N-1")] == ["ingest", "classification", "retrieval", "routing", "final"]
    assert res["action"] == "escalate"


# ---------------------------------------------------------------------------- split + experiment

def test_holdout_split_is_by_text_deterministic_and_about_20pct():
    dev = json.load(open("data/development_tickets.json", encoding="utf-8"))
    train, hold = dev_holdout_split(dev)
    assert (train, hold) == dev_holdout_split(dev)
    assert not set(train) & set(hold) and len(train) + len(hold) == len(dev)
    by_id = {t["ticket_id"]: t for t in dev}
    assert not {text_key(by_id[i]) for i in train} & {text_key(by_id[i]) for i in hold}
    distinct = len({text_key(t) for t in dev})
    assert 0.17 <= len({text_key(by_id[i]) for i in hold}) / distinct <= 0.23


def test_experiment_runs_end_to_end(fake_embedder, tmp_path):
    spec = importlib.util.spec_from_file_location("exp", "docs/retrieval_experiment.py")
    exp = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(exp)
    dev = json.load(open("data/development_tickets.json", encoding="utf-8"))
    val = json.load(open("data/validation_tickets.json", encoding="utf-8"))
    r = exp.run_experiment(fake_embedder, dev, val, chroma_path=str(tmp_path))
    assert {c["config"] for c in r["comparison"]} == set(CONFIGS)
    assert r["chosen_config"] in CONFIGS and 0.0 <= r["cutoff"] <= 0.9
    hits = [s["hit3_answerable"] for s in r["sweep_holdout"]]
    assert hits == sorted(hits, reverse=True)  # raising the cutoff never adds hits
    assert "## 3. Cutoff sweep" in exp.to_markdown(r)


def test_src_never_reads_fluency():  # FR-19
    import pathlib
    import re
    pattern = re.compile(r"""(\.get\(\s*|\[\s*)["']language_fluency["']""")
    for f in pathlib.Path("src").rglob("*.py"):
        assert not pattern.search(f.read_text(encoding="utf-8")), f
