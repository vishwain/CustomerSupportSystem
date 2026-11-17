# Success Measures — Notes Outside the Workbook

Findings from Stage 1, Section 4 (what the client counts as success) that don't fit the workbook table.
Feed into PRD success measures (Stage 2) and the evaluation report.

---

## 1. Reported vs real metric
- Marcus reports **reply time** (it's in the SLA). He cares about **first-contact resolution** (escalation costs ~4x, angers customers more than waiting).
- Exec team sees only the reported figure. A project that moves FCR but not reply time could still look like a failure upstairs.
- Our data can't measure reply time. No first-response field. Only `resolution_time_minutes`.
- **Implication:** evaluation report must translate FCR gains into what Marcus reports. Auto-responses give a near-zero first reply by design; state that, don't claim it from data.

## 2. Measures nobody owns
| Measure | Gap | Action |
|---|---|---|
| CSAT | No interviewee quotes it. Brief 3.2, data 2.97. | Ask who reports it. Use data baseline, state both. |
| Repeat contacts | Brief "not measured". Field exists (21.6%) but definition unclear. | Agree a definition before setting a target. |
| Agent workload | Only anecdote. No minutes per agent. | Proxy: escalation-weighted tickets, or minutes saved by drafts. |
| Service per tier | Nobody watches. Enterprise already worst. | Add to fairness audit and monitoring dashboard. |
| Service per fluency | Nobody watches. Currently no gap. | Monitor so the system doesn't create one. |
| Wrong answers sent | Marcus's #1 failure. No baseline. | Track via hallucination rate, must_not_claim hits, customer corrections. |

## 3. Success conditions that are not metrics
- **Explainability.** Marcus has a compliance review in the autumn. Success = every decision explainable. Maps to decision log coverage (Brief governance: complete coverage).
- **No extra work for agents.** Canned responses failed this way. Success = drafts used, not rewritten. Possible measure: share of drafts sent with light edits.
- **Honesty about automation.** Ravi wants AI-drafted replies labelled. Not a metric. A requirement.

## 4. No cost data
- Marcus: escalation costs ~4x a resolved ticket. No currency figure, no cost per ticket, no agent cost.
- Can't state savings in money. Report minutes and escalations avoided instead.
- Open question for the PRD: cost per ticket, cost per escalation.

## 5. Still open in Section 4
- The sentence test (three prompts below the table) is not yet filled.
- Needs a decision on which targets to adopt where the Brief conflicts (FCR 60 vs 65, CSAT 4.0 vs 4.2, reply 2 hrs vs 5 min). See `DocumentInconsistencies.md` I4–I7.
