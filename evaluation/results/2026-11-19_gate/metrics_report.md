# Metrics report: 20261119T155250Z_validation_tickets_7e98

Input `data\validation_tickets.json` (sha256 94c5b1adc120), run 7 on this file, finished 2026-11-19T15:56:34.711Z, git 2c453f4. Built from the decision log and the input file (FR-27) by `evaluation/metrics.py`.

## Volume

| Figure | Value |
| --- | --- |
| Tickets processed | 80 |
| Answered automatically | 49 |
| Escalated | 31 |

| Channel | Tickets | Automatic | Escalated |
| --- | --- | --- | --- |
| chat | 22 | 10 | 12 |
| docs_comment | 16 | 11 | 5 |
| email | 31 | 21 | 10 |
| forum | 11 | 7 | 4 |

Escalated by cause: must_escalate_intent 20, no_retrieval_hit 9, validate_block 2

Blocked by guardrail: grounding 2

## Business

| Figure | Value | Target |
| --- | --- | --- |
| Auto-resolution rate | 61.2% | 50% or more (Section 8) |
| Escalation rate | 38.8% | 50% or less |
| Replay FCR (label-based) | 43.8% | 50% or more |
| Time to final action, mean / median | 1955 ms / 2211 ms | |

automatic answers on tickets labelled expected_route = auto_respond, that passed Validate, / all tickets (PRD Section 8). The label follows past handling (AS-07).

## Technical

| Figure | Value | Target |
| --- | --- | --- |
| Intent accuracy | 100% | |
| Intent macro precision / recall | 100% / 100% | 85% or more (NFR-03) |
| Urgency accuracy | 41.2% | |
| Retrieval hit rate, top 3 (answerable, n=53) | 83% | 85% or more (AS-01) |
| Latency p50 / p95, ingest to final action | 2211 ms / 5164 ms | |
| Latency p50 / p95, excluding provider waits (NFR-01) | 1730 ms / 4883 ms | p95 under 3,000 ms: FAIL |
| Stage latency p50 / p95 | classification 11 / 13 ms (n=80); retrieval 14 / 17 ms (n=80); generation 2455 / 5854 ms (n=51); validation 0 / 0 ms (n=51) | |
| Provider requests / cache hits / wait total | 47 / 0 / 30965 ms | |
| Generated answers whose citations resolve (checked in code) | 100% of 51 | |
| Sent answers: every cited passage in the retrieved set | 100% of 49 | 100% |
| Sent answers citing a labelled expected article | 94.4% of 36 | reported only |
| Hallucination rate / human citation accuracy | from answer_review.csv | 5% or less / 95% or more (NFR-08) |

Citation validity is checked in code: every cited passage id must be in the set retrieved for that ticket. Agreement with expected_doc_ids is reported, not a gate (AS-03, AS-07: labels are per intent and follow past handling). Hallucination rate and human citation accuracy come from answer_review.csv (NFR-08).

Intent per class (labelled n, precision, recall): account_access 4 100/100; api_key_issue 6 100/100; api_usage_question 4 100/100; authentication_failure 3 100/100; billing_query 10 100/100; compliance_request 1 100/100; configuration_help 3 100/100; data_export 1 100/100; data_residency 6 100/100; database_issue 1 100/100; deployment_failure 5 100/100; feature_request 3 100/100; integration_help 3 100/100; onboarding 4 100/100; performance_degradation 3 100/100; quota_or_overage 2 100/100; rate_limit 1 100/100; rollback_request 6 100/100; security_incident 4 100/100; sso_configuration 1 100/100; unclear_request 6 100/100; webhook_issue 3 100/100

Urgency per level (n, precision, recall): high 25 40/24; low 20 33.3/10; medium 35 42.4/71.4

## Governance

| Figure | Value |
| --- | --- |
| Final rows / tickets in input | 80 / 80 |
| Tickets without a final row / duplicate final rows | 0 / 0 |
| Rows with an empty required field | 0 |
| Decision-log coverage (NFR-05) | 100%: PASS |
| Validate blocks | 2 |
| Private-data detections (NFR-04) | 0 |
| Unsafe automatic answers (must_not_auto_respond, NFR-09) | 0 |
| Degraded-mode tickets | 0 |
| Errors | none 80 |

Route rule activations: must_escalate_intent 20, no_retrieval_hit 9

| Validate check | Pass | Block | Warn |
| --- | --- | --- | --- |
| citations | 51 | 0 | 0 |
| commitments | 51 | 0 | 0 |
| confidence_floor | 51 | 0 | 0 |
| grounding | 49 | 2 | 0 |
| integrity | 51 | 0 | 0 |
| private_data | 51 | 0 | 0 |
| style | 40 | 0 | 11 |

