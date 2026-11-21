# Demo commands (6.15)

Everything for the live demo, in order. PowerShell, repo root, virtual environment active
(`.\.venv\Scripts\Activate.ps1`). Ticket files are in `docs/demo/`.

## Before recording (one time)

```
# Terminal A: the API (leave running)
uvicorn src.api:app --host 0.0.0.0 --port 8001

# Terminal B: monitoring (leave running)
docker compose -f monitoring/docker-compose.yml up -d

# Terminal B: check the kill switch is OFF and the API is healthy
python -m src.killswitch status
curl.exe -s http://localhost:8001/health | python -m json.tool
```

Dry-run every command below once before recording, so the embedding model is loaded and nothing surprises you.
Then restart Terminal A (Ctrl+C, run uvicorn again) so the Grafana counts start from zero for the recording.

## Demo 1: automatic answer with citations (about 1 min)

```
curl.exe -s -X POST http://localhost:8001/tickets -H "Content-Type: application/json" --data-binary "@docs/demo/01_answer.json" | python -m json.tool
```

Point at: `"outcome": "answered"`, `citations` (DOC-DEPLOY-002, "Rolling back a failed release"), the reply starting
"This is an automated reply", the `Sources:` line, `reason` (confidence 1.00 >= 0.95, passed Validate), `decision_id`.

## Demo 2: escalation with summary and sources (about 1.5 min)

```
curl.exe -s -X POST http://localhost:8001/tickets -H "Content-Type: application/json" --data-binary "@docs/demo/02_escalation.json" | python -m json.tool
python -m src.trace ticket DEMO-2-ESCALATE
```

Point at: `"outcome": "escalated"`, `rule_fired` = must_escalate_intent:security_incident, the `escalation_summary`,
the holding `customer_message` (no product claim). In the trace: every stage row, the retrieval `sources`
passed to the agent, and the routing reason. No model call was made for the answer.

## Demo 3: guardrails blocking (about 2 min)

a) Engineered injection ticket, stopped before any model call:

```
curl.exe -s -X POST http://localhost:8001/tickets -H "Content-Type: application/json" --data-binary "@docs/demo/03_guardrail_injection.json" | python -m json.tool
```

Point at: `rule_fired` = instruction_integrity, "escalated", reason. The text tried to make the system refund and
print its prompt.

b) Engineered commitment bait (waive a charge, promise a fix date):

```
curl.exe -s -X POST http://localhost:8001/tickets -H "Content-Type: application/json" --data-binary "@docs/demo/04_guardrail_dispute.json" | python -m json.tool
```

Point at: `rule_fired` = billing_dispute: the system never promises money or fixes.

c) Validate blocking a bad answer (private data, unsupported claim, promise, prompt leak):

```
python docs/guardrail_demo.py
```

Then open `evaluation/results/<today>_guardrail_demo/demo.md`. Point at case B (email and phone in the answer:
blocked), case E (unsupported sentence: blocked) and case F (refund promise: blocked). Same Validate code that runs
on every live answer. Also show `evaluation/results/guardrail_evidence/blocked_outputs.md` section 3: the two real
drafts Validate blocked on run 11.

d) Optional, 30 s: kill switch.

```
python -m src.killswitch on --by "Vishwain" --reason "demo"
curl.exe -s -X POST http://localhost:8001/tickets -H "Content-Type: application/json" --data-binary "@docs/demo/01_answer.json" | python -m json.tool
python -m src.killswitch off --by "Vishwain" --reason "demo over"
```

Point at: the same ticket that was answered in Demo 1 now escalates with rule `kill_switch`.

## Demo 4: the unattended full run (about 2.5 min)

Start it FIRST in Terminal C at the beginning of the demo section, so it runs while you show Demos 1 to 3:

```
python -m evaluation.harness --input data/validation_tickets.json --output evaluation/results/demo_full_run
```

When it ends, show:

```
Get-Content evaluation/results/demo_full_run/reconcile.json
python -m evaluation.gate_check --run-dir evaluation/results/demo_full_run
python -m evaluation.log_audit --run-dir evaluation/results/demo_full_run
```

Then open `evaluation/results/demo_full_run/metrics_report.md` in the editor and scroll: volume, business,
technical, governance, segments.

Say: one command, 80 tickets, no intervention; 80 final rows for 80 tickets; gate passed. The provider cache is on
by default, so a repeat run is faster; the official run 11 (`evaluation/results/validation_5.17_official/`) was run
with `--no-cache`, and the fresh-clone check re-ran it from GitHub with the same result.

## Demo 5: Grafana (30 s, end of demo)

Open http://localhost:3000. Point at: tickets by channel and outcome, auto vs escalated, latency p50/p95,
guardrail activations (instruction_integrity, tone_scope, must_escalate from the demo tickets), confidence histogram.

## If something fails during recording

- Provider slow or rate-limited: the ticket escalates with a reason. Say so; it is the failure handling working.
- API not answering: restart Terminal A. The decision log keeps everything.
- Full run still going at minute 12: show `evaluation/results/validation_5.17_official/` (same files) and come back.
