"""5b.6 kill switch drill: flip the real switch (config/runtime.json, via src.killswitch) and show what happens
to tickets, through the real pipeline (local classifier, retrieval, live provider, Validate, decision log).

Phases, on three validation tickets that run 11 answered automatically:
  1. OFF        VAL-0001                      -> answered automatically (baseline)
  2. IN FLIGHT  VAL-0004, switch flipped ON after Route chose to answer and the model replied
                                               -> escalates at send time (kill_switch_at_send), answer kept as draft
  3. ON         VAL-0001, VAL-0004, VAL-0005  -> all escalate (kill_switch), no provider request
  4. OFF again  VAL-0005                      -> automatic answers resume
Every ticket gets a final decision row; the drill reconciles tickets processed against final rows.
The switch is always set back OFF at the end, even if the drill fails.

Usage (repo root, .env with the key):  python docs/kill_switch_drill.py
Output: evaluation/results/<date>_kill_switch_drill/ (kill_switch_drill.md, results.json, decisions.db, audit)
"""

from __future__ import annotations

import json
import sys
import time
import uuid
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from evaluation.harness import build_components, process_ticket  # noqa: E402
from src import killswitch  # noqa: E402
from src.guardrails import private_terms_for  # noqa: E402
from src.ingest import load  # noqa: E402
from src.logging_store import DecisionLog  # noqa: E402
from src.route import RUNTIME_CONFIG, automation_paused  # noqa: E402

