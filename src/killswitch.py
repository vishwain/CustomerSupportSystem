"""Kill switch (FR-31, Governance Framework section 5): stop automatic answers at once, without a deployment.

Mechanism: the flag "automation_paused" in config/runtime.json. Route reads it before every ticket (before any
model call) and the harness and API read it again just before an answer is sent. While it is on, every ticket
escalates to a person with the holding message; nothing is dropped. A missing or unreadable file counts as on.

    python -m src.killswitch status
    python -m src.killswitch on  --by "Marcus" --reason "wrong answers about SSO, incident 1"
    python -m src.killswitch off --by "Marcus" --reason "fix verified on validation set"

Every change is appended to <STORAGE_DIR>/killswitch_audit.jsonl (who, when, why, before, after).
The write is atomic (temporary file, then rename), so a reader never sees half a file.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from src.route import RUNTIME_CONFIG, automation_paused


def audit_path() -> Path:
    return Path(os.environ.get("STORAGE_DIR", "storage")) / "killswitch_audit.jsonl"


def set_paused(paused: bool, by: str, reason: str, path: str | Path = RUNTIME_CONFIG,
               audit: str | Path | None = None) -> dict:
    if not by.strip() or not reason.strip():
        raise ValueError("--by and --reason are required: every change must say who and why")
    path = Path(path)
    before, _ = automation_paused(path)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    data = {"automation_paused": paused, "changed_by": by, "changed_at": now, "reason": reason}
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".runtime.", suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")
    os.replace(tmp, path)
    entry = {"at": now, "by": by, "reason": reason, "before": before, "after": paused, "file": str(path)}
    a = Path(audit) if audit else audit_path()
    a.parent.mkdir(parents=True, exist_ok=True)
    with open(a, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
    return entry


def status(path: str | Path = RUNTIME_CONFIG) -> dict:
    paused, why = automation_paused(path)
    try:
        d = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        d = {}
    return {"automation_paused": paused, "note": why, "changed_by": d.get("changed_by"),
            "changed_at": d.get("changed_at"), "reason": d.get("reason")}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Kill switch for automatic answers (FR-31).")
    ap.add_argument("command", choices=["status", "on", "off"])
    ap.add_argument("--by", default="")
    ap.add_argument("--reason", default="")
    ap.add_argument("--file", default=str(RUNTIME_CONFIG))
    a = ap.parse_args(argv)
    if a.command == "status":
        print(json.dumps(status(a.file), indent=2))
        return 0
    try:
        e = set_paused(a.command == "on", a.by, a.reason, a.file)
    except ValueError as err:
        print(f"refused: {err}", file=sys.stderr)
        return 2
    state = "ON: automatic answers stopped, every ticket escalates" if e["after"] else "OFF: automatic answers resume"
    print(f"Kill switch {state}. Takes effect on the next ticket. Logged to {audit_path()}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
