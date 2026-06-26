"""Qdrant adapter — works with remote Qdrant server or embedded (`:memory:` / local path)."""

from __future__ import annotations

from perfectrag.core.protocols import Chunk, Hit


class QdrantStore:
    def __init__(self, url: str | None = None, path: str | None = None):
        try:
            from qdrant_client import QdrantClient
        except ImportError:
            raise RuntimeError("qdrant-client not installed. `pip install 'perfectrag[qdrant]'`")
        if url:
            self._client = QdrantClient(url=url)
        elif path:
            self._client = QdrantClient(path=path)
        else:
            self._client = QdrantClient(":memory:")

    def ensure_collection(self, name: str, dim: int) -> None:
        from qdrant_client.models import Distance, VectorParams

        existing = [c.name for c in self._client.get_collections().collections]
        if name not in existing:
            self._client.create_collection(
                collection_name=name,
                vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
            )

    def upsert(self, collection: str, chunks, vectors):
        from qdrant_client.models import PointStruct

        points = [
            PointStruct(
                id=c.id,
                vector=v,
                payload={"text": c.text, "source": c.source, **c.metadata},
            )
            for c, v in zip(chunks, vectors)
        ]
        self._client.upsert(collection_name=collection, points=points)

    def search(self, collection: str, query_vec, k: int = 5) -> list[Hit]:
        hits = self._client.search(collection_name=collection, query_vector=query_vec, limit=k)
        out: list[Hit] = []
        for h in hits:
            payload = h.payload or {}
            out.append(Hit(
                chunk=Chunk(
                    id=str(h.id),
                    text=payload.get("text", ""),
                    source=payload.get("source", ""),
                    metadata={k: v for k, v in payload.items() if k not in ("text", "source")},
                ),
                score=h.score,
            ))
        return out

    def delete_collection(self, name: str) -> None:
        self._client.delete_collection(name)

    def list_collections(self) -> list[str]:
        return [c.name for c in self._client.get_collections().collections]
