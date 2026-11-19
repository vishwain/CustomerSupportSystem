# Customer Support System

AI-assisted support for CloudServe (FDE Capstone). Each ticket is normalised, classified, matched to help
articles, routed by rules and a data-derived threshold, answered with citations or escalated with a
summary, checked by guardrails, and logged. Every decision, answered or escalated, has a row in a SQLite
decision log.

## Repo layout

| Path | What is there |
| --- | --- |
| `src/` | the pipeline: `ingest.py`, `classify.py`, `retrieve.py`, `route.py`, `generate.py`, `guardrails.py` (Validate), `llm.py` (provider client), `logging_store.py` (decision log), `pii.py`, `api.py` (FastAPI) |
| `prompts/` | prompt register; `build/` runs in the system (PR-02 classify, PR-03 answer, JSON repair) |
| `config/` | values set from data, each with its date and evidence: retrieval cutoff and query mode, routing threshold, calibration, grounding floor, prompt version, customer messages, kill switch (`runtime.json`) |
| `data/` | the capstone datasets: dev and validation tickets, documentation, ground-truth responses |
| `evaluation/` | `harness.py` (unattended run), `metrics.py` (FR-27 report), `gate_check.py`, `show_answers.py`, `show_log.py`; `results/` holds dated run evidence |
| `docs/` | experiments that set the config values (`retrieval_experiment.py`, `calibration.py`, `query_experiment.py`, ...) and their reports |
| `tests/` | the test suite and fixtures (engineered, failure and must-escalate tickets) |
| `Workbooks/`, `Observations/` | stage workbooks (PRD, prompt library, revision log) and working notes |
| `.github/workflows/` | CI |
| `storage/` | created at runtime: Chroma store, decision logs, trained classifier, provider cache. Never committed |

## Setup (fresh clone)

