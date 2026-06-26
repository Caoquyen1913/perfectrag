"""Tests for retrieval-quality metrics and the CI gate."""

from __future__ import annotations

from perfectrag.core.evaluation import (
    evaluate_retrieval,
    ndcg_at_k,
    passes_gate,
    recall_at_k,
    reciprocal_rank,
)
from perfectrag.core.protocols import Chunk, Hit


def test_recall_at_k():
    assert recall_at_k(["a", "b", "c"], {"a", "c"}, 3) == 1.0
    assert recall_at_k(["a", "x", "y"], {"a", "c"}, 3) == 0.5
    assert recall_at_k(["x", "y"], {"a"}, 3) == 0.0
    assert recall_at_k([], set(), 3) == 0.0


def test_recall_respects_k():
    # relevant item sits at rank 3 but k=2 → not counted
    assert recall_at_k(["x", "y", "a"], {"a"}, 2) == 0.0
    assert recall_at_k(["x", "y", "a"], {"a"}, 3) == 1.0


def test_reciprocal_rank():
    assert reciprocal_rank(["a", "b"], {"a"}) == 1.0
    assert reciprocal_rank(["x", "a"], {"a"}) == 0.5
    assert reciprocal_rank(["x", "y"], {"a"}) == 0.0


def test_ndcg_at_k():
    # perfect ranking → 1.0
    assert ndcg_at_k(["a", "b"], {"a", "b"}, 2) == 1.0
    # single relevant at rank 1 → 1.0
    assert ndcg_at_k(["a", "x"], {"a"}, 2) == 1.0
    # single relevant at rank 2 → 1/log2(3) normalised by ideal (1.0) ≈ 0.6309
    assert abs(ndcg_at_k(["x", "a"], {"a"}, 2) - 0.6309) < 1e-3
    assert ndcg_at_k(["x"], set(), 2) == 0.0


class _FakeChunk:
    def __init__(self, source):
        self.chunk = Chunk(id="i", text="t", source=source, metadata={})


class _FakeRAG:
    """retrieve() returns hits whose sources come from a fixed map."""

    def __init__(self, mapping):
        self._mapping = mapping

    def retrieve(self, question, k=5):
        sources = self._mapping.get(question, [])[:k]
        return [Hit(chunk=Chunk(id="i", text="t", source=s, metadata={}), score=1.0)
                for s in sources]


def test_evaluate_retrieval_aggregates():
    rag = _FakeRAG({
        "q1": ["docA.md", "docB.md"],   # relevant docA at rank 1
        "q2": ["docX.md", "docY.md"],   # relevant docY at rank 2
    })
    dataset = [
        {"question": "q1", "relevant": ["docA.md"]},
        {"question": "q2", "relevant": ["docY.md"]},
    ]
    m = evaluate_retrieval(rag, dataset, k=5)
    assert m.n == 2
    assert m.recall_at_k == 1.0           # both found within k
    assert abs(m.mrr - 0.75) < 1e-9       # (1.0 + 0.5) / 2
    assert 0.0 < m.ndcg_at_k <= 1.0


def test_evaluate_skips_items_without_relevant():
    rag = _FakeRAG({"q1": ["a.md"]})
    dataset = [
        {"question": "q1", "relevant": ["a.md"]},
        {"question": "q2", "relevant": []},      # skipped
        {"question": "", "relevant": ["b.md"]},  # skipped
    ]
    m = evaluate_retrieval(rag, dataset, k=5)
    assert m.n == 1


def test_passes_gate():
    rag = _FakeRAG({"q1": ["a.md"]})
    m = evaluate_retrieval(rag, [{"question": "q1", "relevant": ["a.md"]}], k=5)
    ok, failures = passes_gate(m, {"recall_at_k": 0.8, "mrr": 0.7})
    assert ok and failures == []
    ok2, failures2 = passes_gate(m, {"recall_at_k": 1.1})  # impossible threshold
    assert not ok2 and failures2
