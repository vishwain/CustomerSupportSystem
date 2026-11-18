# Decision Log Design (Checklist 1.16)

Decided in Stage 1, before the PRD. Feeds PRD requirements (auditability NFR, FR for logging) and acceptance criterion A8.
Checked against: Governance Framework section 1 (minimum record, coverage check), Brief section 7 (decision logging: complete coverage), Setup Guide section 5 (SQLite table).

## 1. What counts as a decision
One row per automated decision, per ticket. Five stages, plus one terminal row.

| Stage | Decision | Reason it needs a row |
|---|---|---|
| classification | intent and urgency, with confidence | Everything downstream depends on it (S3 steps 1–2) |
| retrieval | which passages, with scores, or none | Findability is the core problem (S2 answerable rows) |
| routing | auto-respond, draft for review, or escalate | Marcus must explain why (S1 Marcus row) |
| generation | reply or escalation package produced | Prompt and model version decide behaviour |
| validation | guardrails pass or block | A7. Zero private data is a hard condition |
| final | the single action taken on the ticket | The coverage count is made on these rows |

## 2. Fields
Governance minimum is the base. "Added" marks my additions, each tied to a Stage 1 finding.

| Field | Source | Notes |
|---|---|---|
| decision_id | Governance | Unique per row |
| timestamp | Governance | UTC |
| ticket_id | Governance | Key. Never customer_id or customer_name (S5 private data) |
| stage | Governance | Values above, plus `final` |
| input_summary | Governance | See open point 1. Never customer_name, customer_id |
| model.name, model.version | Governance | Setup Guide table omits these |
| prediction.value, prediction.confidence | Governance | Confidence is needed for the calibration check (Brief: within 5 pts) |
| alternatives[] | Governance | Runner-up classes with confidence. Setup Guide table omits this |
| sources_used[] | Governance | doc_id, passage id, score |
| threshold_applied | Governance | Setup Guide calls it `threshold` |
| action_taken | Governance | auto_respond, escalate, block |
| reason | Governance | Human-readable. One sentence |
| guardrail_results | Governance | Each guardrail separately: pii, grounding, instruction_integrity, must_not_claim, tone |
| prompt_version | Governance | PR-xx vX.Y from the Stage 3 library |
| requirement_ids[] | Governance | FR ids from the PRD. Placeholder until Stage 2 |
| run_id | Added | Separates dev, validation and hidden runs (S5 data sources) |
| rule_fired | Added | Hard rule (security, data residency, compliance, billing dispute) vs threshold. A5 needs the same input to give the same routing |
| doc_review_age | Added | `last_reviewed_days_ago` of each cited doc. Risk 4 (stale docs). Currently 0 for all 29 |
| escalation_package | Added | What was passed to tier two, and what the system was unsure of (S3 step 8, Daniel) |
| ~~segment (tier, fluency, channel, region)~~ | Removed 18 Nov | Not logged. The evaluation layer joins segments from the input file by ticket_id (PRD FR-03, NFR-06). |
| error, degraded_mode | Added | Provider timeout, no retrieval hit, malformed input. A11 |
| latency_ms, tokens_in, tokens_out | Added | Cost per ticket and latency (S1 'cost per ticket' row) |

Never logged: customer_name, customer_id, labels.*, history.*. Labels and history are joined from the ticket file by ticket_id at evaluation time only.

## 3. Coverage condition
Brief: complete coverage. Governance: logged decisions must reconcile exactly with tickets processed.

Invariants, each checked by a script in `evaluation/`:
1. Exactly one `final` row per ticket processed. count(final) = tickets processed.
2. Every ticket has a classification row and a routing row, unless an error row explains why not.
3. No null in a required field. `reason` is never empty.
4. Failure paths log too. Provider down, no retrieval hit, malformed input, rate limit (A11). Action is escalate, reason names the cause.
5. Write the log row before the action is taken. If the write fails, do not send. Escalate and raise an alert. This is fail-closed.
6. The hidden-set run uses the same log, with its own run_id (A9, A10).

A8 check: open the log, count `final` rows against tickets processed. They must match.

## 4. Gaps in the reference material
- Setup Guide table has 13 columns. It lacks input_summary, model, alternatives. Governance minimum has them. Use the Governance list.
- Setup Guide table has no run_id, rule_fired, error. Add them.
- Setup Guide vector-store code reads `doc["id"]`. The real field in `documentation.json` is `doc_id`. As written it raises a KeyError.

## 5. Open points for the PRD
1. **input_summary.** Store a 200-character excerpt that has passed the private-data scan, plus a hash of the full text? Or only the hash and rely on the ticket file? Recommend excerpt plus hash. **Decided 18 Nov: excerpt plus SHA-256 (PRD 10.5).**
2. **Retention.** **Decided 18 Nov: 12 months in live use; capstone keeps one SQLite file per run until submission (PRD 10.5).**
3. **requirement_ids.** Resolved: FR ids exist (mapping in PRD_Requirements_Notes §6).
4. **Storage.** SQLite at `storage/decisions.db` (Setup Guide). `storage/` is gitignored, so the log itself is never committed. **Decided 18 Nov: commit a 20-row log extract and the reconcile counts per run under evaluation/results/ (PRD 10.5).**

## 6. PRD hooks
- NFR-05 Auditability: every ticket has one `final` row and the stage rows above. Verified by the reconcile script.
- FR (Must): the system shall write the decision record before acting. Fail closed on write error.
- FR (Must): the system shall log failure paths, with the cause as reason.
- Success measures: calibration, fairness and cost are all computed from this log plus the ticket file. No second data source.
