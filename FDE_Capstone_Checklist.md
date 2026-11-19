# FDE Capstone: Step-by-Step Checklist (CloudServe AI Support System)

Deadline: 21 November, 23:59. Individual project.
Rule: tick a box ONLY after you confirm the step is done. Do not skip ahead; each stage feeds the next.
Non-code files live in Drive FDECapstone. Reference/ is read-only. Fill workbooks in Workbooks/.

Legend: [ ] not done, [x] done (confirmed)

---

## Stage 0: Orientation and environment (Week 1, Day 1)
- [x] 0.1 Read 00_PROJECT_INSTRUCTIONS.docx fully
- [x] 0.2 Read 00_Start_Here.docx
- [x] 0.3 Read 01_Project_Brief.docx in full (incl. evaluation + governance sections)
- [x] 0.4 Read 02_Build_Specification.docx (12 acceptance criteria A1-A12, gate, daily checkpoints)
- [x] 0.5 Skim Submission_Guide.docx (video needs live demo; effort log needs entries throughout)
- [x] 0.6 Read Dataset_Guide.docx (schemas, how each set may be used)
- [x] 0.7 Confirm Python 3.10+, Git, editor, ~4 GB disk
- [x] 0.8 Create GitHub repo, set up .venv, add .gitignore (.env, storage/) BEFORE creating .env
- [x] 0.9 Copy requirements.txt + .env.example into repo; install dependencies
- [x] 0.10 Get free OpenRouter/Groq key, store in .env only; confirm a real model call returns text
- [x] 0.11 Create repo skeleton per Setup Guide section 8 (src/, prompts/, tests/, evaluation/, docs/, data/)
- [x] 0.12 Clone repo fresh and follow own README once (day-1 rehearsal)
- [x] 0.13 Start Effort Log (Workbooks/Effort_Log.docx): details section + first entries
- [x] 0.14 Note which stakeholder-interview/hidden-set details are unclear (see Open Clarifications at bottom)

## Stage 1: Discovery (Week 1, Days 1-3) -> Workbooks/Stage_1_Discovery_Workbook.docx
- [x] 1.1 Read all five interview transcripts (Stakeholder_Interviews.docx) before writing anything
- [x] 1.2 Section 1 table: per stakeholder (Marcus, Sofia, Daniel, Ines, Ravi): told you / do not know / verify in data
- [x] 1.3 Record at least 3 disagreements between accounts, and how the data settles each
- [x] 1.4 Record "what nobody said" (at least 3 items) and how to check
- [x] 1.5 Load development_tickets.json; fill Section 2 data table from counts (channel, intent, urgency, FCR, CSAT, top question, answerable-from-docs %, non-fluent segment, tier outcomes, repeat contacts)
- [x] 1.6 Note the surprises in the figures (answerable-from-docs % and non-fluent segment matter most)
- [x] 1.7 Section 3: volume vs effort by ticket category (7 rows) with evidence
- [x] 1.8 Section 3: reconstruct Sofia's agent steps, time per step, automatable or not
- [x] 1.9 Section 4: client success measures, who watches, current value, what success means
- [x] 1.10 Complete the three "sentence test" prompts using only recorded figures
- [x] 1.11 Section 5: data sources table (tickets, docs, past resolutions, customer records) + private data present
- [x] 1.12 Section 5: initial risk register (4 given rows + your own)
- [x] 1.13 Section 6: problem statement table, every clause cited to a workbook row
- [x] 1.14 Write the one-paragraph problem statement in non-technical language
- [x] 1.15 Test statement against each of the 5 transcripts (would each person recognise it?); fix framing if not
- [x] 1.16 Decide in week 1 what the decision log will record (governance by design)
- [x] 1.17 Update Effort Log

## Stage 2: Requirements, PRD v1.0 (Week 1, Days 4-5) -> Workbooks/Stage_2_PRD_Template.docx
- [x] 2.1 Document control (version 1.0, author, date, status)
- [x] 2.2 Copy problem paragraph from Stage 1 (keep in sync)
- [x] 2.3 Define user groups (customers, tier 1, tier 2, head of support, others) with need / today / success signal
- [x] 2.4 Write functional requirements FR-01...: ID, statement, MoSCoW priority, discovery evidence ref (section/row), acceptance criteria
- [x] 2.5 Map FRs to the six components (Ingest, Classify, Retrieve, Route, Generate, Validate) plus guardrails/logging/monitoring; ensure A1-A12 are covered
- [x] 2.6 Write NFR-01...: latency, availability, accuracy, privacy, auditability, fairness, cost, with verification method
- [x] 2.7 Out-of-scope table (what, why, what would reconsider it)
- [x] 2.8 Assumptions table (why believed, what if false, how found out); this feeds Stage 5
- [x] 2.9 Success measures table (baseline, target, how measured, reported by)
- [x] 2.10 Open questions with owner and resolve-by date
- [x] 2.11 Architecture design + justification (adapt Brief architecture where discovery warrants); initial risk assessment
- [x] 2.12 Engineer-could-build-it review of every requirement (20 min check)
- [x] 2.13 Week-1 milestone check: discovery + PRD v1 done; update Effort Log

