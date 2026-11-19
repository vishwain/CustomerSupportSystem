"""Model-provider client (PRD 10.6, FR-25, NFR-01, NFR-07). Used by the PR-02 classifier fallback now
and by Generate later. All provider failure handling lives here, so every caller gets the same behaviour.

| Failure        | Behaviour                                                                                   |
| -------------- | ------------------------------------------------------------------------------------------- |
| Timeout (10 s) | Two retries with exponential backoff and jitter, then error = timeout.                       |
| 429            | Wait as told by Retry-After, at most 60 s per call in total, then error = rate_limit.       |
|                | Requests are paced at least 3 s apart. Wait time is reported apart from latency (NFR-01).   |
| Outage         | Five failed attempts in a row open the circuit: degraded mode, error = provider_down, no    |
|                | request sent. One probe request is allowed every 60 s; a success closes the circuit.        |
| Cost           | Only ':free' model ids (NFR-07), unless ALLOW_PAID_MODEL=1.                                 |

LLM_CACHE=1 caches responses by prompt hash in storage/llm_cache (development only, 10.6).
The API key is read from the environment (.env via python-dotenv); it is never logged.
"""

from __future__ import annotations

import hashlib
import json
import os
import random
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

OPENROUTER_URL = "https://openrouter.ai/api/v1"


class ProviderError(Exception):
    def __init__(self, kind: str, message: str = "", retry_after: float | None = None):
        super().__init__(message or kind)
        self.kind = kind  # "timeout" | "rate_limit" | "provider_error"
        self.retry_after = retry_after


class LLMConfigError(Exception):
    pass


@dataclass
class LLMResult:
    text: str | None
    error: str = "none"  # none | timeout | rate_limit | provider_down
    requests: int = 0
    retries: int = 0
    rate_limit_wait_ms: int = 0
    latency_ms: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    degraded: bool = False
    cached: bool = False
    model: str = ""
    detail: str = ""

    @property
    def ok(self) -> bool:
        return self.error == "none" and self.text is not None


# transport(system, user, timeout_s) -> (text, tokens_in, tokens_out); raises ProviderError
Transport = Callable[[str, str, float], "tuple[str, int, int]"]


def openai_transport(model: str, api_key: str, base_url: str = OPENROUTER_URL,
                     reasoning_off: bool = True, max_tokens: int = 600) -> Transport:
    import openai

    client = openai.OpenAI(base_url=base_url, api_key=api_key, max_retries=0)

    def call(system: str, user: str, timeout_s: float):
        kw = {"extra_body": {"reasoning": {"enabled": False}}} if reasoning_off else {}
        try:
            r = client.chat.completions.create(
                model=model, temperature=0, max_tokens=max_tokens, timeout=timeout_s,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}], **kw)
        except openai.APITimeoutError as e:
            raise ProviderError("timeout", str(e)) from e
        except openai.RateLimitError as e:
            ra = None
            try:
                ra = float(e.response.headers.get("retry-after"))
            except (TypeError, ValueError, AttributeError):
                pass
            raise ProviderError("rate_limit", str(e), ra) from e
        except (openai.APIConnectionError, openai.APIStatusError) as e:
            raise ProviderError("provider_error", f"{type(e).__name__}: {e}") from e
        text = (r.choices[0].message.content or "") if r.choices else ""
        u = getattr(r, "usage", None)
        return text, int(getattr(u, "prompt_tokens", 0) or 0), int(getattr(u, "completion_tokens", 0) or 0)

    return call


