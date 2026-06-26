"""In-process llama.cpp via llama-cpp-python."""

from __future__ import annotations

from collections.abc import Iterator


class LlamaCppLLM:
    def __init__(self, model: str, n_ctx: int = 4096, n_gpu_layers: int = -1, **params):
        """`model` is either a local .gguf path or a Hugging Face repo_id."""
        try:
            from llama_cpp import Llama
        except ImportError:
            raise RuntimeError("llama-cpp-python not installed. `pip install 'perfectrag[llamacpp]'`")
        if model.endswith(".gguf"):
            self._llm = Llama(model_path=model, n_ctx=n_ctx, n_gpu_layers=n_gpu_layers, verbose=False, **params)
        else:
            # HF repo_id like "TheBloke/qwen2.5-7b-gguf"
            self._llm = Llama.from_pretrained(repo_id=model, n_ctx=n_ctx, n_gpu_layers=n_gpu_layers,
                                              verbose=False, **params)

    def generate(self, prompt: str, max_tokens: int = 512, **kw) -> str:
        out = self._llm(prompt, max_tokens=max_tokens, **kw)
        return out["choices"][0]["text"]

    def stream(self, prompt: str, max_tokens: int = 512, **kw) -> Iterator[str]:
        for tok in self._llm(prompt, max_tokens=max_tokens, stream=True, **kw):
            yield tok["choices"][0]["text"]
