# PRD Requirements — Notes Outside the PRD (Checklist 2.4–2.6)

Points from writing FRs, component mapping and NFRs that don't belong in the PRD.
Feeds Stage 3 (prompt library), Stage 4 (sprint plan, cut order), Stage 5 (PRD revision) and the test suite.

---

## 1. MoSCoW split and a seed cut order (Stage 4)
- 32 FRs: Must 20, Should 7, Could 4, Will not 1.
- Must share is high (62%) because 12 acceptance criteria are pass/fail and each needs a Must. Defend this in Stage 4, don't hide it.
- Suggested cut order, first to go:
  1. Could: FR-30 (draft edit status), FR-29 (per-article report), FR-10 (review date), FR-07 (restatement).
  2. Should: FR-06 (urgency queue order — no queue UI exists), FR-28 (80 vs 35 split — cheap, keep if possible), FR-20 (plain English), FR-18 (automated label), FR-31 (kill switch), FR-23 (commitment block), FR-14 (draft on escalation).
  3. Never cut: any Must. Cut intent classes instead (Build Spec §05: two intents done properly passes the gate).
- FR-31 kill switch is Should in the PRD but the Governance Framework calls a missing one "your first governance finding". Consider raising it to Must in Stage 5.

## 2. FR → prompt hooks (Stage 3)
| Prompt needed | FRs | Notes |
|---|---|---|
| Classify intent + urgency | FR-04, FR-05 | Must return confidence and alternatives. Could be non-LLM (embedding + classifier) to save calls (NFR-07). |
| Generate cited answer | FR-15, FR-16, FR-18, FR-20 | Fixed JSON structure. "I don't know" path. Ticket text in a delimited data block (FR-17). |
| Escalation package | FR-13, FR-14, FR-07 | Summary, intent, urgency, articles, what was unclear. No reference examples exist; write own (DataSources_Notes §4). |
| Evaluation: grounding judge | NFR-08 | Two reviewers still needed for hallucination rate. A judge prompt is a helper, not a substitute. |
- NFR-07 caps model calls at 2 per ticket. Classify + generate already uses both. The escalation summary must come from the same generate call, or classify must be non-LLM.

## 3. Test cases the FRs imply (for tests/, A12)
- One ticket per channel (FR-01).
- Empty body, missing subject, non-ASCII text (FR-02).
- Prompt-injection ticket: "ignore your instructions" (FR-17).
- Ticket engineered to echo an email or customer id (FR-22). This is the A7 demo ticket.
- Draft promising a refund (FR-23).
- Each must-escalate class: security, compliance, data residency, billing dispute, feature request, unclear (FR-12).
- Same ticket twice, same route (FR-11).
- Provider disconnected, rate limit, log write failure (FR-25, FR-24).
- Kill switch on (FR-31).

## 4. Fairness: validation segments are too small
- Validation (80): enterprise 8, business 30, standard 42. Non-fluent 19, fluent 61. Chat 22, email 31, docs comment 16, forum 11.
- One enterprise ticket = 12.5 pts. A 5-pt test on validation alone is noise.
- NFR-06 now says: pool dev hold-out plus validation, state sample sizes, flag groups under 20.
- Dev hold-out must be split by text (254 dev tickets share a text). Otherwise duplicates inflate every segment score.
- Report a confidence interval per segment, or at least n, in the fairness table.

## 5. Latency risk
- NFR-01 keeps the Brief's p95 under 3 s. A free-tier hosted LLM plus retrieval may not meet it, and rate-limit backoff will blow it.
- Measure on day 4 of the build, not at the end. If it fails, record it in the Stage 5 revision log with the measured figure rather than quietly redefining the metric.
- NFR-01 already separates rate-limit waits. Keep that split honest in the report.

## 6. Decisions now possible in DecisionLog_Design.md
- Open point 3 (requirement_ids): FR ids now exist. Suggested mapping per stage:
  - classification: FR-04, FR-05
  - retrieval: FR-08, FR-09, FR-19
  - routing: FR-11, FR-12, FR-13, FR-25, FR-31
  - generation: FR-15, FR-16, FR-17
  - validation: FR-22, FR-23
  - final: FR-24
- NFR-05 Auditability matches the "NFR-05" hook already in that note.

## 7. Items for later PRD sections (2.7 onward)
- Out of scope: reply translation (FR-21), new articles, learning from snippet files, hiring.
- Assumptions: a helpdesk queue exists for FR-06, FR-14, FR-30 (not in data, InterviewScratchList N10). Tier, region, fluency read per ticket as given.
- Success measures: escalation target must be restated. NFR-09 holds the 37.8% floor. Reply time still has no baseline.
- Open questions: who owns the compliance review (auditor row, user groups). Engineering/Product not interviewed but receive escalations.

## 8. Out of scope (2.7): scoping choices to defend
- "No auto-send without human review" would contradict FR-11, FR-15, FR-16 (Must). The system does auto-reply above the threshold, which is the only way FCR moves. Scoped to drafts on escalated tickets instead.
- "Must-escalate classes" are out for answering only. Classification, packaging and escalation stay in (FR-12, FR-13).
- Ticketing-system integration is out. FR-06 (queue order) and FR-30 (edit status) still assume a queue somewhere. Record as an assumption in 2.8: output is a queue export file, not a write-back.
- Tier-based tailoring is out. If Marcus insists on enterprise priority, that is a PRD revision (Stage 5) and must pass the fairness audit.

