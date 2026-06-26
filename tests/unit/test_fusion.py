"""Tests for Reciprocal Rank Fusion and multi-query retrieval."""

from __future__ import annotations

from perfectrag.core.fusion import reciprocal_rank_fusion
from perfectrag.core.protocols import Chunk, Hit
from perfectrag.core.rag import RAG


def test_rrf_empty():
    assert reciprocal_rank_fusion([]) == []
    assert reciprocal_rank_fusion([[]]) == []


def test_rrf_single_list_preserves_order():
    assert reciprocal_rank_fusion([["a", "b", "c"]]) == ["a", "b", "c"]


def test_rrf_rewards_consensus():
    # "b" is mid-rank in both lists; "a" and "c" each top one list.
    # b appears twice → its summed RRF score beats single-appearance items.
    fused = reciprocal_rank_fusion([["a", "b"], ["c", "b"]])
    assert fused[0] == "b"
    assert set(fused) == {"a", "b", "c"}


def test_rrf_k_damping_changes_nothing_about_membership():
    fused = reciprocal_rank_fusion([["x", "y"], ["y", "z"]], k=10)
    assert fused[0] == "y"


class _Store:
    """Returns a fixed hit list per query string."""

    def __init__(self, mapping):
        self._mapping = mapping

    def search(self, collection, query_vec, k):
        ids = self._mapping.get(query_vec, [])[:k]
        return [Hit(chunk=Chunk(id=i, text=i, source=i, metadata={}), score=1.0) for i in ids]

    def ensure_collection(self, *a):  # pragma: no cover
        pass


class _Embedder:
    dim = 1

    def embed(self, text):
        return text  # identity → store keys on the raw query string

    def embed_batch(self, texts):
        return list(texts)


class _LLM:
    def generate(self, prompt, **kw):
        return "alt query one\nalt query two"

    def stream(self, prompt, **kw):  # pragma: no cover
        yield ""


def test_multi_query_fuses_across_expansions():
    store = _Store({
        "orig":          ["d1", "d2"],
        "alt query one": ["d2", "d3"],
        "alt query two": ["d2", "d4"],
    })
    rag = RAG(store=store, embedder=_Embedder(), llm=_LLM(), top_k=3, query_expansion=2)
    hits = rag.retrieve("orig", k=3)
    sources = [h.chunk.source for h in hits]
    # d2 appears in all three rankings → fused to the top
    assert sources[0] == "d2"
    assert "d1" in sources and "d3" in sources


def test_query_expansion_zero_uses_single_query():
    store = _Store({"orig": ["d1", "d2", "d3"]})
    rag = RAG(store=store, embedder=_Embedder(), llm=_LLM(), top_k=2, query_expansion=0)
    hits = rag.retrieve("orig", k=2)
    assert [h.chunk.source for h in hits] == ["d1", "d2"]
