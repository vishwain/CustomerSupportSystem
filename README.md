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
| `MODEL_NAME` | chat model used for generation | `meta-llama/llama-3.1-8b-instruct` |
| `EMBEDDING_MODEL` | sentence-transformers embedding model | `all-MiniLM-L6-v2` |
| `CHROMA_PATH` | vector store location | `./storage/chroma` |
| `DATABASE_URL` | decision log database | `sqlite:///./storage/decisions.db` |
| `LOG_LEVEL` | logging verbosity | `INFO` |
| `CONFIDENCE_THRESHOLD` | minimum confidence before escalating | `0.80` |

`.env` holds your secret key. It is git-ignored: never commit it.


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
