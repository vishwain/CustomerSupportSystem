"""Decision log tests (A8, FR-24, NFR-05)."""

import json
import sqlite3

import pytest

from src.logging_store import REQUIRED, DecisionLog, LogWriteError, summarise_input


@pytest.fixture
def log(tmp_path):
    d = DecisionLog(tmp_path / "decisions.db", run_id="test-run")
    yield d
    d.close()


def final(log, tid, **kw):
    return log.write(ticket_id=tid, stage="final", action_taken="escalate",
                     reason="test escalation", input_text="hello", **kw)


def test_row_has_every_required_field(log):
    row = log.write(ticket_id="T-1", stage="classification", action_taken="classify",
                    reason="intent api_key_issue at 0.91 >= 0.80", input_text="My key fails",
                    model_name="minilm-logreg", model_version="2026-11-18", prompt_version="n/a",
                    prediction={"intent": "api_key_issue", "urgency": "medium"}, confidence=0.91,
                    alternatives=[{"value": "auth_error", "confidence": 0.05}], threshold_applied=0.8)
    stored = log.rows("T-1")[0]
    for col in REQUIRED:
        assert stored[col] not in (None, ""), col
    assert stored["prediction"]["intent"] == "api_key_issue"
    assert stored["requirement_ids"] == ["FR-04", "FR-05", "FR-24"]
    assert row["timestamp"].endswith("Z")


def test_failure_path_row_is_written(log):
    log.write(ticket_id="T-2", stage="generation", action_taken="failed", reason="provider timed out after 10 s",
              error="timeout", degraded_mode=True)
    final(log, "T-2", error="timeout")
    rows = log.rows("T-2")
    assert [r["stage"] for r in rows] == ["generation", "final"]
    assert rows[0]["error"] == "timeout" and rows[0]["degraded_mode"] == 1


def test_one_final_row_per_ticket_enforced_by_db(log):
    final(log, "T-3")
    with pytest.raises(LogWriteError):
        final(log, "T-3")
    assert log.fallback_path.exists()


def test_db_failure_goes_to_fallback_and_alert(log):
    log._conn.close()  # simulate the database becoming unwritable
    with pytest.raises(LogWriteError):
        final(log, "T-4")
    saved = json.loads(log.fallback_path.read_text(encoding="utf-8").splitlines()[-1])
    assert saved["ticket_id"] == "T-4" and saved["stage"] == "final"
    assert "ALERT" in log.alert_path.read_text(encoding="utf-8")


@pytest.mark.parametrize("bad", [
    dict(stage="nope", action_taken="escalate", reason="x"),
    dict(stage="final", action_taken="send_anyway", reason="x"),
    dict(stage="final", action_taken="escalate", reason="   "),
    dict(stage="final", action_taken="escalate", reason="x", error="mystery"),
    dict(stage="final", action_taken="escalate", reason="x", customer_id="CUST-1"),
])
def test_bad_rows_rejected_before_write(log, bad):
    with pytest.raises(ValueError):
        log.write(ticket_id="T-5", **bad)


def test_db_check_constraint_blocks_empty_reason(log):
    with pytest.raises(sqlite3.IntegrityError):
        log._conn.execute("INSERT INTO decisions (decision_id,timestamp,run_id,ticket_id,stage,input_summary,"
                          "input_sha256,model_name,model_version,prompt_version,action_taken,reason,"
                          "requirement_ids) VALUES ('x','t','r','T','final','s','h','m','v','p','escalate','','[]')")


def test_input_summary_scrubbed_and_cut():
    text = "Contact me at jane@example.com or CUST-1234. " + "the build fails again " * 20
    summary, digest = summarise_input(text)
    assert "jane@example.com" not in summary and "CUST-1234" not in summary
    assert len(summary) == 200 and len(digest) == 64


def test_reconcile_counts(log):
    for t in ("A", "B"):
        log.write(ticket_id=t, stage="ingest", action_taken="accept", reason="accepted")
        final(log, t)
    ok = log.reconcile(["A", "B"])
    assert ok["ok"] and ok["final_rows"] == 2 and ok["rows_by_stage"] == {"final": 2, "ingest": 2}
    bad = log.reconcile(["A", "B", "C"])
    assert not bad["ok"] and bad["missing_final"] == ["C"]


def test_runs_table_counts_runs_on_same_input(tmp_path):
    db = tmp_path / "d.db"
    for i in range(2):
        d = DecisionLog(db, run_id=f"r{i}")
        d.start_run("hidden.json", "abc")
        d.finish_run(5, 5)
        d.close()
    assert DecisionLog(db, run_id="r9").runs_on_input("abc") == 2
