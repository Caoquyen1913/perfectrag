"""OpenAI-compatible embeddings API (OpenAI, LiteLLM proxy, etc.)."""

from __future__ import annotations

import httpx

from perfectrag import keys as _keys


class OpenAIEmbedder:
    def __init__(
        self,
        model: str = "text-embedding-3-small",
        api_base: str = "https://api.openai.com/v1",
        api_key_name: str = "openai",
    ):
        self._model = model
        self._url = api_base.rstrip("/")
        self._key = _keys.get_key(api_key_name)
        if not self._key:
            raise RuntimeError(f"{api_key_name} API key missing.")
        self._dim = 0

    @property
    def dim(self) -> int:
        if self._dim == 0:
            self._dim = len(self.embed("warmup"))
        return self._dim

    def embed(self, text: str) -> list[float]:
        return self.embed_batch([text])[0]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        r = httpx.post(
            f"{self._url}/embeddings",
            headers={"Authorization": f"Bearer {self._key}"},
            json={"model": self._model, "input": texts},
            timeout=60,
        )
        r.raise_for_status()
        return [row["embedding"] for row in r.json()["data"]]
