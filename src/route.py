"""Route (A5; PRD FR-11, FR-12, FR-17 part 2, FR-31, 10.3 step 4).

Deterministic: the same ticket text, classification, retrieval result and config files always give the
same decision. No model call, no randomness, no clock.

Order (first match wins):
  Hard rules, before any threshold (FR-12). Each sets rule_fired and escalates with no model call.
    1. kill_switch            config/runtime.json automation_paused = true, re-read every ticket (FR-31).
                              An unreadable or missing file counts as paused (fail closed).
    2. instruction_integrity  text matches the instruction-integrity list (FR-17).
    3. prior_contact_claim    text says an earlier support contact told or promised something. History is
                              not read (FR-03), so it cannot be checked; a person replies.
    4. classification_failed  intent 'unknown' (FR-05).
    5. must_escalate_intent   predicted intent is security_incident, compliance_request, data_residency,
                              feature_request or unclear_request.
    6. billing_dispute        the text matches the dispute list (OQ-06, including waiver and compensation
                              requests), whatever the predicted intent (5.10: a dispute misread as an
                              outage or quota ticket must still reach a person).
    7. risk_terms:<group>     the text names a security, legal or residency matter (RISK_TERMS) whatever the
                              predicted intent. Catches a risky ticket the classifier files under a safe intent.
    8. must_escalate_alternative  the must-escalate classes together hold at least must_escalate_alt_floor
                              of the calibrated probability (top class excluded). Floor set from data by
                              docs/must_escalate_check.py.
  Gates (FR-11):
    9. no passage passed the retrieval cutoff        -> escalate, no model call.
   10. intent confidence below the threshold         -> draft_for_review (Generate drafts, a person sends).
   11. otherwise                                     -> auto_respond.

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
# Text that names a security, legal or residency matter. Checked on every ticket (5.10). On the 580 dev
# and validation tickets these match only security_incident, compliance_request and data_residency tickets.
RISK_TERMS = {
    "security": (r"\bbreach(es|ed)?\b", r"\bcompromis", r"\bhack(ed|er|ers)?\b", r"\bunauthori[sz]ed\b",
                 r"\bphishing\b", r"\bransomware\b", r"\bmalicious\b",
                 r"\b(key|secret|token|password|credential)s?\b[^.\n]{0,40}\bleak",
                 r"\bleak(ed|s)?\b[^.\n]{0,40}\b(key|secret|token|password|credential)s?\b",
                 r"\bnone of us recogni[sz]e", r"\bnobody (on the team )?(claims|recogni[sz]es)"),
    "legal": (r"\bgdpr\b", r"\blawyers?\b", r"\blegal\b", r"\bsubpoena", r"\bcourt\b", r"\bregulators?\b",
              r"\bhipaa\b", r"\bsoc ?2\b", r"\bauditors?\b", r"\bdata processing agreement\b"),
    "residency": (r"\bresidency\b", r"\bphysically stored\b",
                  r"\b(stay|stays|stored|kept|held|hosted) (only )?in the (eu|uk|us|european union)\b"),
}
DISPUTE_PATTERNS = (r"\brefund", r"\bdispute", r"\bchargeback", r"\bcredit\b", r"\bcredits\b",
                    r"\bovercharg", r"\breimburs", r"\bwaiv", r"\bwrite[- ]?off", r"\bcompensat",
                    r"\bmoney\s+back", r"\bgoodwill")
# The ticket says an earlier support contact told or promised something. History is not read (FR-03),
# so the system cannot check what was said, and an automatic reply could contradict a person.
PRIOR_CONTACT_PATTERNS = (
    r"\b(your|the|an?|one\s+of\s+your)\s+(support\s+)?(agent|engineer|rep|representative|colleague|team|support)"
    r"\s+(told|said|promised|confirmed|assured|agreed)\b",
    r"\byou\s+(promised|told\s+(me|us)|agreed|assured)\b",
    r"\bas\s+(promised|agreed)\b",
    r"\b(previous|earlier|existing|open)\s+(ticket|case|support\s+request)\b",
    r"\b(ticket|case)\s+(number|no\.?|#)\s*\w",
    r"\blast\s+time\s+(i|we)\s+(contacted|wrote|spoke|asked)\b",
)
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
    dispute_patterns: tuple[str, ...] = DISPUTE_PATTERNS
    integrity_patterns: tuple[str, ...] = INTEGRITY_PATTERNS
    prior_contact_patterns: tuple[str, ...] = PRIOR_CONTACT_PATTERNS
    risk_terms: dict[str, tuple[str, ...]] = field(default_factory=lambda: dict(RISK_TERMS))
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
        self._prior = [re.compile(p, f) for p in self.cfg.prior_contact_patterns]
        self._risk = {g: [re.compile(p, f) for p in ps] for g, ps in self.cfg.risk_terms.items()}

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
        for rx in self._prior:
            m = rx.search(text or "")
            if m:
                return RouteDecision(
                    "escalate", f"ticket refers to an earlier support contact ({m.group(0)[:40]!r}); history is "
                    "not read (FR-03), so what was said cannot be checked", "prior_contact_claim",
                    self.cfg.threshold)
        return None

    @staticmethod
    def _match(rxs, text: str) -> str | None:
        for rx in rxs:
            m = rx.search(text or "")
            if m:
                return m.group(0)[:40]
        return None

    def must_escalate_mass(self, cls) -> tuple[float, str]:
        """Calibrated probability held by the must-escalate classes other than the top one, and the largest
        of them. Uses the full distribution when the local model gives one, else the top-3 alternatives."""
        must = self.cfg.must_escalate_intents
        dist = getattr(cls, "intent_distribution", None) or {a["label"]: a["confidence"]
                                                             for a in cls.intent_alternatives}
        risky = {k: float(v) for k, v in dist.items() if k in must and k != cls.intent}
        if not risky:
            return 0.0, "none"
        top = max(risky, key=risky.get)
        return round(sum(risky.values()), 4), top

    def layers(self, text: str, cls) -> dict[str, Any]:
        """Which 5.10 checks would catch this ticket, each on its own (evidence for the defence in depth)."""
        mass, top = self.must_escalate_mass(cls)
        return {
            "intent_rule": cls.intent in self.cfg.must_escalate_intents,
            "dispute": self._match(self._dispute, text) is not None,
            "risk_terms": next((g for g, rxs in self._risk.items() if self._match(rxs, text)), None),
            "alternative_mass": mass, "alternative_top": top,
            "alternative_guard": mass >= self.cfg.must_escalate_alt_floor,
        }

    def decide(self, text: str, cls, retrieval) -> RouteDecision:
        """cls: src.classify.Classification. retrieval: src.retrieve.RetrievalResult or None (not run).
        A rule that fires first still wins, but when retrieval also found nothing the reason says so,
        so the log shows every cause of the escalation (5.11)."""
        d = self._decide(text, cls, retrieval)
        if (d.action == "escalate" and d.rule_fired != "no_retrieval_hit" and retrieval is not None
                and not retrieval.passages):
            d.reason += " Also: no supporting passage passed the relevance cutoff."
            d.gates = {**d.gates, "passages": 0}
        return d

    def _decide(self, text: str, cls, retrieval) -> RouteDecision:
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
        m = self._match(self._dispute, text)
        if m:
            return RouteDecision("escalate", f"dispute wording ({m!r}) in a {cls.intent} ticket; "
                                 "disputes always escalate (FR-12, OQ-06)", "billing_dispute", **d)
        for group, rxs in self._risk.items():
            m = self._match(rxs, text)
            if m:
                return RouteDecision("escalate", f"{group} wording ({m!r}) in a {cls.intent} ticket; "
                                     "a person checks it whatever the predicted intent (FR-12)",
                                     f"risk_terms:{group}", **d)
        mass, top_risky = self.must_escalate_mass(cls)
        if mass >= cfg.must_escalate_alt_floor:
            return RouteDecision("escalate", f"must-escalate classes hold {mass:.3f} of the probability "
                                 f"(largest {top_risky}) >= floor {cfg.must_escalate_alt_floor:g}; too likely "
                                 "to be a risky ticket to answer automatically",
                                 f"must_escalate_alternative:{top_risky}", **d)

        n_pass = len(retrieval.passages) if retrieval is not None else 0
        gates = {"passages": n_pass, "confidence_ok": conf >= cfg.threshold, "must_escalate_mass": mass}
        if n_pass == 0:
            why = "retrieval not run" if retrieval is None else retrieval.reason
            return RouteDecision("escalate", f"no supporting passage: nothing passed the relevance cutoff ({why}); "
                                 "escalated without a draft or a model call", "no_retrieval_hit", gates=gates, **d)
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
