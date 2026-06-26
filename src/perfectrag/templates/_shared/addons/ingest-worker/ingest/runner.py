"""Scheduled crawler: Crawl4AI → chunk → embed (Ollama) → upsert Qdrant.

Runs as a long-lived container. On each cron tick, pulls all configured sources,
dedupes by URL hash stored in /app/state/seen.txt, upserts new chunks.
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import time
import uuid
from datetime import datetime
from pathlib import Path

import httpx
import yaml
from crawl4ai import AsyncWebCrawler
from croniter import croniter
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

CONFIG_PATH = Path(os.environ.get("INGEST_CONFIG", "/app/config.yml"))
STATE_DIR = Path("/app/state")
SEEN_FILE = STATE_DIR / "seen.txt"

OLLAMA_URL = os.environ["OLLAMA_URL"]
QDRANT_URL = os.environ["QDRANT_URL"]
COLLECTION = os.environ.get("QDRANT_COLLECTION", "documents")
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "nomic-embed-text")
CHUNK_SIZE = int(os.environ.get("CHUNK_SIZE", "512"))


def load_config() -> dict:
    return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) or {}


def url_hash(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()[:16]


def load_seen() -> set[str]:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    if not SEEN_FILE.exists():
        return set()
    return set(SEEN_FILE.read_text(encoding="utf-8").splitlines())


def mark_seen(hashes: set[str]) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    with SEEN_FILE.open("a", encoding="utf-8") as f:
        for h in hashes:
            f.write(h + "\n")


def chunk_text(text: str, size: int = CHUNK_SIZE) -> list[str]:
    words = text.split()
    return [" ".join(words[i : i + size]) for i in range(0, len(words), size)]


async def embed(text: str) -> list[float]:
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            f"{OLLAMA_URL}/api/embeddings",
            json={"model": EMBEDDING_MODEL, "prompt": text},
        )
        r.raise_for_status()
        return r.json()["embedding"]


async def crawl_and_index(urls: list[str], source_name: str, qdrant: QdrantClient) -> int:
    seen = load_seen()
    new_hashes: set[str] = set()
    indexed_chunks = 0

    async with AsyncWebCrawler() as crawler:
        for url in urls:
            h = url_hash(url)
            if h in seen:
                continue
            try:
                result = await crawler.arun(url=url)
            except Exception as e:
                print(f"[crawl fail] {url}: {e}", flush=True)
                continue
            text = getattr(result, "markdown", "") or getattr(result, "text", "")
            if not text:
                continue
            chunks = chunk_text(text)
            if not chunks:
                continue
            points: list[PointStruct] = []
            for chunk in chunks:
                vec = await embed(chunk)
                if COLLECTION not in [c.name for c in qdrant.get_collections().collections]:
                    qdrant.create_collection(
                        collection_name=COLLECTION,
                        vectors_config=VectorParams(size=len(vec), distance=Distance.COSINE),
                    )
                points.append(PointStruct(
                    id=str(uuid.uuid4()),
                    vector=vec,
                    payload={
                        "text": chunk,
                        "source": url,
                        "source_name": source_name,
                        "ingested_at": datetime.utcnow().isoformat(),
                    },
                ))
            qdrant.upsert(collection_name=COLLECTION, points=points)
            indexed_chunks += len(points)
            new_hashes.add(h)
            print(f"[ok] {url}: {len(points)} chunks", flush=True)

    mark_seen(new_hashes)
    return indexed_chunks


async def tick_once() -> None:
    cfg = load_config()
    qdrant = QdrantClient(url=QDRANT_URL)
    total = 0
    for source in cfg.get("sources", []):
        total += await crawl_and_index(
            urls=source.get("urls", []),
            source_name=source.get("name", "unnamed"),
            qdrant=qdrant,
        )
    print(f"[tick] indexed {total} new chunks at {datetime.utcnow().isoformat()}", flush=True)


async def main() -> None:
    cfg = load_config()
    schedule = cfg.get("schedule", "0 */6 * * *")
    print(f"[boot] schedule={schedule}", flush=True)
    # Run once on boot, then follow cron
    await tick_once()
    itr = croniter(schedule, datetime.utcnow())
    while True:
        next_run = itr.get_next(datetime)
        sleep_sec = max(1, int((next_run - datetime.utcnow()).total_seconds()))
        print(f"[sleep] next run at {next_run.isoformat()} ({sleep_sec}s)", flush=True)
        time.sleep(sleep_sec)
        try:
            await tick_once()
        except Exception as e:
            print(f"[error] {e}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
