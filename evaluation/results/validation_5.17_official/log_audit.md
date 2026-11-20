# Decision-log audit (5b.1): 20261120T025358Z_validation_tickets_056a

Input `data\validation_tickets.json`; log `storage\runs\20261120T025358Z_validation_tickets_056a\decisions.db`. Checked by `evaluation/log_audit.py` against the Governance Framework minimum record.

**PASS**: fields complete, coverage reconciles exactly.

## 1. Minimum record fields

| Framework field | Column | Present |
| --- | --- | --- |
| decision_id | `decision_id` | yes |
| timestamp | `timestamp` | yes |
| ticket_id | `ticket_id` | yes |
| stage | `stage` | yes |
| input_summary | `input_summary` | yes |
| model.name | `model_name` | yes |
| model.version | `model_version` | yes |
| prediction | `prediction` | yes |
| alternatives | `alternatives` | yes |
| sources_used | `sources_used` | yes |
| threshold_applied | `threshold_applied` | yes |
| action_taken | `action_taken` | yes |
| reason | `reason` | yes |
| guardrail_results | `guardrail_results` | yes |
| prompt_version | `prompt_version` | yes |
| requirement_ids | `requirement_ids` | yes |

506 rows checked: {'ingest': 80, 'classification': 80, 'retrieval': 80, 'routing': 80, 'generation': 53, 'validation': 53, 'final': 80}. Rows with a missing or empty required field: **0**.

Stage-specific checks: classification rows carry confidence and alternatives; routing rows carry the threshold applied; validation rows carry every guardrail result; retrieval rows with no sources say why.

Response or escalation, per ticket: answered: generated sentences, citations and a Validate pass: 51; escalation package on final row: 29. The exact text sent to the customer is in results.jsonl; the log holds the generated sentences (redacted), their citations and the Validate result it was built from.

## 2. Coverage

| Check | Result |
| --- | --- |
| Tickets in the input | 80 |
| Final decision rows | 80 |
| Tickets without a final row | 0 |
| Final rows without a ticket | 0 |
| Duplicate final rows | 0 |
| Duplicate stage rows | 0 |
| Duplicate ticket ids in the input | 0 |
| Tickets missing an ingest, classification, retrieval or routing row | 0 |
