"""vLLM OpenAI-compatible HTTP client."""

from __future__ import annotations

from collections.abc import Iterator

import httpx


class VLLMClient:
    def __init__(self, model: str, url: str = "http://localhost:8000", **params):
        self._model = model
        self._url = url.rstrip("/")
        self._params = params

    def generate(self, prompt: str, **kw) -> str:
        r = httpx.post(
            f"{self._url}/v1/completions",
            json={"model": self._model, "prompt": prompt, "stream": False, **self._params, **kw},
            timeout=300,
        )
        r.raise_for_status()
        return r.json()["choices"][0]["text"]

    def stream(self, prompt: str, **kw) -> Iterator[str]:
        import json

        with httpx.stream(
            "POST", f"{self._url}/v1/completions",
            json={"model": self._model, "prompt": prompt, "stream": True, **self._params, **kw},
            timeout=300,
        ) as r:
            r.raise_for_status()
            for line in r.iter_lines():
                if not line or not line.startswith("data: "):
                    continue
                payload = line[len("data: "):]
                if payload == "[DONE]":
                    break
                try:
                    data = json.loads(payload)
                    yield data["choices"][0]["text"]
                except (json.JSONDecodeError, KeyError):
                    continue
