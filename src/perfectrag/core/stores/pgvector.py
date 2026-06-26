"""pgvector adapter — reuse an existing Postgres with the pgvector extension."""

from __future__ import annotations

import json

from perfectrag.core.protocols import Chunk, Hit


class PgVectorStore:
    def __init__(self, url: str):
        try:
            import psycopg
        except ImportError:
            raise RuntimeError("psycopg not installed. `pip install 'perfectrag[pgvector]'`")
        self._conn = psycopg.connect(url, autocommit=True)
        with self._conn.cursor() as cur:
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector")

    def ensure_collection(self, name, dim) -> None:
        with self._conn.cursor() as cur:
            cur.execute(
                f"CREATE TABLE IF NOT EXISTS {name} "
                f"(id text primary key, vector vector({dim}), text text, source text, metadata jsonb)"
            )

    def upsert(self, collection, chunks, vectors) -> None:
        with self._conn.cursor() as cur:
            for c, v in zip(chunks, vectors):
                cur.execute(
                    f"INSERT INTO {collection} (id, vector, text, source, metadata) "
                    f"VALUES (%s, %s, %s, %s, %s) "
                    f"ON CONFLICT (id) DO UPDATE SET vector=EXCLUDED.vector, text=EXCLUDED.text",
                    (c.id, str(v), c.text, c.source, json.dumps(c.metadata)),
                )

    def search(self, collection, query_vec, k=5):
        with self._conn.cursor() as cur:
            cur.execute(
                f"SELECT id, text, source, metadata, vector <=> %s::vector AS dist "
                f"FROM {collection} ORDER BY dist ASC LIMIT %s",
                (str(query_vec), k),
            )
            rows = cur.fetchall()
        return [
            Hit(
                chunk=Chunk(id=r[0], text=r[1], source=r[2], metadata=r[3] or {}),
                score=1.0 - float(r[4]),
            ) for r in rows
        ]

    def delete_collection(self, name) -> None:
        with self._conn.cursor() as cur:
            cur.execute(f"DROP TABLE IF EXISTS {name}")

    def list_collections(self) -> list[str]:
        with self._conn.cursor() as cur:
            cur.execute("SELECT tablename FROM pg_tables WHERE schemaname='public'")
            return [r[0] for r in cur.fetchall()]
