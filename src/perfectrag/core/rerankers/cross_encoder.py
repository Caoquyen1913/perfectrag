"""CrossEncoder-based reranker — covers BGE, Jina, mxbai."""

from __future__ import annotations


class CrossEncoderReranker:
    def __init__(self, model: str, device: str | None = None):
        try:
            from sentence_transformers import CrossEncoder
        except ImportError:
            raise RuntimeError("sentence-transformers required. `pip install 'perfectrag[embed-torch]'`")
        self._model = CrossEncoder(model, device=device, trust_remote_code=True)

    def rerank(self, query: str, docs: list[str], top_k: int = 5) -> list[tuple[int, float]]:
        if not docs:
            return []
        pairs = [(query, d) for d in docs]
        scores = self._model.predict(pairs)
        ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
        return [(i, float(s)) for i, s in ranked[:top_k]]
