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
| Tests (A12) | `python -m pytest tests -q` |
| Ingest proof: one ticket per channel, normalised (A2) | `python -m src.ingest --input data/development_tickets.json` |
| Retrieval experiment: compare chunking, pick cutoff, write `config/retrieval.json` (A4) | `python docs/retrieval_experiment.py --write-config` |
| Train the local classifier (also happens automatically on first use) (A3) | `python -m src.classify` |
| Routing study at Route level (FR-11 view, 5.6) | `python docs/routing_threshold.py` |
| Calibration table and routing threshold: writes `evaluation/results/<date>_calibration/`, `config/routing.json`, `config/calibration.json` (5.7) | `python docs/calibration.py --write-config` |
| Compare answer prompts PR-03 v1.0 and v2.0 on the dev hold-out; writes `config/generation.json` (5.8) | `python docs/generate_eval.py --write-config` |
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

Current state: Ingest, Classify, Retrieve, Route and Generate run, and each writes its own decision-log row.
Generate (PR-03) runs only when Route chose auto_respond or draft_for_review; every cited passage id is checked in
code against the passages retrieved for that ticket. Validate (5.9) is not built, so nothing is sent yet: an answer
that passes the citation check is held for an agent and marked `would_send` in `results.jsonl`. Customer-facing
text (automated label, greeting, sign-off, holding message) is in `config/messages.json`. Which PR-03 version runs is
in `config/generation.json`. Generate also sees the other chunks of each retrieved article (`expand_docs` in
`config/retrieval.json`, default 2), so an answer can reach the Resolution steps; Route still counts only the
passages that passed the cutoff. `--limit 20` runs the
first 20 tickets; `--no-models` skips the embedding model; `--no-llm` skips all provider calls.

Read the generated answers next to the ticket and the cited passage text:
`python -m evaluation.show_answers --run-dir evaluation/results/<run-folder>`.

Read a run's decision log as text: `python -m evaluation.show_log --run-dir evaluation/results/<run-folder>`.

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
