"""Gemini via google-generativeai."""

from __future__ import annotations

from collections.abc import Iterator

from perfectrag import keys as _keys


class GeminiLLM:
    def __init__(self, model: str = "gemini-2.5-flash", **params):
        try:
            import google.generativeai as genai
        except ImportError:
            raise RuntimeError("google-generativeai not installed. `pip install 'perfectrag[advisor]'`")
        api_key = _keys.get_key("gemini")
        if not api_key:
            raise RuntimeError("Gemini API key missing. `perfectrag add key gemini <key>`")
        genai.configure(api_key=api_key)
        self._genai = genai
        self._model_name = model
        self._model = genai.GenerativeModel(model)
        self._params = params

    def generate(self, prompt: str, **kw) -> str:
        resp = self._model.generate_content(prompt, generation_config={**self._params, **kw})
        return resp.text

    def stream(self, prompt: str, **kw) -> Iterator[str]:
        for chunk in self._model.generate_content(prompt, stream=True, generation_config={**self._params, **kw}):
            if chunk.text:
                yield chunk.text
