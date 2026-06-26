"""LanceDB adapter — embedded columnar vector store."""

from __future__ import annotations

from perfectrag.core.protocols import Chunk, Hit


class LanceDBStore:
    def __init__(self, path: str = "./lancedb", url: str | None = None):
        try:
            import lancedb
        except ImportError:
            raise RuntimeError("lancedb not installed. `pip install 'perfectrag[lancedb]'`")
        self._db = lancedb.connect(path)
        self._dims: dict[str, int] = {}

    def ensure_collection(self, name, dim) -> None:
        self._dims[name] = dim  # tables created lazily on first upsert

    def upsert(self, collection, chunks, vectors) -> None:
        rows = [
            {"id": c.id, "vector": v, "text": c.text, "source": c.source, "metadata": c.metadata}
            for c, v in zip(chunks, vectors)
        ]
        if collection in self._db.table_names():
            t = self._db.open_table(collection)
            t.add(rows)
        else:
            self._db.create_table(collection, data=rows)

    def search(self, collection, query_vec, k=5):
        t = self._db.open_table(collection)
        res = t.search(query_vec).limit(k).to_list()
        return [
            Hit(
                chunk=Chunk(id=r["id"], text=r["text"], source=r["source"], metadata=r.get("metadata") or {}),
                score=1.0 - float(r.get("_distance", 0)),
            ) for r in res
        ]

    def delete_collection(self, name) -> None:
        if name in self._db.table_names():
            self._db.drop_table(name)

    def list_collections(self) -> list[str]:
        return list(self._db.table_names())
