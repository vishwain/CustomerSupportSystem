"""Ingest (A2; PRD FR-01, FR-02, FR-03).

Turns one raw ticket record from any channel into one normalised TicketRecord.
Never raises on a bad record: problems become flags, and an unusable record gets
ingest_error = "malformed_input" so the pipeline escalates it (PRD 10.6).

What later components may read (FR-03): TicketRecord.model_view() only
(ticket_id, channel, subject, body, received_at, text). customer_id and
customer_name are held aside in `held_for_validate` for the Validate block
check (FR-22). Tier, region, fluency, labels and history are dropped here; the
evaluation layer joins them from the input file by ticket_id.

Proof run (prints one ticket per channel):
    python -m src.ingest --input data/development_tickets.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import unicodedata
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator

INGEST_VERSION = "ingest-1.0"
CHANNELS = ("email", "chat", "docs_comment", "forum")
MAX_TEXT_CHARS = 4000  # FR-02
MALFORMED = "malformed_input"
UNREADABLE_SHARE = 0.3  # body more than 30% U+FFFD (undecodable bytes) = unreadable, escalate

# Fields that must never pass ingest (FR-03). Kept here so a test can assert it.
DROPPED_FIELDS = ("customer_tier", "customer_region", "language_fluency", "labels", "history")
HELD_FIELDS = ("customer_id", "customer_name")


@dataclass
class TicketRecord:
    """The one record shape every later component reads. Field names are stable."""

    ticket_id: str
    channel: str  # one of CHANNELS, or "unknown"
    subject: str  # original, unchanged ("" if missing)
    body: str  # original, unchanged ("" if missing)
    received_at: str  # as given (ISO 8601 expected); flagged if unparseable
    text: str  # cleaned: subject + body, NFC, control chars removed, max 4,000 chars
    ingest_error: str | None = None  # "malformed_input" -> escalate, no model call
    ingest_reason: str = "accepted"
    flags: dict[str, bool] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    # Held aside for Validate only (FR-03, FR-22). Never in model_view().
    held_for_validate: dict[str, str] = field(default_factory=dict, repr=False)

    @property
    def ok(self) -> bool:
        return self.ingest_error is None

    def model_view(self) -> dict[str, str]:
        """The only fields Classify, Retrieve, Route and Generate receive (FR-03)."""
        return {
            "ticket_id": self.ticket_id,
            "channel": self.channel,
            "subject": self.subject,
            "body": self.body,
            "received_at": self.received_at,
            "text": self.text,
        }

    def to_dict(self, include_held: bool = False) -> dict[str, Any]:
        d = asdict(self)
        if not include_held:  # show the id (needed to prove it is carried), mask the name
            d["held_for_validate"] = {
                k: (v if k == "customer_id" else "[held]") for k, v in self.held_for_validate.items()
            }
        return d


_CONTROL_KEEP = {"\n", "\t"}


def _clean(s: str) -> tuple[str, bool]:
    """NFC-normalise and strip control characters (keep newline and tab). Returns (text, changed)."""
    s = unicodedata.normalize("NFC", s).replace("\r\n", "\n").replace("\r", "\n")
    out = "".join(
        c for c in s if c in _CONTROL_KEEP or unicodedata.category(c) not in ("Cc", "Cf", "Cs", "Co")
    )
    return out, out != s


def _as_str(v: Any) -> str:
    if v is None:
        return ""
    return v if isinstance(v, str) else str(v)


def _valid_timestamp(ts: str) -> bool:
    try:
        datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return True
    except ValueError:
        return False


def _row_id(position: int) -> str:
    return f"ROW-{position + 1:04d}"


def malformed_record(position: int, reason: str, raw_preview: str = "") -> TicketRecord:
    """A record we could not parse at all. Still gets an id so the log reconciles."""
    return TicketRecord(
        ticket_id=_row_id(position),
        channel="unknown",
        subject="",
        body="",
        received_at="",
        text="",
        ingest_error=MALFORMED,
        ingest_reason=reason,
        flags={"unparseable": True},
        metadata={
            "position": position,
            "ingest_version": INGEST_VERSION,
            "raw_preview_chars": len(raw_preview),
        },
    )


def normalise(raw: Any, position: int) -> TicketRecord:
    """One raw record (dict from the pack JSON) -> TicketRecord. Never raises."""
    if not isinstance(raw, dict):
        return malformed_record(position, f"record is {type(raw).__name__}, not an object", _as_str(raw))

    flags: dict[str, bool] = {}

    ticket_id = _as_str(raw.get("ticket_id")).strip()
    if not ticket_id:
        ticket_id = _row_id(position)
        flags["missing_ticket_id"] = True

    channel_raw = raw.get("channel")
    channel = _as_str(channel_raw).strip().lower()
    if not channel:
        channel = "unknown"
        flags["missing_channel"] = True
    elif channel not in CHANNELS:
        channel = "unknown"
        flags["unknown_channel"] = True

    subject = _as_str(raw.get("subject"))
    body = _as_str(raw.get("body"))
    if not subject.strip():
        flags["missing_subject"] = True

    received_at = _as_str(raw.get("received_at")).strip()
    if not received_at:
        flags["missing_received_at"] = True
    elif not _valid_timestamp(received_at):
        flags["bad_received_at"] = True

    subj_clean, c1 = _clean(subject.strip())
    body_clean, c2 = _clean(body.strip())
    if c1 or c2:
        flags["control_chars_removed"] = True
    text = f"{subj_clean}\n\n{body_clean}" if subj_clean else body_clean
    if len(text) > MAX_TEXT_CHARS:
        text = text[:MAX_TEXT_CHARS]
        flags["truncated"] = True
    if any(ord(c) > 127 for c in text):
        flags["non_ascii"] = True  # kept, not an error (FR-02)

    ingest_error, reason = None, "accepted"
    bad = body_clean.count("\ufffd")
    if bad:
        flags["replacement_chars"] = True  # bytes that could not be decoded
    visible = len("".join(body_clean.split()))
    if not body_clean.strip():
        ingest_error = MALFORMED
        reason = "empty or whitespace-only body"
        flags["empty_body"] = True
    elif visible and bad / visible > UNREADABLE_SHARE:
        ingest_error = MALFORMED
        reason = f"unreadable body: {bad} of {visible} characters could not be decoded"

    held = {k: _as_str(raw.get(k)) for k in HELD_FIELDS if raw.get(k) not in (None, "")}

    return TicketRecord(
        ticket_id=ticket_id,
        channel=channel,
        subject=subject,
        body=body,
        received_at=received_at,
        text=text,
        ingest_error=ingest_error,
        ingest_reason=reason,
        flags=dict(sorted(flags.items())),
        metadata={
            "position": position,
            "ingest_version": INGEST_VERSION,
            "channel_original": _as_str(channel_raw),
            "char_count": len(text),
            "word_count": len(text.split()),
            "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        },
        held_for_validate=held,
    )


class InputFileError(Exception):
    """The whole input file is unreadable (missing, not JSON, not a list). Nothing can be processed."""


def read_text_any(p: Path) -> tuple[str, str]:
    """Decode a ticket file without failing the run on an odd encoding. Returns (text, how).
    UTF-8 (with or without BOM) and UTF-16 with a BOM decode as is. Anything else decodes as UTF-8 with
    bad bytes replaced by U+FFFD; normalise() then flags those records, or escalates them if unreadable."""
    try:
        raw = p.read_bytes()
    except OSError as e:
        raise InputFileError(f"cannot read {p}: {e}") from e
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return raw.decode("utf-16"), "utf-16"
    try:
        return raw.decode("utf-8-sig"), "utf-8"
    except UnicodeDecodeError:
        return raw.decode("utf-8", errors="replace"), "utf-8 with replacements"


def iter_raw(path: str | Path) -> Iterator[tuple[int, Any]]:
    """Yield (position, raw) from a .json array or a .jsonl file.

    A bad line in .jsonl yields a malformed marker so processing continues (FR-02).
    """
    p = Path(path)
    content, _ = read_text_any(p)

    if p.suffix.lower() == ".jsonl":
        for i, line in enumerate(x for x in content.splitlines() if x.strip()):
            try:
                yield i, json.loads(line)
            except json.JSONDecodeError as e:
                yield i, _Unparseable(f"invalid JSON on line {i + 1}: {e.msg}")
        return

    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        raise InputFileError(f"{p} is not valid JSON: {e}") from e
    if isinstance(data, dict) and isinstance(data.get("tickets"), list):
        data = data["tickets"]
    if isinstance(data, dict):
        data = [data]  # a single ticket record
    if not isinstance(data, list):
        raise InputFileError(f"{p} must hold a list of ticket records")
    yield from enumerate(data)


@dataclass
class _Unparseable:
    reason: str


def load(path: str | Path) -> list[TicketRecord]:
    """Read every record in the file into TicketRecords. Bad records come back flagged, not dropped."""
    out = []
    seen: dict[str, int] = {}
    for pos, raw in iter_raw(path):
        r = malformed_record(pos, raw.reason) if isinstance(raw, _Unparseable) else normalise(raw, pos)
        # Duplicate ids would break "one final row per ticket". Keep both, make the id unique.
        n = seen.get(r.ticket_id, 0) + 1
        seen[r.ticket_id] = n
        if n > 1:
            r.metadata["ticket_id_original"] = r.ticket_id
            r.ticket_id = f"{r.ticket_id}#{n}"
            r.flags["duplicate_ticket_id"] = True
        out.append(r)
    return out


def one_per_channel(records: list[TicketRecord]) -> list[TicketRecord]:
    """First accepted record for each channel, in CHANNELS order."""
    picked = {}
    for r in records:
        if r.ok and r.channel in CHANNELS and r.channel not in picked:
            picked[r.channel] = r
    return [picked[c] for c in CHANNELS if c in picked]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Normalise tickets; print one per channel as proof (A2).")
    ap.add_argument("--input", required=True, help="ticket file (.json list or .jsonl)")
    ap.add_argument("--all", action="store_true", help="print every record, not one per channel")
    a = ap.parse_args(argv)

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # Windows console safety

    records = load(a.input)
    shown = records if a.all else one_per_channel(records)
    for r in shown:
        print(json.dumps(r.to_dict(), ensure_ascii=False, indent=2))
    missing = [c for c in CHANNELS if c not in {r.channel for r in shown}]
    print(f"\n{len(records)} records read, {sum(not r.ok for r in records)} malformed. "
          f"Shown: {len(shown)}. Channels missing from file: {missing or 'none'}.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
