# Deadline Planning Notes (found while writing Stage 4)

Facts and gaps noticed on 18 Nov while reviewing the project for the Stage 4 workbook.
Each point stands on its own evidence (cited). None of it comes from the sprint plan's schedule.

> **Do not use `Workbooks/Stage_4_Sprint_Plan.docx` as context.** It is a submission artefact only and is not being followed. Its hours, order, scope and cuts are not project decisions. Real state lives in the PRD, the prompt library, `FDE_Capstone_Checklist.md` and these notes.

---

## 1. Hours so far (Effort Log, 18 Nov)
- 26 h logged, 3 to 18 Nov: 3 + 5 + 6 + 6 + 6.
- Effort Log Section 2 plans 40 h, 6.67 h per stage. Discovery rows alone hold 20 h (15 and 16 Nov rows include repo setup and environment).
- Section 2 "why the difference" will need this split. Setup time sits under Discovery today.
- Effort Log has no row yet for the Stage 4 session on the night of 18 Nov.

## 2. Build-order facts from the pack
- **Decision log before the first harness run.** The Stage 4 template has B-10 (logging) depend on B-07 (routing). But A8 reconcile and the checklist (5.3) need the log from the first run. Build it with the harness, not after routing.
- **Failure handling before the first full run.** 80 tickets in sequence will meet rate limits (Build Spec §02, A9 box). Timeout, 429 backoff and circuit breaker (PRD 10.6) should exist before the gate, not after.
- **Gate file.** Stage 4 template and checklist 4.3 say "hidden set". PRD OQ-01 default says validation. The report must name the file used.
- **Build Spec §05 fallback.** If behind, narrow the intents that auto-answer; keep the unattended run. Two intents done properly passes the gate.

## 3. Call budget for full runs
- Validation automated ceiling: 45 of 80 (PRD_Requirements_Notes §10). Drafts for below-threshold tickets add calls. Expect roughly 45 to 60 calls per full run, plus JSON repairs.
- With the $10 credit (1,000 a day, PRD NFR-07) several full runs fit in a day. Without credit (50 a day) not even one.
- Cache responses on disk from the first call so re-runs cost nothing (Build Spec §07).

## 4. Cheapest scope to drop if time runs out
- Checklist 5b.8 Prometheus + Grafana = PRD FR-34, a Should. Nothing in A1 to A12 needs it. Metrics report (FR-27) already carries the figures.
- PRD Could FRs (FR-30, FR-29, FR-10, FR-07) next. Seed order in PRD_Requirements_Notes §1.
- Never drop: the unattended run, decision log, a blocking guardrail, tests, README rehearsal, PRD v2.0 (compulsory).

## 5. Video and report risks
- Record the full unattended run while it happens. Build Spec §01: if live assessment fails, the recording is the evidence.
- Video needs at least 7 min live demo (Submission Guide; checklist 6.15). A provider limit during recording is a real risk; keep cached responses for the demo tickets.
- Report needs gate figures, run date and run count (checklist 6.7). These come only after the full run.

## 6. Where report sections can draw from (existing material)
| Report section | Existing source |
|---|---|
| Problem, discovery | Stage 1 workbook; ProblemStatement_Traceability.md; InterviewScratchList.md |
| Requirements | PRD v1.0; PRD_EngineerReview.md |
| Architecture | PRD Section 10, Figure 2 (`docs/architecture_flow.dot`) |
| Evaluation caveats | DataSources_Notes.md §1–2 (35 unseen of 80, label noise) |
| Governance | DecisionLog_Design.md; RiskRegister_Notes.md |
| Revision | PromptLibrary_Notes.md §2 (chunk count wrong, unsure_about gap) |
| AI tool use declaration | PromptLibrary_Notes.md §5 |

## 7. Calendar
- 21 Nov 2026 is a Saturday. Checklist deadline is 23:59.
