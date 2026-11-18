# PRD Engineer-Could-Build-It Review (Checklist 2.12)

Date: 18 Nov 2026. PRD v1.0, Stage_2_PRD_Template.docx. Fixes applied in the PRD itself.
Four questions per requirement: **U** unambiguous, **T** testable, **H** has a home (4a + 10), **C** consistent.
Figure 2 regenerated from `docs/architecture_flow.dot`.

---

## 1. Findings and fixes, FRs

| ID | Failed | Problem | Fix |
|---|---|---|---|
| FR-01 | U | "Accept tickets from email, chat…" reads as live connectors. Record fields not listed. | Pack JSON via harness file or API. Field list named. Live connectors out of scope (Section 6). |
| FR-02 | U, C | "Unusual characters" undefined. Acceptance escalated non-English characters: hurts non-fluent customers (FR-19) and contradicts 10.6 (replace, continue). | Rule per case: NFC kept, control chars stripped, 4,000-char truncation, only empty/unparseable escalates. 7 fixtures. |
| FR-03 | C | Validate blocks the ticket's own name and id (10.3), but FR-03 dropped them at ingest. Tier and region not listed, yet Section 6 cites FR-03 for tier. | Carve-out for Validate. Tier, region, fluency added. Evaluation layer reads them by ticket_id. |
| FR-04 | U | "22 intents", "runner-up alternatives": which list, how many. | labels.intent values; next two alternatives; `unknown` only via FR-05. |
| FR-05 | U | "Cannot classify" could mean low confidence. | Classifier error only. Low confidence stays with FR-11. Urgency `unknown`. |
| FR-06 | U | "Escalation queue export": no file, no tie-break. | `escalation_queue.csv`; high+unknown, medium, low; then oldest first. |
| FR-07 | U, H | "Plain sentence" untestable. No model call exists for rule escalations. | ≤25 words, same call as Generate; subject used when no call. |
| FR-08 | U | No result count. Hit rate per passage or per article unclear. | Up to 5 passages; hit = expected doc among articles of top 3. |
| FR-09 | T | Cutoff rule unstated. One feature-request ticket is a demo, not a test. | Highest cutoff keeping top-3 hit ≥85% on dev hold-out. Rates recorded. |
| FR-10 | U | Data has `last_reviewed_days_ago`, not a date. | Carry that value. |
| FR-11 | U, H | Retrieval-hit gate in 10.1 and diagram but not in the FR. "Set from data" had no rule. | Three gates stated. Threshold = lowest value with ≥90% automatic precision, 0 unsafe. **My pick of 90%: confirm.** |
| FR-12 | U | "Billing disputes" undefined. Injection and kill switch now Route rules too. | Intent list + dispute keyword list (OQ-06) + FR-17 list + FR-31. |
| FR-13 | U, H, C | "Summary" source unknown: rule escalations have no model call. "Send" with no ticketing integration (Section 6). | Template summary when no call. Written to queue file + log. Field list. |
| FR-14 | U, C | Diagram sent low-confidence tickets straight to escalate, so no draft could exist (contradicted 10.4). Security tickets would get drafts. | Draft only for below-threshold + passage. No draft for rule escalations. Draft goes through Validate. |
| FR-15 | U | "Fixed structure" undefined. "Each claim" unmeasurable. | Schema fields named; every answer sentence carries ≥1 passage id. |
| FR-16 | T, C | Acceptance "no false-labelled dev ticket auto-answered" is impossible: 47 of 143 sit on texts that also carry a true label. | Judged on consistent-label texts; conflicting ones reported apart. Holding message fixed in config. |
| FR-17 | U, T, H | Principle, not a build. Acceptance contradicted itself ("does not change behaviour" vs "blocked"). | Data block + input phrase rule in Route + output check in Validate. 6 fixtures. |
| FR-18 | U | Label text and source format open. | Fixed label from config; Sources line with title and doc_id. |
| FR-19 | C | Measure differed from NFR-06 (raw rate vs among eligible). | Aligned to NFR-06 measures and pooled set. |
| FR-20 | T | "Idioms", "product terms" no check. | Script on sentence length; reviewer marks idioms. |
| FR-22 | U | "Private data" and "claims not in passages" undefined. Drafts not covered. | Pattern list, citation-set check, grounding floor from reference answers. Drafts included. |
| FR-23 | U, C | "Timelines" would block grounded article text ("unlocks after thirty minutes"). must_not_claim exists only for 200 dev tickets. | Block commitments absent from cited passages. Phrase list seeded from the 3 must_not_claim items (identical across all 200). |
| FR-24 | U | Required fields pointed outside the PRD. | Listed in 10.5; input_summary decided (excerpt + hash). |
| FR-25 | T | Timeout value only in 10.6. | Values in the FR; 429 test added. |
| FR-26 | U | Command and output files open. | Exact command, `results.jsonl`. |
| FR-27 | U, C | "Every Build Spec figure group" not listed. Length segment missing (NFR-06 has it). Run date and run count required by Brief, missing. | Groups listed; length split at 28 words; run facts; `n/a` when no labels. |
| FR-28 | U | "Not seen" matching rule. | Lower-case, whitespace-collapsed text match. |
| FR-30 | H | No input path for agent actions exists anywhere in the design. | Optional agent-outcome file; difflib thresholds. |
| FR-31 | U, C, H | "One setting": an env var cannot change mid-run. Diagram skipped Classify, so the package (FR-13) would be empty. Should vs Governance "first finding". | File re-read per ticket; first Route rule. **Raised to Must.** |
| FR-32 | H | `storage/` is gitignored, so index and classifier must be rebuilt. CI in 4a but not the FR. | Rebuild by README commands; CI on push. |
| FR-33 | H (new) | Build Spec §06 posts tickets to a running system. No FR for the API. | Added, Must. |
| FR-34 | H (new) | Checklist 5b.8 Prometheus/Grafana had no FR. | Added, Should. |

