"""Chroma adapter — always embedded (file-backed or in-memory)."""

from __future__ import annotations

from perfectrag.core.protocols import Chunk, Hit


class ChromaStore:
    def __init__(self, path: str | None = None, url: str | None = None):
        try:
            import chromadb
        except ImportError:
            raise RuntimeError("chromadb not installed. `pip install 'perfectrag[chroma]'`")
        if url:
            host, _, port = url.replace("http://", "").partition(":")
            self._client = chromadb.HttpClient(host=host or "localhost", port=int(port) if port else 8000)
        elif path:
            self._client = chromadb.PersistentClient(path=path)
        else:
            self._client = chromadb.EphemeralClient()

    def ensure_collection(self, name: str, dim: int) -> None:  # dim not needed for Chroma
        self._client.get_or_create_collection(name=name)

    def upsert(self, collection: str, chunks, vectors) -> None:
        c = self._client.get_or_create_collection(collection)
        c.upsert(
            ids=[x.id for x in chunks],
            embeddings=vectors,
            documents=[x.text for x in chunks],
            metadatas=[{"source": x.source, **x.metadata} for x in chunks],
        )

    def search(self, collection: str, query_vec, k: int = 5) -> list[Hit]:
        c = self._client.get_or_create_collection(collection)
        r = c.query(query_embeddings=[query_vec], n_results=k)
        hits: list[Hit] = []
        ids = r["ids"][0] if r.get("ids") else []
        docs = r["documents"][0] if r.get("documents") else []
        metas = r["metadatas"][0] if r.get("metadatas") else []
        dists = r["distances"][0] if r.get("distances") else []
        for i, id_ in enumerate(ids):
            meta = metas[i] or {}
            hits.append(Hit(
                chunk=Chunk(
                    id=id_,
                    text=docs[i],
                    source=meta.get("source", ""),
                    metadata={k: v for k, v in meta.items() if k != "source"},
                ),
                # Chroma returns distance (lower=better); convert to similarity
                score=1.0 - float(dists[i]) if dists else 0.0,
            ))
        return hits

    def delete_collection(self, name: str) -> None:
        self._client.delete_collection(name)

    def list_collections(self) -> list[str]:
        return [c.name for c in self._client.list_collections()]
