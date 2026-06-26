"""Reciprocal Rank Fusion (RRF) — merge several ranked lists into one.

The standard, parameter-light way to combine results from multiple retrievers or
multiple query variants (dense + sparse, or original + rewritten queries). Each
item's fused score is sum(1 / (k + rank)) across the lists it appears in.
"""

from __future__ import annotations


def reciprocal_rank_fusion(rankings: list[list[str]], k: int = 60) -> list[str]:
    """Fuse ranked id-lists into a single ranking (best first).

    `rankings` is a list of ranked lists of ids (rank 0 = top). `k` damps the
    contribution of low ranks (60 is the common default). Ids are returned in
    descending fused score; ties keep first-seen order.
    """
    scores: dict[str, float] = {}
    order: list[str] = []
    for ranking in rankings:
        for rank, item in enumerate(ranking):
            if item not in scores:
                scores[item] = 0.0
                order.append(item)
            scores[item] += 1.0 / (k + rank + 1)
    return sorted(order, key=lambda i: scores[i], reverse=True)
