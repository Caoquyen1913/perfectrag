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

import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

import yaml

from perfectrag.core import embeddings, llms, parsers, rerankers, stores
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


def _chunk_text(text: str, size: int = 512) -> list[str]:
    words = text.split()
    return [" ".join(words[i : i + size]) for i in range(0, len(words), size) if words[i : i + size]]


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
    ):
        self.store = store
        self.embedder = embedder
        self.reranker = reranker
        self.llm = llm
        self.parser = parser
        self.collection = collection
        self.chunk_size = chunk_size
        self.top_k = top_k
        # Contextual Retrieval (Anthropic): prepend an LLM-generated situating
        # sentence to each chunk before embedding. Cuts retrieval failures a lot
        # at the cost of one cheap LLM call per chunk at ingest time.
        self.contextual = contextual
        # Query expansion: generate N alternate phrasings per query, retrieve for
        # each, and fuse with Reciprocal Rank Fusion. Helps recall on terse or
        # multi-hop questions. 0 disables (single-query path).
        self.query_expansion = query_expansion

    @classmethod
    def from_config(cls, path: str | Path) -> RAG:
        cfg = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        return cls.from_dict(cfg)

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

    def _index(self, text: str, *, source: str) -> int:
        """Chunk → (optionally) contextualize → embed → upsert. Returns chunk count."""
        chunks_text = _chunk_text(text, self.chunk_size)
        if not chunks_text:
            return 0
        chunks = [
            Chunk(id=str(uuid.uuid4()), text=t, source=source, metadata={"chunk_index": i})
            for i, t in enumerate(chunks_text)
        ]
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

    def retrieve(self, question: str, k: int | None = None) -> list[Hit]:
        k = k or self.top_k
        retrieval_k = k * 3 if self.reranker else k
        if self.query_expansion and self.llm is not None:
            hits = self._multi_query_search(question, retrieval_k)
        else:
            qvec = self.embedder.embed(question)
            hits = self.store.search(self.collection, qvec, retrieval_k)
        if self.reranker and hits:
            docs = [h.chunk.text for h in hits]
            ranked = self.reranker.rerank(question, docs, top_k=k)
            return [Hit(chunk=hits[i].chunk, score=s) for i, s in ranked]
        return hits[:k]

    def _multi_query_search(self, question: str, retrieval_k: int) -> list[Hit]:
        """Retrieve for the original + expanded queries, fuse with RRF."""
        from perfectrag.core.fusion import reciprocal_rank_fusion

        queries = [question, *self._expand_query(question, self.query_expansion)]
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

    def query(self, question: str, k: int | None = None) -> QueryResult:
        hits = self.retrieve(question, k)
        context = "\n---\n".join(h.chunk.text for h in hits)
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
        context = "\n---\n".join(h.chunk.text for h in hits)
        prompt = (
            f"Use the context to answer.\n\nContext:\n{context}\n\nQuestion: {question}\nAnswer:"
        )
        for tok in self.llm.stream(prompt):
            yield ("token", tok)
