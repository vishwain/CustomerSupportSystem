# Human review results (5.18)

Sample: 59 items (30 sent answers, 2 blocked drafts, 27 escalations); see SAMPLE.md. Rubric: RUBRIC.md.

Assessor A: LLM: Claude Sonnet 5.5 (Anthropic), run as a separate agent that was given only RUBRIC.md, review_packet.md and its blank sheet; no access to the build conversation, the code, or Assessor B's sheet. Assessor B: LLM: Claude Opus 5.5 (Anthropic), run as a separate agent that was given only RUBRIC.md, review_packet.md and its blank sheet; no access to the build conversation, the code, or Assessor A's sheet. Scored independently; neither saw the other's sheet before finishing.

| Figure | Assessor A | Assessor B | Final (agreed + adjudicated) |
| --- | --- | --- | --- |
| Hallucination rate, sent answers (any unsupported sentence) | 16.7% | 13.3% | 13.3% |
| Unsupported sentences, sent answers | 5.5% | 4.4% | 4.4% |
| Citation accuracy, sent answers (supporting links) | 97.8% | 95.7% | 95.7% |
| Mean CSAT proxy (1 to 5), all items | 3.85 | 4.18 | 4.02 |
| Escalation was the right call | 85.2% | 88.9% | 88.9% |
| Escalation summary accurate (no added facts) | 100.0% | 100.0% | 100.0% |
| Blocked drafts: block justified | 0 of 2 | 0 of 2 | 0 of 2 |
| Blocked drafts: hallucination rate | 0.0% | 0.0% | 0.0% |
| Blocked drafts: citation accuracy | 100.0% | 100.0% | 100.0% |

NFR-08 targets: hallucination 5% or less, citation accuracy 95% or more (final: 13.3% / 95.7%).

Mean CSAT proxy by item type (final): answered 4.07, blocked 4.25, escalated 3.95

Hallucinating items (final): VAL-0016, VAL-0025, VAL-0057, VAL-0064

## Agreement between assessors

| Judgement | n | Agreement | Kappa |
| --- | --- | --- | --- |
| Hallucination flag | 32 | 96.9% | 0.871 |
| citations_supporting count (exact) | 32 | 87.5% | |
| block_justified | 2 | 100.0% | 1.0 |
| escalation_correct | 27 | 88.9% | 0.509 |
| summary_accurate | 27 | 100.0% | 1.0 |
| correctness (1 to 5) | 59 | exact 71.2%, within 1 98.3% | weighted 0.749 |
| completeness (1 to 5) | 59 | exact 44.1%, within 1 86.4% | weighted 0.27 |
| tone (1 to 5) | 59 | exact 83.1%, within 1 100.0% | weighted 0.22 |

Kappa is undefined-but-reported-as-1.0 when both assessors give the same single value to every item.

## Disagreements (17)

| Ticket | Field | A | B | Final | How settled |
| --- | --- | --- | --- | --- | --- |
| VAL-0014 | completeness | 2 | 4 | 3 | Re-read against RUBRIC.md by the adjudicator. Holding message says a person will reply (what happens next) but gives no timeframe or first step for an urgent outage or security case: 'covers part of the need' (3). One rule for all eight urgent escalations. |
| VAL-0025 | citations_supporting | 4 | 3 | 3 | Re-read against RUBRIC.md by the adjudicator. Both assessors count s2 unsupported (drops 'a reasonable starting point for services that load models or caches'). Rubric 2: a link counts only if it supports the claim, so s2's link does not: 3 of 4. |
| VAL-0029 | escalation_correct | y | n | n | Re-read against RUBRIC.md by the adjudicator. Onboarding question, not a must-escalate class; DOC-ONB-001 answers it (best score 0.44, under the cutoff; the same article answers VAL-0036/0050). Unnecessary escalation caused by a retrieval miss, ruled the same way as VAL-0014 and VAL-0031, where both assessors said n. |
| VAL-0031 | completeness | 2 | 4 | 3 | Re-read against RUBRIC.md by the adjudicator. Holding message says a person will reply (what happens next) but gives no timeframe or first step for an urgent outage or security case: 'covers part of the need' (3). One rule for all eight urgent escalations. |
| VAL-0038 | escalation_correct | n | y | y | Re-read against RUBRIC.md by the adjudicator. p95 doubled with no customer change may be a platform issue; DOC-PERF-001 helps only partly. Rubric 3 says n only if the docs answer it safely and fully, which they do not. |
| VAL-0038 | completeness | 2 | 4 | 3 | Re-read against RUBRIC.md by the adjudicator. Holding message says a person will reply (what happens next) but gives no timeframe or first step for an urgent outage or security case: 'covers part of the need' (3). One rule for all eight urgent escalations. |
| VAL-0041 | unsupported_sentences | 1 | 0 | 0 | Re-read against RUBRIC.md by the adjudicator. s2 'may be running and accruing charges': the passage says these environments are billed at the production rate, so they accrue charges; this follows directly (rubric 1). Loses the passage's point (same rate as production), scored under completeness instead. |
| VAL-0041 | citations_supporting | 2 | 3 | 3 | Re-read against RUBRIC.md by the adjudicator. Follows from the s2 ruling: all 3 links support. |
| VAL-0043 | completeness | 2 | 4 | 3 | Re-read against RUBRIC.md by the adjudicator. Holding message says a person will reply (what happens next) but gives no timeframe or first step for an urgent outage or security case: 'covers part of the need' (3). One rule for all eight urgent escalations. |
| VAL-0048 | completeness | 2 | 4 | 3 | Re-read against RUBRIC.md by the adjudicator. Holding message says a person will reply (what happens next) but gives no timeframe or first step for an urgent outage or security case: 'covers part of the need' (3). One rule for all eight urgent escalations. |
| VAL-0049 | escalation_correct | n | y | y | Re-read against RUBRIC.md by the adjudicator. Subject says the key is exposed; a possible exposure is unsafe to answer automatically even though the body is a scope question (rubric 3: unsafe to answer). |
| VAL-0049 | correctness | 2 | 4 | 4 | Re-read against RUBRIC.md by the adjudicator. Escalation ruled correct, so correctness follows B. |
| VAL-0049 | completeness | 2 | 4 | 3 | Re-read against RUBRIC.md by the adjudicator. Holding message says a person will reply (what happens next) but gives no timeframe or first step for an urgent outage or security case: 'covers part of the need' (3). One rule for all eight urgent escalations. |
| VAL-0057 | citations_supporting | 4 | 3 | 3 | Re-read against RUBRIC.md by the adjudicator. Same sentence and passage as VAL-0025; same ruling: 3 of 4. |
| VAL-0064 | citations_supporting | 3 | 2 | 2 | Re-read against RUBRIC.md by the adjudicator. Both count s1 unsupported (condition changed from 'anything that may change while you iterate' to 'large result sets'); its link does not support it: 2 of 3. |
| VAL-0067 | completeness | 2 | 4 | 3 | Re-read against RUBRIC.md by the adjudicator. Holding message says a person will reply (what happens next) but gives no timeframe or first step for an urgent outage or security case: 'covers part of the need' (3). One rule for all eight urgent escalations. |
| VAL-0068 | completeness | 2 | 4 | 3 | Re-read against RUBRIC.md by the adjudicator. Holding message says a person will reply (what happens next) but gives no timeframe or first step for an urgent outage or security case: 'covers part of the need' (3). One rule for all eight urgent escalations. |
