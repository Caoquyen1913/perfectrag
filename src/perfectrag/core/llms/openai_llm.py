"""OpenAI-compatible chat (OpenAI, Groq, LiteLLM proxy, etc.)."""

from __future__ import annotations

from collections.abc import Iterator

import httpx

from perfectrag import keys as _keys


class OpenAILLM:
    def __init__(
        self,
        model: str = "gpt-4o-mini",
        api_base: str = "https://api.openai.com/v1",
        api_key_name: str = "openai",
        **params,
    ):
        self._model = model
        self._url = api_base.rstrip("/")
        self._key = _keys.get_key(api_key_name)
        if not self._key:
            raise RuntimeError(f"{api_key_name} API key missing.")
        self._params = params

    def generate(self, prompt: str, **kw) -> str:
        r = httpx.post(
            f"{self._url}/chat/completions",
            headers={"Authorization": f"Bearer {self._key}"},
            json={
                "model": self._model,
                "messages": [{"role": "user", "content": prompt}],
                **self._params, **kw,
            },
            timeout=300,
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]

    def stream(self, prompt: str, **kw) -> Iterator[str]:
        import json

        with httpx.stream(
            "POST", f"{self._url}/chat/completions",
            headers={"Authorization": f"Bearer {self._key}"},
            json={
                "model": self._model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": True,
                **self._params, **kw,
            },
            timeout=300,
        ) as r:
            r.raise_for_status()
            for line in r.iter_lines():
                if not line or not line.startswith("data: "):
                    continue
                payload = line[len("data: "):]
                if payload.strip() == "[DONE]":
                    break
                try:
                    chunk = json.loads(payload)
                    delta = chunk["choices"][0]["delta"].get("content", "")
                    if delta:
                        yield delta
                except (json.JSONDecodeError, KeyError):
                    continue