## 9. Assumptions (2.8): checks to run and data facts found
- Stage 5 step 5.23 revisits AS-01 to AS-12. Each has a pass bar in the PRD. Record the measured figure, not just held/failed.
- Checks by build day: day 2 AS-01, AS-08 (top-3 hit rate overall and by fluency). Day 3 AS-05, AS-06 (calibration, recall on 4 intents). Day 4 AS-02 (timing). Before Stage 3: AS-03 (20 reference answers). Now: AS-04 mix comparison.
- Found in dev data: must_not_auto_respond = true for exactly four intents, 87 of 87 (security_incident 26, compliance_request 26, feature_request 20, unclear_request 15). An intent rule catches all of them if the classifier never misses those four.
- data_residency is NOT must-not in the labels: only 8 of 29 are labelled escalate. FR-12 escalates all 29 (Daniel). That is stricter than the labels and costs about 4 pts of FCR on dev. Keep it, but state the cost in the evaluation report.
- Billing disputes are not labelled at all. FR-12's dispute rule has no ground truth. Needs hand-built test tickets.
- The other 102 escalate-labelled tickets sit in routine intents. Only the threshold catches them, and route labels are noisy there.
- NFR-09 corrected: was "100% of must-escalate escalated", which was untestable given route-label noise. Now: zero auto-answers on must_not_auto_respond, and overall escalation not below 37.8%.

## 10. Success measures (2.9): numbers behind the targets
- FCR is two measures. Today's 42–43.8% counts tier-one human resolution. Replay can only measure automated resolution. Live FCR 60% (sentence test) = automated plus tier one helped by drafts. Replay target is automated resolution 50% or more.
- Automated ceiling with FR-12 rules: dev 290 of 500 = 58.0% (311 auto_respond minus 21 data_residency). Validation 45 of 80 = 56.2%.
- Escalation below 42% in replay means something auto-answered past the ceiling. Investigate before celebrating.
- Validation segment ceilings differ widely: enterprise 75.0% (n=8), business 70.0%, standard 42.9%. Non-fluent 36.8% (n=19) vs fluent 62.3%. Raw automated rates by segment will show large "gaps" the system did not cause. NFR-06 and the fairness row now use rate among auto-eligible tickets.
- Stage 1 sentence test (1.10) still matches: FCR 60% is live, 3 months. If the evaluation report quotes only replay figures, say so in the same sentence.
- CSAT proxy rubric is step 5.18. The PRD row is labelled PROXY. Don't call it CSAT anywhere in the report.

## 11. Bridge save issue (18 Nov)
- Two saves at ~18:29 landed with the previous version's content (assumptions and NFR-09 fix missing, this note missing section 9). Redone from fresh file paths and re-checked on the device after saving.

## 12. Open questions (2.10): what the build relies on
- 17 questions, OQ-01 to OQ-17. Each has a default the PRD relies on if nobody replies.
- Build-blocking, resolve by 19 Nov: OQ-01 gate file, OQ-02 validation reuse, OQ-05 external provider and region, OQ-06 billing-dispute rule.
- Pack questions (OQ-01 to OQ-04) are owned by the course assessor. Add the assessor's name if known.
- Stage 4 sprint plan: treat each default as the working decision. Stage 5 revision log: record which questions got answers and what changed.
- OQ-06 default keyword list (refund, dispute, chargeback, credit, overcharged) needs hand-built test tickets. No label exists.

## 13. Architecture (2.11): build notes and repo mismatches
- Only one model-provider call per ticket (Generate). Classify, Retrieve, Route and Validate are local. Leaves one spare call under NFR-07 for a restatement step if AS-08 fails.
- Classifier: MiniLM embeddings + logistic regression, calibrated on a dev hold-out split by text. Needs a saved model file or a deterministic train-on-start step for the clean-checkout run (A1). Decide in Stage 4.
- Chunking: one passage per article section. Articles are 138-214 words, ~9 sections each, about 260 passages. Passage id = doc_id + section.
- Retrieval query = ticket text + predicted intent description. Cheap help for non-fluent wording. Measure on build day 2.
- Repo mismatches to fix (not PRD content):
  - .env.example MODEL_NAME = meta-llama/llama-3.1-8b-instruct has no ':free' suffix. On OpenRouter that may be a paid model. NFR-07 says $0. Check before the first full run.
  - test.py calls nvidia/nemotron-3.5-lightning:free. Different model from .env.example. Pick one; record it in the README and the decision log (model.name).
  - .env.example CONFIDENCE_THRESHOLD=0.80 is the Brief's illustrative value. Replace with the measured threshold and note the date.
  - README says data/ holds "small samples only". It holds the full pack datasets. Align with OQ-04.
  - docs/architecture.md is a placeholder. Copy Section 10 summary and Figure 2 there so the repo explains itself.
- Failure settings to implement and test: 10 s timeout, 2 retries with jitter, 60 s max wait on 429, circuit breaker after 5 consecutive failures, probe every 60 s, one JSON repair retry, fallback file if the log write fails.
- Kill switch: env/config flag read per ticket, not at start-up, so it works mid-run.

## 14. Weak evidence to watch in revision
- FR-02, FR-25, FR-26 cite S5 data rows for unattended-run needs. The real source is the Build Spec. Fine for traceability, but say so if challenged.
- FR-17 rests on one S5 row. Governance R-03 is the stronger source; add it in Stage 5 when the risk register gains R-03.
- FR-32 has no discovery row. Stated openly in the PRD as a delivery requirement.
