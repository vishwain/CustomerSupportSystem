# Metrics report: 20261119T162713Z_validation_tickets_73f0

Input `data\validation_tickets.json` (sha256 94c5b1adc120), run 9 on this file, finished 2026-11-19T16:30:38.958Z, git 46ebcd8. Built from the decision log and the input file (FR-27) by `evaluation/metrics.py`.

## Volume

| Figure | Value |
| --- | --- |
| Tickets processed | 80 |
| Answered automatically | 51 |
| Escalated | 29 |

| Channel | Tickets | Automatic | Escalated |
| --- | --- | --- | --- |
| chat | 22 | 16 | 6 |
| docs_comment | 16 | 11 | 5 |
| email | 31 | 18 | 13 |
| forum | 11 | 6 | 5 |

Escalated by cause: must_escalate_intent 20, no_retrieval_hit 7, validate_block 2

Blocked by guardrail: grounding 2

## Business

| Figure | Value | Target |
| --- | --- | --- |
| Auto-resolution rate | 63.8% | 50% or more (Section 8) |
| Escalation rate | 36.2% | 50% or less |
| Replay FCR (label-based) | 47.5% | 50% or more |
| Time to final action, mean / median | 1856 ms / 2343 ms | |

automatic answers on tickets labelled expected_route = auto_respond, that passed Validate, / all tickets (PRD Section 8). The label follows past handling (AS-07).

## Technical

| Figure | Value | Target |
| --- | --- | --- |
| Intent accuracy | 100% | |
| Intent macro precision / recall | 100% / 100% | 85% or more (NFR-03) |
| Urgency accuracy | 41.2% | |
| Retrieval hit rate, top 3 (answerable, n=53) | 88.7% | 85% or more (AS-01) |
| Hit@3 with / without a subject | 87.5% (n=40) / 92.3% (n=13) | Tickets with the intent-expanded query: 22 |
| Latency p50 / p95, ingest to final action | 2343 ms / 3588 ms | |
| Latency p50 / p95, excluding provider waits (NFR-01) | 1818 ms / 2740 ms | p95 under 3,000 ms: PASS |
| Stage latency p50 / p95 | classification 10 / 11 ms (n=80); retrieval 13 / 16 ms (n=80); generation 2565 / 3403 ms (n=53); validation 0 / 0 ms (n=53) | |
| Provider requests / cache hits / wait total | 48 / 5 / 35413 ms | |
| Generated answers whose citations resolve (checked in code) | 100% of 53 | |
| Sent answers: every cited passage in the retrieved set | 100% of 51 | 100% |
| Sent answers citing a labelled expected article | 94.7% of 38 | reported only |
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

Route rule activations: must_escalate_intent 20, no_retrieval_hit 7

| Validate check | Pass | Block | Warn |
| --- | --- | --- | --- |
| citations | 53 | 0 | 0 |
| commitments | 53 | 0 | 0 |
| confidence_floor | 53 | 0 | 0 |
| grounding | 51 | 2 | 0 |
| integrity | 53 | 0 | 0 |
| private_data | 53 | 0 | 0 |
| style | 46 | 0 | 7 |

Rows by stage: {'ingest': 80, 'classification': 80, 'retrieval': 80, 'routing': 80, 'generation': 53, 'validation': 53, 'final': 80}

## Segments (NFR-06: under 5 pts between groups of 10 or more; 5b.3)

Auto rate (eligible) = automatic answers among tickets labelled answerable and not must-not-auto-respond, so intent mix does not drive the gap (FR-19 acceptance).

| Dimension | Group | n | Auto rate (all) | Auto rate, eligible (n) | Hit@3 (n) | Intent acc |
| --- | --- | --- | --- | --- | --- | --- |
| tier | business | 30 | 83.3% | 90.5% (21) | 95.5% (22) | 100% |
| tier | enterprise | 8 | 50% | 66.7% (6) | 83.3% (6) | 100% |
| tier | standard | 42 | 52.4% | 68.2% (22) | 84% (25) | 100% |
| tier | **gap (groups of 10+)** | | | 22.3 pts | 11.5 pts | FAIL |
| region | asia_pacific | 21 | 66.7% | 75% (16) | 76.5% (17) | 100% |
| region | europe | 25 | 68% | 75% (16) | 94.7% (19) | 100% |
| region | latin_america | 7 | 28.6% | 66.7% (3) | 100% (3) | 100% |
| region | north_america | 27 | 66.7% | 85.7% (14) | 92.9% (14) | 100% |
| region | **gap (groups of 10+)** | | | 10.7 pts | 18.2 pts | FAIL |
| fluency | fluent | 61 | 67.2% | 80.5% (41) | 90.9% (44) | 100% |
| fluency | non_fluent | 19 | 52.6% | 62.5% (8) | 77.8% (9) | 100% |
| fluency | **gap (groups of 10+)** | | | 18 pts | 13.1 pts | FAIL |
| channel | chat | 22 | 72.7% | 92.3% (13) | 92.3% (13) | 100% |
| channel | docs_comment | 16 | 68.8% | 87.5% (8) | 90% (10) | 100% |
| channel | email | 31 | 58.1% | 66.7% (21) | 86.4% (22) | 100% |
| channel | forum | 11 | 54.5% | 71.4% (7) | 87.5% (8) | 100% |
| channel | **gap (groups of 10+)** | | | 25.6 pts | 5.9 pts | FAIL |
| length | long (>28 words) | 19 | 52.6% | 61.5% (13) | 78.6% (14) | 100% |
| length | short (<=28 words) | 61 | 67.2% | 83.3% (36) | 92.3% (39) | 100% |
| length | **gap (groups of 10+)** | | | 21.8 pts | 13.7 pts | FAIL |

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
| all | 80 | 63.8% | 100% | 88.7% (53) | 94.7% (38) |
| unseen | 35 | 57.1% | 100% | 85% (20) | 92.9% (14) |
| repeats_dev_text | 45 | 68.9% | 100% | 90.9% (33) | 95.8% (24) |

## Consistency with results.jsonl

**Every figure matches** between the decision log and results.jsonl.

| Figure | Decision log | results.jsonl | Match |
| --- | --- | --- | --- |
| tickets | 80 | 80 | yes |
| final actions | {'auto_respond': 51, 'escalate': 29} | {'auto_respond': 51, 'escalate': 29} | yes |
| channels | {'forum': 11, 'chat': 22, 'docs_comment': 16, 'email': 31} | {'forum': 11, 'chat': 22, 'docs_comment': 16, 'email': 31} | yes |
| route actions | {'auto_respond': 53, 'escalate': 27} | {'auto_respond': 53, 'escalate': 27} | yes |
| final rule fired | {'none': 51, 'must_escalate_intent:unclear_request': 6, 'no_retrieval_hit': 7, 'must_escalate_intent:compliance_request': 1, 'must_escalate_intent:feature_request': 3, 'must_escalate_intent:data_residency': 6, 'guardrail:grounding': 2, 'must_escalate_intent:security_incident': 4} | {'none': 51, 'must_escalate_intent:unclear_request': 6, 'no_retrieval_hit': 7, 'must_escalate_intent:compliance_request': 1, 'must_escalate_intent:feature_request': 3, 'must_escalate_intent:data_residency': 6, 'guardrail:grounding': 2, 'must_escalate_intent:security_incident': 4} | yes |
| errors | {'none': 80} | {'none': 80} | yes |
| sent answers with a reply | 51 | 51 | yes |
| Validate blocks | 2 | 2 | yes |
