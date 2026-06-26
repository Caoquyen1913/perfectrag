"""sentence-transformers wrapper — covers BGE, nomic, Jina, E5, Qwen."""

from __future__ import annotations


class STEmbedder:
    def __init__(self, model: str, device: str | None = None):
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError:
            raise RuntimeError("sentence-transformers not installed. `pip install 'perfectrag[embed-torch]'`")
        self._model = SentenceTransformer(model, device=device, trust_remote_code=True)
        self._dim = self._model.get_sentence_embedding_dimension() or 0

    @property
    def dim(self) -> int:
        return self._dim

    def embed(self, text: str) -> list[float]:
        return self.embed_batch([text])[0]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        vecs = self._model.encode(texts, convert_to_numpy=True, normalize_embeddings=True)
        return vecs.tolist()
