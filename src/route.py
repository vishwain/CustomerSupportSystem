"""Route (A5; PRD FR-11, FR-12, FR-17 part 2, FR-31, 10.3 step 4).

Deterministic: the same ticket text, classification, retrieval result and config files always give the
same decision. No model call, no randomness, no clock.

Order (first match wins):
  Hard rules, before any threshold (FR-12). Each sets rule_fired and escalates with no model call.
    1. kill_switch            config/runtime.json automation_paused = true, re-read every ticket (FR-31).
                              An unreadable or missing file counts as paused (fail closed).
    2. instruction_integrity  text matches the instruction-integrity list (FR-17).
    3. classification_failed  intent 'unknown' (FR-05).
    4. must_escalate_intent   predicted intent is security_incident, compliance_request, data_residency,
                              feature_request or unclear_request.
    5. billing_dispute        billing_query or quota_or_overage and the text matches the dispute list (OQ-06).
    6. must_escalate_alternative  one of those five intents is an alternative at or above
                              must_escalate_alt_floor. Safety net for a misclassified risky ticket.
  Gates (FR-11):
    7. no passage passed the retrieval cutoff        -> escalate, no model call.
    8. intent confidence below the threshold         -> draft_for_review (Generate drafts, a person sends).
    9. otherwise                                     -> auto_respond.

The rules and lists are in src/route.py defaults, overridable in config/routing.json. The threshold
is set from data by docs/routing_threshold.py and stored with its date. With no routing config the
threshold is above 1.0, so nothing is answered automatically (fail safe).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROUTING_CONFIG = Path("config/routing.json")
RUNTIME_CONFIG = Path("config/runtime.json")

MUST_ESCALATE_INTENTS = ("security_incident", "compliance_request", "data_residency",
                         "feature_request", "unclear_request")
DISPUTE_INTENTS = ("billing_query", "quota_or_overage")
DISPUTE_PATTERNS = (r"\brefund", r"\bdispute", r"\bchargeback", r"\bcredit\b", r"\bcredits\b",
                    r"\bovercharg", r"\breimburs")
INTEGRITY_PATTERNS = (
    r"\bignore\b[^.\n]{0,40}\b(instruction|instructions|rules|prompt)\b",
    r"\bdisregard\b[^.\n]{0,40}\b(instruction|instructions|rules|prompt|above|previous)\b",
    r"\bforget\b[^.\n]{0,40}\b(instruction|instructions|rules)\b",
    r"\bsystem\s+prompt\b",
    r"\byou\s+are\s+now\b",
    r"\b(reveal|print|show|repeat)\b[^.\n]{0,30}\b(your|the)\s+(prompt|instructions)\b",
    r"^\s*(system|assistant)\s*:",
    r"<<<|>>>",
)
NEVER = 1.01  # threshold that no confidence can reach


@dataclass
class RoutingConfig:
    threshold: float = NEVER
    must_escalate_intents: tuple[str, ...] = MUST_ESCALATE_INTENTS
    dispute_intents: tuple[str, ...] = DISPUTE_INTENTS
    dispute_patterns: tuple[str, ...] = DISPUTE_PATTERNS
    integrity_patterns: tuple[str, ...] = INTEGRITY_PATTERNS
    must_escalate_alt_floor: float = 0.15
    set_on: str = ""
    rule: str = ""
    source: str = "defaults (no config/routing.json: nothing auto-answered)"

    @classmethod
    def load(cls, path: str | Path = ROUTING_CONFIG) -> "RoutingConfig":
        p = Path(path)
        if not p.exists():
            return cls()
        d = json.loads(p.read_text(encoding="utf-8"))
        kw = {k: (tuple(v) if isinstance(v, list) else v) for k, v in d.items()
              if k in cls.__dataclass_fields__}
        cfg = cls(**kw, source=str(p).replace("\\", "/"))
        if not 0.0 <= cfg.threshold <= NEVER:
            raise ValueError(f"threshold {cfg.threshold} out of range in {p}")
        return cfg


@dataclass
class RouteDecision:
    action: str  # auto_respond | draft_for_review | escalate
    reason: str
    rule_fired: str = "none"
    threshold: float = NEVER
    confidence: float = 0.0
    gates: dict[str, Any] = field(default_factory=dict)

    @property
    def escalates(self) -> bool:
        return self.action != "auto_respond"

    @property
    def model_call_allowed(self) -> bool:
        """Rule fired or no passage: escalate without any model call (10.3 step 4)."""
        return self.action != "escalate"


def automation_paused(path: str | Path = RUNTIME_CONFIG) -> tuple[bool, str]:
    """Re-read on every call (FR-31). Missing or unreadable file = paused (fail closed)."""
    try:
        d = json.loads(Path(path).read_text(encoding="utf-8"))
        return bool(d["automation_paused"]), ""
    except (OSError, ValueError, KeyError, TypeError) as e:
        return True, f"runtime config unreadable ({type(e).__name__}); treated as paused"


class Router:
    def __init__(self, cfg: RoutingConfig | None = None, runtime_path: str | Path = RUNTIME_CONFIG):
        self.cfg = cfg or RoutingConfig.load()
        self.runtime_path = Path(runtime_path)
        f = re.IGNORECASE | re.MULTILINE
        self._integrity = [re.compile(p, f) for p in self.cfg.integrity_patterns]
        self._dispute = [re.compile(p, f) for p in self.cfg.dispute_patterns]

    # Rules that need only the text. Run BEFORE classification so no model call happens when they fire.
    def pre_rules(self, text: str) -> RouteDecision | None:
        paused, why = automation_paused(self.runtime_path)
        if paused:
            return RouteDecision("escalate", "automation paused" + (f": {why}" if why else ""), "kill_switch",
                                 self.cfg.threshold)
        for rx in self._integrity:
            m = rx.search(text or "")
            if m:
                return RouteDecision(
                    "escalate", f"instruction-integrity list matched ({m.group(0)[:40]!r}); "
                    "escalated before any model call", "instruction_integrity", self.cfg.threshold)
        return None

    def decide(self, text: str, cls, retrieval) -> RouteDecision:
        """cls: src.classify.Classification. retrieval: src.retrieve.RetrievalResult or None (not run)."""
        cfg = self.cfg
        pre = self.pre_rules(text)
        if pre:
            pre.confidence = cls.intent_confidence if cls else 0.0
            return pre
        conf = float(cls.intent_confidence)
        d = dict(threshold=cfg.threshold, confidence=conf)

        if cls.failed:
            return RouteDecision("escalate", f"classification failed ({cls.error}); escalated",
                                 "classification_failed", **d)
        if cls.intent in cfg.must_escalate_intents:
            return RouteDecision("escalate", f"intent {cls.intent} must always escalate (FR-12)",
                                 f"must_escalate_intent:{cls.intent}", **d)
        if cls.intent in cfg.dispute_intents:
            for rx in self._dispute:
                m = rx.search(text or "")
                if m:
                    return RouteDecision("escalate", f"{cls.intent} with dispute wording ({m.group(0)!r}); "
                                         "disputes always escalate (FR-12, OQ-06)", "billing_dispute", **d)
        risky = [a for a in cls.intent_alternatives
                 if a["label"] in cfg.must_escalate_intents and a["confidence"] >= cfg.must_escalate_alt_floor]
        if risky:
            a = risky[0]
            return RouteDecision("escalate", f"alternative {a['label']} at {a['confidence']:.2f} >= "
                                 f"{cfg.must_escalate_alt_floor:.2f}; a must-escalate class is too likely to "
                                 "answer automatically", f"must_escalate_alternative:{a['label']}", **d)

        n_pass = len(retrieval.passages) if retrieval is not None else 0
        gates = {"passages": n_pass, "confidence_ok": conf >= cfg.threshold}
        if n_pass == 0:
            why = "retrieval not run" if retrieval is None else retrieval.reason
            return RouteDecision("escalate", f"no passage passed the relevance cutoff ({why}); "
                                 "escalated without a model call", "no_retrieval_hit", gates=gates, **d)
        if conf < cfg.threshold:
            return RouteDecision("draft_for_review", f"intent {cls.intent} confidence {conf:.2f} below threshold "
                                 f"{cfg.threshold:.2f}; {n_pass} passage(s) found, so a draft goes to an agent",
                                 "below_threshold", gates=gates, **d)
        return RouteDecision("auto_respond", f"no rule fired; intent {cls.intent} confidence {conf:.2f} >= "
                             f"threshold {cfg.threshold:.2f}; {n_pass} passage(s) passed the cutoff",
                             gates=gates, **d)


def log_routing(log, ticket_id: str, text: str, decision: RouteDecision, cls, cfg: RoutingConfig) -> None:
    log.write(
        ticket_id=ticket_id, stage="routing", action_taken=decision.action, reason=decision.reason,
        input_text=text, model_name="rules:route", model_version=f"threshold {cfg.threshold} ({cfg.set_on or 'unset'})",
        prediction={"intent": getattr(cls, "intent", "unknown"), "gates": decision.gates,
                    "config": cfg.source},
        confidence=decision.confidence, threshold_applied=decision.threshold, rule_fired=decision.rule_fired,
    )
