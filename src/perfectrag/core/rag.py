"""Main `RAG` class — embedded pure-Python RAG pipeline.

Usage:
    from perfectrag import RAG
    rag = RAG.from_config("perfectrag.yml")
    rag.ingest("./docs")
    print(rag.query("What is RAG?"))

Config schema (perfectrag.yml):

    collection: documents
    chunk_size: 512
    top_k: 5

    store:
      name: chroma             # qdrant | milvus | chroma | lancedb | pgvector
      path: ./data/chroma      # optional backend-specific kwargs

    embedding:
      model: BAAI/bge-m3
      backend: sentence_transformers   # optional override

    reranker:
      model: BAAI/bge-reranker-v2-m3   # or null to skip

    llm:
      runtime: ollama          # ollama | llamacpp | vllm | gemini | anthropic | openai
      model: qwen2.5:7b-instruct-q5_K_M
      url: http://localhost:11434    # backend-specific

    parser:
      name: markitdown         # markitdown | docling | simple
"""

from __future__ import annotations

import os
import re
import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from perfectrag.core import embeddings, llms, parsers, rerankers, stores
from perfectrag.core import extensions as ext
from perfectrag.core.protocols import Chunk, Hit


@dataclass
class QueryResult:
    answer: str
    hits: list[Hit]
    prompt: str

    def as_dict(self) -> dict:
        return {
            "answer": self.answer,
            "sources": [
                {"source": h.chunk.source, "score": h.score, "text": h.chunk.text[:400]}
                for h in self.hits
            ],
        }


_ENV_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::-([^}]*))?\}")


