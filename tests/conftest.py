"""Shared test fixtures. FakeEmbedder keeps tests offline and fast: hashed bag of words,
L2-normalised. It tests plumbing only; retrieval quality numbers come from the real model."""

import hashlib
import re

import numpy as np
import pytest


class FakeEmbedder:
    name = "fake-hash-embedder"
    dim = 256

    def encode(self, texts):
        out = np.zeros((len(texts), self.dim), dtype=np.float32)
        for i, t in enumerate(texts):
            for w in re.findall(r"[a-z0-9]+", t.lower()):
                if len(w) > 2:
                    out[i, int(hashlib.md5(w.encode()).hexdigest(), 16) % self.dim] += 1.0
            n = np.linalg.norm(out[i])
            if n:
                out[i] /= n
            else:
                out[i, 0] = 1.0
        return out


@pytest.fixture
def fake_embedder():
    return FakeEmbedder()


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    """Every test runs without API keys or network (A12). A real provider call or a model download fails
    the test loudly instead of happening. A real key in .env is never used: python-dotenv does not
    override a variable that is already set."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key-not-real")
    monkeypatch.setenv("LLM_CACHE", "0")
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    monkeypatch.setenv("TRANSFORMERS_OFFLINE", "1")

    def no_provider(*a, **k):
        raise RuntimeError("a test tried to build a real provider client; use a scripted transport")

    def no_model(self, *a, **k):
        raise RuntimeError("a test tried to load the real embedding model; use FakeEmbedder")

    import src.llm
    import src.retrieve
    monkeypatch.setattr(src.llm, "openai_transport", no_provider)
    monkeypatch.setattr(src.retrieve.SentenceTransformerEmbedder, "__init__", no_model)
