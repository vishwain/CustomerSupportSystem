# Attribution

## AI-generated code

This repository was built with Claude (Anthropic), used through the Claude app with access to the project folder,
as declared in Section 11 of the report (VishwainAnnadate_Capstone_Report.pdf).

- **Written mostly by Claude, directed and reviewed by Vishwain Annadate:** all of `src/`, `evaluation/`
  (harness, metrics, gate check, review, log and fairness audits), the experiment and drill scripts in `docs/`,
  `tests/` (including fixtures), `monitoring/`, `.github/workflows/ci.yml`, and `config/` values set by those scripts.
- **Prompts in `prompts/`:** drafted with Claude and revised against evaluation results (Stage 3 prompt library).
- **Evidence in `evaluation/results/`:** produced by running the code above on Vishwain Annadate's machine.
  The two assessors in `evaluation/results/human_review/` were separate Claude agents (stated in the report).
- **Workbooks and report:** written with Claude's assistance as declared in Section 11 of the report. The reflection
  answers in the revision log and all decisions on scope, threshold rules and trade-offs are Vishwain Annadate's.

Every run, test and evaluation was executed and checked by Vishwain Annadate. No code was copied from another
student, a previous cohort or a public repository.

## Generation model (part of the system, not authoring help)

The running system calls `nvidia/nemotron-3.5-lightning:free` through OpenRouter to write answers (see README).

## Third-party libraries and models

Pinned in `requirements.txt` and used under their own licences, including: FastAPI, Uvicorn, Pydantic,
sentence-transformers with the `all-MiniLM-L6-v2` model, scikit-learn, Chroma, LangChain text splitters,
the OpenAI Python client (for the OpenRouter API), prometheus_client, NumPy and pytest.
Monitoring uses the Prometheus and Grafana Docker images.

## Data

`data/` holds the course-provided CloudServe datasets (development and validation tickets, documentation and
reference answers) from the FDE Capstone project pack. CloudServe is fictional. The hidden evaluation set is not
in this repository.
