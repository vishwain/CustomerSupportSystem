# Document Inconsistencies and Open Observations

Points found during Stage 1 that do not belong in the Discovery Workbook.
Mostly contradictions between project pack documents. Each has an impact and a working assumption.
Raise with the assessor where marked. Log assumptions in the PRD (Stage 2, assumptions section).

Source of data figures: `docs/discovery_analysis.py` on `data/development_tickets.json`.

---

## 1. Contradictions between project documents

| # | Topic | Doc A says | Doc B says | Impact | Working assumption |
|---|---|---|---|---|---|
| I1 | Hidden evaluation set size | Dataset Guide, README: 120 tickets | Build Spec, Project Instructions, Evaluation Framework: 100 tickets | Harness must not assume a count | Harness processes whatever file it is given. No hardcoded size. |
| I2 | Validation set usage | Brief: final evaluation, run once. Do not look or tune. | Dataset Guide, README: use as often as you like | Changes dev workflow | Follow Dataset Guide (newer, more specific). Report every validation run anyway. **Ask assessor.** |
| I3 | What the gate runs on | Brief, Build Spec: hidden evaluation set | README, Project Instructions checklist: full validation set | Which file the unattended run is tested on | Make harness path-driven. Test unattended run on validation set. |
| I4 | FCR target | Brief, section 1: 65% or better | Brief, section 7: 60% or better | Which target the report measures against | Use 60% (success measures table). Note 65% as client aspiration. |
| I5 | CSAT target | Brief, section 1: 4.2 | Brief, section 7: 4.0 | Same | Use 4.0. Note 4.2. |
| I6 | First reply target | Brief, section 1: under 2 hours (SLA) | Brief, section 7: under 5 minutes | Latency design and reporting | 5 min for auto-responses. 2 hr SLA for escalated tickets. |
| I7 | FCR vs escalation targets | Brief defines FCR = closed without escalation / total | Targets: FCR ≥60% AND escalation ≤30% | FCR = 1 − escalation (500/500 tickets). 60% FCR means 40% escalation. Targets can't both define the same split. | Treat escalation ≤30% as unreachable as written. See D1. |
| I8 | Documentation categories | Dataset Guide: "eight categories" | Same sentence lists ten. `documentation.json` has 10. | None for build. Shows guide figures need checking. | Use 10: authentication 4, deployment 4, api 3, performance 3, billing 3, data 3, security 3, account 2, integration 2, onboarding 2. |
| I9 | Submission deadline | Pack: 13 September | Actual: 21/11/26 | Planning | 21/11/26. |

---

## 2. Data observations outside the workbook tables

| # | Observation | Evidence | Design question |
|---|---|---|---|
| D1 | Escalation target below the label floor | expected_route = escalate: 37.8%. must_not_auto_respond: 17.4%. Brief target ≤30%. | Reset target in PRD, or count escalation-with-context as success? |
| D2 | Automation ceiling ≈ 62%, not 71% | 71.4% answerable. 87.1% of those auto-eligible. auto_respond = 62.2% overall. | Set PRD automation target against 62%. |
| D3 | Doc review age unverifiable | `last_reviewed_days_ago` = 0 for all 29 articles | Can't test Ines's review cycle. Treat as open question, not evidence. |
| D4 | Brief baseline CSAT higher than data | Brief 3.2. Data 2.97. | Report improvement against data baseline. State both. |
| D5 | Repeat contact field undefined | `repeat_contact` 21.6%. Brief definition (same customer + intent, 7 days) finds 1 ticket. | Define the metric before targeting "reduce by half". |
| D6 | No first-response time in data | Only `resolution_time_minutes` exists | Headline SLA metric unmeasurable from baseline. Log as open question. |

---

## 3. To raise with the assessor
- I2: which rule governs the validation set. Still open (PRD OQ-02, default: never tune on validation, log every run).
- I1 / I3: RESOLVED 18 Nov. Gate runs on validation (OQ-01). Hidden-set size does not matter; harness takes any count (OQ-03).
- I7 / D1: still open (PRD OQ-07, default: replay 50% or less, live 40% or less, never below 37.8%).