## 2. Findings and fixes, NFRs

| ID | Failed | Problem | Fix |
|---|---|---|---|
| NFR-01 | U | Whether rate-limit waits count in the 3 s. | Excluded from the target; including-waits figure reported beside it. |
| NFR-02 | T, H | "Health checks" of what? Prometheus not in a clean checkout. | Tickets reaching a final action ≥99.5%; /health probe for the API. |
| NFR-03 | U, T | Hold-out size and split not fixed. No urgency measure, though FR-06 relies on it. | 20% of texts, stratified, seed 42. Urgency reported, no target (label noise). |
| NFR-04 | U | "Private data" undefined; drafts not covered. | FR-22 list; drafts included. |
| NFR-06 | U, C | "Variation" undefined. "Answer quality" undefined. 5-pt vs 11-pt baseline looked like a conflict. Segment source said decision log, but pipeline must not read tier. | Max-min within dimension; 3 automated measures; 11 pts = live FCR; segments joined by evaluation. |
| NFR-07 | T, C | "Fits one day's quota" has no number. Retries in 10.6 broke "≤2 calls". Model id without `:free` may be paid. | 1 request + ≤3 retries; ≤80% of cap; `:free` only; cap in README. |
| NFR-08 | U, H | Sample source open. Two assessors on an individual project. | Validation replies, top-up from hold-out; OQ-18 added. |
| NFR-09 | C | 37.8% is the dev floor only. | Per-set floor (validation 40.0%); dev 42% with data-residency rule. |
| NFR-10 | U | Band edges open. | 5 bands of 0.2. |
| NFR-11 | H (new) | Credential scan (Build Spec §06 step 11) had no requirement. | Added: gitleaks in CI, 0 findings. |

## 3. Architecture diagram and Section 10

- Kill switch moved from before Classify into Route (first rule). Package stays complete.
- Low confidence + passage now goes to Generate in draft mode, then Validate, then escalate with draft.
- Rule and no-passage escalations make no model call. Labelled on the arrow.
- Empty/unreadable ingest path shown.
- Validate covers drafts and schema / prompt leak.
- Source box shows the real inputs: harness file and API.
- 10.1 table, 10.2 kill-switch row, 10.3 Generate and Validate rows, 10.4 rows, 10.5 field list, 10.6 rate-limit pacing updated to match.
- Other sections touched for consistency: Section 3 vague success signals, 4a mapping, A2 row, Section 6 two rows, AS-02, Section 8 cost row, OQ-18.

## 4. Values I picked: confirm or change
- FR-11 automatic precision bar 90%.
- FR-02 truncation 4,000 characters. FR-07 25 words. FR-13 summary 60 words.
- FR-08 top 5 returned. FR-30 difflib 0.95 / 0.60. Section 6 drafts-as-is 70%.
- FR-22 grounding floor = 5th percentile on reference answers.
- NFR-03 hold-out 20%, seed 42. NFR-06 length split at 28 words (dev median).
- 10.5 input_summary = 200-char scanned excerpt + SHA-256 (DecisionLog_Design open point 1).

## 5. Biggest risk found
- OpenRouter without credits: 50 free requests a day, 20 a minute. One 80-ticket run needs about 50–60. NFR-07 now caps a run at 40.
- Decide before build day 4: Groq as primary, or response cache plus split runs. Record in AS-02 result.

## 6. Follow-ups outside the PRD
- DecisionLog_Design.md: "segment" field now joined at evaluation, not logged by the pipeline.
- PRD_Requirements_Notes.md §1: counts now 34 FRs, Must 22 (FR-31 raised, FR-33 added), Should 7, Could 4, Will not 1.
- `.env.example`: MODEL_NAME needs a `:free` id. `test.py` uses a different model.
- `docs/architecture.md`: copy Figure 2 and 10.1.
- Problem statement unchanged, so Stage 1 needs no sync.
