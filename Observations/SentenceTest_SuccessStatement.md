# Sentence Test — Success Statement (Stage 1 → Stage 2)

Copied from Discovery Workbook, Section 4. Every figure traces to a row in Section 2 or Section 4.
Use as the core of the PRD success measures (Stage 2).

---

## 1. Worth doing if, within three months of launch…
- First-contact resolution rises from 42% to at least 60%.
- First reply meets the 2-hr SLA.
- CSAT moves up from 2.97 toward 4.0.
- No tier gets worse. Enterprise starts at 37.3% FCR.
- Wrong answers sent stay near zero.

## 2. We will know it did not work if we see…
- FCR still near 42–43.8%. Escalation still near 56–58%.
- Any confidently wrong answer reaching a customer.
- The tier gap widening. Enterprise FCR below 37.3%.
- Agents rewriting drafts. More work than saved, as with canned responses.
- Escalation pushed below the 37.8% the labels require. Means unsafe auto-answers.

## 3. The measure the client will actually be judged on internally is…
- Time to first reply against the 2-hr SLA (8–12 hrs today).
- It is the red number Marcus reports to the exec team.
- FCR (42%, benchmark 65%) is what drives it and what he cares about.
- Escalation costs ~4x. The project must move both.

---

## Traceability

| Figure | Source |
|---|---|
| FCR 42% baseline, 60% target, 65% benchmark | Section 4, FCR row (Marcus, Brief §1, §7) |
| FCR 43.8% (data) | Section 2, FCR row |
| 2-hr SLA, 8–12 hrs | Section 4, reply time row |
| CSAT 2.97, target 4.0 | Section 2 CSAT row; Section 4 CSAT row (Brief §7) |
| Enterprise FCR 37.3% | Section 2 tier row; Section 4 tier row |
| Escalation 56–58% | Section 2 (56.2%); Section 4 (Brief 58%) |
| 37.8% must escalate | Section 4 escalation row (labels) |
| Escalation ~4x cost | Section 3 evidence (Marcus) |
| Wrong answers near zero | Section 4 wrong-answers row (Marcus) |

## Choices made (confirmed in PRD, 18 Nov)
- **FCR target 60%, not 65%.** Brief §7 success table. 65% kept as benchmark.
- **Reply target = 2-hr SLA.** Brief §7's 5-min figure applies only to auto-responses. See `DocumentInconsistencies.md` I6.
- **CSAT "toward 4.0", not "reach 4.0".** 2.97 → 4.0 in three months is not credible. Interim target set: 3.5 at 3 months, 4.0 end goal (PRD Section 8).
- **No escalation target stated.** Brief's ≤30% is below the 37.8% label floor. Sentence 2 sets the floor as a failure signal instead.
- **Judged-on measure = reply time.** It's what reaches the exec team. FCR is the driver. Both go in the PRD as primary measures.

## Gaps
- Reply time can't be measured from baseline data. The PRD needs a measurement plan for after launch.
- "Wrong answers near zero" has no baseline. Define it in the PRD (hallucination rate ≤5%, must_not_claim hits = 0).
