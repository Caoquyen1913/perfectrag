"""Jina embeddings API (cloud, needs key)."""

from __future__ import annotations

import httpx

from perfectrag import keys as _keys


class JinaAPIEmbedder:
    def __init__(self, model: str = "jina-embeddings-v3", task: str = "retrieval.passage"):
        self._model = model
        self._task = task
        self._key = _keys.get_key("jina")
        if not self._key:
            raise RuntimeError("Jina API key missing. `perfectrag add key jina <key>`.")
        self._dim = 1024  # jina-v3 default

    @property
    def dim(self) -> int:
        return self._dim

    def embed(self, text: str) -> list[float]:
        return self.embed_batch([text])[0]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        r = httpx.post(
            "https://api.jina.ai/v1/embeddings",
            headers={"Authorization": f"Bearer {self._key}"},
            json={"model": self._model, "task": self._task, "input": texts},
            timeout=60,
        )
        r.raise_for_status()
        return [row["embedding"] for row in r.json()["data"]]
