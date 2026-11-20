"""5b.8 traffic: replay ticket files against the running API so the Grafana panels show real data.

Sends every ticket in the given files to POST /tickets one after another (the API handles one at a time),
plus a few malformed requests so the invalid-request counter moves. Only the ticket fields are sent; labels
and history stay behind. At the end it saves the /metrics text as evidence.

Usage (API running: uvicorn src.api:app --host 0.0.0.0 --port 8001):
    python docs/replay_api.py
    python docs/replay_api.py --url http://localhost:8001 --input data/validation_tickets.json \
        --input tests/fixtures/engineered_tickets.json --input tests/fixtures/must_escalate_tickets.json
Output: evaluation/results/<date>_api_replay/ (replay.md, responses.jsonl, metrics_snapshot.txt)
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from collections import Counter
from datetime import date
from pathlib import Path

import httpx

FIELDS = ("ticket_id", "channel", "subject", "body", "received_at", "customer_id", "customer_name")
DEFAULT_INPUTS = ["data/validation_tickets.json", "tests/fixtures/engineered_tickets.json",
                  "tests/fixtures/must_escalate_tickets.json"]
MALFORMED = [
    {"ticket_id": "BAD-1", "channel": "fax", "body": "Unknown channel."},
    {"ticket_id": "BAD-2", "channel": "email", "body": "   "},
    {"channel": "chat", "body": "No ticket id."},
]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--url", default="http://localhost:8001")
    ap.add_argument("--input", action="append", help="ticket file (repeatable); default: validation + engineered "
                    "+ must-escalate fixtures")
    ap.add_argument("--limit", type=int, default=None, help="at most this many tickets per file")
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    out = Path(a.out or f"evaluation/results/{date.today().isoformat()}_api_replay")
    out.mkdir(parents=True, exist_ok=True)
    client = httpx.Client(base_url=a.url, timeout=180)
    h = client.get("/health").json()
    print(f"API {a.url}: status {h['status']}, components {h['components']}, paused {h['automation_paused']}")
    if h["automation_paused"]:
        print("Kill switch is ON: every ticket will escalate. Turn it off first for a normal replay.")

    tickets = []
    for path in a.input or DEFAULT_INPUTS:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        tickets += [(path, {k: t.get(k) for k in FIELDS if k in t}) for t in raw[: a.limit]]
    rows, lat = [], []
    t_start = time.perf_counter()
    with open(out / "responses.jsonl", "w", encoding="utf-8") as f:
        for i, (src, t) in enumerate(tickets, 1):
            t0 = time.perf_counter()
            r = client.post("/tickets", json=t)
            dt = time.perf_counter() - t0
            d = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
            row = {"source": src, "ticket_id": t.get("ticket_id"), "channel": t.get("channel"), "status": r.status_code,
                   "outcome": d.get("outcome", f"http_{r.status_code}"), "rule_fired": d.get("rule_fired"),
                   "intent": d.get("intent"), "confidence": d.get("intent_confidence"), "seconds": round(dt, 3)}
            rows.append(row)
            lat.append(dt)
            f.write(json.dumps(row) + "\n")
            print(f"{i:>3}/{len(tickets)} {row['ticket_id']:<10} {row['channel'] or '':<12} {row['outcome']:<10} "
                  f"{row['rule_fired'] or '':<34} {dt:5.2f}s")
        for bad in MALFORMED:
            r = client.post("/tickets", json=bad)
            f.write(json.dumps({"malformed": bad, "status": r.status_code}) + "\n")
            print(f"malformed {bad.get('ticket_id', '(no id)'):<10} -> HTTP {r.status_code}")
    wall = time.perf_counter() - t_start
    metrics = client.get("/metrics").text
    (out / "metrics_snapshot.txt").write_text(metrics, encoding="utf-8")

    by_out = Counter(r["outcome"] for r in rows)
    by_rule = Counter((r["rule_fired"] or "").split(":")[0] for r in rows if r["outcome"] == "escalated")
    q = statistics.quantiles(lat, n=20) if len(lat) >= 2 else [0] * 19
    L = [f"# API replay (5b.8): {len(rows)} tickets + {len(MALFORMED)} malformed requests", "",
         f"API {a.url}, {date.today().isoformat()}, {wall / 60:.1f} minutes. Inputs: "
         + ", ".join(f"`{p}`" for p in (a.input or DEFAULT_INPUTS)) + ".", "",
         f"- Answered automatically: {by_out.get('answered', 0)} ({100 * by_out.get('answered', 0) / len(rows):.1f}%)",
         f"- Escalated: {by_out.get('escalated', 0)}",
         f"- Other: {sum(v for k, v in by_out.items() if k not in ('answered', 'escalated'))}",
         f"- Client-side latency: p50 {statistics.median(lat):.2f} s, p95 {q[18]:.2f} s, max {max(lat):.2f} s",
         f"- Escalation rules: " + ", ".join(f"{k} {v}" for k, v in by_rule.most_common()), "",
         "`metrics_snapshot.txt` is the /metrics output at the end; `responses.jsonl` has one line per request."]
    (out / "replay.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
