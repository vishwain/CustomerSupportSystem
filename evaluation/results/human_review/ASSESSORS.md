# Assessors (5.18)

Assessor A: LLM: Claude Sonnet 5.5 (Anthropic), run as a separate agent that was given only RUBRIC.md, review_packet.md and its blank sheet; no access to the build conversation, the code, or Assessor B's sheet
Assessor B: LLM: Claude Opus 5.5 (Anthropic), run as a separate agent that was given only RUBRIC.md, review_packet.md and its blank sheet; no access to the build conversation, the code, or Assessor A's sheet

No human assessor scored the sample; the project author chose two LLM assessors.
Two different model sizes were used so the assessors are not the same model.

Independence: each assessor scored in their own sheet (`assessor_A.csv`, `assessor_B.csv`) from the same
packet and rubric. Neither opened the other's sheet before both were finished. Assessor B scored first; Assessor A was started after B's sheet was moved where A could not read it.

Limits: Assessor B is a language model, not a person. It is a different model from the one that generated the
answers (nvidia/nemotron-3.5-lightning), but both assessors are the same model family (Claude) as the assistant that helped build the
system, so they may share blind spots and their agreement may overstate what two people would reach.
Disagreements are settled by re-reading the packet against the rubric and are listed with their resolution
in review_results.md.

Adjudication: the 17 disagreements were settled by the main assistant session (Claude Opus 5.5, the same
assistant that helped build the system), by re-reading each item against RUBRIC.md. Each ruling and its reason
is in adjudication.csv and review_results.md. This is a conflict of interest: the project author can override
any ruling by editing adjudication.csv and re-running `python -m evaluation.review_score`.