Needs Python 3.14 (developed and tested on 3.14; `requirements.txt` is a pinned freeze from that version,
so other versions are not verified), git, and an [OpenRouter](https://openrouter.ai/keys) API key. Commands are for PowerShell on Windows; the
macOS / Linux form is given where it differs.

**1. Clone**

```
git clone https://github.com/vishwain/CustomerSupportSystem.git
cd CustomerSupportSystem
```

**2. Virtual environment**

```
python -m venv .venv
.venv\Scripts\Activate.ps1          # macOS / Linux: source .venv/bin/activate
```

**3. Dependencies**

```
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

The first install is large (`torch`, `sentence-transformers`); allow several minutes.

**4. Environment file**

```
copy .env.example .env              # macOS / Linux: cp .env.example .env
```

Open `.env` and set `OPENROUTER_API_KEY`. Every other variable has a working default; each is explained
in `.env.example`. `.env` is git-ignored: never commit it.

**5. Ingest the knowledge base (builds the Chroma store)**

```
python -m src.retrieve --build
```

Downloads the embedding model (`all-MiniLM-L6-v2`, about 90 MB) on first use, chunks
`data/documentation.json` with the configured chunking and writes the store to `storage/chroma`. It prints
the passage count and a test query. The store is rebuilt automatically whenever the articles, the chunking
or the model change.

**6. Check the install**

```
pytest
```

About 20 seconds, no API key or network needed (see [Tests](#tests)). Expect every test to pass.

## Full run (one command)

```
python -m evaluation.harness --input data/validation_tickets.json --output evaluation/results/my_run
```

Runs every ticket unattended: answered or escalated, never stopped by a bad ticket or a provider failure.
On first use it trains the local classifier (under a minute, saved in `storage/models`). The 80 validation
tickets take about 4 minutes, mostly provider calls spaced 3 s apart. `--input` takes any `.json` list or
`.jsonl` file in the pack schema; no file name or ticket count is built in.

The output folder gets:

| File | What |
| --- | --- |
| `results.jsonl` | one line per ticket: action, reason, rule, reply or escalation package |
| `metrics_report.md`, `.json` | volume, business, technical, governance, segments, calibration (FR-27), built from the decision log |
| `answer_review.csv` | every sent answer with its cited passage text, for the two-assessor review (NFR-08) |
| `escalation_queue.csv` | escalations sorted by urgency, then age (FR-06) |
| `reconcile.json`, `run_info.json` | final rows = tickets check; run id, input hash, decision-log path |

Exit code 0 means every ticket has exactly one final decision row. Useful flags: `--limit 20` (first 20
tickets), `--no-llm` (no provider calls), `--no-models` (no embedding model), `--no-cache`.

Check a run independently of the harness, and read it:

```
python -m evaluation.gate_check --run-dir evaluation/results/my_run
python -m evaluation.show_answers --run-dir evaluation/results/my_run
python -m evaluation.show_log --run-dir evaluation/results/my_run
python -m evaluation.metrics --run-dir evaluation/results/my_run      # rebuild the report
```

## API

```
uvicorn src.api:app --port 8000
```

Loads the same components as the harness (about 10 s) and logs every request to
`storage/api/decisions.db`. Interactive docs at http://127.0.0.1:8000/docs. If port 8000 is taken, use
`--port 8001`.

| Endpoint | What it does |
| --- | --- |
| `POST /tickets` | One ticket in (`ticket_id`, `channel`, `subject`, `body`, `received_at`). Returns `outcome` (answered or escalated), `reason`, `rule_fired`, `citations`, the reply or holding message, and the `decision_id` of the final decision-log row. |
| `GET /health` | Status, which components loaded, kill-switch state. |
| `GET /metrics` | Prometheus text format: tickets by outcome, rules fired, invalid requests, latency, kill switch. |

Send one ticket (in PowerShell use `curl.exe`; `curl` is an alias there):

```
curl.exe -s -X POST http://127.0.0.1:8000/tickets -H "Content-Type: application/json" --data-binary "@tests/fixtures/api_ticket.json"
```

Malformed input (missing or wrong-typed field, blank body, unknown channel, broken JSON) gets HTTP 422 with
the field and the problem. `API_NO_MODELS=1` / `API_NO_LLM=1` start a degraded server that escalates
everything.

## Tests

```
pytest
```

`pytest.ini` points at `tests/` and puts the repo root on the import path. The suite needs no API key, no
network and no model download: model calls go through scripted clients and embeddings through a hashed
`FakeEmbedder`. An autouse fixture in `tests/conftest.py` fails any test that tries a real provider call or
model load, and sets a dummy key so a real key in `.env` is never used.

| A12 area | Tests |
| --- | --- |
| Ingest normalisation, each channel | `test_a12.py::test_ingest_normalises_each_channel`, `test_ingest.py` |
| Routing rule incl. must_not_auto_respond | `test_a12.py::test_must_not_auto_respond_class_escalates_with_no_model_call`, `test_route.py`, `test_must_escalate_check.py` |
| A guardrail that blocks | `test_a12.py::test_guardrail_blocks_private_data_and_nothing_is_sent`, `test_guardrails.py` |
| Failure handling | `test_a12.py::test_provider_timeout_escalates_with_reason_and_log_row`, `test_failures.py`, `test_llm.py` |
| Citation resolution | `test_a12.py::test_citations_resolve_to_retrieved_passages`, `test_generate.py` |
| Decision-log coverage | `test_a12.py::test_every_ticket_has_exactly_one_final_row`, `test_logging_store.py`, `test_gate_check.py` |

`pytest tests/test_a12.py` runs the six areas only; `pytest -x` stops at the first failure.

## Configuration set from data

Thresholds are not environment variables. Each is set by a script from measured data and committed with
its date, rule and evidence. Re-run a script only to re-derive its value; the committed values are what
the system uses.

| Config | Value | Set by |
| --- | --- | --- |
| `config/retrieval.json` | chunking, relevance cutoff, query mode | `python docs/retrieval_experiment.py --write-config`, then `python docs/query_experiment.py --write-config` |
| `config/calibration.json`, `config/routing.json` | confidence temperature, routing threshold | `python docs/calibration.py --write-config` |
| `config/routing.json` | must-escalate alternative floor | `python docs/must_escalate_check.py --write-config` |
| `config/generation.json` | answer prompt version (PR-03) | `python docs/generate_eval.py --write-config` |
| `config/guardrails.json` | grounding floor | `python docs/grounding_floor.py --write-config` |
| `config/runtime.json` | kill switch: `"automation_paused": true` escalates the next ticket (FR-31) | edit by hand |
| `config/messages.json`, `config/intent_descriptions.json` | customer-facing text; intent descriptions for the retrieval query | edit by hand |

Other evidence scripts: `python -m src.ingest --input data/development_tickets.json` (one normalised ticket
per channel), `python docs/guardrail_demo.py` (every guardrail firing), `python docs/failure_drill.py`
(forced failures, each run reconciles), `python docs/routing_threshold.py` (routing study).

## How it behaves

- **Routing:** rules first, before any confidence check: kill switch, instruction integrity, claims about an
  earlier support contact, must-escalate intents (security, compliance, data residency, feature request,
  unclear), dispute and risk wording on any intent, and the calibrated probability of the risky classes.
  Then: no supporting passage escalates; confidence below the threshold becomes a draft for an agent;
  otherwise an automatic answer.
- **Validate** checks every answer and draft before it leaves: private data, citations, grounding against
  the cited passages, instruction integrity, commitments and the confidence floor. A block escalates and
  drops the draft. Without a grounding floor every answer is blocked (fail closed).
- **Failure handling:** malformed records, no supporting passage, provider timeouts and outages (bounded
  retries, circuit breaker), rate limits, bad keys and broken model JSON all end in an escalation with a
  logged reason. Successful provider responses are cached, so a re-run spends no calls.

## Where data goes

| Location | What | Committed? |
| --- | --- | --- |
| `data/` | capstone datasets (input) | yes |
| `config/` | data-derived settings and their evidence pointers | yes |
| `evaluation/results/` | dated run evidence | yes |
| `storage/chroma/` | Chroma store (`CHROMA_PATH`) | no |
| `storage/runs/<run_id>/decisions.db`, `storage/api/decisions.db` | decision logs (`STORAGE_DIR`) | no |
| `storage/models/`, `storage/llm_cache/` | trained classifier, provider cache | no |

Delete `storage/` to reset all runtime state; the next run rebuilds the store and retrains the classifier.
If the repo sits in a synced folder (Google Drive, OneDrive) and SQLite reports locking errors, add
`--storage <local folder>` to the harness.
