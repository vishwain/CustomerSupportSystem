"""Harness tests (A9, A10, FR-26): any file, one command, every ticket reaches a final row."""

import json

from evaluation import harness
from src.ingest import normalise
from src.logging_store import DecisionLog, LogWriteError

def ticket(i, channel="email", **over):
    t = {"ticket_id": f"NEW-{i}", "channel": channel, "subject": "s", "body": f"body {i}",
         "received_at": "2026-03-02T08:32:00Z", "customer_id": "CUST-1", "customer_name": "N"}
    t.update(over)
    return t

def run(tmp_path, input_path):
    out = tmp_path / "out"
    code = harness.main(["--input", str(input_path), "--output", str(out),
                         "--storage", str(tmp_path / "storage"), "--quiet"])
    return code, out

def test_unseen_five_ticket_file(tmp_path):
    p = tmp_path / "five.json"
    p.write_text(json.dumps([ticket(i, c) for i, c in
                             enumerate(["email", "chat", "docs_comment", "forum", "email"])]), encoding="utf-8")
    code, out = run(tmp_path, p)
    assert code == 0
    rec = json.loads((out / "reconcile.json").read_text(encoding="utf-8"))
    assert rec["ok"] and rec["final_rows"] == 5
    results = [json.loads(x) for x in (out / "results.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(results) == 5 and all(r["action"] == "escalate" for r in results)
    for f in ("metrics_report.md", "metrics_report.json", "decision_log_extract.jsonl", "run_info.json"):
        assert (out / f).exists()

def test_bad_records_still_reconcile(tmp_path):
    p = tmp_path / "mixed.jsonl"
    lines = [json.dumps(ticket(1)), "{broken", json.dumps(ticket(2, body="   ")),
             json.dumps(ticket(3, channel=None)), json.dumps(ticket(1))]  # last is a duplicate id
    p.write_text("\n".join(lines), encoding="utf-8")
    code, out = run(tmp_path, p)
    assert code == 0
    results = {r["ticket_id"]: r for r in
               (json.loads(x) for x in (out / "results.jsonl").read_text(encoding="utf-8").splitlines())}
    assert results["ROW-0002"]["error"] == "malformed_input"
    assert results["NEW-2"]["error"] == "malformed_input"
    assert results["NEW-3"]["channel"] == "unknown"
    assert "NEW-1#2" in results

def test_unreadable_input_exits_2(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text("not json", encoding="utf-8")
    assert run(tmp_path, p)[0] == 2

def test_run_count_per_input_file(tmp_path):
    p = tmp_path / "one.json"
    p.write_text(json.dumps([ticket(1)]), encoding="utf-8")
    run(tmp_path, p)
    _, out = run(tmp_path, p)
    assert json.loads((out / "run_info.json").read_text(encoding="utf-8"))["runs_on_this_input"] == 2

def test_final_write_failure_fails_closed(tmp_path, monkeypatch):
    log = DecisionLog(tmp_path / "d.db", "r")
    real = DecisionLog.write

    def flaky(self, **kw):
        if kw["stage"] == "final":
            raise LogWriteError("disk full")
        return real(self, **kw)

    monkeypatch.setattr(DecisionLog, "write", flaky)
    r = harness.process_ticket(normalise(ticket(1), 0), log)
    assert r["action"] == "escalate" and r["error"] == "log_write_failed"
    assert r["reply"] is None and r["log_written"] is False

def test_pipeline_crash_escalates_and_logs(tmp_path, monkeypatch):
    log = DecisionLog(tmp_path / "d.db", "r")

    def boom(record, log):
        raise RuntimeError("classifier exploded for jane@example.com")

    monkeypatch.setattr(harness, "run_pipeline", boom)
    r = harness.process_ticket(normalise(ticket(1), 0), log)
    assert r["error"] == "internal_error" and "jane@example.com" not in r["reason"]
    assert [x["stage"] for x in log.rows("NEW-1")] == ["ingest", "final"]
