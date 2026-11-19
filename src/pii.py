"""Private-data patterns, shared by the decision log (input_summary scrub) and, later, Validate (FR-22).

Patterns match docs/data_audit.py so the Stage 1 scan and the runtime scan agree.
"""

from __future__ import annotations

import re

PATTERNS: dict[str, str] = {
    "email": r"[\w.+-]+@[\w-]+\.[\w.]+",
    "url": r"https?://\S+",
    "ip_address": r"\b\d{1,3}(?:\.\d{1,3}){3}\b",
    "card_like": r"\b(?:\d[ -]?){13,16}\b",
    "phone": r"\+?\d[\d\s().-]{8,}\d",
    "key_like": r"\b(?:sk|pk|key|token|api)[-_][A-Za-z0-9]{8,}\b|AKIA[0-9A-Z]{16}",
    "long_secret": r"\b[A-Za-z0-9+/]{32,}\b",
    "customer_id": r"CUST-\d+",
}

_COMPILED = {name: re.compile(rx, re.IGNORECASE) for name, rx in PATTERNS.items()}


def find(text: str) -> dict[str, int]:
    """Count matches per pattern. Zero counts are left out."""
    hits = {name: len(rx.findall(text or "")) for name, rx in _COMPILED.items()}
    return {k: v for k, v in hits.items() if v}


def scrub(text: str) -> str:
    """Replace every match with [REDACTED:<type>]. Order matters: longer, more specific patterns first."""
    out = text or ""
    for name, rx in _COMPILED.items():
        out = rx.sub(f"[REDACTED:{name}]", out)
    return out


def redact(text: str, terms=()) -> str:
    """scrub() plus every given private term (customer names and ids in the run), case-insensitive.
    Used for model output written to the decision log before Validate has run (FR-22, NFR-04)."""
    out = scrub(text)
    for t in sorted({t for t in terms if t and len(t) >= 3}, key=len, reverse=True):
        out = re.sub(re.escape(t), "[REDACTED:customer]", out, flags=re.IGNORECASE)
    return out
