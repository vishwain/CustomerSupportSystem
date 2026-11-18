# Prompt Library: Notes Outside the Workbook (Checklist 3.1–3.9)

Workbook: Stage_3_Prompt_Library.docx. Prompts: `prompts/`. Smoke evidence: `evaluation/prompt_smoke/`.

---

## 1. Decisions taken in Stage 3
- **Classification prompt (PR-02) is a baseline/fallback only.** PRD 10.2 and 10.3 reject an LLM classifier: its confidence is uncalibrated, it costs a call, and it is not deterministic. PR-02 exists to give Stage 5 a measured comparison, and a fallback if AS-05 or AS-06 fails. Making it primary would be a PRD change, and it breaks the one-call budget (NFR-07).
- **One generate prompt for both modes.** Answer and draft modes share PR-03, with `MODE` in the user message. This avoids two texts drifting apart. FR-14 is served by the mode switch.
- **The "I don't know" path has two layers.** No passage over the cutoff: Route escalates with no model call (FR-11). Passages retrieved but not answering: PR-03 returns `can_answer = false` (FR-16).
- **Schemas committed:** `src/schemas/answer.json` (named in FR-15) and `src/schemas/classification.json`.
- **Passage id format fixed:** `doc_id#symptoms|common-causes|resolution|notes`.

## 2. Gaps found that need a decision (not changed in the PRD)
1. **Partial answers.** Every answer-mode smoke reply filled `unsure_about` (37–68 words), usually with agent checks. PRD says nothing about Route when `can_answer = true` and `unsure_about` is not empty. Options:
   - (a) ignore `unsure_about` in answer mode;
   - (b) treat non-empty as draft-and-escalate, which would escalate nearly everything at present;
   - (c) tighten PR-03 to leave it empty unless part of the question goes unanswered, then apply (b). Recommended.
   Decide before build day 4. A change to PR-03 makes it v1.1.
2. **Customer-typed private data reaches the provider.** FR-03 removes fields, but a customer can type an email, phone or id in the body (smoke G5). The model did not echo them, but they leave the machine. Decide under OQ-05: redact with the FR-22 pattern list before the call, or accept and state it.
3. **PRD 10.3 chunk count is wrong.** It says ~9 sections per article and ~260 passages. Every article has 4 sections (Symptoms, Common causes, Resolution, Notes): 116 passages. Fix in the Stage 5 revision log.
4. **Derived figures pass the citation check.** G8 stated "roughly forty minutes", worked out from "ten minutes per hundred gigabytes". The cited passage holds the rate, not the result. The FR-22 grounding floor may or may not catch it. Add a fixture.
5. **Escalation summary length.** Smoke summaries ran 40–58 words against the 60-word cap. Code must count words and fall back to the template summary.
6. **Few-shot ids inside the system prompt.** PR-03's examples cite DOC-API-001 and DOC-DATA-001 passages. Only the citation-set check (FR-22.2) stops a reply that cites them for an unrelated ticket.
7. **Model id still not pinned.** `.env.example` (`meta-llama/llama-3.1-8b-instruct`, no `:free`) and `test.py` (`nvidia/nemotron-3.5-lightning:free`) disagree. Every build prompt's "model used" depends on it.
8. **Config files the prompts rely on do not exist yet:** `config/messages.json` (holding message, automated label), the instruction-integrity phrase list, the commitment phrase list.

## 3. Label noise seen while testing
- DEV-0073 (charges for an unused service) and DEV-0024 (400 GB restore duration) are labelled `answerable_from_docs = false`, yet DOC-BILL-001 and DOC-DATA-002 give usable steps. DEV-0087 (expired export link) is labelled false, while DOC-DATA-001 answers it directly.
- This fits DataSources_Notes §2 (36 conflicting answerable labels). FR-16's acceptance already reports conflicting texts apart. Expect PR-03 to "fail" some false-labelled tickets with grounded answers. Read those by hand before you tighten the prompt.

## 4. Test case IDs
- TC-xx ids in workbook Section 4 are reserved names for tests not yet written (Stage 5, tests/). SM-xx ids are the smoke cases in `evaluation/prompt_smoke/`.

## 5. For report 6.12 (AI tool use declaration)
Stage 3 was drafted with AI help (Claude Opus 5.5, in the claude.ai project), 18 Nov 2026:
- Drafted: Section 1 specification rows (from PRD v1.0 text), all seven prompt files, the register entries, the checklist results and the traceability table, `src/schemas/*.json`, `prompts/README.md`, the smoke-test scripts and this note.
- To reduce AI marking its own work, prompts were smoke-tested by a separate agent (Claude Haiku). It saw only the rendered prompt and test inputs, none of the design discussion. Outputs were then checked by code, not by the drafting model.
- My part: [fill in: what you reviewed, changed or rejected, and the decisions you took on §2].
- Limits: the stand-in model is not the production model. "How you know it worked" and "known weaknesses" stay open until Stage 5.
