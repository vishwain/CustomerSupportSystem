# PRD v2.0 change list (5.20), for the revision log (5.21 to 5.24)

PRD: Workbooks/Stage_2_PRD_Template.docx, v2.0, 20 Nov 2026. v1.0 text: Workbooks/archive/Stage_2_PRD_v1.0.docx (v1.0 as approved on 18 Nov, with the two 20 Nov protocol notes removed) and git history.
Each changed cell in the PRD ends with a 'Changed in v2.0' or 'Added in v2.0' line naming its trigger. v1 text below is the full v1 cell text (requirement | acceptance).

Totals: 13 requirements changed, 2 added, 0 removed; 3 success measures redefined; 8 assumption status lines; 4 protocol facts; document control.

## Requirements and measures changed

### FR-02 (4 Functional requirements)

- **v1:** The system shall not stop on bad input. Missing subject: empty string. Missing channel: ‘unknown’. Missing ticket_id: row position (ROW-0007). Processing continues for all three.
Non-ASCII text kept (Unicode NFC). Control characters removed from the cleaned text. Cleaned text over 4,000 characters truncated, flag truncated = true.
Empty or whitespace-only body, or a record that cannot be parsed: escalate with error = malformed_input. | Fixtures in tests/: empty body, whitespace body, no subject, accented and non-Latin text, control characters, 10,000-character body, invalid JSON record.
Empty body, whitespace body and invalid record each end escalated with error = malformed_input.
No subject, accented text and long body proceed normally. The long one has truncated = true.
The run moves on in every case.
- **v2:** The system shall not stop on bad input. Missing subject: empty string. Missing channel: ‘unknown’. Missing ticket_id: row position (ROW-0007). Processing continues for all three. / Non-ASCII text kept (Unicode NFC). Control characters removed. Cleaned text over 4,000 characters truncated, flag truncated = true. / A file that is not valid UTF-8 is read with undecodable bytes replaced and flagged; UTF-16 with a byte-order mark is read as is. A body more than 30% undecodable escalates with error = malformed_input. / Empty or whitespace-only body, or a record that cannot be parsed: escalate with error = malformed_input.
- **Trigger:** 5.11 failure drill: a Windows-1252 export stopped the whole run.

### FR-08 (4 Functional requirements)

