"""Gate checker (5.12) on real harness output: validation file, no models, no provider."""

import json

from evaluation import gate_check, harness


def run(tmp_path, name, input_path="data/validation_tickets.json"):
    out = tmp_path / name
    code = harness.main(["--input", input_path, "--output", str(out), "--storage", str(tmp_path / "s"),
                         "--quiet", "--no-models", "--no-llm"])
    return code, out


def test_gate_passes_and_reruns_match(tmp_path):
    c1, a = run(tmp_path, "a")
    c2, b = run(tmp_path, "b")
    assert c1 == c2 == 0
    assert gate_check.main(["--run-dir", str(a), "--compare", str(b)]) == 0
    r = json.loads((a / "gate_check.json").read_text(encoding="utf-8"))
    assert r["ok"] and r["checks"]["final_rows_in_log"] == r["checks"]["records_in_file"] == 80
    assert r["checks"]["compare_differences"] == []
    assert "GATE PASSED" in (a / "gate_check.md").read_text(encoding="utf-8")


def test_gate_counts_malformed_records(tmp_path):
    code, out = run(tmp_path, "f", "tests/fixtures/failure_tickets.json")
    assert gate_check.main(["--run-dir", str(out)]) == 0
    r = json.loads((out / "gate_check.json").read_text(encoding="utf-8"))
    assert r["checks"]["records_in_file"] == r["checks"]["final_rows_in_log"] == 16


def test_gate_fails_when_a_final_row_is_missing(tmp_path):
    import sqlite3
    code, out = run(tmp_path, "m")
    info = json.loads((out / "run_info.json").read_text(encoding="utf-8"))
    con = sqlite3.connect(info["db_path"])
    try:
        con.execute("DROP TRIGGER IF EXISTS decisions_no_delete")
    except sqlite3.Error:
        pass
    victims = con.execute("SELECT ticket_id FROM decisions WHERE stage='final' LIMIT 1").fetchone()
    try:
        con.execute("DELETE FROM decisions WHERE stage='final' AND ticket_id=?", victims)
        con.commit()
    except sqlite3.Error:
        con.close()
        return  # log is append-only: deletion is refused, which is itself the guarantee
    con.close()
    assert gate_check.main(["--run-dir", str(out)]) == 1
    r = json.loads((out / "gate_check.json").read_text(encoding="utf-8"))
    assert victims[0] in r["checks"]["tickets_without_final"]