## Stage 3: Prompt library and specifications (Week 2, Days 1-2) -> Workbooks/Stage_3_Prompt_Library.docx
- [x] 3.1 Section 1: specification for every FR (summary, inputs, outputs, acceptance criteria)
- [x] 3.2 Register prompts PR-01...: Specification / Build / Review / Evaluation categories
- [x] 3.3 For each prompt: purpose, serves requirement, version, model, inputs, output format, how you know it worked, weaknesses, change history, full text
- [x] 3.4 Build prompts: classification, answer drafting with citations, "I don't know" behaviour, structured parseable output
- [x] 3.5 Prompt-injection defence documented per build prompt (ticket text delimited from instructions)
- [x] 3.6 Run the Section 3 prompt-quality checklist on each build prompt
- [x] 3.7 Store prompts as versioned files in repo prompts/ plus prompts/README.md register
- [x] 3.8 Section 4 traceability table: FR -> spec -> prompts -> test case ID -> gaps
- [x] 3.9 Update Effort Log

## Stage 4: Sprint plan (Week 2, Day 1) -> Workbooks/Stage_4_Sprint_Plan.docx
(Do this alongside/just before Stage 3 spec work; it governs the build order.)
- [x] 4.1 Section 1: realistic capacity per week, other commitments, days off
- [x] 4.2 Section 2: backlog B-01...B-15 (+ your extras): hours, priority, dependencies, definition of done written BEFORE work starts
- [x] 4.3 Place retrieval layer and evaluation harness early; schedule the gate run (B-11) in week 2
- [x] 4.4 Section 3: week-2 day-by-day plan with hours and risks (align to Build Spec checkpoints)
- [x] 4.5 Section 4: week-3 day-by-day plan
- [x] 4.6 Section 5: cut-order list (what you drop first/second/third and what you will say in report)
- [x] 4.7 Start daily check-in record (finished / doing / blocked); keep updating each day
- [x] 4.8 Rule set: anything blocked more than 1 hour gets written down and escalated or worked around

## Stage 5: Build, evaluate, revise (Week 2 into Week 3)
Build checkpoints (Build Specification):
- [x] 5.1 Day 1: Ingest; one ticket per channel (email, chat, docs_comment, forum) printed normalised (A2)
- [x] 5.2 Day 2: Chunking (try at least 2 configs, measure, record why) + embeddings + Chroma + retrieval returns traceable passages; relevance threshold (return nothing if irrelevant) (A4)
- [x] 5.3 Decision log schema + SQLite store created early (A8)
- [x] 5.4 Evaluation harness skeleton: takes --input and --output path arguments, no hardcoded filenames (A9, A10)
- [x] 5.5 Day 3: Classifier (intent + urgency + confidence + alternatives + fallback) (A3)
- [x] 5.6 Day 3: Routing with data-derived threshold, deterministic, reason logged (A5); run 20 tickets and read the log
- [x] 5.7 Calibrate confidence (bins vs observed accuracy); choose threshold from data and record trade-off
- [x] 5.8 Day 4: Generation with citations that resolve to retrieved passages (A6)
- [x] 5.9 Day 4: Guardrails (private data, grounding, instruction integrity, tone/scope, confidence floor) that actually block (A7); test with engineered ticket
- [x] 5.10 must_not_auto_respond classes always escalate; escalations carry summary + sources
- [x] 5.11 Failure handling: no retrieval hit, provider timeout/outage, rate limit (backoff, cache), malformed input (A11)
- [x] 5.12 Day 5: THE GATE: full unattended run over the validation set, one command, no intervention, every ticket answered or escalated, decisions reconcile with tickets (A9)
- [x] 5.13 Metrics report auto-generated: volume, business, technical, governance figures (A10)
- [x] 5.14 Tests runnable with a single documented command and passing (A12)
- [x] 5.15 FastAPI interface (src/api.py) working
- [x] 5.16 README written and verified: fresh clone on another machine/dir follows steps to running (A1); .env.example complete
- [ ] 5.17 Validation-set evaluation (80 tickets); record business + technical results honestly
- [ ] 5.18 Human review sample: at least 50 responses, 2 assessors, for hallucination rate; CSAT proxy rubric; citation accuracy check
- [ ] 5.19 Hidden/final evaluation run: ONCE only; record date and number of runs (see clarifications)
- [ ] 5.20 Revise PRD to v2.0 (compulsory) -> Workbooks/Stage_5_PRD_Revision_Log.docx
- [ ] 5.21 Revision log Section 1: summary counts and reviewer
- [ ] 5.22 Section 2: each change: ID, v1 text, v2 text, specific trigger, agreed by
- [ ] 5.23 Section 3: each v1 assumption: held or not, what found, what changed
- [ ] 5.24 Section 4: things that looked wrong but left, why, cost, revisit date
- [ ] 5.25 Section 5: four reflection answers in full sentences (your own judgment, not AI-written)
- [ ] 5.26 Commit regularly throughout (history reviewed for steady work); no keys in code or history
- [ ] 5.27 Update Effort Log and daily check-ins

