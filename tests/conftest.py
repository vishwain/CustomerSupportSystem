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
