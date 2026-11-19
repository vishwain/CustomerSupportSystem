"""Metrics report (5.13, FR-27): every group present, figures computed from the decision log, and the
consistency section matches results.jsonl. Scripted components: no model, no provider."""

import csv
import json

from evaluation import harness, metrics
from src.generate import Generator, load_messages
from src.guardrails import Check, ValidationResult
from src.ingest import load
from src.logging_store import DecisionLog
from src.route import Router, RoutingConfig
from tests.test_generate import PASSAGES, FakeClient, StubClassifier, StubRetriever, answer


class StubValidator:
    def __init__(self, block=()):
        from src.guardrails import GuardrailConfig
        self.block = set(block)
        self.cfg = GuardrailConfig(grounding_floor=0.21)

    def validate(self, ticket_text, sentences, extra_texts, passages, mode, confidence, threshold, private_terms):
        names = ("private_data", "citations", "grounding", "integrity", "commitments", "confidence_floor")
        return ValidationResult([Check(n, "block" if n in self.block else "pass", "stub") for n in names]
                                + [Check("style", "warn", "stub")])


def labelled(tid, intent="rate_limit", must_not=False, docs=("DOC-API-001",), channel="email", **over):
    t = {"ticket_id": tid, "channel": channel, "subject": "429s", "body": f"Every call returns 429 ({tid}).",
         "received_at": "2026-11-19T09:00:00Z", "customer_id": "CUST-1", "customer_name": "N",
         "customer_tier": "pro", "language_fluency": "fluent",
         "labels": {"intent": intent, "urgency": "medium", "expected_route": "auto_respond",
                    "answerable_from_docs": True, "expected_doc_ids": list(docs), "must_not_auto_respond": must_not}}
    t.update(over)
    return t


def run_synthetic(tmp_path, tickets, outputs, block=()):
    inp = tmp_path / "in.json"
    inp.write_text(json.dumps(tickets), encoding="utf-8")
    rt = tmp_path / "runtime.json"
    rt.write_text('{"automation_paused": false}', encoding="utf-8")
    comp = harness.Components(retriever=StubRetriever(PASSAGES), classifier=StubClassifier("rate_limit", 0.99),
                              router=Router(RoutingConfig(threshold=0.95), runtime_path=rt),
                              generator=Generator(FakeClient(outputs)), messages=load_messages(),
                              validator=StubValidator(block))
    log = DecisionLog(tmp_path / "d.db", "run-1")
    results = [harness.process_ticket(rec, log, comp) for rec in load(inp)]
    info = {"run_id": "run-1", "input_path": str(inp), "input_sha256": "x", "finished_at": "now",
            "runs_on_this_input": 1}
    return metrics.build_report(log.rows(), info, results), results, info


def test_every_group_and_the_numbers(tmp_path):
    tickets = [labelled("T-1"), labelled("T-2", channel="chat"), labelled("T-3", intent="billing_query",
                                                                           docs=("DOC-BILL-001",))]
    m, results, _ = run_synthetic(tmp_path, tickets, [answer(), answer(), answer()])
    for k in ("volume", "business", "technical", "governance", "segments", "calibration", "fr28", "consistency"):
        assert m[k] is not None, k
    assert m["volume"]["processed"] == 3 and m["volume"]["automatic"] == 3
    assert m["volume"]["by_channel"] == {"email": 2, "chat": 1}
    assert m["business"]["auto_resolution_rate"] == 100.0 and m["business"]["escalation_rate"] == 0.0
    assert m["technical"]["intent"]["accuracy"] == 66.7  # T-3 is labelled billing_query, predicted rate_limit
    c = m["technical"]["citations"]
    assert c["citations_resolve_in_code"] == 100.0 and c["sent_cited_ids_in_retrieved_set"] == 100.0
    assert c["sent_cites_expected_doc"] == 66.7  # T-3 cites DOC-API-001, expected DOC-BILL-001
    assert m["governance"]["decision_log_coverage_ok"] and m["governance"]["unsafe_automatic_answers"] == 0
    assert m["governance"]["validate_checks"]["style"]["warn"] == 3
    assert all(x["match"] for x in m["consistency"].values())


def test_blocks_and_unsafe_answers_are_counted(tmp_path):
    tickets = [labelled("T-1", must_not=True), labelled("T-2")]
    m, _, _ = run_synthetic(tmp_path, tickets, [answer(), answer()], block=("grounding",))
    assert m["volume"]["automatic"] == 0 and m["volume"]["blocked_by_guardrail"] == {"grounding": 2}
    assert m["governance"]["validate_blocks"] == 2 and m["governance"]["unsafe_automatic_answers"] == 0
    assert m["volume"]["escalated_by_cause"] == {"validate_block": 2}
    assert all(x["match"] for x in m["consistency"].values())


def test_unlabelled_input_gives_na(tmp_path):
    t = labelled("T-1")
    del t["labels"]
    m, _, _ = run_synthetic(tmp_path, [t], [answer()])
    assert m["technical"]["intent"] is None and m["governance"]["unsafe_automatic_answers"] is None
    assert m["segments"] is None and "n/a" in metrics.to_markdown(m)


def test_processing_latency_excludes_provider_wait(tmp_path):
    m, _, _ = run_synthetic(tmp_path, [labelled("T-1")], [answer()])
    t = m["technical"]
    assert t["processing_ms_p95"] <= t["latency_ms_p95"]


def test_harness_writes_report_and_review_sheet(tmp_path):
    out = tmp_path / "out"
    assert harness.main(["--input", "data/validation_tickets.json", "--output", str(out),
                         "--storage", str(tmp_path / "s"), "--quiet", "--no-models", "--no-llm"]) == 0
    m = json.loads((out / "metrics_report.json").read_text(encoding="utf-8"))
    assert m["volume"]["processed"] == 80 and m["governance"]["decision_log_coverage_ok"]
    assert "unseen" in m["fr28"] and m["fr28"]["unseen"]["n"] == 35
    assert all(x["match"] for x in m["consistency"].values())
    md = (out / "metrics_report.md").read_text(encoding="utf-8")
    for h in ("## Volume", "## Business", "## Technical", "## Governance", "## Segments", "## Calibration",
              "FR-28", "Every figure matches"):
        assert h in md, h
    # rebuild from the run folder alone
    assert metrics.main(["--run-dir", str(out)]) == 0


def test_review_sheet_rows_and_scrubbing(tmp_path):
    t = labelled("T-1", body="Mail me at jane.doe@example.com: every call returns 429.")
    m, results, info = run_synthetic(tmp_path, [t], [answer()])
    n = metrics.write_review_sheet(tmp_path / "r.csv", results, tmp_path / "in.json", chunking="chars800")
    rows = list(csv.DictReader(open(tmp_path / "r.csv", encoding="utf-8-sig")))
    assert n == 1 and rows[0]["ticket_id"] == "T-1" and "[REDACTED:email]" in rows[0]["ticket_text"]
    assert rows[0]["cited_passages"] == "DOC-API-001#c01"
