"""Milvus adapter — uses Milvus-Lite (embedded) by default, or remote URL."""

from __future__ import annotations

from perfectrag.core.protocols import Chunk, Hit


class MilvusStore:
    def __init__(self, url: str | None = None, path: str = "./milvus.db"):
        try:
            from pymilvus import MilvusClient
        except ImportError:
            raise RuntimeError("pymilvus not installed. `pip install 'perfectrag[milvus]'`")
        # Milvus-Lite: pass a local file path as URI; remote: full host:port URI
        self._uri = url or path
        self._client = MilvusClient(uri=self._uri)
        self._dims: dict[str, int] = {}

    def ensure_collection(self, name: str, dim: int) -> None:
        if not self._client.has_collection(name):
            self._client.create_collection(collection_name=name, dimension=dim, auto_id=False)
        self._dims[name] = dim

    def upsert(self, collection, chunks, vectors) -> None:
        rows = [
            {"id": int(str(c.id).replace("-", "")[:18] or "0", 16),  # Milvus id needs int; hash
             "vector": v,
             "text": c.text,
             "source": c.source}
            for c, v in zip(chunks, vectors)
        ]
        self._client.insert(collection_name=collection, data=rows)

    def search(self, collection, query_vec, k=5):
        res = self._client.search(
            collection_name=collection,
            data=[query_vec],
            limit=k,
            output_fields=["text", "source"],
        )
        hits: list[Hit] = []
        for row in res[0] if res else []:
            ent = row.get("entity") or {}
            hits.append(Hit(
                chunk=Chunk(
                    id=str(row.get("id", "")),
                    text=ent.get("text", ""),
                    source=ent.get("source", ""),
                    metadata={},
                ),
                score=1.0 - float(row.get("distance", 0)),
            ))
        return hits

    def delete_collection(self, name) -> None:
        self._client.drop_collection(name)

    def list_collections(self) -> list[str]:
        return list(self._client.list_collections())
