# Gate check (5.12): 20261119T155250Z_validation_tickets_7e98

Input `data\validation_tickets.json` (sha256 94c5b1adc120). Checked by `evaluation/gate_check.py` from the input file and the SQLite decision log, independently of the harness.

**GATE PASSED**

| Check | Result |
| --- | --- |
| one final row per ticket, none extra | PASS |
| every final action is auto_respond or escalate | PASS |
| every escalation has a reason | PASS |
| every automatic answer has a reply that passed Validate | PASS |
| every ticket has an ingest row | PASS |
| no must_not_auto_respond ticket answered automatically | PASS |
| harness reconcile.json ok | PASS |
| same input, same route and final action (determinism) | PASS |

| Count | Value |
| --- | --- |
| Records in the input file | 80 |
| Tickets after ingest | 80 |
| Lines in results.jsonl | 80 |
| Final rows in the decision log | 80 |
| Final actions | {'auto_respond': 49, 'escalate': 31} |
| Route actions | {'auto_respond': 51, 'escalate': 29} |
| Errors | {'none': 80} |
| Automatic answers by intent | {'api_key_issue': 4, 'authentication_failure': 3, 'account_access': 4, 'billing_query': 10, 'rollback_request': 5, 'performance_degradation': 3, 'api_usage_question': 3, 'onboarding': 1, 'deployment_failure': 5, 'quota_or_overage': 2, 'webhook_issue': 3, 'data_export': 1, 'integration_help': 3, 'configuration_help': 1, 'sso_configuration': 1} |
| Provider requests / cache hits | 47 / 4 |
| Degraded-mode tickets | 0 |
| Latency p50 / p95 (ms) | 2211 / 5164 |

Rules fired: none 49, no_retrieval_hit 9, must_escalate_intent:unclear_request 6, must_escalate_intent:data_residency 6, must_escalate_intent:security_incident 4, must_escalate_intent:feature_request 3, guardrail:grounding 2, must_escalate_intent:compliance_request 1

Re-run compared: `evaluation\results\2026-11-19_gate_rerun`: 0 ticket(s) differ; re-run provider requests 0, cache hits 51.
