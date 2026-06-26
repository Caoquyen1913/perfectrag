"""Retrieval-quality metrics and a CI quality gate.

These measure *retrieval* (did we fetch the right chunks?) separately from
*generation* (was the answer faithful?). Generation/faithfulness is covered by
the RAGAS/DeepEval `eval` addon; this module is deterministic, needs no LLM, and
is meant to gate a build: feed it a golden set of (question -> relevant sources)
and assert recall/MRR/nDCG stay above thresholds.

    from perfectrag.core.evaluation import evaluate_retrieval, passes_gate
    m = evaluate_retrieval(rag, dataset, k=5)
    ok, failures = passes_gate(m, {"recall_at_k": 0.8, "mrr": 0.7})
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Protocol

from perfectrag.core.protocols import Hit


@dataclass
class RetrievalMetrics:
    recall_at_k: float
    mrr: float
    ndcg_at_k: float
    k: int
    n: int  # number of evaluated queries

    def as_dict(self) -> dict[str, float | int]:
        return {
            "recall_at_k": round(self.recall_at_k, 4),
            "mrr": round(self.mrr, 4),
            "ndcg_at_k": round(self.ndcg_at_k, 4),
            "k": self.k,
            "n": self.n,
        }


def recall_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    """Fraction of relevant items present in the top-k retrieved."""
    if not relevant:
        return 0.0
    top = retrieved[:k]
    found = sum(1 for r in relevant if r in top)
    return found / len(relevant)


def reciprocal_rank(retrieved: list[str], relevant: set[str]) -> float:
    """1 / (rank of first relevant item), or 0 if none retrieved."""
    for i, doc in enumerate(retrieved, start=1):
        if doc in relevant:
            return 1.0 / i
    return 0.0


def ndcg_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    """Binary-relevance nDCG@k."""
    if not relevant:
        return 0.0
    dcg = 0.0
    for i, doc in enumerate(retrieved[:k], start=1):
        if doc in relevant:
            dcg += 1.0 / math.log2(i + 1)
    ideal_hits = min(len(relevant), k)
    idcg = sum(1.0 / math.log2(i + 1) for i in range(1, ideal_hits + 1))
    return dcg / idcg if idcg else 0.0


class _Retriever(Protocol):
    def retrieve(self, question: str, k: int | None = ...) -> list[Hit]: ...


def evaluate_retrieval(
    rag: _Retriever, dataset: list[dict[str, Any]], k: int = 5
) -> RetrievalMetrics:
    """Run each dataset query through `rag.retrieve` and average the metrics.

    dataset items: {"question": str, "relevant": [source, ...]}. A retrieved
    chunk counts as relevant when its `source` is in the item's relevant set.
    """
    recalls, rrs, ndcgs = [], [], []
    evaluated = 0
    for item in dataset:
        question = item.get("question")
        relevant = set(item.get("relevant") or [])
        if not question or not relevant:
            continue
        hits = rag.retrieve(question, k)
        retrieved = [h.chunk.source for h in hits]
        recalls.append(recall_at_k(retrieved, relevant, k))
        rrs.append(reciprocal_rank(retrieved, relevant))
        ndcgs.append(ndcg_at_k(retrieved, relevant, k))
        evaluated += 1

    def _avg(xs: list[float]) -> float:
        return sum(xs) / len(xs) if xs else 0.0

    return RetrievalMetrics(
        recall_at_k=_avg(recalls),
        mrr=_avg(rrs),
        ndcg_at_k=_avg(ndcgs),
        k=k,
        n=evaluated,
    )


def passes_gate(metrics: RetrievalMetrics, thresholds: dict[str, float]) -> tuple[bool, list[str]]:
    """Return (ok, failures). Each threshold key maps to a RetrievalMetrics field;
    a metric below its threshold is a failure. Unknown keys are ignored."""
    failures: list[str] = []
    values = metrics.as_dict()
    for key, minimum in thresholds.items():
        actual = values.get(key)
        if actual is None:
            continue
        if actual < minimum:
            failures.append(f"{key}={actual:.3f} < {minimum:.3f}")
    return (not failures), failures