def _expand_env(value: Any) -> Any:
    """Recursively expand ${VAR} and ${VAR:-default} in a loaded config using os.environ.

    perfectrag.yml mirrors docker-compose env syntax so the same file works in a
    container (where QDRANT_URL etc. are set) and locally (where the default wins)."""
    if isinstance(value, str):
        return _ENV_RE.sub(lambda m: os.environ.get(m.group(1)) or (m.group(2) or ""), value)
    if isinstance(value, dict):
        return {k: _expand_env(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_expand_env(v) for v in value]
    return value


def _chunk_text(text: str, size: int = 512) -> list[str]:
    words = text.split()
    return [" ".join(words[i : i + size]) for i in range(0, len(words), size) if words[i : i + size]]


def _parent_child_chunks(text: str, parent_size: int, child_size: int) -> list[tuple[str, str]]:
    """Split into parent blocks, each into child chunks. Returns (child, parent) pairs."""
    pairs: list[tuple[str, str]] = []
    for parent in _chunk_text(text, parent_size):
        for child in _chunk_text(parent, child_size):
            pairs.append((child, parent))
    return pairs


class RAG:
    def __init__(
        self,
        store,
        embedder,
        llm,
        reranker=None,
        parser=None,
        collection: str = "documents",
        chunk_size: int = 512,
        top_k: int = 5,
        contextual: bool = False,
        query_expansion: int = 0,
        parent_chunk_size: int = 0,
        corrective: bool = False,
        extensions: list[str] | None = None,
        retriever: str | None = None,
        transforms: list[str] | None = None,
    ):
        # Load user extension modules first so their @inject/@retrieve/@transform/
        # @tool/@skill decorators are registered before we reference them by name.
        for src in extensions or []:
            ext.load_extensions(src)
        self.store = store
        self.embedder = embedder
        self.reranker = reranker
        self.llm = llm
        self.parser = parser
        self.collection = collection
        self.chunk_size = chunk_size
        self.top_k = top_k
        # Name of a registered @retrieve to use instead of the built-in retriever.
        self.retriever = retriever
        # Names of registered @transform hooks applied (in order) after retrieval.
        self.transforms = list(transforms or [])
        # Contextual Retrieval (Anthropic): prepend an LLM-generated situating
        # sentence to each chunk before embedding. Cuts retrieval failures a lot
        # at the cost of one cheap LLM call per chunk at ingest time.
        self.contextual = contextual
        # Query expansion: generate N alternate phrasings per query, retrieve for
        # each, and fuse with Reciprocal Rank Fusion. Helps recall on terse or
        # multi-hop questions. 0 disables (single-query path).
        self.query_expansion = query_expansion
        # Parent-document retrieval: embed small child chunks (precise matching)
        # but feed the larger parent block to the LLM (more context). 0 disables.
        self.parent_chunk_size = parent_chunk_size
        # Corrective RAG (CRAG): grade the initial results; if they look irrelevant,
        # re-retrieve once with query expansion before answering.
        self.corrective = corrective

    @classmethod
    def from_config(cls, path: str | Path) -> RAG:
        cfg = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        return cls.from_dict(_expand_env(cfg))

    @classmethod
    def from_dict(cls, cfg: dict) -> RAG:
        store_cfg = cfg.get("store", {"name": "chroma"})
        store = stores.build(store_cfg.pop("name"), **store_cfg)

        emb_cfg = cfg.get("embedding", {"model": "BAAI/bge-m3"})
        embedder = embeddings.build(emb_cfg.pop("model"), **emb_cfg)

        rer_cfg = cfg.get("reranker") or {}
        reranker = rerankers.build(rer_cfg.pop("model", None), **rer_cfg) if rer_cfg or "model" in (cfg.get("reranker") or {}) else None

        llm_cfg = cfg.get("llm", {"runtime": "ollama", "model": "qwen2.5:3b-instruct-q4_K_M"})
        runtime = llm_cfg.pop("runtime")
        model = llm_cfg.pop("model")
        llm = llms.build(runtime, model, **llm_cfg)

        parser_cfg = cfg.get("parser", {"name": "simple"})
        parser = parsers.build(parser_cfg.get("name", "simple"))

        return cls(
            store=store,
            embedder=embedder,
            reranker=reranker,
            llm=llm,
            parser=parser,
            collection=cfg.get("collection", "documents"),
            chunk_size=int(cfg.get("chunk_size", 512)),
            top_k=int(cfg.get("top_k", 5)),
            contextual=bool(cfg.get("contextual", False)),
            query_expansion=int(cfg.get("query_expansion", 0)),
            parent_chunk_size=int(cfg.get("parent_chunk_size", 0)),
            corrective=bool(cfg.get("corrective", False)),
            extensions=cfg.get("extensions") or [],
            retriever=cfg.get("retriever"),
            transforms=cfg.get("transforms") or [],
        )

    # --- ingestion ---

    def ingest(self, path: str | Path, *, glob: str = "**/*") -> int:
        """Ingest a single file or all files in a dir. Returns chunk count."""
        p = Path(path)
        paths: Iterable[Path] = [p] if p.is_file() else [x for x in p.glob(glob) if x.is_file()]
        total = 0
        for fp in paths:
            total += self._ingest_one(fp)
        return total

    def _ingest_one(self, fp: Path) -> int:
        if self.parser is None:
            self.parser = parsers.build("simple")
        text = self.parser.parse(str(fp))
        return self._index(text, source=str(fp))

    def ingest_text(self, text: str, source: str = "inline") -> int:
        return self._index(text, source=source)

    def ingest_from(self, source: str, **kwargs) -> int:
        """Ingest via a registered ``@inject`` data source. Returns chunk count.

        The inject function may yield ``Document``/str/dict/(text, source) items::

            @inject("notion")
            def notion(database_id: str):
                yield Document(text=..., source=..., metadata={...})

            rag.ingest_from("notion", database_id="abc")
        """
        ext_obj = ext.REGISTRY.get(ext.INJECT, source)
        if ext_obj is None:
            raise KeyError(
                f"No @inject source named {source!r}. "
                f"Registered: {ext.REGISTRY.names(ext.INJECT) or '[]'}"
            )
        result = self._call(ext_obj, **kwargs)
        total = 0
        for doc in ext.iter_docs(result, default_source=source):
            total += self._index(doc.text, source=doc.source, extra_meta=doc.metadata)
        return total

    def _index(self, text: str, *, source: str, extra_meta: dict[str, Any] | None = None) -> int:
        """Chunk → (optionally) contextualize → embed → upsert. Returns chunk count."""
        if self.parent_chunk_size and self.parent_chunk_size > self.chunk_size:
            pairs = _parent_child_chunks(text, self.parent_chunk_size, self.chunk_size)
        else:
            pairs = [(t, "") for t in _chunk_text(text, self.chunk_size)]
        if not pairs:
            return 0
        chunks = []
        for i, (child, parent) in enumerate(pairs):
            meta: dict[str, object] = {"chunk_index": i, **(extra_meta or {})}
            if parent:
                meta["parent_text"] = parent
            chunks.append(Chunk(id=str(uuid.uuid4()), text=child, source=source, metadata=meta))
        embed_inputs = [
            self._contextualize(text, c.text) if self.contextual else c.text
            for c in chunks
        ]
        vectors = self.embedder.embed_batch(embed_inputs)
        self.store.ensure_collection(self.collection, self.embedder.dim or len(vectors[0]))
        self.store.upsert(self.collection, chunks, vectors)
        return len(chunks)

    def _contextualize(self, document: str, chunk: str) -> str:
        """Prepend a one-sentence situating context (Anthropic Contextual Retrieval).

        Falls back to the raw chunk if no LLM is configured or the call fails."""
        if self.llm is None:
            return chunk
        prompt = (
            "<document>\n" + document[:8000] + "\n</document>\n"
            "<chunk>\n" + chunk + "\n</chunk>\n"
            "Give a short, single-sentence context that situates this chunk within "
            "the document to improve search retrieval. Answer with the context only."
        )
        try:
            context = self.llm.generate(prompt, max_tokens=80).strip()
        except Exception:
            return chunk
        return f"{context}\n\n{chunk}" if context else chunk

    # --- query ---

    # --- extension plumbing ---

    def _ctx(self) -> ext.Context:
        return ext.Context(rag=self, config=getattr(self, "_config", {}))

    def _call(self, ext_obj: ext.Extension, *args: Any, **kwargs: Any) -> Any:
        """Invoke an extension, passing a Context first if it asked for `ctx`."""
        if ext_obj.wants_ctx:
            return ext_obj.fn(self._ctx(), *args, **kwargs)
        return ext_obj.fn(*args, **kwargs)

    def retrieve(self, question: str, k: int | None = None) -> list[Hit]:
        """Retrieve hits: a registered ``@retrieve`` if set, else the built-in
        pipeline — then run every registered ``@transform`` hook in order."""
        k = k or self.top_k
        if self.retriever:
            r = ext.REGISTRY.get(ext.RETRIEVE, self.retriever)
            hits = list(self._call(r, question, k)) if r else self._default_retrieve(question, k)
        else:
            hits = self._default_retrieve(question, k)
        for name in self.transforms:
            t = ext.REGISTRY.get(ext.TRANSFORM, name)
            if t is not None:
                hits = list(self._call(t, question, hits))
        return hits

    # --- tools & skills (callable extensions) ---

    def tool_names(self) -> list[str]:
        return ext.REGISTRY.names(ext.TOOL)

    def tool_schemas(self) -> list[dict]:
        """OpenAI/Anthropic-style function schemas for every registered ``@tool``."""
        return [e.schema() for e in ext.REGISTRY.all(ext.TOOL)]

    def call_tool(self, name: str, **kwargs: Any) -> Any:
        e = ext.REGISTRY.get(ext.TOOL, name)
        if e is None:
            raise KeyError(f"No @tool named {name!r}. Registered: {self.tool_names() or '[]'}")
        return self._call(e, **kwargs)

    def skill_names(self) -> list[str]:
        return ext.REGISTRY.names(ext.SKILL)

    def run_skill(self, name: str, **kwargs: Any) -> Any:
        e = ext.REGISTRY.get(ext.SKILL, name)
        if e is None:
            raise KeyError(f"No @skill named {name!r}. Registered: {self.skill_names() or '[]'}")
        return self._call(e, **kwargs)

    def extensions(self) -> dict[str, list[str]]:
        """Everything currently registered, grouped by kind."""
        return ext.REGISTRY.summary()

    def _default_retrieve(self, question: str, k: int | None = None) -> list[Hit]:
        k = k or self.top_k
        retrieval_k = k * 3 if self.reranker else k
        if self.query_expansion and self.llm is not None:
            hits = self._multi_query_search(question, retrieval_k)
        else:
            qvec = self.embedder.embed(question)
            hits = self.store.search(self.collection, qvec, retrieval_k)
        # CRAG: if the first pass looks irrelevant, retry once with expansion.
        if (self.corrective and self.llm is not None and hits
                and not self.query_expansion and not self._grade_relevance(question, hits)):
            hits = self._multi_query_search(question, retrieval_k, n=3)
        if self.reranker and hits:
            docs = [h.chunk.text for h in hits]
            ranked = self.reranker.rerank(question, docs, top_k=k)
            return [Hit(chunk=hits[i].chunk, score=s) for i, s in ranked]
        return hits[:k]

    def _multi_query_search(self, question: str, retrieval_k: int, n: int | None = None) -> list[Hit]:
        """Retrieve for the original + expanded queries, fuse with RRF."""
        from perfectrag.core.fusion import reciprocal_rank_fusion

        n = self.query_expansion if n is None else n
        queries = [question, *self._expand_query(question, n)]
        by_id: dict[str, Hit] = {}
        rankings: list[list[str]] = []
        for q in queries:
            qvec = self.embedder.embed(q)
            hits = self.store.search(self.collection, qvec, retrieval_k)
            rankings.append([h.chunk.id for h in hits])
            for h in hits:
                by_id.setdefault(h.chunk.id, h)
        fused_ids = reciprocal_rank_fusion(rankings)
        return [by_id[i] for i in fused_ids]

    def _expand_query(self, question: str, n: int) -> list[str]:
        """Ask the LLM for n alternate phrasings; empty list on any failure."""
        if self.llm is None or n <= 0:
            return []
        prompt = (
            f"Rewrite this search query into {n} alternative phrasings that retrieve "
            "the same information. One per line, no numbering, no extra text.\n"
            f"Query: {question}"
        )
        try:
            out = self.llm.generate(prompt, max_tokens=120)
        except Exception:
            return []
        lines = [ln.strip("-*0123456789. ").strip() for ln in out.splitlines() if ln.strip()]
        return lines[:n]

    def _grade_relevance(self, question: str, hits: list[Hit]) -> bool:
        """LLM judges whether the retrieved context can answer the question.
        Returns True (assume relevant) on any failure — never blocks answering."""
        if self.llm is None or not hits:
            return True
        sample = "\n".join(h.chunk.text[:200] for h in hits[:3])
        prompt = (
            f"Question: {question}\nRetrieved context:\n{sample}\n\n"
            "Is this context relevant and sufficient to answer the question? "
            "Answer only YES or NO."
        )
        try:
            out = self.llm.generate(prompt, max_tokens=5).strip().upper()
        except Exception:
            return True
        return not out.startswith("NO")

    @staticmethod
    def _build_context(hits: list[Hit]) -> str:
        """Join hit texts, expanding each to its parent block (parent-document
        retrieval) and de-duplicating so a shared parent isn't repeated."""
        seen: set[str] = set()
        parts: list[str] = []
        for h in hits:
            parent = h.chunk.metadata.get("parent_text")
            text = parent or h.chunk.text
            key = parent or h.chunk.id
            if key in seen:
                continue
            seen.add(key)
            parts.append(text)
        return "\n---\n".join(parts)

    def query(self, question: str, k: int | None = None) -> QueryResult:
        hits = self.retrieve(question, k)
        context = self._build_context(hits)
        prompt = (
            f"Use the context to answer. If the context doesn't contain the answer, say so.\n\n"
            f"Context:\n{context}\n\nQuestion: {question}\nAnswer:"
        )
        answer = self.llm.generate(prompt)
        return QueryResult(answer=answer, hits=hits, prompt=prompt)

    def stream(self, question: str, k: int | None = None):
        """Yield (event_type, payload) for streaming UIs.

        event_type is "retrieval" (once, with hits) then "token" (repeatedly, with str).
        """
        hits = self.retrieve(question, k)
        yield ("retrieval", hits)
        context = self._build_context(hits)
        prompt = (
            f"Use the context to answer.\n\nContext:\n{context}\n\nQuestion: {question}\nAnswer:"
        )
        for tok in self.llm.stream(prompt):
            yield ("token", tok)
