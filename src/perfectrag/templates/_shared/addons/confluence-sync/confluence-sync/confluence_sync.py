"""Confluence → Qdrant sync using atlassian-python-api."""

from __future__ import annotations

import hashlib
import os
import time
import uuid
from datetime import datetime
from pathlib import Path

import httpx
from atlassian import Confluence
from bs4 import BeautifulSoup
from croniter import croniter
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

URL = os.environ["CONFLUENCE_URL"]
USER = os.environ["CONFLUENCE_USER"]
TOKEN = os.environ["CONFLUENCE_API_TOKEN"]
SPACE = os.environ.get("CONFLUENCE_SPACE")
OLLAMA_URL = os.environ["OLLAMA_URL"]
QDRANT_URL = os.environ["QDRANT_URL"]
COLLECTION = os.environ.get("QDRANT_COLLECTION", "documents")
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "nomic-embed-text")
SCHEDULE = os.environ.get("SYNC_SCHEDULE", "0 */6 * * *")
STATE = Path("/app/state/confluence-seen.txt")

confluence = Confluence(url=URL, username=USER, password=TOKEN, cloud=True)


def seen() -> set[str]:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    return set(STATE.read_text().splitlines()) if STATE.exists() else set()


def mark(sigs: set[str]) -> None:
    with STATE.open("a", encoding="utf-8") as f:
        for s in sigs:
            f.write(s + "\n")


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
    start = 0
    while True:
        pages = confluence.get_all_pages_from_space(
            space=SPACE, start=start, limit=50, expand="version,body.storage",
        )
        if not pages:
            break
        for p in pages:
            sig = hashlib.sha256(f"{p['id']}-{p['version']['number']}".encode()).hexdigest()[:16]
            if sig in seen_set:
                continue
            html = p.get("body", {}).get("storage", {}).get("value", "")
            text = BeautifulSoup(html, "html.parser").get_text("\n")
            if not text.strip():
                continue
            vec = embed(text[:8000])
            if COLLECTION not in [c.name for c in qdrant.get_collections().collections]:
                qdrant.create_collection(
                    collection_name=COLLECTION,
                    vectors_config=VectorParams(size=len(vec), distance=Distance.COSINE),
                )
            qdrant.upsert(collection_name=COLLECTION, points=[PointStruct(
                id=str(uuid.uuid4()),
                vector=vec,
                payload={"text": text[:8000], "source": f"confluence://{p['id']}/{p['title']}",
                         "ingested_at": datetime.utcnow().isoformat()},
            )])
            indexed += 1
            new_sigs.add(sig)
            print(f"[confluence] indexed {p['title']}", flush=True)
        start += len(pages)
    mark(new_sigs)
    return indexed


def main() -> None:
    print(f"[boot] confluence-sync schedule={SCHEDULE}", flush=True)
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
