# Hidden / final evaluation set (5.19)

**Case that applies: no hidden set was available.** Checked on 2026-11-20 (11:40 IST).

## What was checked

- `Reference/05_Datasets/` holds `development_tickets.json` (500), `validation_tickets.json` (80),
  `ground_truth_responses.json` (200), `documentation.json` (29), `Dataset_Guide.docx` and
  `Stakeholder_Interviews.docx`. No hidden, held-out or test ticket file. The rest of `Reference/` and the
  repo's `data/` folder hold no other ticket file either.
- The pack says the hidden set is not distributed: the Dataset Guide and the README describe "a hidden set of
  120 tickets" run after submission; the Evaluation Framework and the Build Specification refer to "the hundred
  tickets". The size differs by document; the set itself is absent in both.
- Nothing was invented or relabelled as a hidden set.

## What was used instead, and how often

| Set | Used for | Runs |
| --- | --- | --- |
| `development_tickets.json` (500) | building and tuning: classifier training, a 20% hold-out split by text that set every threshold (retrieval cutoff and query mode, calibration temperature and routing threshold, must-escalate floor), grounding floor from the 200 reference answers | **0 harness runs.** Used only through the experiment scripts in `docs/`, each recorded with its date in the config value it set |
| `validation_tickets.json` (80) | checking only; no value was set on it | **11 harness runs** on 19-20 Nov 2026 (first 2026-11-19 02:34 UTC, last 2026-11-20 02:57 UTC). Run 11 is the reported evaluation (5.17). Also 2 ten-ticket runs in the clean-clone check (5.16), in a separate checkout |

## Sentence for the report (section 6.7) and the PRD protocol note

No hidden evaluation set was available: the pack states that the hidden set (120 tickets in the Dataset Guide,
100 in the Evaluation Framework) is not distributed and is run after submission. The system was built and
tuned on the 500 development tickets, with every threshold set on a 20% hold-out of them and no harness run on
the development file, and checked on the 80 validation tickets: 11 harness runs on 19-20 November 2026, of
which run 11 (20 November 2026, 02:57 UTC) is the reported evaluation, plus two ten-ticket runs in the
clean-clone check. Every figure in this report comes from the validation set, not from the hidden set.

The harness takes `--input` and `--output`, so it can be pointed at the hidden set exactly as submitted:

```
python -m evaluation.harness --input <hidden_tickets.json> --output evaluation/results/hidden_run
```
