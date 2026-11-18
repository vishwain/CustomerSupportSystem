# Risk Register — Notes Outside the Workbook

Workbook: Section 5, Initial risk register. Eight rows: four starter, four added.

## Template gaps
- The Stage 1 table has no early-warning or citation column. Early warning sits at the end of the last column. Citations sit under each risk.
- The Governance Framework register needs an owner per risk. Stage 1 has none. Name owners in Stage 5.
- Governance register has four risks Stage 1 does not: R-03 ticket text treated as an instruction, R-06 model provider down, R-07 latency under load, R-08 cost rises with volume.
  - Not drawn from Stage 1 evidence, so left out here. Add in Stage 5.
  - R-03 matters: tickets are customer-written text going into a prompt.

## Added risks, and where each came from
| # | Risk | Source in workbook |
|---|---|---|
| 5 | Targets past what labels allow | S4 escalation, FCR rows. S2 answerable, escalation rows |
| 6 | Fast but wrong looks like success | S2 first-contact row. S4 reply time, wrong answers rows |
| 7 | Test scores overstate quality | S5 validation tickets row |
| 8 | Non-fluent customers can't use the reply | S2 non-fluent row. S1 reply-language row |

## Open points
- Risk 5: "97% of automatable tickets right" = 60 / 62. Both are rounded workbook figures. Recomputed 18 Nov: 60 / 62.2 = 96.5%, rounds to ~97%. PRD figure stands.
- Risk 3: Non-fluent shows no gap today. The risk is that retrieval creates one. Only the fairness audit can show it.
- Risk 8: Nothing in the data tests reply comprehension. Needs hand review of drafts.
- Likelihood and impact are my ratings (High/Medium/Severe). No scale is defined in the workbook. Decided 18 Nov: Brief §08 3×3 matrix, Severe = High. Stated in PRD 10.7 with a rating per risk. All 8 risks carried into PRD 10.7.
