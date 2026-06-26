"""OpenAI-style Query API for a perfectrag project.

Mount endpoints:
- POST /v1/query         — single RAG query (bearer-auth, rate-limited, usage-tracked)
- POST /v1/ingest        — ingest files/text
- GET  /v1/collections   — list collections
- POST /v1/keys          — issue key (requires admin key or disabled in dev)
- GET  /v1/keys          — list keys (admin)
- DELETE /v1/keys/{key}  — revoke
- GET  /v1/usage         — caller's own usage

Config: reads `PERFECTRAG_CONFIG` env for perfectrag.yml path, and
`PERFECTRAG_PROJECT_DIR` for SQLite key store (defaults to config's directory).
Admin key via `PERFECTRAG_ADMIN_KEY` env for /v1/keys write operations.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from pydantic import BaseModel

from perfectrag import api_keys

app = FastAPI(title="perfectRAG Query API", version="1.1.0")

# Lazy-loaded RAG instance (one per process; config immutable)
_rag = None


def _project_dir() -> Path:
    return Path(os.environ.get("PERFECTRAG_PROJECT_DIR")
                or Path(os.environ.get("PERFECTRAG_CONFIG", "perfectrag.yml")).parent or ".")


def _get_rag():
    global _rag
    if _rag is None:
        from perfectrag import RAG

        cfg = os.environ.get("PERFECTRAG_CONFIG", "perfectrag.yml")
        _rag = RAG.from_config(cfg)
    return _rag


def require_key(
    authorization: Annotated[str | None, Header()] = None,
) -> api_keys.ApiKey:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Missing Authorization: Bearer sk-rag-...")
    token = authorization.split(" ", 1)[1].strip()
    project = _project_dir()
    key = api_keys.lookup(project, token)
    if not key or key.revoked:
        raise HTTPException(401, "Invalid or revoked API key")
    if not api_keys.check_rate_limit(project, token, key.rate_per_minute):
        raise HTTPException(429, f"Rate limit exceeded ({key.rate_per_minute}/min)")
    return key


def require_admin(authorization: Annotated[str | None, Header()] = None) -> None:
    admin = os.environ.get("PERFECTRAG_ADMIN_KEY")
    if not admin:
        # If no admin key set, allow (dev mode) but warn via header in response isn't possible here
        return
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Admin bearer required")
    token = authorization.split(" ", 1)[1].strip()
    if token != admin:
        raise HTTPException(403, "Admin key required")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


class QueryReq(BaseModel):
    question: str
    top_k: int | None = None


@app.post("/v1/query")
def query(req: QueryReq, request: Request, key: ApiKey = Depends(require_key)):  # type: ignore[name-defined]
    rag = _get_rag()
    result = rag.query(req.question, k=req.top_k)
    tokens_approx = len(result.answer.split())
    api_keys.record_usage(_project_dir(), key.key, "/v1/query", 200, tokens_approx)
    return result.as_dict()


class IngestReq(BaseModel):
    path: str | None = None   # local file/dir path (server-side)
    text: str | None = None   # or inline text


@app.post("/v1/ingest")
def ingest(req: IngestReq, key: ApiKey = Depends(require_key)):  # type: ignore[name-defined]
    rag = _get_rag()
    if req.path:
        n = rag.ingest(req.path)
    elif req.text:
        n = rag.ingest_text(req.text)
    else:
        raise HTTPException(400, "Provide `path` or `text`")
    api_keys.record_usage(_project_dir(), key.key, "/v1/ingest", 200, n)
    return {"chunks": n}


@app.get("/v1/collections")
def list_collections(key: ApiKey = Depends(require_key)):  # type: ignore[name-defined]
    rag = _get_rag()
    return {"collections": rag.store.list_collections()}


class KeyIssueReq(BaseModel):
    name: str
    rate_per_minute: int = 60


@app.post("/v1/keys")
def issue_key(req: KeyIssueReq, _: None = Depends(require_admin)):
    k = api_keys.issue(_project_dir(), req.name, req.rate_per_minute)
    return {"key": k.key, "name": k.name, "rate_per_minute": k.rate_per_minute,
            "created_at": k.created_at}


@app.get("/v1/keys")
def list_keys(_: None = Depends(require_admin)):
    rows = api_keys.list_all(_project_dir())
    return [
        {"key": f"sk-rag-…{k.key[-6:]}" if len(k.key) > 10 else k.key,
         "name": k.name, "rate_per_minute": k.rate_per_minute,
         "revoked": k.revoked, "created_at": k.created_at}
        for k in rows
    ]


@app.delete("/v1/keys/{key_suffix}")
def revoke_key(key_suffix: str, _: None = Depends(require_admin)):
    rows = api_keys.list_all(_project_dir())
    matches = [k for k in rows if k.key.endswith(key_suffix)]
    if not matches:
        raise HTTPException(404, "Key not found")
    revoked = 0
    for k in matches:
        if api_keys.revoke(_project_dir(), k.key):
            revoked += 1
    return {"revoked": revoked}


@app.get("/v1/usage")
def usage(key: ApiKey = Depends(require_key)):  # type: ignore[name-defined]
    return api_keys.usage_summary(_project_dir(), key.key)


# Re-export type for forward refs
ApiKey = api_keys.ApiKey
