"""Notion → Qdrant sync. Pulls all pages the integration has access to, dedupes by
page ID + last_edited_time. Runs on a cron schedule.
"""

from __future__ import annotations

import hashlib
import os
import time
import uuid
from datetime import datetime
from pathlib import Path

import httpx
from croniter import croniter
from notion_client import Client
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

NOTION = Client(auth=os.environ["NOTION_API_KEY"])
OLLAMA_URL = os.environ["OLLAMA_URL"]
QDRANT_URL = os.environ["QDRANT_URL"]
COLLECTION = os.environ.get("QDRANT_COLLECTION", "documents")
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "nomic-embed-text")
SCHEDULE = os.environ.get("SYNC_SCHEDULE", "0 */6 * * *")
STATE = Path("/app/state/notion-seen.txt")


def seen() -> set[str]:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    return set(STATE.read_text().splitlines()) if STATE.exists() else set()


def mark(sigs: set[str]) -> None:
    with STATE.open("a", encoding="utf-8") as f:
        for s in sigs:
            f.write(s + "\n")


def block_to_text(block: dict) -> str:
    t = block.get("type")
    content = block.get(t, {})
    rich = content.get("rich_text") or content.get("text") or []
    return " ".join(r.get("plain_text", "") for r in rich if isinstance(r, dict))


def page_text(page_id: str) -> str:
    parts: list[str] = []
    cursor: str | None = None
    while True:
        resp = NOTION.blocks.children.list(block_id=page_id, start_cursor=cursor, page_size=100)
        for b in resp.get("results", []):
            parts.append(block_to_text(b))
        if not resp.get("has_more"):
            break
        cursor = resp.get("next_cursor")
    return "\n".join(p for p in parts if p)


def embed(text: str) -> list[float]:
    with httpx.Client(timeout=60) as c:
        r = c.post(f"{OLLAMA_URL}/api/embeddings",
                   json={"model": EMBEDDING_MODEL, "prompt": text})
        r.raise_for_status()
        return r.json()["embedding"]


def sync_once() -> int:
    qdrant = QdrantClient(url=QDRANT_URL)
    seen_set = seen()
    new_sigs: set[str] = set()
    indexed = 0
    cursor: str | None = None
    while True:
        resp = NOTION.search(filter={"property": "object", "value": "page"},
                             start_cursor=cursor, page_size=50)
        for page in resp.get("results", []):
            sig = hashlib.sha256(
                f"{page['id']}-{page.get('last_edited_time','')}".encode()
            ).hexdigest()[:16]
            if sig in seen_set:
                continue
            text = page_text(page["id"])
            if not text.strip():
                continue
            vec = embed(text)
            if COLLECTION not in [c.name for c in qdrant.get_collections().collections]:
                qdrant.create_collection(
                    collection_name=COLLECTION,
                    vectors_config=VectorParams(size=len(vec), distance=Distance.COSINE),
                )
            qdrant.upsert(collection_name=COLLECTION, points=[PointStruct(
                id=str(uuid.uuid4()),
                vector=vec,
                payload={"text": text[:8000], "source": f"notion://{page['id']}",
                         "ingested_at": datetime.utcnow().isoformat()},
            )])
            indexed += 1
            new_sigs.add(sig)
            print(f"[notion] indexed {page['id']}", flush=True)
        if not resp.get("has_more"):
            break
        cursor = resp.get("next_cursor")
    mark(new_sigs)
    return indexed


def main() -> None:
    print(f"[boot] notion-sync schedule={SCHEDULE}", flush=True)
    print(f"[tick] indexed {sync_once()} pages", flush=True)
    it = croniter(SCHEDULE, datetime.utcnow())
    while True:
        next_run = it.get_next(datetime)
        time.sleep(max(1, int((next_run - datetime.utcnow()).total_seconds())))
        try:
            print(f"[tick] indexed {sync_once()} pages", flush=True)
        except Exception as e:
            print(f"[error] {e}", flush=True)


if __name__ == "__main__":
    main()
