"""Vector store adapters. Factory picks implementation by name, imports lazily."""

from __future__ import annotations

from perfectrag.core.protocols import VectorStore

SUPPORTED = ["qdrant", "milvus", "chroma", "lancedb", "pgvector"]


def build(name: str, **kwargs) -> VectorStore:
    name = name.lower()
    if name == "qdrant":
        from perfectrag.core.stores.qdrant import QdrantStore
        return QdrantStore(**kwargs)
    if name == "milvus":
        from perfectrag.core.stores.milvus import MilvusStore
        return MilvusStore(**kwargs)
    if name == "chroma":
        from perfectrag.core.stores.chroma import ChromaStore
        return ChromaStore(**kwargs)
    if name == "lancedb":
        from perfectrag.core.stores.lancedb_store import LanceDBStore
        return LanceDBStore(**kwargs)
    if name == "pgvector":
        from perfectrag.core.stores.pgvector import PgVectorStore
        return PgVectorStore(**kwargs)
    raise ValueError(f"Unknown vector store: {name}. Supported: {SUPPORTED}")