@dataclass
class LLMClient:
    transport: Transport
    model: str
    timeout_s: float = 10.0
    retries: int = 2
    min_interval_s: float = 3.0
    max_wait_s: float = 60.0
    breaker_threshold: int = 5
    probe_interval_s: float = 60.0
    cache_dir: Path | None = None
    sleep: Callable[[float], None] = time.sleep
    clock: Callable[[], float] = time.monotonic
    _fails_in_row: int = field(default=0, init=False)
    _opened_at: float | None = field(default=None, init=False)
    _last_request: float | None = field(default=None, init=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False)

    @property
    def degraded(self) -> bool:
        return self._opened_at is not None

    def _cache_path(self, system: str, user: str) -> Path | None:
        if not self.cache_dir:
            return None
        h = hashlib.sha256(f"{self.model}\n{system}\n{user}".encode("utf-8")).hexdigest()
        return Path(self.cache_dir) / f"{h}.json"

    def _pace(self) -> int:
        """Keep requests at least min_interval_s apart. Returns ms waited (counted as rate-limit wait)."""
        if self._last_request is None:
            return 0
        gap = self.min_interval_s - (self.clock() - self._last_request)
        if gap > 0:
            self.sleep(gap)
            return int(gap * 1000)
        return 0

    def complete(self, system: str, user: str) -> LLMResult:
        with self._lock:
            return self._complete(system, user)

    def _complete(self, system: str, user: str) -> LLMResult:
        res = LLMResult(text=None, model=self.model)
        cp = self._cache_path(system, user)
        if cp and cp.exists():
            d = json.loads(cp.read_text(encoding="utf-8"))
            res.text, res.cached = d["text"], True
            return res

        if self._opened_at is not None:  # circuit open
            if self.clock() - self._opened_at < self.probe_interval_s:
                res.error, res.degraded, res.detail = "provider_down", True, "circuit open, no request sent"
                return res
            res.degraded = True  # this call is the probe

        t0 = self.clock()
        wait_ms = 0
        timeouts = 0
        attempt_budget = 1 + self.retries
        last_kind = "provider_error"
        while True:
            wait_ms += self._pace()
            self._last_request = self.clock()
            res.requests += 1
            try:
                text, tin, tout = self.transport(system, user, self.timeout_s)
            except ProviderError as e:
                last_kind = e.kind
                res.detail = str(e)[:200]
                if e.kind != "rate_limit":  # a 429 is not an outage
                    self._fails_in_row += 1
                    if self._fails_in_row >= self.breaker_threshold:
                        self._opened_at = self.clock()
                        res.degraded = True
                        res.error = "provider_down"
                        break
                if e.kind == "rate_limit":
                    want = e.retry_after if e.retry_after is not None else 2.0 * res.requests
                    left = self.max_wait_s - wait_ms / 1000
                    if want > left or left <= 0:
                        res.error = "rate_limit"
                        break
                    self.sleep(want)
                    wait_ms += int(want * 1000)
                    res.retries += 1
                    continue
                timeouts += 1
                if timeouts >= attempt_budget:
                    res.error = "timeout" if last_kind == "timeout" else "provider_down"
                    break
                backoff = (2 ** (timeouts - 1)) * 1.0 + random.uniform(0, 0.5)
                self.sleep(backoff)
                res.retries += 1
                continue
            # success
            self._fails_in_row = 0
            self._opened_at = None
            res.text, res.tokens_in, res.tokens_out = text, tin, tout
            res.degraded = False
            break

        res.rate_limit_wait_ms = wait_ms
        res.latency_ms = max(0, int((self.clock() - t0) * 1000) - wait_ms)
        if res.ok and cp:
            cp.parent.mkdir(parents=True, exist_ok=True)
            cp.write_text(json.dumps({"text": res.text}), encoding="utf-8")
        return res


def client_from_env(**overrides) -> LLMClient:
    """Build the OpenRouter client from .env. Raises LLMConfigError when it cannot run safely."""
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass
    model = os.getenv("MODEL_NAME", "")
    key = os.getenv("OPENROUTER_API_KEY", "")
    if not model:
        raise LLMConfigError("MODEL_NAME is not set")
    if not model.endswith(":free") and os.getenv("ALLOW_PAID_MODEL") != "1":
        raise LLMConfigError(f"MODEL_NAME {model!r} is not a ':free' model id (NFR-07)")
    if not key or key == "your_key_here":
        raise LLMConfigError("OPENROUTER_API_KEY is not set")
    cache = Path(os.getenv("LLM_CACHE_DIR", "storage/llm_cache")) if os.getenv("LLM_CACHE") == "1" else None
    kw = dict(
        model=model,
        timeout_s=float(os.getenv("LLM_TIMEOUT_S", "10")),
        min_interval_s=float(os.getenv("LLM_MIN_INTERVAL_S", "3")),
        cache_dir=cache,
    )
    kw.update(overrides)
    transport = openai_transport(model, key, os.getenv("LLM_BASE_URL", OPENROUTER_URL),
                                 reasoning_off=os.getenv("LLM_REASONING", "off") == "off")
    return LLMClient(transport=transport, **kw)