INPUT = "data/validation_tickets.json"
BY = "Vishwain Annadate (kill switch drill)"


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    out = Path("evaluation/results") / f"{date.today().isoformat()}_kill_switch_drill"
    out.mkdir(parents=True, exist_ok=True)
    audit = out / "killswitch_audit.jsonl"
    audit.unlink(missing_ok=True)
    # One run id per phase: the log allows one final row per (run, ticket), and the drill sends the same
    # tickets through more than once.
    run_base = f"{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}_kill_switch_drill_{uuid.uuid4().hex[:4]}"
    db = out / "decisions.db"
    db.unlink(missing_ok=True)

    records = {r.ticket_id: r for r in load(INPUT)}
    comp = build_components()
    comp.private_terms = private_terms_for(list(records.values()))
    logs: dict[str, DecisionLog] = {}
    rows: list[dict] = []
    flips: list[dict] = []

    def flip(on: bool, reason: str) -> float:
        e = killswitch.set_paused(on, BY, reason, RUNTIME_CONFIG, audit)
        flips.append(e)
        return time.perf_counter()

    def run(phase: str, tid: str, t_flip: float | None = None) -> dict:
        if phase not in logs:
            logs[phase] = DecisionLog(db, f"{run_base}_p{phase.split()[0]}")
        r = process_ticket(records[tid], logs[phase], comp)
        g = r.get("generation") or {}
        row = {"phase": phase, "run_id": logs[phase].run_id, "ticket_id": tid, "log_written": r["log_written"], "action": r["action"], "rule_fired": r["rule_fired"],
               "reason": r["reason"], "provider_requests": g.get("requests", 0) if g else 0,
               "cached": g.get("cached") if g else None, "reply_sent": r["reply"] is not None,
               "draft_kept_for_agent": bool((r.get("escalation_package") or {}).get("draft")),
               "customer_message": (r["customer_message"] or "")[:160], "latency_ms": r["latency_ms"]}
        if t_flip is not None:
            row["ms_from_flip_to_decision"] = int((time.perf_counter() - t_flip) * 1000)
        rows.append(row)
        print(f"{phase:<10} {tid}  {r['action']:<12} {r['rule_fired']}")
        return row

    start_state = automation_paused()
    try:
        flip(False, "drill start: switch OFF")
        run("1 OFF", "VAL-0001")

        # 2. In flight: flip the switch after the model replied, before Validate and send.
        real_generate = comp.generator.generate if comp.generator else None
        state = {"t": None}

        def generate_then_flip(*a, **k):
            res = real_generate(*a, **k)
            state["t"] = flip(True, "drill: switch ON while VAL-0004 is in flight (after Route and Generate)")
            return res

        if comp.generator:
            comp.generator.generate = generate_then_flip
        try:
            run("2 IN FLIGHT", "VAL-0004")
        finally:
            if comp.generator:
                comp.generator.generate = real_generate
        if state["t"] is None:
            state["t"] = flip(True, "drill: switch ON (generate was not reached for VAL-0004)")

        t_on = time.perf_counter()
        for tid in ("VAL-0001", "VAL-0004", "VAL-0005"):
            run("3 ON", tid, t_on if tid == "VAL-0001" else None)

        t_off = flip(False, "drill: switch OFF, automatic answers resume")
        run("4 OFF", "VAL-0005", t_off)
    finally:
        if automation_paused()[0]:
            killswitch.set_paused(False, BY, "drill end: restore OFF", RUNTIME_CONFIG, audit)
        finals = []
        for lg in logs.values():
            finals += [r for r in lg.rows() if r["stage"] == "final"]
            lg.close()

    on_rows = [r for r in rows if r["phase"] == "3 ON"]
    inflight = next(r for r in rows if r["phase"] == "2 IN FLIGHT")
    checks = {
        "ON: every ticket escalated by the kill switch": all(r["action"] == "escalate" and r["rule_fired"] == "kill_switch"
                                                             for r in on_rows),
        "ON: no provider request": sum(r["provider_requests"] or 0 for r in on_rows) == 0,
        "ON: no reply sent; customer gets the holding message": not any(r["reply_sent"] for r in on_rows),
        "IN FLIGHT: not sent; escalated at send time": inflight["action"] == "escalate"
                                                       and inflight["rule_fired"] in ("kill_switch_at_send",),
        "IN FLIGHT: validated answer kept as a draft for the agent": inflight["draft_kept_for_agent"],
        "Nothing dropped: one final row per ticket processed": len(finals) == len(rows)
                                                               and all(r["log_written"] for r in rows),
        "ON: customer gets the holding message": all(r["customer_message"] for r in on_rows),
        "Switch OFF at the end": not automation_paused()[0],
    }
    ok = all(checks.values())
    result = {"run_ids": [lg.run_id for lg in logs.values()], "started_with_paused": start_state[0], "rows": rows, "flips": flips,
              "final_rows": len(finals), "tickets_processed": len(rows), "checks": checks, "ok": ok}
    (out / "results.json").write_text(json.dumps(result, indent=2), encoding="utf-8")

    L = [f"# Kill switch drill (5b.6): {'PASS' if ok else 'FAIL'}", "",
         f"Runs `{run_base}_p1` to `_p4` (one per phase), {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC. Real pipeline and live provider; the "
         "switch flipped with `src.killswitch` on the real `config/runtime.json`. Log: `decisions.db` here; switch "
         "changes: `killswitch_audit.jsonl`.", "",
         "| Phase | Ticket | Final action | Rule | Provider requests | Reply sent | Draft kept for agent | ms from flip |",
         "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    for r in rows:
        L.append(f"| {r['phase']} | {r['ticket_id']} | {r['action']} | {r['rule_fired']} | {r['provider_requests']}"
                 f"{' (cache)' if r['cached'] else ''} | {'yes' if r['reply_sent'] else 'no'} | "
                 f"{'yes' if r['draft_kept_for_agent'] else 'no'} | {r.get('ms_from_flip_to_decision', '')} |")
    L += ["", "Reasons logged:", ""]
    for r in rows:
        L.append(f"- {r['phase']} {r['ticket_id']}: {r['reason'][:240]}")
    L += ["", "What the customer received while ON (holding message):", "", f"> {on_rows[0]['customer_message']}", "",
          "Checks:", ""] + [f"- [{'x' if v else ' '}] {k}" for k, v in checks.items()]
    L += ["", f"Reconciliation: {len(rows)} tickets processed, {len(finals)} final rows."]
    (out / "kill_switch_drill.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
