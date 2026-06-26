"""Adapter protocols for stores / embeddings / rerankers / LLMs / parsers."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass
class Chunk:
    id: str
    text: str
    source: str
    metadata: dict


@dataclass
class Hit:
    chunk: Chunk
    score: float


@runtime_checkable
class VectorStore(Protocol):
    def ensure_collection(self, name: str, dim: int) -> None: ...
    def upsert(self, collection: str, chunks: list[Chunk], vectors: list[list[float]]) -> None: ...
    def search(self, collection: str, query_vec: list[float], k: int) -> list[Hit]: ...
    def delete_collection(self, name: str) -> None: ...
    def list_collections(self) -> list[str]: ...


@runtime_checkable
class Embedder(Protocol):
    @property
    def dim(self) -> int: ...
    def embed(self, text: str) -> list[float]: ...
    def embed_batch(self, texts: list[str]) -> list[list[float]]: ...


@runtime_checkable
class Reranker(Protocol):
    def rerank(self, query: str, docs: list[str], top_k: int = 5) -> list[tuple[int, float]]:
        """Return list of (doc_index, score) sorted descending."""


@runtime_checkable
class LLM(Protocol):
    def generate(self, prompt: str, **kwargs) -> str: ...
    def stream(self, prompt: str, **kwargs) -> Iterator[str]: ...


@runtime_checkable
class Parser(Protocol):
    def parse(self, path: str) -> str:
        """Extract text from file at `path` and return as a single string."""
