"""ColBERT late-interaction reranker. Fallback to CrossEncoder if ragatouille missing."""

from __future__ import annotations


class ColbertReranker:
    def __init__(self, model: str = "colbert-ir/colbertv2.0"):
        try:
            from ragatouille import RAGPretrainedModel
        except ImportError:
            raise RuntimeError(
                "ragatouille not installed. `pip install 'perfectrag[colbert]'` or pick another reranker."
            )
        self._model = RAGPretrainedModel.from_pretrained(model)

    def rerank(self, query: str, docs: list[str], top_k: int = 5) -> list[tuple[int, float]]:
        if not docs:
            return []
        results = self._model.rerank(query=query, documents=docs, k=top_k)
        return [(r["result_index"], float(r["score"])) for r in results]
