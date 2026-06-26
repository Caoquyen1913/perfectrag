"""Embedding adapters. sentence-transformers handles most local models; others HTTP-based."""

from __future__ import annotations

from perfectrag.core.protocols import Embedder

SUPPORTED = {
    "BAAI/bge-m3": "sentence_transformers",
    "nomic-embed-text": "ollama",
    "nomic-ai/nomic-embed-text-v1.5": "sentence_transformers",
    "jinaai/jina-embeddings-v3": "sentence_transformers",
    "intfloat/e5-large-v2": "sentence_transformers",
    "Qwen/Qwen3-Embedding-0.6B": "sentence_transformers",
}


def build(model: str, backend: str | None = None, **kwargs) -> Embedder:
    backend = backend or SUPPORTED.get(model, "sentence_transformers")
    if backend == "sentence_transformers":
        from perfectrag.core.embeddings.st import STEmbedder
        return STEmbedder(model=model, **kwargs)
    if backend == "ollama":
        from perfectrag.core.embeddings.ollama import OllamaEmbedder
        return OllamaEmbedder(model=model, **kwargs)
    if backend == "jina_api":
        from perfectrag.core.embeddings.jina_api import JinaAPIEmbedder
        return JinaAPIEmbedder(model=model, **kwargs)
    if backend == "openai":
        from perfectrag.core.embeddings.openai_api import OpenAIEmbedder
        return OpenAIEmbedder(model=model, **kwargs)
    raise ValueError(f"Unknown embedding backend: {backend}")
