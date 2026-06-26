"""Anthropic Claude via anthropic SDK."""

from __future__ import annotations

from collections.abc import Iterator

from perfectrag import keys as _keys


class AnthropicLLM:
    def __init__(self, model: str = "claude-opus-4-7", max_tokens: int = 1024, **params):
        try:
            import anthropic
        except ImportError:
            raise RuntimeError("anthropic not installed. `pip install anthropic`")
        api_key = _keys.get_key("anthropic")
        if not api_key:
            raise RuntimeError("Anthropic API key missing. `perfectrag add key anthropic <key>`")
        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model
        self._max_tokens = max_tokens
        self._params = params

    def generate(self, prompt: str, **kw) -> str:
        msg = self._client.messages.create(
            model=self._model,
            max_tokens=kw.pop("max_tokens", self._max_tokens),
            messages=[{"role": "user", "content": prompt}],
            **{**self._params, **kw},
        )
        return msg.content[0].text if msg.content else ""

    def stream(self, prompt: str, **kw) -> Iterator[str]:
        with self._client.messages.stream(
            model=self._model,
            max_tokens=kw.pop("max_tokens", self._max_tokens),
            messages=[{"role": "user", "content": prompt}],
            **{**self._params, **kw},
        ) as s:
            for text in s.text_stream:
                yield text
