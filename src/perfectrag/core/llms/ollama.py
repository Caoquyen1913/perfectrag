"""Ollama HTTP LLM."""

from __future__ import annotations

import json
from collections.abc import Iterator

import httpx


class OllamaLLM:
    def __init__(self, model: str, url: str = "http://localhost:11434", **params):
        self._model = model
        self._url = url.rstrip("/")
        self._params = params

    def generate(self, prompt: str, **kw) -> str:
        r = httpx.post(
            f"{self._url}/api/generate",
            json={"model": self._model, "prompt": prompt, "stream": False, **self._params, **kw},
            timeout=300,
        )
        r.raise_for_status()
        return r.json()["response"]

    def stream(self, prompt: str, **kw) -> Iterator[str]:
        with httpx.stream(
            "POST", f"{self._url}/api/generate",
            json={"model": self._model, "prompt": prompt, "stream": True, **self._params, **kw},
            timeout=300,
        ) as r:
            r.raise_for_status()
            for line in r.iter_lines():
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    tok = data.get("response")
                    if tok:
                        yield tok
                except json.JSONDecodeError:
                    continue