Rows by stage: {'ingest': 80, 'classification': 80, 'retrieval': 80, 'routing': 80, 'generation': 51, 'validation': 51, 'final': 80}

## Segments (NFR-06: under 5 pts between groups of 10 or more)

Auto rate (eligible) = automatic answers among tickets labelled answerable and not must-not-auto-respond, so intent mix does not drive the gap (FR-19 acceptance).

| Dimension | Group | n | Auto rate (all) | Auto rate, eligible (n) | Hit@3 (n) | Intent acc |
| --- | --- | --- | --- | --- | --- | --- |
| tier | business | 30 | 73.3% | 76.2% (21) | 81.8% (22) | 100% |
| tier | enterprise | 8 | 50% | 66.7% (6) | 83.3% (6) | 100% |
| tier | standard | 42 | 54.8% | 72.7% (22) | 84% (25) | 100% |
| tier | **gap (groups of 10+)** | | | 3.5 pts | 2.2 pts | PASS |
| fluency | fluent | 61 | 62.3% | 75.6% (41) | 84.1% (44) | 100% |
| fluency | non_fluent | 19 | 57.9% | 62.5% (8) | 77.8% (9) | 100% |
| fluency | **gap (groups of 10+)** | | | 13.1 pts | 6.3 pts | FAIL |
| channel | chat | 22 | 45.5% | 53.8% (13) | 46.2% (13) | 100% |
| channel | docs_comment | 16 | 68.8% | 87.5% (8) | 90% (10) | 100% |
| channel | email | 31 | 67.7% | 76.2% (21) | 95.5% (22) | 100% |
| channel | forum | 11 | 63.6% | 85.7% (7) | 100% (8) | 100% |
| channel | **gap (groups of 10+)** | | | 33.7 pts | 53.8 pts | FAIL |
| length | long (>28 words) | 19 | 68.4% | 76.9% (13) | 85.7% (14) | 100% |
| length | short (<=28 words) | 61 | 59% | 72.2% (36) | 82.1% (39) | 100% |
| length | **gap (groups of 10+)** | | | 4.7 pts | 3.6 pts | PASS |

## Calibration (NFR-10: within 5 pts in bands of 20+)

| Band | n | Mean confidence | Accuracy | Gap | Result |
| --- | --- | --- | --- | --- | --- |
| 0-0.5 | 0 | | | | |
| 0.5-0.7 | 0 | | | | |
| 0.7-0.9 | 0 | | | | |
| 0.9-0.95 | 0 | | | | |
| 0.95-1 | 80 | 100.0% | 100.0% | -0.0 | PASS |

## All tickets vs unseen text (FR-28)

| Subset | n | Auto rate | Intent acc | Hit@3 (n) | Sent citing expected article (n) |
| --- | --- | --- | --- | --- | --- |
| all | 80 | 61.2% | 100% | 83% (53) | 94.4% (36) |
| unseen | 35 | 60% | 100% | 80% (20) | 92.9% (14) |
| repeats_dev_text | 45 | 62.2% | 100% | 84.8% (33) | 95.5% (22) |

## Consistency with results.jsonl

**Every figure matches** between the decision log and results.jsonl.

| Figure | Decision log | results.jsonl | Match |
| --- | --- | --- | --- |
| tickets | 80 | 80 | yes |
| final actions | {'auto_respond': 49, 'escalate': 31} | {'auto_respond': 49, 'escalate': 31} | yes |
| channels | {'forum': 11, 'chat': 22, 'docs_comment': 16, 'email': 31} | {'forum': 11, 'chat': 22, 'docs_comment': 16, 'email': 31} | yes |
| route actions | {'auto_respond': 51, 'escalate': 29} | {'auto_respond': 51, 'escalate': 29} | yes |
| final rule fired | {'none': 49, 'must_escalate_intent:unclear_request': 6, 'no_retrieval_hit': 9, 'must_escalate_intent:compliance_request': 1, 'must_escalate_intent:feature_request': 3, 'must_escalate_intent:data_residency': 6, 'guardrail:grounding': 2, 'must_escalate_intent:security_incident': 4} | {'none': 49, 'must_escalate_intent:unclear_request': 6, 'no_retrieval_hit': 9, 'must_escalate_intent:compliance_request': 1, 'must_escalate_intent:feature_request': 3, 'must_escalate_intent:data_residency': 6, 'guardrail:grounding': 2, 'must_escalate_intent:security_incident': 4} | yes |
| errors | {'none': 80} | {'none': 80} | yes |
| sent answers with a reply | 49 | 49 | yes |
| Validate blocks | 2 | 2 | yes |
