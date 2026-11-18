# Prompt register

Every prompt the system or its evaluation uses, with its version. The full register (purpose, inputs, injection defence, checklist results) is in `Workbooks/Stage_3_Prompt_Library.docx`, Section 2. This file is the in-repo index; the `.txt` files are the source of truth.

| Folder | What runs there |
| --- | --- |
| `specification/` | design time: turn a PRD requirement into a specification |
| `build/` | inside the running system |
| `review/` | design time: check an artifact against its requirements |
| `evaluation/` | offline: judge the system's output |

## Register

| ID | File | Category | Version | Serves | In default runtime path? | Change note |
| --- | --- | --- | --- | --- | --- | --- |
| PR-01 | `specification/fr_to_spec_v1.txt` | Specification | 1.0 | FR-01 to FR-34 | No | First version, 18 Nov 2026 |
| PR-02 | `build/classify_v1.txt` | Build | 1.0 | FR-04, FR-05 | **No.** Baseline and fallback. Default Classify is local (PRD 10.3) | First version, 18 Nov 2026 |
| PR-03 | `build/generate_v1.txt` | Build | 1.0 | FR-15, FR-16, FR-17, FR-20 (+ fields for FR-07, FR-13, FR-14) | Yes. The only model call | First version, 18 Nov 2026. Two wording fixes before release from smoke run 1 |
| PR-04 | `build/json_repair_v1.txt` | Build | 1.0 | FR-15, FR-25 (10.6) | Yes, only after a parse or schema failure, at most once | First version, 18 Nov 2026 |
| PR-05 | `review/requirement_review_v1.txt` | Review | 1.0 | All FRs (traceability) | No | First version, 18 Nov 2026 |
| PR-06 | `evaluation/groundedness_judge_v1.txt` | Evaluation | 1.0 | NFR-08 | No (offline) | First version, 18 Nov 2026 |
| PR-07 | `evaluation/reference_compare_v1.txt` | Evaluation | 1.0 | NFR-08, AS-03 | No (offline) | First version, 18 Nov 2026 |

Output schemas: `src/schemas/answer.json` (PR-03, PR-04), `src/schemas/classification.json` (PR-02).

## File format and conventions

- Lines starting with `#` at the top are a header for people. They are not sent to the model.
- The text after a line that is exactly `### SYSTEM` is the system message. The text after a line that is exactly `### USER` is the user message. Split on those two lines only (anchored, whole line). The header itself mentions `### SYSTEM` inside quotes, so a plain `split("### SYSTEM")` breaks; this happened in the first smoke run.
- Placeholders are `{{name}}`. After filling, no `{{` may remain.
- Before filling, code removes every `<<<` and `>>>` from ticket text, passage text and model output (FR-17). Delimiters then cannot be forged.
- Passage ids are `doc_id#section`, with section one of `symptoms`, `common-causes`, `resolution`, `notes` (the only four headings in `documentation.json`).
- Each decision-log row records `prompt_version` as `PR-xx vX.Y` (FR-24, NFR-05).

## Versioning rule

- Any change to the text after `### SYSTEM` or `### USER` makes a new file (`_v2.txt`) and a new register row. The old file stays.
- A header-only change keeps the version.
- Record the reason for each change here, and in the workbook change history.
- Stage 5 fills "how you know it worked" and "known weaknesses" from runs on real tickets.

## Smoke tests

`evaluation/prompt_smoke/` holds a separate-context smoke test of v1.0: rendered inputs, raw outputs and the code checks. It shows that the instructions are clear and the output parses. It is not a quality result: the stand-in model was not the production model.
