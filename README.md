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

## Setup

```
python -m venv .venv
.venv\Scripts\activate        # Windows
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
copy .env.example .env        # then fill in your key (.env is gitignored)
```

Non-source project documents (PRD, workbooks, reports) live in the FDECapstone Google Drive folder.
