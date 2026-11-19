"""Classify (A3; PRD FR-04, FR-05, 10.3).

Default: a LOCAL classifier. all-MiniLM-L6-v2 sentence embeddings + logistic regression, one head for
intent (22 classes) and one for urgency (3). Trained on the dev TRAIN split only (src/splits.py), so the
dev hold-out stays clean for calibration (5.7) and the routing threshold (5.6). No provider call, so
routing and hard rules keep working in degraded mode (10.6).

Fallback: PR-02 (prompts/build/classify_v1.txt) through the provider, used ONLY when the local
classifier raises (model missing, embedding error). Low local confidence does not call the LLM:
FR-05 says low confidence is not a failure, Route handles it (FR-11), and a cascade would break
calibration and double provider calls.

LLM output handling (free-tier models do return malformed JSON):
  1. Deterministic repair: strip fences and chatter, take the first balanced {...}, fix smart quotes and
     trailing commas, normalise label case and spacing, read "85%" or "85" as 0.85, drop alternatives
     that repeat the chosen label, fill missing urgency alternatives with the remaining levels at 0.0,
     rescale when label + alternatives sum above 1.0. Every repair is listed in `repairs`.
  2. Schema check against src/schemas/classification.json (an invented label is never repaired).
  3. Still invalid: one retry of the same call (counts as a retry). Still invalid: FR-05 fallback.

FR-05 fallback: intent 'unknown', urgency 'unknown', confidence 0, no alternatives. Route escalates it.

Train or rebuild the local model:  python -m src.classify --train
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

INTENTS = (
    "account_access", "api_key_issue", "api_usage_question", "authentication_failure", "billing_query",
    "compliance_request", "configuration_help", "data_export", "data_residency", "database_issue",
    "deployment_failure", "feature_request", "integration_help", "onboarding", "performance_degradation",
    "quota_or_overage", "rate_limit", "rollback_request", "security_incident", "sso_configuration",
    "unclear_request", "webhook_issue",
)
URGENCIES = ("high", "medium", "low")
UNKNOWN = "unknown"
SCHEMA_PATH = Path("src/schemas/classification.json")
CALIBRATION_CONFIG = Path("config/calibration.json")
LOCAL_NAME = "minilm-logreg"
C_GRID = (0.25, 0.5, 1.0, 2.0, 4.0, 8.0, 16.0, 32.0, 64.0)


@dataclass
class Classification:
    intent: str
    intent_confidence: float
    intent_alternatives: list[dict[str, Any]]  # [{"label", "confidence"}] x2
    urgency: str
    urgency_confidence: float
    urgency_alternatives: list[dict[str, Any]]
    source: str  # "local" | "llm" | "fallback"
    model_name: str
    model_version: str
    prompt_version: str = "n/a"
    error: str = "none"
    reason: str = ""
    repairs: list[str] = field(default_factory=list)
    requests: int = 0
    retries: int = 0
    rate_limit_wait_ms: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    degraded: bool = False
    latency_ms: int = 0

    @property
    def failed(self) -> bool:
        return self.intent == UNKNOWN

    def prediction(self) -> dict[str, Any]:
        return {"intent": self.intent, "urgency": self.urgency, "urgency_confidence": self.urgency_confidence,
                "urgency_alternatives": self.urgency_alternatives, "source": self.source,
                **({"repairs": self.repairs} if self.repairs else {})}


def fallback(reason: str, error: str = "classifier_error", **kw: Any) -> Classification:
    """FR-05: intent and urgency unknown, confidence 0, no alternatives."""
    return Classification(UNKNOWN, 0.0, [], UNKNOWN, 0.0, [], "fallback",
                          kw.pop("model_name", "none"), kw.pop("model_version", "n/a"),
                          error=error, reason=reason, **kw)


# ============================================================================ calibration (5.7)

def apply_temperature(proba, temperature: float):
    """Temperature scaling on probabilities: p_i^(1/T), renormalised. Same as softmax(logits / T).
    T > 1 softens (less confident), T < 1 sharpens. T = 1 changes nothing. Ranking never changes."""
    import numpy as np

    p = np.clip(np.asarray(proba, dtype=float), 1e-12, 1.0)
    if temperature == 1.0:
        return p / p.sum(axis=-1, keepdims=True)
    logp = np.log(p) / float(temperature)
    logp -= logp.max(axis=-1, keepdims=True)
    q = np.exp(logp)
    return q / q.sum(axis=-1, keepdims=True)


def load_temperature(path: str | Path = CALIBRATION_CONFIG) -> float:
    """Intent temperature from config/calibration.json (written by docs/calibration.py). Missing = 1.0."""
    p = Path(path)
    if not p.exists():
        return 1.0
    d = json.loads(p.read_text(encoding="utf-8"))
    t = float(d.get("intent_temperature", 1.0)) if d.get("adopted", False) else 1.0
    if not 0.05 <= t <= 20:
        raise ValueError(f"intent_temperature {t} out of range in {p}")
    return t


# ============================================================================ LLM output parsing

def _first_json_object(s: str) -> str | None:
    """First balanced {...}, aware of strings and escapes."""
    start = s.find("{")
    while start != -1:
        depth, in_str, esc = 0, False, False
        for i in range(start, len(s)):
            c = s[i]
            if in_str:
                if esc:
                    esc = False
                elif c == "\\":
                    esc = True
                elif c == '"':
                    in_str = False
            elif c == '"':
                in_str = True
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    return s[start:i + 1]
        start = s.find("{", start + 1)
    return None


def _loads_lenient(raw: str, repairs: list[str]) -> Any:
    s = (raw or "").strip()
    if not s:
        raise ValueError("empty output")
    if "```" in s:
        s = re.sub(r"```(?:json)?", "", s)
        repairs.append("removed markdown fences")
    obj = _first_json_object(s)
    if obj is None:
        raise ValueError("no JSON object found")
    if obj != s.strip():
        repairs.append("removed text around the JSON object")
    try:
        return json.loads(obj)
    except json.JSONDecodeError:
        pass
    fixed = obj.translate({0x201C: '"', 0x201D: '"', 0x2018: "'", 0x2019: "'"})
    fixed = re.sub(r",\s*([}\]])", r"\1", fixed)
    if '"' not in fixed:
        fixed = fixed.replace("'", '"')
    try:
        out = json.loads(fixed)
    except json.JSONDecodeError as e:
        raise ValueError(f"invalid JSON: {e.msg}") from e
    repairs.append("fixed quotes or trailing commas")
    return out


def _label(v: Any) -> str:
    return re.sub(r"[\s\-]+", "_", str(v or "").strip().lower())


def _conf(v: Any, what: str, repairs: list[str]) -> float:
    if isinstance(v, str):
        t = v.strip().rstrip("%")
        pct = v.strip().endswith("%")
        v = float(t)
        if pct:
            v /= 100
        repairs.append(f"{what}: confidence given as text")
    v = float(v)
    if 1.0 < v <= 100.0 and (v >= 5 or float(v).is_integer()):  # 85 -> 0.85; 1.7 stays invalid
        v /= 100
        repairs.append(f"{what}: confidence on a 0-100 scale")
    if not 0.0 <= v <= 1.0:
        raise ValueError(f"{what}: confidence {v} outside [0, 1]")
    return round(v, 4)


def _alts(raw: Any, chosen: str, allowed: tuple[str, ...], what: str, repairs: list[str],
          fill: bool) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for a in raw if isinstance(raw, list) else []:
        if isinstance(a, dict):
            lab = _label(a.get("label", a.get("value", a.get(what))))
            conf = a.get("confidence", a.get("score"))
        elif isinstance(a, (list, tuple)) and len(a) == 2:
            lab, conf = _label(a[0]), a[1]
        else:
            continue
        if lab == chosen or lab in {x["label"] for x in out}:
            repairs.append(f"{what}: dropped repeated alternative {lab}")
            continue
        if lab not in allowed or conf is None:
            raise ValueError(f"{what}: invalid alternative {lab!r}")
        out.append({"label": lab, "confidence": _conf(conf, what, repairs)})
    if len(out) > 2:
        out = sorted(out, key=lambda x: -x["confidence"])[:2]
        repairs.append(f"{what}: kept the two most likely alternatives")
    if len(out) < 2 and fill:
        for lab in allowed:
            if len(out) == 2:
                break
            if lab != chosen and lab not in {x["label"] for x in out}:
                out.append({"label": lab, "confidence": 0.0})
                repairs.append(f"{what}: missing alternative {lab} filled at 0.0")
    return out


def _rescale(conf: float, alts: list[dict[str, Any]], what: str, repairs: list[str]) -> tuple[float, list]:
    total = conf + sum(a["confidence"] for a in alts)
    if total > 1.0001:
        repairs.append(f"{what}: label + alternatives summed to {total:.2f}, rescaled to 1.0")
        conf = round(conf / total, 4)
        alts = [{**a, "confidence": round(a["confidence"] / total, 4)} for a in alts]
    return conf, sorted(alts, key=lambda a: -a["confidence"])


def parse_llm_output(raw: str) -> tuple[dict[str, Any], list[str]]:
    """Raw model text -> schema-valid dict and the list of repairs made. Raises ValueError if unusable."""
    repairs: list[str] = []
    d = _loads_lenient(raw, repairs)
    if not isinstance(d, dict):
        raise ValueError("output is not a JSON object")
    intent, urgency = _label(d.get("intent")), _label(d.get("urgency"))
    if intent not in INTENTS:
        raise ValueError(f"intent {d.get('intent')!r} is not one of the 22 labels")
    if urgency not in URGENCIES:
        raise ValueError(f"urgency {d.get('urgency')!r} is not high, medium or low")
    ic = _conf(d.get("intent_confidence"), "intent", repairs)
    uc = _conf(d.get("urgency_confidence"), "urgency", repairs)
    ia = _alts(d.get("intent_alternatives"), intent, INTENTS, "intent", repairs, fill=False)
    ua = _alts(d.get("urgency_alternatives"), urgency, URGENCIES, "urgency", repairs, fill=True)
    if len(ia) != 2:
        raise ValueError(f"intent: {len(ia)} usable alternatives, need 2")
    ic, ia = _rescale(ic, ia, "intent", repairs)
    uc, ua = _rescale(uc, ua, "urgency", repairs)
    out = {"intent": intent, "intent_confidence": ic, "intent_alternatives": ia,
           "urgency": urgency, "urgency_confidence": uc, "urgency_alternatives": ua}
    _validate_schema(out)
    return out, repairs


def _validate_schema(obj: dict[str, Any]) -> None:
    import jsonschema

    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    try:
        jsonschema.validate(obj, schema)
    except jsonschema.ValidationError as e:
        raise ValueError(f"schema: {e.message}") from e


# ============================================================================ classifiers

class TicketLike(Protocol):
    ticket_id: str
    channel: str
    subject: str
    body: str
    text: str


class LLMClassifier:
    """PR-02 through the provider (src/llm.py). Never raises: returns FR-05 fallback on any failure."""

    def __init__(self, client, prompt_path: str = "build/classify_v1.txt"):
        from src.prompts import load_prompt

        self.client = client
        self.prompt = load_prompt(prompt_path)
        self.name = f"llm:{client.model}"

    def classify(self, t: TicketLike) -> Classification:
        sys_msg, user_msg = self.prompt.render(channel=t.channel, subject=(t.subject or "").strip() or "(empty)",
                                               body=t.body or "")
        tot = {"requests": 0, "retries": 0, "rate_limit_wait_ms": 0, "tokens_in": 0, "tokens_out": 0,
               "latency_ms": 0}
        meta = {"model_name": self.name, "model_version": self.client.model,
                "prompt_version": self.prompt.version}
        last_problem = ""
        for attempt in range(2):  # first call + one retry on bad output
            r = self.client.complete(sys_msg, user_msg)
            for k in tot:
                tot[k] += getattr(r, k)
            if attempt == 1:
                tot["retries"] += 1
            if not r.ok:
                return fallback(f"classification failed: provider {r.error} ({r.detail})", r.error,
                                degraded=r.degraded, **meta, **tot)
            try:
                d, repairs = parse_llm_output(r.text)
            except ValueError as e:
                last_problem = str(e)
                continue
            return Classification(**d, source="llm", **meta, repairs=repairs,
                                  reason="PR-02 output parsed" + (" after repair" if repairs else ""), **tot)
        return fallback(f"classification failed: model output unusable after one retry ({last_problem})",
                        "bad_output", **meta, **tot)


class LocalClassifier:
    """MiniLM embeddings + logistic regression. load_or_train() before use."""

    def __init__(self, embedder, dev_path: str | Path = "data/development_tickets.json",
                 model_dir: str | Path = "storage/models", temperature: float | None = None,
                 calibration_path: str | Path = CALIBRATION_CONFIG):
        self.embedder = embedder
        self.temperature = load_temperature(calibration_path) if temperature is None else float(temperature)
        self.dev_path = Path(dev_path)
        self.model_dir = Path(model_dir)
        self.name = LOCAL_NAME
        self.version = ""
        self.meta: dict[str, Any] = {}
        self._intent = self._urgency = None

    # ---------------------------------------------------------------- training
    def _training_set(self):
        from src.ingest import normalise
        from src.splits import dev_holdout_split, text_key

        raw = json.loads(self.dev_path.read_text(encoding="utf-8"))
        train_ids, _ = dev_holdout_split(raw)
        keep = set(train_ids)
        rows = [(normalise(t, i), t) for i, t in enumerate(raw) if t["ticket_id"] in keep]
        rows = [(r, t) for r, t in rows if r.ok]
        texts = [r.text for r, _ in rows]
        return (texts, [t["labels"]["intent"] for _, t in rows], [t["labels"]["urgency"] for _, t in rows],
                [text_key(t) for _, t in rows], sorted(keep))

    def _fingerprint(self, train_ids: list[str]) -> str:
        import sklearn

        h = hashlib.sha256()
        h.update(self.dev_path.read_bytes())
        h.update(json.dumps([train_ids, self.embedder.name, C_GRID, sklearn.__version__]).encode())
        return h.hexdigest()[:12]

    @staticmethod
    def _pick_c(X, y, groups) -> tuple[float, dict[str, float]]:
        """C by grouped 5-fold log-loss on train (groups = distinct text, so repeats never leak)."""
        import numpy as np
        from sklearn.linear_model import LogisticRegression
        from sklearn.model_selection import GroupKFold

        classes = sorted(set(y))
        idx = {c: i for i, c in enumerate(classes)}
        y = np.asarray(y)
        scores = {}
        for C in C_GRID:
            losses = []
            for tr, te in GroupKFold(n_splits=5).split(X, y, groups):
                m = LogisticRegression(C=C, max_iter=3000).fit(X[tr], y[tr])
                p = np.full((len(te), len(classes)), 1e-6)
                for j, c in enumerate(m.classes_):
                    p[:, idx[c]] = np.maximum(m.predict_proba(X[te])[:, j], 1e-6)
                p /= p.sum(axis=1, keepdims=True)
                losses.append(-np.mean(np.log(p[np.arange(len(te)), [idx[v] for v in y[te]]])))
            scores[str(C)] = round(float(np.mean(losses)), 4)
        best = min(C_GRID, key=lambda c: scores[str(c)])
        return best, scores

    def train(self) -> None:
        import numpy as np
        from sklearn.linear_model import LogisticRegression

        texts, yi, yu, groups, train_ids = self._training_set()
        X = np.asarray(self.embedder.encode(texts))
        ci, si = self._pick_c(X, yi, groups)
        cu, su = self._pick_c(X, yu, groups)
        self._intent = LogisticRegression(C=ci, max_iter=3000).fit(X, yi)
        self._urgency = LogisticRegression(C=cu, max_iter=3000).fit(X, yu)
        fp = self._fingerprint(train_ids)
        self.version = f"{time.strftime('%Y-%m-%d')}-{fp}"
        self.meta = {"fingerprint": fp, "trained_on": "dev train split (NFR-03)", "n_train": len(texts),
                     "embedding_model": self.embedder.name, "C_intent": ci, "C_urgency": cu,
                     "cv_logloss_intent": si, "cv_logloss_urgency": su,
                     "intent_classes": list(self._intent.classes_), "version": self.version}

    def save(self) -> Path:
        import joblib

        self.model_dir.mkdir(parents=True, exist_ok=True)
        path = self.model_dir / f"local_classifier_{self.meta['fingerprint']}.joblib"
        joblib.dump({"intent": self._intent, "urgency": self._urgency, "meta": self.meta}, path)
        return path

    def load_or_train(self) -> "LocalClassifier":
        """Reuse a saved model with the same data, split, embedder and settings; else train and save."""
        import joblib

        *_, train_ids = self._training_set()
        path = self.model_dir / f"local_classifier_{self._fingerprint(train_ids)}.joblib"
        if path.exists():
            d = joblib.load(path)  # own file in storage/, written by save()
            self._intent, self._urgency, self.meta = d["intent"], d["urgency"], d["meta"]
            self.version = self.meta["version"]
        else:
            self.train()
            self.save()
        return self

    # ---------------------------------------------------------------- inference
    @staticmethod
    def _top3(model, row) -> tuple[str, float, list[dict[str, Any]]]:
        order = row.argsort()[::-1]
        labs = [str(model.classes_[i]) for i in order[:3]]
        confs = [round(float(row[i]), 4) for i in order[:3]]
        alts = [{"label": lab, "confidence": c} for lab, c in zip(labs[1:], confs[1:])]
        return labs[0], confs[0], alts

    def classify(self, t: TicketLike) -> Classification:
        if self._intent is None:
            raise RuntimeError("local classifier not loaded")
        t0 = time.perf_counter()
        X = self.embedder.encode([t.text])
        i_lab, i_conf, i_alts = self._top3(self._intent,
                                           apply_temperature(self._intent.predict_proba(X)[0], self.temperature))
        u_lab, u_conf, u_alts = self._top3(self._urgency, self._urgency.predict_proba(X)[0])
        if len(u_alts) < 2:  # a training set without one urgency level
            u_alts += [{"label": u, "confidence": 0.0} for u in URGENCIES
                       if u != u_lab and u not in {a["label"] for a in u_alts}][: 2 - len(u_alts)]
        version = self.version if self.temperature == 1.0 else f"{self.version}+T{self.temperature:g}"
        return Classification(i_lab, i_conf, i_alts, u_lab, u_conf, u_alts, "local", self.name, version,
                              reason=f"local model: {i_lab} at {i_conf:.2f}, {u_lab} urgency at {u_conf:.2f}",
                              latency_ms=int((time.perf_counter() - t0) * 1000))


class Classifier:
    """What the pipeline calls. Local first; PR-02 only if the local model raises; FR-05 if both fail."""

    def __init__(self, local: LocalClassifier | None, llm: LLMClassifier | None = None):
        self.local, self.llm = local, llm

    def classify(self, t: TicketLike, allow_llm: bool = True) -> Classification:
        problem = "local classifier not available"
        if self.local is not None:
            try:
                return self.local.classify(t)
            except Exception as e:  # noqa: BLE001 - any local failure goes to the fallback chain
                problem = f"local classifier error {type(e).__name__}: {str(e)[:120]}"
        if self.llm is not None and allow_llm:
            c = self.llm.classify(t)
            c.reason = f"{problem}; PR-02 fallback used. {c.reason}"
            return c
        why = "LLM fallback not allowed for this ticket (rule fired before any model call)" if self.llm else \
            "no LLM fallback configured"
        return fallback(f"classification failed: {problem}; {why}")


def log_classification(log, ticket_id: str, text: str, c: Classification) -> None:
    log.write(
        ticket_id=ticket_id, stage="classification",
        action_taken="fallback" if c.failed else "classify",
        reason=c.reason or ("classification failed" if c.failed else "classified"),
        input_text=text, model_name=c.model_name, model_version=c.model_version or "n/a",
        prompt_version=c.prompt_version, prediction=c.prediction(), confidence=c.intent_confidence,
        alternatives=[{"value": a["label"], "confidence": a["confidence"]} for a in c.intent_alternatives],
        error=c.error, degraded_mode=c.degraded, latency_ms=c.latency_ms, requests=c.requests,
        rate_limit_wait_ms=c.rate_limit_wait_ms, tokens_in=c.tokens_in, tokens_out=c.tokens_out,
    )


def build_classifier(embedder, use_llm_fallback: bool = True) -> Classifier:
    local = LocalClassifier(embedder).load_or_train()
    llm = None
    if use_llm_fallback:
        try:
            from src.llm import client_from_env
            llm = LLMClassifier(client_from_env())
        except Exception as e:  # noqa: BLE001 - no key or no model id: run without the fallback
            print(f"WARNING: PR-02 fallback disabled ({e})", file=sys.stderr)
    return Classifier(local, llm)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Train the local classifier on the dev train split.")
    ap.add_argument("--train", action="store_true", help="retrain even if a matching model exists")
    a = ap.parse_args(argv)
    from src.retrieve import SentenceTransformerEmbedder

    clf = LocalClassifier(SentenceTransformerEmbedder())
    if a.train:
        clf.train()
        print(f"saved {clf.save()}")
    else:
        clf.load_or_train()
    print(json.dumps({k: v for k, v in clf.meta.items() if k != "intent_classes"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

