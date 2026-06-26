"""Ollama HTTP embedder (nomic-embed-text, etc.) — no torch dep."""

from __future__ import annotations

import httpx


class OllamaEmbedder:
    def __init__(self, model: str = "nomic-embed-text", url: str = "http://localhost:11434"):
        self._model = model
        self._url = url.rstrip("/")
        self._dim = 0

    @property
    def dim(self) -> int:
        if self._dim == 0:
            self._dim = len(self.embed("warmup"))
        return self._dim

    def embed(self, text: str) -> list[float]:
        r = httpx.post(f"{self._url}/api/embeddings",
                       json={"model": self._model, "prompt": text}, timeout=60)
        r.raise_for_status()
        return r.json()["embedding"]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [self.embed(t) for t in texts]
