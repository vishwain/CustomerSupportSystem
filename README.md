# Customer Support System

AI-powered customer support system (FDE Capstone).

## Layout

| Path | Purpose |
| --- | --- |
| `src/` | application code (ingest, classify, retrieve, route, generate, guardrails, logging_store, api) |
| `prompts/` | prompt register; `build/` runs in the system, `evaluation/` judges output |
| `tests/` | unit and integration tests |
| `evaluation/` | evaluation harness and dated results |
| `docs/` | architecture and design docs |
| `data/` | small samples only |
| `storage/` | generated at runtime, never committed |

## Setup (fresh clone)

Requires Python 3.10+ (developed on 3.14) and an [OpenRouter](https://openrouter.ai/keys) API key.

### 1. Clone the repo

```
git clone <repo-url>
cd CustomerSupportSystem
```

### 2. Create and activate a virtual environment

```
python -m venv .venv
```

Activate it:

| Shell | Command |
| --- | --- |
| Windows (PowerShell) | `.venv\Scripts\Activate.ps1` |
| Windows (cmd) | `.venv\Scripts\activate.bat` |
| macOS / Linux / Git Bash | `source .venv/bin/activate` (Git Bash on Windows: `source .venv/Scripts/activate`) |

### 3. Install dependencies

```
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

`requirements.txt` is a full `pip freeze` (pinned, including transitive dependencies). The first install is large
because it pulls in `torch` and `sentence-transformers`, so allow some time on a slow connection.

### 4. Configure environment variables

Copy the template to `.env` and fill in your values:

```
# Windows (cmd / PowerShell)
copy .env.example .env

# macOS / Linux / Git Bash
cp .env.example .env
```

| Variable | Purpose | Default in template |
| --- | --- | --- |
| `OPENROUTER_API_KEY` | your OpenRouter key (required) | _none, set this_ |
| `MODEL_NAME` | chat model for Generate and the PR-02 classifier fallback; `:free` ids only (NFR-07) | `nvidia/nemotron-3.5-lightning:free` |
| `LLM_REASONING`, `LLM_TIMEOUT_S`, `LLM_MIN_INTERVAL_S` | provider call settings (PRD 10.6) | `off`, `10`, `3` |
| `LLM_CACHE` | `1` caches provider responses by prompt hash in `storage/llm_cache` (development only) | `0` |
| `EMBEDDING_MODEL` | sentence-transformers embedding model | `all-MiniLM-L6-v2` |
| `CHROMA_PATH` | vector store location | `./storage/chroma` |
| `DATABASE_URL` | decision log database | `sqlite:///./storage/decisions.db` |
| `LOG_LEVEL` | logging verbosity | `INFO` |

`.env` holds your secret key. It is git-ignored: never commit it.

Thresholds are not environment variables. They are set from data and committed with their date:
`config/retrieval.json` (relevance cutoff), `config/routing.json` (routing threshold, from the calibration table)
and `config/calibration.json` (confidence temperature, used only if the calibration run adopted it).
`config/runtime.json` holds the kill switch: set `"automation_paused": true` and the next ticket escalates (FR-31).


## Run

All commands run from the repo root with the virtual environment active.

| What | Command |
| --- | --- |
| Tests (A12) | `pytest` (see Tests below) |
| Ingest proof: one ticket per channel, normalised (A2) | `python -m src.ingest --input data/development_tickets.json` |
| Retrieval experiment: compare chunking, pick cutoff, write `config/retrieval.json` (A4) | `python docs/retrieval_experiment.py --write-config` |
| Train the local classifier (also happens automatically on first use) (A3) | `python -m src.classify` |
| Routing study at Route level (FR-11 view, 5.6) | `python docs/routing_threshold.py` |
| Calibration table and routing threshold: writes `evaluation/results/<date>_calibration/`, `config/routing.json`, `config/calibration.json` (5.7) | `python docs/calibration.py --write-config` |
| Compare answer prompts PR-03 v1.0 and v2.0 on the dev hold-out; writes `config/generation.json` (5.8) | `python docs/generate_eval.py --write-config` |
| Grounding floor for Validate, plus guardrail false-positive check; writes `config/guardrails.json` (5.9) | `python docs/grounding_floor.py --write-config` |
| Guardrail demo: every guard fires on crafted outputs, no model call (A7, video) | `python docs/guardrail_demo.py` |
| Must-not-auto-respond check: every risky class escalates; sets the alternative-guard floor (5.10) | `python docs/must_escalate_check.py --write-config` |
| Failure drill: malformed input, no docs, bad key, timeout, cache re-run; each run must reconcile (5.11, A11) | `python docs/failure_drill.py` |
| Engineered tickets through the full pipeline (A7) | `python -m evaluation.harness --input tests/fixtures/engineered_tickets.json --output evaluation/results/<run-folder>` |
| Query experiment: text vs intent-expanded retrieval query, cutoff per mode; sets `query_mode` and cutoff (5.13 follow-up, NFR-06) | `python docs/query_experiment.py --write-config` |
| Gate check: input records = final log rows, valid actions, no must-not ticket answered; optional re-run comparison (5.12) | `python -m evaluation.gate_check --run-dir evaluation/results/<gate run> --compare evaluation/results/<re-run>` |
| Full unattended run on any ticket file (A9, A10) | `python -m evaluation.harness --input data/validation_tickets.json --output evaluation/results/<run-folder>` |

The harness takes any `.json` list or `.jsonl` file of tickets in the pack schema. No filename or ticket count is
built in. It writes `results.jsonl`, `reconcile.json`, `decision_log_extract.jsonl`, `metrics_report.md/.json`
and `run_info.json` to the output folder. Exit code 0 means every ticket has exactly one final decision row.

The decision log for each run is a SQLite file at `storage/runs/<run_id>/decisions.db` (override with `--db`, or
`--storage` / `STORAGE_DIR` for the folder). If the repo sits in a synced folder (Google Drive, OneDrive) and SQLite
reports locking errors, point `--storage` at a local folder.

Retrieval needs `config/retrieval.json`, which the experiment writes from measured data (chunking config,
relevance cutoff, date set). The first run downloads `all-MiniLM-L6-v2` to the Hugging Face cache; the Chroma
index is built in `storage/chroma` and rebuilt automatically when the docs, chunking or model change.
Results and the reasoning are in `docs/retrieval_experiment.md`.

Current state: the full pipeline runs: Ingest, Classify, Retrieve, Route, Generate (PR-03), Validate, each with
its own decision-log row. Validate (`src/guardrails.py`) checks every answer and draft before anything leaves:
private data (including every customer name and id in the run), citations, grounding against the cited passages
(floor in `config/guardrails.json`, set from data), instruction integrity (ticket and output), commitments
(refunds, fixes, dates) and the confidence floor. A block escalates the ticket, drops the draft and logs the
reason; only an answer that passes is sent (final action `auto_respond`). Without the grounding floor every
answer is blocked (fail closed). Route escalates must-not-auto-respond tickets before any confidence check, on
four independent checks: predicted intent, dispute wording (any intent), security/legal/residency wording (any
intent) and the calibrated probability of the risky classes (floor set from data). Each escalation carries a
summary, the opening of the ticket and the retrieved sources. Customer-facing text is in `config/messages.json`; the PR-03 version in
`config/generation.json`. `--limit 20` runs the first 20 tickets; `--no-models` skips the embedding model;
`--no-llm` skips all provider calls; `--no-cache` skips the provider cache.

Failure handling (A11): a malformed record (empty, missing fields, wrong types, undecodable text, non-UTF-8
file) is logged and escalated without a model call. No supporting passage escalates with no draft. Every
provider call has a timeout (`LLM_TIMEOUT_S`), two retries with backoff, a 60 s cap on rate-limit waits and a
circuit breaker; a bad key or model id is not retried and opens the circuit at once. Broken model JSON gets one
repair, then escalates. Successful responses are cached (on by default), so a re-run of the same file spends
no calls. Every case writes a final decision row with its reason, so every run reconciles.

Read the generated answers next to the ticket and the cited passage text:
`python -m evaluation.show_answers --run-dir evaluation/results/<run-folder>`.

Read a run's decision log as text: `python -m evaluation.show_log --run-dir evaluation/results/<run-folder>`.

## Tests

From the repo root, with the virtual environment active:

```
pytest
```

`pytest.ini` points at `tests/` and puts the repo root on the import path, so no other arguments are
needed (`python -m pytest` works too). The suite takes about 20 seconds and needs **no API key, no network
and no model download**: model calls go through scripted clients (`FakeClient`, scripted transports) and
embeddings through a hashed `FakeEmbedder`. An autouse fixture in `tests/conftest.py` makes any real
provider call or model load fail the test, and sets a dummy key so a real key in `.env` is never used.

What the A12 areas are covered by (`tests/test_a12.py` has one end-to-end test per area; the other files
go deeper):

| Area | Tests |
| --- | --- |
| Ingest normalisation, each channel | `test_a12.py::test_ingest_normalises_each_channel`, `test_ingest.py` |
| Routing rule incl. must_not_auto_respond | `test_a12.py::test_must_not_auto_respond_class_escalates_with_no_model_call`, `test_route.py`, `test_must_escalate_check.py` |
| A guardrail that blocks | `test_a12.py::test_guardrail_blocks_private_data_and_nothing_is_sent`, `test_guardrails.py` |
| Failure handling | `test_a12.py::test_provider_timeout_escalates_with_reason_and_log_row`, `test_failures.py`, `test_llm.py` |
| Citation resolution | `test_a12.py::test_citations_resolve_to_retrieved_passages`, `test_generate.py` |
| Decision-log coverage | `test_a12.py::test_every_ticket_has_exactly_one_final_row`, `test_logging_store.py`, `test_gate_check.py` |

Useful variants: `pytest tests/test_a12.py` (the six areas only), `pytest -k route` (one area),
`pytest -x` (stop at the first failure).

## Where data goes

| Location | What | Committed? |
| --- | --- | --- |
| `data/` | small sample inputs only (place sample tickets / knowledge-base files here for ingest) | yes (small files only) |
| `storage/chroma/` | Chroma vector store, created at runtime from `CHROMA_PATH` | no |
| `storage/decisions.db` | SQLite decision log, created at runtime from `DATABASE_URL` | no |
| `evaluation/results/` | dated evaluation outputs | yes |

`storage/` is created automatically on first run. To reset the system's state, delete `storage/` and re-run ingest.
Do not put large or private datasets in `data/`.

Non-source project documents (PRD, workbooks, reports) live in the FDECapstone Google Drive folder.
