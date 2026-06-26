"""LLM adapters — 6 providers, lazy imports."""

from __future__ import annotations

from perfectrag.core.protocols import LLM

SUPPORTED = ["ollama", "llamacpp", "vllm", "gemini", "anthropic", "openai"]


def build(runtime: str, model: str, **kwargs) -> LLM:
    runtime = runtime.lower()
    if runtime == "ollama":
        from perfectrag.core.llms.ollama import OllamaLLM
        return OllamaLLM(model=model, **kwargs)
    if runtime == "llamacpp":
        from perfectrag.core.llms.llamacpp import LlamaCppLLM
        return LlamaCppLLM(model=model, **kwargs)
    if runtime == "vllm":
        from perfectrag.core.llms.vllm_http import VLLMClient
        return VLLMClient(model=model, **kwargs)
    if runtime == "gemini":
        from perfectrag.core.llms.gemini import GeminiLLM
        return GeminiLLM(model=model, **kwargs)
    if runtime == "anthropic":
        from perfectrag.core.llms.anthropic_llm import AnthropicLLM
        return AnthropicLLM(model=model, **kwargs)
    if runtime == "openai":
        from perfectrag.core.llms.openai_llm import OpenAILLM
        return OpenAILLM(model=model, **kwargs)
    raise ValueError(f"Unknown LLM runtime: {runtime}. Supported: {SUPPORTED}")
