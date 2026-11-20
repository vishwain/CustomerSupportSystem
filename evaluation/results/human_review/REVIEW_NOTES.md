# Review findings for the 5.20 revision log

From the 5.18 review of the 5.17 run (59 items; final figures in review_results.md). Responses were not edited
and no code changed during the review.

| # | Finding | Evidence | Against |
| --- | --- | --- | --- |
| 1 | **Hallucination rate 13.3% of sent answers (4 of 30), target 5% or less: NFR-08 fails.** Per sentence 4.4%. All four are the same kind: the answer drops a qualifier or changes the condition the passage puts on a step. No invented facts, numbers or promises were found. | VAL-0016 s4 ("request count" for "request concurrency"); VAL-0025 s2 and VAL-0057 s2 ("thirty seconds" stated as the setting, the passage says "a reasonable starting point for services that load models or caches"); VAL-0064 s1 ("large result sets" for "anything that may change while you iterate") | NFR-08, PR-03 |
| 2 | Citation accuracy 95.7% (88 of 92 links), target 95% or more: met, by one link. The 4 failing links are the 4 sentences above. | review_results.md | NFR-08 |
| 3 | Grounding check (Validate) does not catch dropped qualifiers: all four hallucinating answers passed it. | the four items above, all sent | FR-22 |
| 4 | **Both blocked drafts were false positives** (0 of 2 blocks justified): word-for-word from DOC-ONB-001 and right for the ticket. The opening sentence scored 0.18 against the 0.21 grounding floor. | VAL-0036, VAL-0050 | FR-22 grounding floor |
| 5 | 3 of 27 escalations were unnecessary (88.9% correct): the right article scored just under the 0.51 retrieval cutoff. VAL-0031 is the same text as VAL-0011, which was answered. | VAL-0014 (0.48), VAL-0031 (0.51), VAL-0029 (0.44) | FR-09 cutoff |
| 6 | **A possible security exposure was answered automatically.** Both assessors flagged it independently: the customer pushed a key to a public repo; the answer's two sentences (rotate first, then revoke; revoke immediately) conflict for that case. Not in the must-escalate rules or risk terms. | VAL-0039 | FR-12, NFR-09 |
| 7 | The holding message gives no timeframe or first step for urgent outages and security incidents (completeness 3 of 5 on all eight). | VAL-0014, 0031, 0038, 0043, 0048, 0049, 0067, 0068 | FR-18 messages |
| 8 | Escalation summaries were accurate on all 27 (no added facts). | review_results.md | FR-13 |
| 9 | Limits of this review: both assessors are LLMs of the same family as the assistant that helped build the system; disagreements were settled by that assistant. No human scored the sample. | ASSESSORS.md | NFR-08 method |
