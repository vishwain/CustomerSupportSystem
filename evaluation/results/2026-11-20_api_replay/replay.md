# API replay (5b.8): 101 tickets + 3 malformed requests

API http://localhost:8001, 2026-11-20, 3.3 minutes. Inputs: `data/validation_tickets.json`, `tests/fixtures/engineered_tickets.json`, `tests/fixtures/must_escalate_tickets.json`.

- Answered automatically: 52 (51.5%)
- Escalated: 49
- Other: 0
- Client-side latency: p50 2.07 s, p95 4.79 s, max 9.92 s
- Escalation rules: must_escalate_intent 30, no_retrieval_hit 7, billing_dispute 4, guardrail 2, instruction_integrity 2, risk_terms 2, prior_contact_claim 1, must_escalate_alternative 1

`metrics_snapshot.txt` is the /metrics output at the end; `responses.jsonl` has one line per request.
