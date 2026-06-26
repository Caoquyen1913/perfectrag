"""Google Drive → Qdrant sync. Uses service-account JSON to list files in a folder,
exports Google Docs/Sheets/Slides as text, embeds, upserts.
"""

from __future__ import annotations

import hashlib
import io
import os
import time
import uuid
from datetime import datetime
from pathlib import Path

import httpx
from croniter import croniter
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
FOLDER_ID = os.environ.get("GDRIVE_FOLDER_ID")  # root if None
OLLAMA_URL = os.environ["OLLAMA_URL"]
QDRANT_URL = os.environ["QDRANT_URL"]
COLLECTION = os.environ.get("QDRANT_COLLECTION", "documents")
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "nomic-embed-text")
SCHEDULE = os.environ.get("SYNC_SCHEDULE", "0 */6 * * *")
STATE = Path("/app/state/gdrive-seen.txt")

creds = service_account.Credentials.from_service_account_file("/app/sa.json", scopes=SCOPES)
drive = build("drive", "v3", credentials=creds)

EXPORT_MIME = {
    "application/vnd.google-apps.document":     "text/plain",
    "application/vnd.google-apps.spreadsheet":  "text/csv",
    "application/vnd.google-apps.presentation": "text/plain",
}


def seen() -> set[str]:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    return set(STATE.read_text().splitlines()) if STATE.exists() else set()


def mark(sigs: set[str]) -> None:
    with STATE.open("a", encoding="utf-8") as f:
        for s in sigs:
            f.write(s + "\n")


def fetch_text(file_meta: dict) -> str:
    mime = file_meta["mimeType"]
    file_id = file_meta["id"]
    if mime in EXPORT_MIME:
        req = drive.files().export_media(fileId=file_id, mimeType=EXPORT_MIME[mime])
    elif mime == "text/plain" or mime.startswith("text/"):
        req = drive.files().get_media(fileId=file_id)
    else:
        return ""  # skip binary
    buf = io.BytesIO()
    dl = MediaIoBaseDownload(buf, req)
    done = False
    while not done:
        _, done = dl.next_chunk()
    return buf.getvalue().decode("utf-8", errors="ignore")


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
    q = f"'{FOLDER_ID}' in parents and trashed=false" if FOLDER_ID else "trashed=false"
    page_token: str | None = None
    while True:
        resp = drive.files().list(
            q=q, pageSize=100, pageToken=page_token,
            fields="nextPageToken, files(id,name,mimeType,modifiedTime)",
        ).execute()
        for f in resp.get("files", []):
            sig = hashlib.sha256(f"{f['id']}-{f.get('modifiedTime','')}".encode()).hexdigest()[:16]
            if sig in seen_set:
                continue
            text = fetch_text(f)
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
                payload={"text": text[:8000], "source": f"gdrive://{f['id']}/{f['name']}",
                         "ingested_at": datetime.utcnow().isoformat()},
            )])
            indexed += 1
            new_sigs.add(sig)
            print(f"[gdrive] indexed {f['name']}", flush=True)
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    mark(new_sigs)
    return indexed


def main() -> None:
    print(f"[boot] gdrive-sync schedule={SCHEDULE}", flush=True)
    print(f"[tick] indexed {sync_once()} files", flush=True)
    it = croniter(SCHEDULE, datetime.utcnow())
    while True:
        next_run = it.get_next(datetime)
        time.sleep(max(1, int((next_run - datetime.utcnow()).total_seconds())))
        try:
            print(f"[tick] indexed {sync_once()} files", flush=True)
        except Exception as e:
            print(f"[error] {e}", flush=True)


if __name__ == "__main__":
    main()