- **v1:** The system shall search only passages built from documentation.json (29 articles, one passage per section) and return up to 5 passages ranked by score, each with doc_id, passage id (doc_id#section) and score. | Every returned passage id resolves to text in documentation.json.
No ticket or reference answer is in the index.
Retrieval hit rate = share of answerable tickets with an expected_doc_id among the articles of the top 3 passages. Reported every run.
- **v2:** The system shall search only passages built from documentation.json: 800-character chunks with 120 overlap and the article title prefixed (59 passages, id doc_id#cNN, section kept as metadata), and return up to 5 passages ranked by score, each with doc_id, passage id and score. / For Generate, the other chunks of the top two articles are added as context (whole-article view); routing counts only the passages that passed the cutoff.
- **Trigger:** 5.2 chunking test: 800/120 + title hit@3 94.7% vs per-section 92.7% on 300 dev train tickets (docs/retrieval_experiment.md); 5.8 review: answers missed steps split across sections.

### FR-09 (4 Functional requirements)

- **v1:** The system shall drop passages scoring below a relevance cutoff, and return none if none pass.
Cutoff set on the dev hold-out (NFR-03 split): the highest value that keeps the top-3 hit rate on answerable tickets at 85% or more (AS-01). Stored in config with the date set. | Cutoff value, rule and hold-out hit rate are recorded.
Share of answerable_from_docs = false hold-out tickets returning zero passages is reported.
A feature-request test ticket returns zero passages.
- **v2:** The system shall drop passages scoring below a relevance cutoff, and return none if none pass. / Query: for a ticket without a subject (every chat ticket), the predicted intent’s description followed by the ticket text; otherwise the ticket text (PRD 10.3 design, as built in v2). / Cutoff set on the dev hold-out for that query: the highest value that keeps the top-3 hit rate on answerable tickets at 85% or more (AS-01). Now 0.51. Stored in config with the date and rule. | Cutoff value, query mode, rule and hold-out hit rate recorded (docs/query_experiment.md). / Hit rate reported with and without a subject, and the share of unanswerable tickets returning zero passages. / A feature-request test ticket returns zero passages.
- **Trigger:** Gate run: chat (no subject) hit@3 46% vs 95% with a subject; the intent-expanded query in the v1 design had not been built. Query experiment: hold-out 87.7% vs 86.0%; validation 88.7% vs 83.0%, chat 92.3% vs 46.2%.

### FR-11 (4 Functional requirements)

- **v1:** The system shall answer automatically only when all three hold: no FR-12 rule fired; intent confidence at or above the threshold; at least one passage passed the cutoff (FR-09). Otherwise it escalates.
Threshold set on the dev hold-out: the lowest value where 90% or more of automatic answers have expected_route = auto_respond, with zero on must_not_auto_respond tickets (NFR-09).
Same ticket, same config and model files: same decision. | Each validation ticket run twice gets the same route.
Recorded: threshold value, rule, and on the hold-out the automatic rate, precision and unsafe count at the value and at ±0.05.
Every route reason names the gate that decided it.
- **v2:** The system shall answer automatically only when all hold: no FR-12 rule fired; intent confidence at or above the threshold; at least one passage passed the cutoff (FR-09); the answer passed Validate (FR-22, FR-23). Otherwise it escalates; below the threshold it drafts for an agent. / Threshold set from the calibration study on 500 out-of-fold dev tickets (temperature T = 0.462): 0.95, above the one band that misses calibration. / Same ticket, same config and model files: same decision. | Hard gates: zero must_not_auto_respond tickets answered automatically; every automatic answer passes Validate. / Correctness: hallucination and citation accuracy from the NFR-08 review; must_not_claim hits. / Agreement with expected_route reported, not a gate (it follows past handling, AS-07). / Each validation ticket run twice gets the same route (gate re-run: 0 differences).
- **Trigger:** Route study: best precision against expected_route 72.4% at any threshold with intent 100% correct; all 94 dev escalate labels have history.escalated = true (AS-07). The v1 90% target was unreachable.

### FR-12 (4 Functional requirements)

- **v1:** The system shall escalate, before any threshold, when:
the predicted intent is security_incident, compliance_request, data_residency, feature_request or unclear_request;
the intent is billing_query or quota_or_overage and the text matches the dispute list (refund, dispute, chargeback, credit, overcharg*, reimburse; OQ-06);
the text matches the instruction-integrity list (FR-17); or the kill switch is on (FR-31). | Zero must_not_auto_respond = true tickets answered automatically, on the dev hold-out and validation.
Every data_residency ticket escalated.
Six hand-built dispute tickets all escalate.
Each such escalation logs rule_fired.
- **v2:** The system shall escalate, before any threshold, when: / the kill switch is on (FR-31) or the text matches the instruction-integrity list (FR-17); / the text says an earlier support contact told or promised something (prior_contact_claim); / the predicted intent is security_incident, compliance_request, data_residency, feature_request or unclear_request; / the text matches the dispute list (refund, dispute, chargeback, credit, overcharge, reimburse, waive, write-off, compensation, money back, goodwill), whatever the intent; / the text names a security, legal or residency matter (risk_terms), whatever the intent; / the must-escalate classes together hold 0.01 or more of the calibrated probability (floor from data). / Added in v2, not yet built: a credential exposed in a public place (pushed to a public repo, posted, shared) escalates as a security matter. | Zero must_not_auto_respond tickets answered automatically on the dev hold-out and validation (met: 0). / Every data_residency ticket escalated. Engineered dispute, prior-contact and disguised risky tickets all escalate (15 of 15, docs/must_escalate_check.py). / Each such escalation logs rule_fired.
- **Trigger:** 5.9 engineered tickets (waiver, earlier agent's promise answered automatically); 5.10 review (dispute or leaked secret inside another intent passed every rule; 0.15 floor untested); 5.18 review: VAL-0039, a key pushed to a public repo, was answered automatically (flagged by both assessors).

### FR-13 (4 Functional requirements)

- **v1:** The system shall write every escalation to escalation_queue.csv in the run output folder and to the decision log, with: ticket_id, summary, restatement (FR-07), intent and confidence, alternatives, urgency, passages (ids and titles, or ‘none found’), reason, unsure_about, draft (FR-14, or empty).
With no model call, summary is the template ‘<intent> (<confidence>), <urgency> urgency, <channel>: <subject>’ and unsure_about is the route reason. With a model call, both come from the model JSON; summary 60 words or fewer.
Upstream fallbacks write ‘unknown’ or ‘none found’. No field is missing. | Every escalation row has every field, none null.
Template summary matches the pattern when no model call was made.
Model summaries are 60 words or fewer.
- **v2:** The system shall write every escalation to escalation_queue.csv and the decision log with: ticket_id, summary, restatement, intent and confidence, alternatives, urgency, passages (ids and titles, or ‘none found’), reason, unsure_about, draft (or empty). / With no model call: summary is the template ‘<intent> (<confidence>), <urgency> urgency, <channel>: <subject>’, the restatement adds the first sentence of the body with private data removed, and unsure_about is the route reason. With a model call, both come from the model JSON; summary 60 words or fewer. / When an earlier rule escalates and retrieval also found nothing, the reason says so.
- **Trigger:** 5.10: a ticket with no subject reached the agent as ‘(no subject)’; 5.11 drill: the no-docs reason was hidden by an earlier rule.

### FR-18 (4 Functional requirements)

- **v1:** The system shall start every automatic reply with the fixed automated label from config/messages.json, and end it with ‘Sources:’ listing title and doc_id of each cited article.
If deferred: customers cannot tell an automated reply or check it. | Every automatic reply starts with the label text exactly and lists at least one cited title and doc_id.
- **v2:** The system shall start every automatic reply with the fixed automated label from config/messages.json, and end it with ‘Sources:’ listing title and doc_id of each cited article. / Added in v2, not yet built: the holding message for a high-urgency escalation (outage, security incident) states when the customer will hear back. / If deferred: customers cannot tell an automated reply or check it.
- **Trigger:** 5.18 review: all eight urgent escalations scored 3 of 5 for completeness; the holding message gives no timeframe or first step.

### FR-22 (4 Functional requirements)

- **v1:** The system shall check every generated text before release, automatic replies and agent drafts:
1. Private data: email, phone, IP address, URL, card-like and key-like strings, CUST- ids, and the ticket’s own customer_name and customer_id.
2. Every cited passage id is in the retrieved set.
3. Grounding: each sentence’s highest similarity to its cited passages is at or above a floor, set as the 5th percentile of sentence-to-cited-article similarity in the 200 reference answers.
Any failure: block and escalate. Never redact and send. | A test ticket built to make the reply contain an email address or customer id is blocked and escalated (A7).
Fixture replies with an uncited sentence, and with a passage id not retrieved, are blocked.
Guardrails run in every run. No flag disables them.
Each check’s result is logged per reply, pass or fail.
- **v2:** The system shall check every generated text before release, automatic replies and agent drafts: / 1. Private data: email, phone, IP address, URL, card-like and key-like strings, CUST- ids, and every customer name and id in the run. / 2. Every cited passage id is in the retrieved set. / 3. Grounding: each sentence’s highest similarity to its cited passages is at or above a floor, the 5th percentile of sentence-to-cited-article similarity in the 200 reference answers (0.21). No floor set: block (fail closed). / 4. Instruction integrity (delimiters, prompt text) and the confidence floor. / Any failure: block and escalate. Never redact and send. Model text written to the log is redacted first. / Known limit: grounding similarity does not detect a dropped qualifier or a changed condition. The NFR-08 review is the control for that. | A test ticket built to make the reply contain private data is blocked and escalated (A7; docs/guardrail_demo.py). / Fixture replies with an uncited sentence, and with a passage id not retrieved, are blocked. / Guardrails run in every run. No flag disables them. Each check’s result is logged per reply. / The false-block rate is reported from the NFR-08 review (validation run 11: 2 blocks, both judged false positives).
- **Trigger:** 5.14: a leaked name blocked by Validate was still stored in the generation log row. 5.18: all 4 hallucinating answers passed grounding (dropped qualifiers); both grounding blocks were good answers.

### FR-25 (4 Functional requirements)

- **v1:** The system shall keep running when the model provider times out (no response in 10 s), rate-limits (429) or is down (5 failures in a row), with the settings in 10.6, and escalate affected tickets with the cause logged. | With the provider disconnected, a full validation run completes.
With a mocked 429 on every request, the run completes. Waits stay at 60 s or less per ticket.
Every affected ticket ends escalated with the cause as its reason.
- **v2:** The system shall keep running when the model provider times out (no response in 10 s), rate-limits (429) or is down (5 failures in a row), with the settings in 10.6, and escalate affected tickets with the cause logged. / A bad key, missing access or wrong model id (401, 403, 404, 400) is not retried and opens the circuit at once. / Successful responses are cached by model and full prompt (prompt version, ticket text, passages), on by default, so a re-run spends no calls; corrupt cache entries are ignored.
- **Trigger:** 5.11 drill: a bad key was retried 3 times per ticket; the gate had to be re-runnable without spending calls.

### FR-27 (4 Functional requirements)

- **v1:** The system shall write <folder>/metrics_report.md and .json at the end of each run, from the decision log and the input file only:
Volume: processed, automatic, escalated, blocked by guardrail type.
Business: automated resolution (replay FCR, Section 8), mean and median time to final action, escalation rate.
Technical: intent precision and recall per class, urgency per level, retrieval hit rate, latency p50 and p95.
Governance: final records vs tickets, guardrail activations by type, private-data detections, unsafe automatic answers.
Segments: tier, fluency, channel, length (28 words or fewer vs longer), with n. Calibration: 5 bands (NFR-10).
Run facts: run_id, date, git commit, input file, number of runs on that file. Label-based figures show ‘n/a’ when the input has no labels. | After a run, both files exist with every group above.
The reconcile script recounts the figures from the log and they match.
- **v2:** The system shall write <folder>/metrics_report.md and .json at the end of each run, from the decision log and the input file only: / Volume: processed, automatic, escalated, by channel and outcome, escalation causes, blocks by guardrail. / Business: auto-resolution and escalation rates, replay FCR (Section 8), time to final action. / Technical: intent and urgency precision and recall, confusion matrices, retrieval hit rate (also with and without a subject), latency p50 and p95 with and without provider waits, stage latency, citation validity. / Governance: final rows vs tickets, guardrail checks, private data in every outbound message, unsafe automatic answers, degraded-mode tickets. / Segments: tier, region, fluency, channel, length, with n. Calibration: 5 bands. All vs unseen text (FR-28). / A consistency section recounts the main figures from results.jsonl and shows they match the log. A run with --limit is reported against the tickets it processed.
- **Trigger:** 5.13 and 5.17 requirements (confusion matrix, every outbound message checked); 5.16 clean-clone check (--limit run reported against all 80).

### NFR-01 (5 Non-functional requirements)

- **v1:** p95 time from ingest to final action under 3 s, over all tickets in a run, excluding provider rate-limit waits (Brief §7).
Reported beside it: p95 including waits, and p95 for tickets with a model request. | Evaluation harness. latency_ms per ticket from the decision log. p50 and p95 in the metrics report.
- **v2:** p95 time from ingest to final action under 3 s, over all tickets in a run, excluding provider rate-limit and pacing waits (Brief §7). Provider-dependent: reported every run, met on some runs, not guaranteed. / And, verifiable for this system: p95 of the system’s own stages (everything except the provider call) under 500 ms (FR-36). Provider generation p95 reported beside it. | Metrics report: processing p95, stage latency p95, provider generation p95. / Validation run 11: 3,078 ms (not met); own stages under 20 ms (met); generation 4,016 ms. Gate v2: 2.7 s.
- **Trigger:** 5.12 gate 4.9 s, gate v2 2.7 s, validation run 11 3.08 s with the same code: the free provider decides the result.

### NFR-06 (5 Non-functional requirements)

- **v1:** Under 5 pts between the highest and lowest group within each dimension (Governance condition): tier (3 groups), fluency (2), channel (4), length (28 words or fewer vs longer, the dev median).
Measures: automatic resolution among auto-eligible tickets; top-3 hit rate among answerable tickets; guardrail block rate among generated replies. Segment ceilings differ, so raw rates would show gaps the system did not cause.
Groups under 20 tickets reported, not judged.
Today’s 11-pt tier gap (enterprise 37.3% vs business 48.2%) is live FCR. After launch it must not widen. | Fairness table in the metrics report. Segments joined from the input file by ticket_id, never read by the pipeline.
Pooled dev hold-out plus validation, because validation alone has 8 enterprise and 19 non-fluent tickets. n per group stated.
- **v2:** Under 5 pts between the highest and lowest group within each dimension: tier (3), region (4), fluency (2), channel (4), length (28 words or fewer vs longer). / Measures: automatic resolution among auto-eligible tickets; top-3 hit rate among answerable tickets; guardrail block rate among generated replies. / Judged only for groups of 20 or more eligible tickets, with a 95% interval on each gap; a gap whose interval includes 5 pts is reported as not established, not as a pass or a fail. / Today’s 11-pt tier gap is live FCR. After launch it must not widen. | Fairness table (FR-27) with n and intervals. Segments joined from the input file, never read by the pipeline. / Pooled dev hold-out plus validation (5b.3).
- **Trigger:** 5.17: every dimension's gap over 5 pts, but groups of 6 to 22 eligible tickets, where one ticket moves a group 5 to 17 pts. The v1 test could not distinguish a real gap from noise. Region added (5b.3).

### NFR-08 (5 Non-functional requirements)

- **v1:** Hallucination rate 5% or lower. Citation accuracy 95% or better (Brief §7).
Sample: at least 50 automatic replies from the validation run, topped up from the dev hold-out if fewer. | Two assessors independently (OQ-18). Agreement and Cohen’s kappa reported. Disagreements settled by discussion before the rate is computed.
Each citation checked against its sentence.
must_mention coverage (case-insensitive match) and must_not_claim hits on dev hold-out reference tickets, few-shot tickets excluded.
- **v2:** Hallucination rate 5% or lower. Citation accuracy 95% or better (Brief §7). / Sample: at least 50 responses from the validation run: every escalation and guardrail block, and a seeded random sample of the automatic answers (5.18: 59 items, 30 answers, seed 42). | Two assessors score independently against a written rubric (evaluation/results/human_review/RUBRIC.md). Agreement and kappa reported. Disagreements settled against the rubric, each recorded with its reason. / 5.18: both assessors were LLMs (Claude Sonnet 5.5 and Claude Opus 5.5), no human available (OQ-18); stated as a limitation. Result: hallucination 13.3% (not met), citation accuracy 95.7% (met). / must_mention coverage reported only (AS-03); must_not_claim hits on dev hold-out reference tickets.
- **Trigger:** OQ-18 had no human second assessor; 5.18 review method and result. AS-03: references are per intent.

### SM: Automated resolution (8 Success measures)

- **v1:** 50% or more.
Brief’s 60% not committed for automation alone: the 58% ceiling would need ~97% of eligible tickets right.
- **v2:** v2: replay FCR is a floor, because expected_route follows past handling (AS-07). Reported beside it: review-based estimate = auto-resolution rate × share of reviewed sent answers with no unsupported sentence. / Validation run 11: replay 47.5% (target 50%, not met); review-based estimate 63.8% × 86.7% = 55.3%.
- **Trigger:** 5.17 replay FCR 47.5%; AS-07 label finding; 5.18 review.

### SM: Latency, p95 (8 Success measures)

- **v1:** Under 3 s (NFR-01).
- **v2:** v2: own stages and provider reported apart (NFR-01, FR-36). Run 11: 3,078 ms (not met); own stages under 20 ms.
- **Trigger:** 5.17

### SM: Variation between groups (8 Success measures)

- **v1:** Under 5 pts between groups (NFR-06).
Live: no tier below today. Enterprise FCR 37.3% or more (sentence test).
- **v2:** v2: judged with intervals on groups of 20+ eligible tickets (NFR-06). Run 11: every gap over 5 pts on groups of 6 to 22; not established either way.
- **Trigger:** 5.17

## Requirements added

### FR-35 (4 Functional requirements)

- **v1:** (none)
- **v2:** The system shall keep the conditions and qualifiers its cited passage puts on a step (for example ‘a reasonable starting point for services that load models’, ‘for anything that may change while you iterate’). An answer sentence that drops or changes one is unsupported. | NFR-08 review: hallucination rate 5% or less. / Generate prompt and Validate updated, then measured on a new validation run logged as such.
- **Trigger:** 5.18 review findings 1 and 3 (NFR-08 failed at 13.3%).

### FR-36 (4 Functional requirements)

- **v1:** (none)
- **v2:** The system shall report the provider’s share of latency apart from its own: p95 of the system’s own stages (everything except the provider call) and p95 of provider generation, per run. | Both figures in the metrics report (FR-27 stage latency).
- **Trigger:** NFR-01 could not be verified as written: the free provider sets most of the time.

## Success measures: results added (no definition change)

### SM: Customer satisfaction (8 Success measures)

- **v1:** Proxy: mean 4.0 or more out of 5.
Live CSAT: 3.5 within 3 months, 4.0 as end goal (Brief §7). 4.2 (Brief §1) not committed.
- **v2:** Validation run 11, 5.18 review (59 items, two LLM assessors): CSAT proxy 4.02 (target 4.0, met by a small margin).
- **Trigger:** 5.18 review

### SM: Escalation rate (8 Success measures)

- **v1:** Replay: 50% or less routed to people. Below 42% means unsafe auto-answers (FR-12 ceiling). Never below 37.8% (NFR-09).
Live: 40% or less to tier two.
Brief’s 30% not committed: below the 37.8% labels require.
- **v2:** Validation run 11: 36.2% (target 50% or less, met); review: 3 of 27 escalations unnecessary (retrieval cutoff misses).
- **Trigger:** 5.17, 5.18

### SM: Hallucination rate (8 Success measures)

- **v1:** 5% or less (NFR-08).
- **v2:** Validation run 11, 5.18 review: 13.3% of sent answers (4 of 30), 4.4% of sentences. Not met; all four drop a qualifier (FR-35).
- **Trigger:** 5.18 review

### SM: Citation accuracy (8 Success measures)

- **v1:** 95% or more (NFR-08).
- **v2:** Validation run 11: 100% of cited passages in the retrieved set; review 95.7% supporting (88 of 92). Met by one link.
- **Trigger:** 5.17, 5.18

## Assumptions: status after build and validation

### AS-01 (7 Assumptions)

- **v1:** AS-01  The 29 articles hold the answer for the 357 tickets labelled answerable (71.4%), and retrieval finds the right ar
- **v2:** v2 status: held. Hold-out 87.7% at cutoff 0.51 (after FR-09); validation 88.7%.
- **Trigger:** 5.17 / 5.18 results

### AS-02 (7 Assumptions)

- **v1:** AS-02  Free-tier model limits and latency allow p95 under 3 s and a full 80-ticket run inside one day’s quota, unattende
- **v2:** v2 status: partly. Runs complete unattended inside the quota, but p95 is provider-dependent: 4.9 s, 2.7 s and 3.08 s on three full runs (NFR-01 restated).
- **Trigger:** 5.17 / 5.18 results

### AS-03 (7 Assumptions)

- **v1:** AS-03  The 200 ground-truth responses are a fair quality standard for answers.
- **v2:** v2 status: false. 13 distinct reference texts for 200 tickets (one per intent); must_mention is per intent. Used for must_not_claim and style only.
- **Trigger:** 5.17 / 5.18 results

### AS-04 (7 Assumptions)

- **v1:** AS-04  Validation and hidden tickets come from the same population as dev: same intent, channel, tier and fluency mix.
- **v2:** v2 status: partly. Validation unseen vs repeats: hit@3 85.0% vs 90.9% (within 10 pts), auto rate 57.1% vs 68.9% (11.8 pts, outside). Hidden set not provided.
- **Trigger:** 5.17 / 5.18 results

### AS-05 (7 Assumptions)

- **v1:** AS-05  Classifier confidence can be calibrated to within 5 pts of observed accuracy, so a routing threshold means someth
- **v2:** v2 status: held after a fix. Temperature T = 0.462; one band (0.50 to 0.95, n = 22) 5.3 pts over, below the 0.95 threshold.
- **Trigger:** 5.17 / 5.18 results

### AS-06 (7 Assumptions)

- **v1:** AS-06  The four must-not-automate intents (security_incident, compliance_request, feature_request, unclear_request) can 
- **v2:** v2 status: held. Intent 100% on hold-out and validation; 0 must_not tickets answered. A keyword backstop (risk_terms) was added anyway (FR-12).
- **Trigger:** 5.17 / 5.18 results

### AS-07 (7 Assumptions)

- **v1:** AS-07  Enough tickets can be answered safely to reach 60% FCR without any must-not-automate ticket answered automaticall
- **v2:** v2 status: partly. 63.8% answered automatically on validation, but replay FCR 47.5% because expected_route follows past handling; review-based estimate 55.3% (Section 8).
- **Trigger:** 5.17 / 5.18 results

### AS-08 (7 Assumptions)

- **v1:** AS-08  A general English embedding model retrieves as well for non-fluent wording as for fluent.
- **v2:** v2 status: held. Hit@3 fluent 84.4% vs non-fluent 84.9% (hold-out + validation).
- **Trigger:** 5.17 / 5.18 results

## Protocol facts (open questions closed)

### OQ-02 (9 Open questions)

- **v1:** OQ-02  May the validation set be run many times, or once only? (I2)
- **v2:** v2: closed. No answer received; the protocol above was followed and is the record.
- **Trigger:** 5.17, 5.19

### OQ-03 (9 Open questions)

- **v1:** OQ-03  Is the hidden set 100 or 120 tickets? (I1)
- **v2:** v2: the pack disagrees: 120 tickets in the Dataset Guide and README, 100 in the Evaluation Framework and Build Specification. No hidden file is in the pack; it was not run. The harness takes any input path and size. / Could run: every harness run and experiment on dev and validation. Could not run: the hidden set (not provided), a human review (no human assessor, OQ-18), live FCR, CSAT and first-reply time (no live traffic).
- **Trigger:** 5.19

### OQ-04 (9 Open questions)

- **v1:** OQ-04  May validation tickets and reference answers sit in a public repo?
- **v2:** v2 decision: the full pack dataset JSONs (development, validation, ground truth, documentation) are committed in data/: synthetic pack data, no real customers. .gitattributes keeps their bytes identical on every clone. The hidden set was never received, so it was never committed.
- **Trigger:** 5.16 clean-clone check (line endings changed the data hashes); 5.19

### OQ-18 (9 Open questions)

- **v1:** OQ-18  Who is the second assessor for hallucination and citation review? (NFR-08)
- **v2:** v2: no human peer was available. Both assessors were LLMs run as separate agents: Claude Sonnet 5.5 (A) and Claude Opus 5.5 (B); disagreements settled against the rubric by the build assistant. Stated as a limitation (NFR-08).
- **Trigger:** 5.18

## Document control

- **v1:** Version 1.0, 18 November 2026, Approved by Vishwain Annadate.
- **v2:** Version 2.0, 20 November 2026, status 'Revised after build, validation run and review (v2.0)', change summary row added, v2.0 approval pending review.