## Stage 5b: Governance, monitoring, CI (Week 3) (Governance_Framework.docx)
- [ ] 5b.1 Decision log verified: minimum record fields, coverage reconciles exactly
- [ ] 5b.2 Risk register complete (R-01...R-08 + own): likelihood, impact, real mitigation, named owner
- [ ] 5b.3 Fairness audit: segments (tier, region, fluency, ticket length) with sample sizes, resolution + quality + citation accuracy, honest findings
- [ ] 5b.4 Guardrail table documented and shown working
- [ ] 5b.5 Incident response procedure (detect, contain, assess, notify, remediate, review) usable at 2 a.m.
- [ ] 5b.6 Kill switch: mechanism, who, time to effect, in-flight tickets, how tested
- [ ] 5b.7 Declaration completed (must never / mechanism / likely harm / not deploy without)
- [ ] 5b.8 Prometheus metrics + Grafana dashboard (tickets by channel/outcome, auto vs escalated, p50/p95 latency, guardrail activations, confidence distribution)
- [ ] 5b.9 GitHub Actions CI running tests on push; no keys in workflow (use secrets or recorded responses)

## Stage 6: Report, video, packaging (Week 3)
Report (single PDF, 20-30 pages excl. appendices; FirstnameLastname_Capstone_Report.pdf)
- [ ] 6.1 Executive summary (1 page, incl. key caveat)
- [ ] 6.2 The problem
- [ ] 6.3 Discovery findings
- [ ] 6.4 Requirements (with IDs)
- [ ] 6.5 Architecture and design (alternatives and why)
- [ ] 6.6 Implementation
- [ ] 6.7 Evaluation (method, results, interpretation, "figures should be treated with caution because...", date and number of hidden-set runs)
- [ ] 6.8 Governance and risk
- [ ] 6.9 Requirements revision
- [ ] 6.10 Conclusions
- [ ] 6.11 Appendices (workbooks, prompt register, result tables, confusion matrix)
- [ ] 6.12 AI tool use declaration (about half a page)
- [ ] 6.13 All figures/tables numbered, captioned, referenced in text

Video (MP4 1080p, 20 min +/- 2, FirstnameLastname_Capstone_Video.mp4)
- [ ] 6.14 Script/outline following 0-2 problem, 2-5 discovery, 5-7 system, 7-14 demo, 14-17 numbers, 17-18 governance, 18-20 next
- [ ] 6.15 Test audio, enlarge fonts; prepare demo: success, escalation, guardrail block, unattended full run evidence (>= 7 min live)
- [ ] 6.16 Record take 1 by mid-week 3; review
- [ ] 6.17 Record take 2; verify length 18-22 min, audio, legibility, you on camera at intro and close

Workbooks and logs
- [ ] 6.18 All five stage workbooks genuinely completed
- [ ] 6.19 Effort Log finished: entries throughout, hours by stage reconcile, estimates vs reality, reflection answers, declaration (FirstnameLastname_Effort_Log.pdf)

Source code
- [ ] 6.20 Fresh clone on a clean machine: README steps work, tests pass, full run works
- [ ] 6.21 Credential scan of code and history; attribution for external/AI-generated code
- [ ] 6.22 Repo structure matches Submission Guide (README, requirements.txt, .env.example, src, prompts, tests, evaluation, docs, data, .github/workflows)

Packaging (day before deadline)
- [ ] 6.23 Build FirstnameLastname_Capstone_Submission.zip with exactly 4 folders: 01_Video, 02_Report, 03_Workbooks, 04_Source_Code
- [ ] 6.24 Run final checklist from Submission_Guide section 5
- [ ] 6.25 Submit before 21 November 23:59

---

## Open clarifications noticed in the pack (resolve early; do not guess)
- Hidden set size is stated as 100 in some docs and 120 in others; validation set is called 80 tickets.
- Some docs say validation set can be used any number of times; Brief says validation_tickets.json is "final evaluation, run once". Decide a protocol (suggest: dev 500 for building, validation 80 for checking, hidden set not available; log how often each used) and record it in the PRD.
- Some docs say the gate runs on "the validation set", others on the hidden set. Build the harness to accept any path.
- Stakeholder interviews are fictional transcripts; the "interview a real person" step in the README means testing your problem statement against the transcripts' viewpoints.
- Data handling: full dataset JSONs are committed in data/ (user confirmed at 1.11). Record this in the PRD and never commit a hidden set.
