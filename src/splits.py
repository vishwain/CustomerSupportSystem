"""Dev hold-out split (PRD NFR-03): 20% of distinct dev texts, stratified by intent, seed 42.

Split by distinct text, not by ticket: 254 dev tickets share a text with another ticket (S5),
so a ticket-level split would leak the same text into both sides. Classify (5.5) and the
retrieval cutoff (5.2) both use this one function, so the hold-out is the same everywhere.
"""

from __future__ import annotations

import random
from collections import defaultdict
from typing import Any

HOLDOUT_SHARE = 0.20
SEED = 42


def text_key(ticket: dict[str, Any]) -> str:
    """Tickets with the same subject + body (case and spacing ignored) are one text."""
    return " ".join(f"{ticket.get('subject') or ''} {ticket.get('body') or ''}".lower().split())


def dev_holdout_split(tickets: list[dict[str, Any]], share: float = HOLDOUT_SHARE,
                      seed: int = SEED) -> tuple[list[str], list[str]]:
    """Return (train_ticket_ids, holdout_ticket_ids). Deterministic for the same input."""
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for t in tickets:
        groups[text_key(t)].append(t)

    by_intent: dict[str, list[str]] = defaultdict(list)
    for key, members in groups.items():
        intent = members[0].get("labels", {}).get("intent", "unknown")
        by_intent[intent].append(key)

    rng = random.Random(seed)
    holdout_keys: set[str] = set()
    for intent in sorted(by_intent):
        keys = sorted(by_intent[intent])
        rng.shuffle(keys)
        n = max(1, round(len(keys) * share)) if len(keys) > 1 else 0
        holdout_keys.update(keys[:n])

    train, holdout = [], []
    for t in tickets:
        (holdout if text_key(t) in holdout_keys else train).append(t["ticket_id"])
    return train, holdout
