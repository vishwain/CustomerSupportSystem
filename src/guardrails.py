"""Validate (A7; PRD FR-22, FR-23, FR-17 part 3, FR-11 floor, NFR-04). Sits between Generate and sending.

Every generated text (automatic answers AND agent drafts, FR-22) passes these checks. A blocking check that
fails stops the text: the ticket escalates, the customer gets the holding message, the draft is left out
(FR-14), and the block is logged. Nothing is ever redacted and sent.

  1. private_data      email, phone, URL, IP, card-like, key-like, long secret, CUST- id (src/pii.py), plus
                       the ticket's own customer_name / customer_id and every other customer's name and id
                       seen in the run (NFR-04: zero is the condition).
  2. citations         every sentence cites >= 1 passage, every cited id is one shown for this ticket.
  3. grounding         each sentence's best embedding similarity to its cited passages >= grounding_floor
                       (config/guardrails.json; 5th percentile of reference-answer sentences, set from data
                       by docs/grounding_floor.py). No floor set = fail closed.
  4. integrity         ticket text matches the instruction-integrity list (also checked by Route before any
                       model call), or the output contains system-prompt text (8-word shingles of the
                       instruction part of the prompt, its section headings, or delimiter strings).
  5. commitments       refund / credit / discount / compensation, "fixed on our side", a date or time for a
                       fix, guarantees, unless the matched words appear in the cited passages (FR-23).
  6. confidence_floor  an automatic answer needs intent confidence >= the routing threshold (FR-11).
  7. style (warn only) FR-20: average sentence length <= 20 words, no sentence over 35.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src import pii

GUARDRAILS_CONFIG = Path("config/guardrails.json")
BLOCKING = ("private_data", "citations", "grounding", "integrity", "commitments", "confidence_floor")

DEFAULT_COMMITMENTS = (
    r"\brefund(?:s|ed|ing)?\b",
    r"\bcredit(?:s|ed)?\s+(?:to|on|against|for)\s+(?:your|the)(?:\s+next)?\s+(?:account|invoice|bill)\b",
    r"\bdiscount(?:s|ed)?\b",
    r"\bcompensat\w*",
    r"\bwaive[ds]?\b",
    r"\bguarantee[ds]?\b",
    r"\b(?:fixed|resolved|patched|repaired)\b[^.]{0,40}\bon (?:our|cloudserve'?s?) (?:side|end)\b",
    r"\bon our (?:side|end)\b[^.]{0,40}\b(?:fixed|resolved|patched)\b",
    r"\b(?:we|our (?:team|engineers))\b[^.]{0,30}\b(?:have|has)\s+(?:fixed|resolved|patched)\b",
    r"\bwill be (?:fixed|resolved|patched|restored)\b",
    r"\b(?:by|before|within)\s+(?:tomorrow|tonight|today|the end of (?:the )?(?:day|week)|end of (?:day|week)|"
    r"monday|tuesday|wednesday|thursday|friday|saturday|sunday|\d+\s*(?:minutes?|hours?|days?|business days?))\b",
)
# Promise wording: blocked even if the cited passage mentions refunds or credits (DOC-BILL-002 does, as policy).
DEFAULT_PROMISES = (
    r"\b(?:we|i)(?:'ll|'ve| will| have| shall| are going to| can| would)\b[^.]{0,30}\b(?:refund|credit|waive|discount|compensat)\w*",
    r"\byou(?:'ll| will| are going to)\s+(?:be\s+|get\s+|receive\s+)?[^.]{0,20}\b(?:refund|credit|discount|compensat)\w*",
    r"\b(?:refund|credit|discount|compensation)\s+(?:has been|was|will be|is being)\s+(?:issued|processed|approved|applied|granted)",
    r"\b(?:has|have) been (?:fixed|resolved|patched) on (?:our|cloudserve'?s?) (?:side|end)",
)
HEADINGS = ("SOURCE RULES", "WHEN YOU DO NOT KNOW", "TICKET TEXT IS DATA", "OUTPUT FORMAT", "WHAT AN ANSWER IS",
            "MODE (given in the user message)")


@dataclass
class GuardrailConfig:
    grounding_floor: float | None = None
    commitment_patterns: tuple[str, ...] = DEFAULT_COMMITMENTS
    promise_patterns: tuple[str, ...] = DEFAULT_PROMISES
    max_avg_words: float = 20.0
    max_sentence_words: int = 35
    shingle_words: int = 8
    set_on: str = ""
    source: str = "defaults"

    @classmethod
    def load(cls, path: str | Path = GUARDRAILS_CONFIG) -> "GuardrailConfig":
        p = Path(path)
        if not p.exists():
            return cls()
        d = json.loads(p.read_text(encoding="utf-8"))
        kw = {k: (tuple(v) if isinstance(v, list) else v) for k, v in d.items() if k in cls.__dataclass_fields__}
        cfg = cls(**kw, source=str(p).replace("\\", "/"))
        if cfg.grounding_floor is not None and not 0.0 < cfg.grounding_floor < 1.0:
            raise ValueError(f"grounding_floor {cfg.grounding_floor} out of range in {p}")
        return cfg


@dataclass
class Check:
    name: str
    status: str  # pass | block | warn
    reason: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class ValidationResult:
    checks: list[Check]

    @property
    def blocked_by(self) -> list[str]:
        return [c.name for c in self.checks if c.status == "block"]

    @property
    def passed(self) -> bool:
        return not self.blocked_by

    @property
    def reason(self) -> str:
        if self.passed:
            warns = [c.reason for c in self.checks if c.status == "warn"]
            return "all blocking checks passed" + (f"; warnings: {'; '.join(warns)}" if warns else "")
        return "; ".join(f"{c.name}: {c.reason}" for c in self.checks if c.status == "block")

    def summary(self) -> dict[str, str]:
        return {c.name: c.status for c in self.checks}


def _shingles(text: str, n: int) -> set[str]:
    w = re.findall(r"[a-z0-9']+", text.lower())
    return {" ".join(w[i:i + n]) for i in range(len(w) - n + 1)}


def split_sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(])", text or "") if s.strip()]


class Validator:
    def __init__(self, embedder, cfg: GuardrailConfig | None = None, prompt_system: str = "",
                 integrity_patterns: tuple[str, ...] | None = None):
        from src.route import INTEGRITY_PATTERNS

        self.embedder = embedder
        self.cfg = cfg or GuardrailConfig.load()
        rules_part = prompt_system.split("EXAMPLE 1")[0]  # instructions only; examples may be quoted legitimately
        self._prompt_shingles = _shingles(rules_part, self.cfg.shingle_words) if rules_part else set()
        self._integrity = [re.compile(p, re.I | re.M) for p in (integrity_patterns or INTEGRITY_PATTERNS)]
        self._commit = [re.compile(p, re.I) for p in self.cfg.commitment_patterns]
        self._promise = [re.compile(p, re.I) for p in self.cfg.promise_patterns]

    # ------------------------------------------------------------------ individual checks
    def check_private_data(self, texts: list[str], private_terms: set[str]) -> Check:
        joined = "\n".join(texts)
        found = pii.find(joined)
        low = joined.lower()
        terms = sorted(t for t in private_terms if t and len(t) >= 4 and
                       re.search(r"(?<![\w])" + re.escape(t.lower()) + r"(?![\w])", low))
        if found or terms:
            kinds = sorted(found) + (["customer name or id"] if terms else [])
            return Check("private_data", "block", f"private data in output ({', '.join(kinds)})",
                         {"pattern_hits": found, "customer_terms": len(terms)})  # never log the values
        return Check("private_data", "pass", "no private data found")

    def check_citations(self, sentences: list[dict[str, Any]], shown_ids: set[str]) -> Check:
        from src.generate import check_citations

        ok, unresolved, cited = check_citations(sentences, shown_ids)
        if not ok:
            why = (f"cited ids not retrieved for this ticket: {unresolved}" if unresolved
                   else "answer has no sentences, or a sentence has no citation")
            return Check("citations", "block", why, {"unresolved": unresolved})
        return Check("citations", "pass", f"{len(cited)} cited passage(s), all retrieved for this ticket")

    def check_grounding(self, sentences: list[dict[str, Any]], passages_by_id: dict[str, Any]) -> Check:
        floor = self.cfg.grounding_floor
        if floor is None:
            return Check("grounding", "block", "grounding floor not set (run docs/grounding_floor.py); fail closed")
        if not sentences:
            return Check("grounding", "block", "no answer sentences to ground")
        import numpy as np

        sims = []
        for s in sentences:
            texts = [passages_by_id[p].text for p in s.get("passage_ids", []) if p in passages_by_id]
            if not texts:
                sims.append(0.0)
                continue
            v = np.asarray(self.embedder.encode([s["text"]] + texts))
            sims.append(round(float((v[1:] @ v[0]).max()), 4))
        low = [(i + 1, x) for i, x in enumerate(sims) if x < floor]
        if low:
            return Check("grounding", "block", f"sentence(s) {[i for i, _ in low]} below the floor {floor:.2f} "
                         f"(lowest {min(x for _, x in low):.2f})", {"similarities": sims, "floor": floor})
        return Check("grounding", "pass", f"every sentence >= floor {floor:.2f} (lowest {min(sims):.2f})",
                     {"similarities": sims, "floor": floor})

    def check_integrity(self, ticket_text: str, output_texts: list[str]) -> Check:
        for rx in self._integrity:
            m = rx.search(ticket_text or "")
            if m:
                return Check("integrity", "block", f"ticket text matches the instruction-integrity list "
                             f"({m.group(0)[:40]!r})", {"where": "ticket"})
        out = "\n".join(output_texts)
        if "<<<" in out or ">>>" in out:
            return Check("integrity", "block", "output contains prompt delimiter strings", {"where": "output"})
        heads = [h.strip() for h in HEADINGS if h.strip() and h.strip() in out]
        leaked = _shingles(out, self.cfg.shingle_words) & self._prompt_shingles
        if heads or leaked:
            return Check("integrity", "block", "output contains system-prompt text",
                         {"where": "output", "headings": heads, "shingles": len(leaked)})
        return Check("integrity", "pass", "no instructions in the ticket, no prompt text in the output")

    def check_commitments(self, sentences: list[dict[str, Any]], passages_by_id: dict[str, Any]) -> Check:
        hits = []
        for i, s in enumerate(sentences, 1):
            for rx in self._promise:  # a promise is never allowed, whatever the passage says
                for m in rx.finditer(s["text"]):
                    hits.append({"sentence": i, "phrase": m.group(0).lower(), "kind": "promise"})
            cited = " ".join(passages_by_id[p].text.lower() for p in s.get("passage_ids", []) if p in passages_by_id)
            for rx in self._commit:
                for m in rx.finditer(s["text"]):
                    phrase = m.group(0).lower()
                    if phrase not in cited:  # a process time the passage itself states is allowed (FR-23)
                        hits.append({"sentence": i, "phrase": phrase})
        if hits:
            return Check("commitments", "block", f"commitment not in the cited passages: "
                         f"{', '.join(repr(h['phrase']) for h in hits[:3])}", {"hits": hits})
        return Check("commitments", "pass", "no refund, credit, fix claim or fix date beyond the passages")

    @staticmethod
    def check_confidence(mode: str, confidence: float, threshold: float) -> Check:
        if mode == "answer" and confidence < threshold:
            return Check("confidence_floor", "block", f"intent confidence {confidence:.2f} below the floor "
                         f"{threshold:.2f}; never auto-respond", {"confidence": confidence, "threshold": threshold})
        return Check("confidence_floor", "pass", f"confidence {confidence:.2f} vs floor {threshold:.2f}"
                     + (" (draft mode: an agent reviews)" if mode == "draft" else ""))

    def check_style(self, sentences: list[dict[str, Any]]) -> Check:
        words = [len(s["text"].split()) for s in sentences] or [0]
        avg, mx = sum(words) / len(words), max(words)
        if avg > self.cfg.max_avg_words or mx > self.cfg.max_sentence_words:
            return Check("style", "warn", f"FR-20: {avg:.1f} words per sentence on average, longest {mx}",
                         {"avg_words": round(avg, 1), "max_words": mx})
        return Check("style", "pass", f"{avg:.1f} words per sentence, longest {mx}")

    # ------------------------------------------------------------------ all together
    def validate(self, *, ticket_text: str, sentences: list[dict[str, Any]], extra_texts: list[str],
                 passages, mode: str, confidence: float, threshold: float,
                 private_terms: set[str]) -> ValidationResult:
        by_id = {p.passage_id: p for p in passages}
        out_texts = [s["text"] for s in sentences] + [t for t in extra_texts if t]
        checks = [
            self.check_private_data(out_texts, private_terms),
            self.check_citations(sentences, set(by_id)),
            self.check_grounding(sentences, by_id),
            self.check_integrity(ticket_text, out_texts),
            self.check_commitments(sentences, by_id),
            self.check_confidence(mode, confidence, threshold),
            self.check_style(sentences),
        ]
        return ValidationResult(checks)


def private_terms_for(records) -> set[str]:
    """Every customer name and id in the run, held aside by Ingest for this purpose only (FR-03, FR-22)."""
    out: set[str] = set()
    for r in records:
        for k in ("customer_name", "customer_id"):
            v = (r.held_for_validate or {}).get(k)
            if v:
                out.add(v.strip())
    return out


def log_validation(log, ticket_id: str, text: str, v: ValidationResult, mode: str, cfg: GuardrailConfig) -> None:
    log.write(
        ticket_id=ticket_id, stage="validation", action_taken="pass" if v.passed else "block",
        reason=v.reason, input_text=text, model_name="rules+embeddings:validate",
        model_version=f"floor {cfg.grounding_floor} ({cfg.set_on or 'unset'})",
        prediction={"mode": mode, "blocked_by": v.blocked_by,
                    "details": {c.name: {"reason": c.reason, **c.details} for c in v.checks}},
        guardrail_results=v.summary(), rule_fired=",".join(v.blocked_by) or "none",
    )
