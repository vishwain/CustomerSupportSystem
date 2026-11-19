"""Retrieve (A4; PRD FR-08, FR-09, FR-10, FR-19).

- Passages are built only from data/documentation.json. Each carries doc_id, passage_id, title,
  section and last_reviewed_days_ago, so every citation traces to a source article.
- Search is by embedding similarity (all-MiniLM-L6-v2, local, CPU) in Chroma. Score = cosine similarity.
- Up to top_k passages are returned, best first. Passages under the relevance cutoff are dropped;
  if none clear it, the result is empty and Route escalates (FR-09, FR-11).
- The chunking config and cutoff come from config/retrieval.json, written by
  docs/retrieval_experiment.py from measured data. Nothing here is a guessed default.
- No fluency, tier or region field is read (FR-19); only the cleaned ticket text is the query.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Protocol, Sequence

DEFAULT_DOCS = Path("data/documentation.json")
DEFAULT_CONFIG = Path("config/retrieval.json")
DEFAULT_MODEL = "all-MiniLM-L6-v2"


# ----------------------------------------------------------------------------- chunking

@dataclass(frozen=True)
class ChunkConfig:
    name: str
    strategy: str  # "section" | "chars"
    chunk_size: int = 0  # chars strategy only
    overlap: int = 0
    title_prefix: bool = True  # prepend "<title> - <section>" to the embedded text

    def describe(self) -> str:
        if self.strategy == "section":
            return "one passage per article section" + (" + title prefix" if self.title_prefix else "")
        return f"{self.chunk_size}/{self.overlap} chars" + (" + title prefix" if self.title_prefix else ", raw")


# The configurations compared in docs/retrieval_experiment.py.
CONFIGS = {
    c.name: c for c in (
        ChunkConfig("chars800_raw", "chars", 800, 120, title_prefix=False),  # Setup Guide as written
        ChunkConfig("chars800", "chars", 800, 120),
        ChunkConfig("chars400", "chars", 400, 80),
        ChunkConfig("section", "section"),  # PRD FR-08 design
    )
}


@dataclass
class Passage:
    passage_id: str  # "<doc_id>#<section-slug>" or "<doc_id>#c<NN>"
    doc_id: str
    title: str
    section: str  # the section the passage starts in
    text: str  # the passage text shown to Generate and cited
    embed_text: str  # what was embedded (text plus optional title prefix)
    last_reviewed_days_ago: int | None = None
    score: float | None = None

    @property
    def reviewed_label(self) -> str:  # FR-10
        n = self.last_reviewed_days_ago
        if n is None:
            return "review date unknown"
        return "reviewed today" if n == 0 else ("reviewed 1 day ago" if n == 1 else f"reviewed {n} days ago")

    def public(self) -> dict[str, Any]:
        d = asdict(self)
        d.pop("embed_text")
        d["reviewed_label"] = self.reviewed_label
        return d


_HEADING = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-") or "section"


def _sections(content: str) -> list[tuple[str, int, str]]:
    """[(section_title, start_offset, body)] for every '## ' heading. Text before the first heading
    (article title, 'Applies to') is not a passage; the title travels as a prefix instead."""
    heads = list(_HEADING.finditer(content))
    out = []
    for i, m in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(content)
        out.append((m.group(1), m.start(), content[m.end():end].strip()))
    return out


def load_docs(path: str | Path = DEFAULT_DOCS) -> list[dict[str, Any]]:
    with open(path, encoding="utf-8") as f:
        docs = json.load(f)
    for d in docs:
        if not d.get("doc_id") or not d.get("content"):
            raise ValueError(f"documentation record without doc_id or content: {str(d)[:80]}")
    return docs


def docs_sha256(path: str | Path = DEFAULT_DOCS) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def chunk_docs(docs: list[dict[str, Any]], cfg: ChunkConfig) -> list[Passage]:
    passages: list[Passage] = []
    for d in docs:
        doc_id, title, content = d["doc_id"], d.get("title", ""), d["content"]
        reviewed = d.get("last_reviewed_days_ago")
        secs = _sections(content)

        if cfg.strategy == "section":
            seen: dict[str, int] = {}
            for sec_title, _, body in secs:
                if not body:
                    continue
                s = slug(sec_title)
                seen[s] = seen.get(s, 0) + 1
                pid = f"{doc_id}#{s}" if seen[s] == 1 else f"{doc_id}#{s}-{seen[s]}"
                prefix = f"{title} - {sec_title}\n" if cfg.title_prefix else ""
                passages.append(Passage(pid, doc_id, title, sec_title, body, prefix + body, reviewed))
            continue

        from langchain_text_splitters import RecursiveCharacterTextSplitter

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=cfg.chunk_size, chunk_overlap=cfg.overlap, add_start_index=True)
        for i, chunk in enumerate(splitter.create_documents([content])):
            start = chunk.metadata.get("start_index", 0)
            sec_title = next((t for t, off, _ in reversed(secs) if off <= start), "Introduction")
            text = chunk.page_content
            prefix = f"{title}\n" if cfg.title_prefix and not text.lstrip().startswith("# ") else ""
            passages.append(Passage(f"{doc_id}#c{i:02d}", doc_id, title, sec_title, text, prefix + text, reviewed))
    return passages


# ----------------------------------------------------------------------------- embeddings

class Embedder(Protocol):
    name: str

    def encode(self, texts: Sequence[str]) -> Any:  # (n, dim) array, rows L2-normalised
        ...


class SentenceTransformerEmbedder:
    """all-MiniLM-L6-v2 on CPU. First use downloads the model to the Hugging Face cache."""

    def __init__(self, model_name: str | None = None):
        from sentence_transformers import SentenceTransformer

        self.name = model_name or os.getenv("EMBEDDING_MODEL", DEFAULT_MODEL)
        self._model = SentenceTransformer(self.name, device="cpu")

    def encode(self, texts: Sequence[str]):
        return self._model.encode(list(texts), normalize_embeddings=True, batch_size=32,
                                  show_progress_bar=False, convert_to_numpy=True)


# ----------------------------------------------------------------------------- retrieval

@dataclass
class RetrievalResult:
    passages: list[Passage]  # only those at or above the cutoff, best first, at most top_k
    candidates: list[Passage]  # top_k before the cutoff (for the log and for analysis)
    cutoff: float
    top_score: float
    reason: str
    # Other chunks of the articles that passed the cutoff, so Generate sees whole articles (a chunk can end
    # at a bare "## Resolution" heading). Never counted as hits: Route and the retrieval metrics use
    # `passages` only. Citable, because they were retrieved for this ticket and are logged.
    context: list[Passage] = field(default_factory=list)

    @property
    def for_generation(self) -> list[Passage]:
        return self.passages + self.context

    @property
    def hit(self) -> bool:
        return bool(self.passages)

    def doc_ids(self, k: int = 3) -> list[str]:
        """Distinct doc ids among the first k returned passages."""
        out: list[str] = []
        for p in self.passages[:k]:
            if p.doc_id not in out:
                out.append(p.doc_id)
        return out


class Retriever:
    """Chroma index over one chunking config. Rebuilt automatically when docs, config or model change."""

    def __init__(self, embedder: Embedder, cfg: ChunkConfig, cutoff: float, top_k: int = 5,
                 docs_path: str | Path = DEFAULT_DOCS, chroma_path: str | Path | None = None,
                 expand_docs: int = 0):
        import chromadb

        if not 0.0 <= cutoff <= 1.0:
            raise ValueError(f"cutoff must be between 0 and 1, got {cutoff}")
        self.embedder, self.cfg, self.cutoff, self.top_k = embedder, cfg, float(cutoff), int(top_k)
        self.expand_docs = int(expand_docs)
        self.docs_path = Path(docs_path)
        self.passages = chunk_docs(load_docs(self.docs_path), cfg)
        self._by_id = {p.passage_id: p for p in self.passages}

        client = (chromadb.PersistentClient(path=str(chroma_path)) if chroma_path
                  else chromadb.EphemeralClient())
        fingerprint = {
            "docs_sha256": docs_sha256(self.docs_path),
            "config": json.dumps(asdict(cfg), sort_keys=True),
            "embedding_model": embedder.name,
        }
        name = f"docs_{cfg.name}_{slug(embedder.name)}"[:60]
        existing = {c.name for c in client.list_collections()}
        col = client.get_collection(name) if name in existing else None
        meta = (col.metadata or {}) if col else {}
        if col is None or any(meta.get(k) != v for k, v in fingerprint.items()) or col.count() != len(self.passages):
            if col is not None:
                client.delete_collection(name)
            col = client.create_collection(name, metadata={"hnsw:space": "cosine", **fingerprint})
            vecs = embedder.encode([p.embed_text for p in self.passages])
            col.add(ids=[p.passage_id for p in self.passages],
                    embeddings=[list(map(float, v)) for v in vecs],
                    documents=[p.text for p in self.passages],
                    metadatas=[{"doc_id": p.doc_id, "title": p.title, "section": p.section,
                                "last_reviewed_days_ago": -1 if p.last_reviewed_days_ago is None
                                else int(p.last_reviewed_days_ago)} for p in self.passages])
        self._col = col

    @property
    def model_version(self) -> str:
        return f"{self.embedder.name}|{self.cfg.name}"

    def score_all(self, text: str) -> list[Passage]:
        """Every passage with its score, best first (analysis and the threshold study)."""
        return self._query(text, len(self.passages))

    def _query(self, text: str, n: int) -> list[Passage]:
        if not (text or "").strip():
            return []
        q = self.embedder.encode([text])[0]
        res = self._col.query(query_embeddings=[list(map(float, q))], n_results=min(n, len(self.passages)),
                              include=["distances"])
        out = []
        for pid, dist in zip(res["ids"][0], res["distances"][0]):
            p = self._by_id[pid]
            out.append(Passage(**{**asdict(p), "score": round(1.0 - float(dist), 4)}))
        out.sort(key=lambda p: p.score, reverse=True)
        return out

    def retrieve(self, text: str, cutoff: float | None = None) -> RetrievalResult:
        cut = self.cutoff if cutoff is None else float(cutoff)
        scored = self._query(text, len(self.passages) if self.expand_docs else self.top_k)
        cands = scored[: self.top_k]
        kept = [p for p in cands if p.score >= cut]
        top = cands[0].score if cands else 0.0
        if kept:
            reason = (f"{len(kept)} passage(s) at or above cutoff {cut:.2f}; "
                      f"best {kept[0].passage_id} at {kept[0].score:.2f}.")
        elif cands:
            reason = f"No passage at or above cutoff {cut:.2f}; best was {cands[0].passage_id} at {top:.2f}."
        else:
            reason = "Empty query text; nothing searched."
        context: list[Passage] = []
        if kept and self.expand_docs:
            docs: list[str] = []
            for p in kept:
                if p.doc_id not in docs:
                    docs.append(p.doc_id)
            have = {p.passage_id for p in kept}
            for doc in docs[: self.expand_docs]:
                context += sorted((p for p in scored if p.doc_id == doc and p.passage_id not in have),
                                  key=lambda p: p.passage_id)
            if context:
                reason += f" Context added from the same article(s): {', '.join(p.passage_id for p in context)}."
        return RetrievalResult(kept, cands, cut, top, reason, context)


# ----------------------------------------------------------------------------- config + log

@dataclass
class RetrievalConfig:
    chunking: str
    cutoff: float
    top_k: int = 5
    embedding_model: str = DEFAULT_MODEL
    expand_docs: int = 2  # whole-article context for Generate (5.8 review); 0 turns it off
    set_on: str = ""
    rule: str = ""
    evidence: dict[str, Any] = field(default_factory=dict)


def load_config(path: str | Path = DEFAULT_CONFIG) -> RetrievalConfig:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(
            f"{p} not found. Run: python docs/retrieval_experiment.py --write-config  (sets chunking and cutoff from data)")
    data = json.loads(p.read_text(encoding="utf-8"))
    if data.get("chunking") not in CONFIGS:
        raise ValueError(f"unknown chunking {data.get('chunking')!r} in {p}")
    return RetrievalConfig(**{k: data[k] for k in RetrievalConfig.__dataclass_fields__ if k in data})


def build_retriever(config_path: str | Path = DEFAULT_CONFIG, embedder: Embedder | None = None,
                    chroma_path: str | Path | None = None) -> Retriever:
    rc = load_config(config_path)
    emb = embedder or SentenceTransformerEmbedder(rc.embedding_model)
    return Retriever(emb, CONFIGS[rc.chunking], rc.cutoff, rc.top_k,
                     chroma_path=chroma_path or os.getenv("CHROMA_PATH", "./storage/chroma"),
                     expand_docs=rc.expand_docs)


def log_retrieval(log, ticket_id: str, text: str, retriever: Retriever, result: RetrievalResult,
                  latency_ms: int = 0) -> None:
    """One decision row for the retrieval stage. No hit is logged as error no_retrieval_hit (A11)."""
    log.write(
        ticket_id=ticket_id, stage="retrieval",
        action_taken="passages_found" if result.hit else "no_passages",
        reason=result.reason, input_text=text,
        model_name=retriever.embedder.name, model_version=retriever.model_version,
        prediction={"returned": len(result.passages), "top_score": result.top_score,
                    "context_added": [p.passage_id for p in result.context]},
        confidence=result.top_score, threshold_applied=result.cutoff,
        sources_used=[{"doc_id": p.doc_id, "passage_id": p.passage_id, "score": p.score}
                      for p in result.passages],
        alternatives=[{"value": p.passage_id, "confidence": p.score}
                      for p in result.candidates if p not in result.passages],
        doc_review_age={p.doc_id: p.last_reviewed_days_ago for p in result.passages},
        error="none" if result.hit else "no_retrieval_hit",
        latency_ms=latency_ms,
    )
