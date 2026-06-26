"""Reranker adapters — cross-encoders and ColBERT."""

from __future__ import annotations

from perfectrag.core.protocols import Reranker

SUPPORTED = [
    "BAAI/bge-reranker-v2-m3",
    "jinaai/jina-reranker-v2-base-multilingual",
    "mixedbread-ai/mxbai-rerank-large-v1",
    "colbert-ir/colbertv2.0",
]


def build(model: str | None, **kwargs) -> Reranker | None:
    if not model or model.lower() in ("none", "null"):
        return None
    if "colbert" in model.lower():
        from perfectrag.core.rerankers.colbert import ColbertReranker
        return ColbertReranker(model=model, **kwargs)
    # BGE / Jina / mxbai all work via sentence-transformers CrossEncoder
    from perfectrag.core.rerankers.cross_encoder import CrossEncoderReranker
    return CrossEncoderReranker(model=model, **kwargs)
