# Review rubric (5.18, NFR-08)

Written before any scoring. Both assessors use this rubric, the same `review_packet.md`, and their own sheet
(`assessor_A.csv` or `assessor_B.csv`). Do not open the other sheet until both are finished. Do not edit any
response. Judge only what is in the packet: the ticket, the response, and the passage text shown.

Each row of the sheet is one sampled ticket. `item_type` says which fields apply. Leave the other fields empty.

| Field | answered | blocked | escalated | Values |
| --- | --- | --- | --- | --- |
| `unsupported_sentences` | yes | yes | | 0 to `sentences` |
| `citations_supporting` | yes | yes | | 0 to `citations` |
| `block_justified` | | yes | | y / n |
| `escalation_correct` | | | yes | y / n |
| `summary_accurate` | | | yes | y / n |
| `correctness`, `completeness`, `tone` | yes | yes | yes | 1 to 5 |
| `notes` | when anything is not a clean pass | | | free text; name the sentence number |

## 1. Hallucination: `unsupported_sentences`

Count the numbered answer sentences (the "Answer sentences and their citations" list) that contain **any claim
not supported by the passage(s) that sentence cites**. A claim is supported if the cited passage states it or
it follows directly from the passage. It is not supported if it adds a fact, number, step, product behaviour,
time, promise or condition that the cited passage does not contain, even if it might be true. It is also not
supported if it contradicts the passage.

- Paraphrase is fine. Dropping a qualifier that changes the meaning ("usually" becoming "always") is unsupported.
- Judge each sentence against **its own** citations, not against other passages.
- A sentence that is supported but does not answer the customer's question is not a hallucination. Score that
  under completeness or correctness.
- The fixed opening and closing lines and the source list are added by code. Do not score them.

An answer **hallucinates** if `unsupported_sentences` is 1 or more.

## 2. Citation accuracy: `citations_supporting`

`citations` is the number of sentence-to-passage links (a sentence citing two passages counts twice). Count how
many links point to a passage that **supports the claim in that sentence**. A link to a passage that is on the
right topic but does not contain the claim does not count. Every citation already resolves to a real retrieved
passage (checked in code); this field judges support, not existence.

Citation accuracy = supporting links / all links.

## 3. Escalated items

- `escalation_correct`: **y** if a person should handle this ticket: it is a must-escalate class (security,
  compliance, data residency, feature request, unclear request, billing dispute), the docs cannot answer it,
  or answering automatically would be unsafe. **n** if the help articles shown could have answered it safely
  and fully, so escalating was unnecessary.
- `summary_accurate`: **y** if the summary and restatement describe the ticket without adding anything the
  ticket does not say. **n** if either adds or distorts a fact. This is the hallucination check for text
  that reaches the agent.

## 4. Blocked items

The draft was never sent. Score it as if it had been sent (sections 1, 2 and 5), then:

- `block_justified`: **y** if the draft has a real problem that should stop it (an unsupported claim, a wrong
  answer, private data, a promise). **n** if the draft was fit to send and the block was a false positive.

## 5. CSAT proxy: `correctness`, `completeness`, `tone` (1 to 5 each)

Score as the customer would experience it. For escalated items, judge the holding message the customer gets and
whether escalating was the right outcome for them.

| Score | correctness | completeness | tone |
| --- | --- | --- | --- |
| 5 | fully right for this ticket | covers everything the customer needs to act | clear, polite, plain, right length |
| 4 | right, one minor imprecision | covers the main need, misses a minor point | good, minor awkwardness |
| 3 | partly right, or right but for a slightly different problem | covers part of the need | acceptable, noticeably stiff or long |
| 2 | mostly wrong or misleading | leaves the main need unanswered | unclear or off-putting |
| 1 | wrong or harmful | nothing useful | inappropriate |

For escalated items: correctness = was escalating the right outcome (5 if clearly right, 1 if it plainly should
have been answered); completeness = does the holding message tell the customer what happens next; tone = the
holding message.

The CSAT proxy for an item is the mean of the three scores.

## 6. How the figures are computed (`python -m evaluation.review_score`)

- Hallucination rate = sent answers with 1 or more unsupported sentences / sent answers reviewed. Reported
  per sentence too, and separately for blocked drafts and escalation summaries.
- Citation accuracy = supporting links / all links, sent answers (blocked drafts separately).
- Mean CSAT proxy = mean of the item means, overall and by item type.
- Agreement between assessors: percentage agreement and Cohen's kappa for the y/n judgements and the
  hallucination flag; quadratic-weighted kappa and within-one-point agreement for the 1 to 5 scores.
- Disagreements: any y/n field or hallucination flag that differs, a `citations_supporting` count that
  differs, or a 1 to 5 score that differs by 2 or more. Each is settled by re-reading the packet against
  this rubric and recorded in `adjudication.csv` with the final value and how it was settled. A 1 to 5
  score that differs by 1 is not a disagreement: the mean of the two is used.
- Final figures use the agreed value where the assessors agree, the adjudicated value where they did not.
