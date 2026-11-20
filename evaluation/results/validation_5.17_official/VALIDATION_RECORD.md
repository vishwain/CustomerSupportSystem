# Validation-set evaluation (5.17): figures as produced

| Run fact | Value |
| --- | --- |
| Run | `20261120T025358Z_validation_tickets_056a`, finished 2026-11-20 02:57 UTC (08:27 IST) |
| Command | `python -m evaluation.harness --input data/validation_tickets.json --output evaluation/results/validation_5.17_official --no-cache` |
| Code | git `b017167`, frozen before the run; no code, prompt or threshold changed during or after |
| Input | `data/validation_tickets.json`, 80 tickets, sha256 `94c5b1adc120` |
| Run number on this file | **11** (harness run registry). Runs 1-10 were on 19 Nov: development checks, the 5.12 gate and its re-run, gate v2 and its re-run. None set a value; see the protocol note below |
| Provider | live calls only (`--no-cache`): 53 requests, 0 cache hits, 0 errors, 0 degraded-mode tickets |

## Business

| Figure | Value | Target | Met |
| --- | --- | --- | --- |
| Auto-resolution rate | 63.8% (51 of 80) | 50% or more | yes |
| Escalation rate | 36.2% (29 of 80) | 50% or less | yes |
| Estimated first-contact resolution (replay FCR: automatic answers on tickets labelled expected_route = auto_respond, passed Validate, / all tickets) | **47.5%** (38 of 80) | 50% or more | **no** |

## Technical

| Figure | Value | Target | Met |
| --- | --- | --- | --- |
| Intent accuracy | 100% (80 of 80); macro precision / recall 100% / 100% | 85% or more (NFR-03) | yes |
| Urgency accuracy | **41.2%** (33 of 80) | none set | weak |
| Confusion matrix, intent | all 80 on the diagonal (22 classes; full matrix in `metrics_report.json`) | | |
| Confusion matrix, urgency (rows label, columns predicted; high/low/medium) | high 6/2/17; low 1/2/17; medium 8/2/25 | | |
| Latency p50 / p95, ingest to final action | 2,500 ms / 4,082 ms | | |
| Latency p50 / p95, excluding provider waits (NFR-01) | 1,832 ms / **3,078 ms** | p95 under 3,000 ms | **no** (by 78 ms) |
| Stage latency p95 | classification 10 ms, retrieval 14 ms, generation 4,016 ms | | |
| Citation validity: generated answers whose citations resolve, checked in code | 100% (53 of 53) | | yes |
| Citation validity: sent answers with every cited passage in the retrieved set | 100% (51 of 51) | 100% | yes |
| Sent answers citing a labelled expected article (reported only: labels per intent, AS-03, AS-07) | 94.7% (36 of 38 with expected articles) | | |
| Retrieval hit rate, top 3 (answerable, n = 53) | 88.7%; with subject 87.5% (n = 40), without 92.3% (n = 13) | 85% or more (AS-01) | yes |
| Guardrail blocks | **2** (grounding: VAL-0036, VAL-0050); 0 private data, citations, integrity, commitments, confidence floor; 11 style warnings | | |
| Hallucination rate / human citation accuracy (NFR-08) | not measured yet: `answer_review.csv` (51 answers) awaits review | 5% or less / 95% or more | pending |

## Safety

| Figure | Value | Required |
| --- | --- | --- |
| Private data in outbound responses: **every** outbound message scanned (51 sent answers + 29 holding messages), against the private-data patterns and all 140 customer names and ids in the input file | **0** | 0 |
| Unsafe automatic answers (must_not_auto_respond ticket answered) | 0 | 0 |

## Reconciliation

| Figure | Value |
| --- | --- |
| Final decision-log rows | **80 for 80 tickets**, one per ticket, 0 missing, 0 duplicate, 0 empty required fields |
| Independent gate check (`gate_check.md`) | GATE PASSED, all 7 checks |
| Report vs results.jsonl | every figure matches |

## All tickets vs unseen text (FR-28)

| Subset | n | Auto rate | Intent acc | Hit@3 |
| --- | --- | --- | --- | --- |
| all | 80 | 63.8% | 100% | 88.7% |
| unseen | 35 | 57.1% | 100% | 85.0% |
| repeats dev text | 45 | 68.9% | 100% | 90.9% |

## Bad numbers, kept as they are (triggers for the 5.20 revision log)

1. Replay FCR 47.5%, under the 50% target. The label follows past handling (AS-07), so this is a floor, but it is the defined measure.
2. NFR-01 p95 3,078 ms excluding waits, 78 ms over. Generation alone is p95 4,016 ms; every other stage is under 20 ms.
3. Urgency accuracy 41.2%: most tickets are predicted medium (59 of 80).
4. Segments (NFR-06): every dimension's gap is over 5 points (tier 22.3, region 10.7, fluency 18.0, channel 25.6, length 21.8 points, eligible auto rate). Groups are 6-22 eligible tickets, so one ticket moves a group 5-17 points; 5b.3 pools data and adds intervals.
5. Unseen tickets: auto rate 57.1% against 68.9% on repeats of dev text.
6. NFR-08 not yet measured.
7. Validate's latency is logged as 0 ms (it is not timed): a logging gap, not a result.

## Protocol note (as recorded in the PRD, OQ-02)

Protocol (no assessor answer): development tickets for building and tuning, with a 20% dev hold-out split by text for every threshold; validation for checking only; every validation run logged with its date and counted. Count on this file: 11 harness runs, 19-20 Nov 2026; this evaluation is run 11. No value was set on validation. One disclosed exception in spirit: the retrieval query change (FR-09) was prompted by the chat gap seen on a validation run; its setting and cutoff were chosen on the dev hold-out by a rule fixed before the experiment, and validation only checked it.
