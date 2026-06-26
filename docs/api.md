# Query API (SaaS)

Every generated project + library-mode `--serve` exposes an OpenAI-style REST API
gated by API keys. Usable by any HTTP client — build your own chat UI, wire into
other services, resell as a product.

## Issue a key

```bash
perfectrag key issue --name "prod app" --rate 100 --project .
# → sk-rag-a1b2c3...
perfectrag key list --project .
perfectrag key usage a1b2c3 --project .      # suffix match
perfectrag key revoke a1b2c3 --project .
```

Keys live in `<project>/.perfectrag/api_keys.db` (SQLite).

## Endpoints

Base URL = wherever the project's `app` service listens (default `http://localhost:8000`).

### POST /v1/query
```bash
curl -X POST http://localhost:8000/v1/query \
  -H "Authorization: Bearer sk-rag-..." \
  -H "Content-Type: application/json" \
  -d '{"question": "What is RAG?", "top_k": 5}'
```
Returns `{answer, sources: [{source, score, text}]}`.

### POST /v1/ingest
Upload text or a server-side path to ingest:
```bash
curl -X POST http://localhost:8000/v1/ingest \
  -H "Authorization: Bearer sk-rag-..." \
  -H "Content-Type: application/json" \
  -d '{"text": "my doc content..."}'
```

### GET /v1/collections
List vector collections in the store.

### GET /v1/usage
Caller's own usage summary (requests, tokens today + total).

### Admin (if `PERFECTRAG_ADMIN_KEY` env set)
- `POST /v1/keys` — issue programmatically
- `GET /v1/keys` — list (masked)
- `DELETE /v1/keys/{suffix}` — revoke

## Auth

Every protected endpoint requires `Authorization: Bearer sk-rag-...`. Admin
endpoints additionally require the bearer to match `PERFECTRAG_ADMIN_KEY`.

## Rate limit

Per-key in-memory sliding window (SQLite-backed): `rate_per_minute` set at key
creation. HTTP 429 on breach.

## Usage tracking

Every request logged to `usage_events` table with key, endpoint, status,
approximate tokens. Queryable via `/v1/usage` or the SQLite directly.

## Env vars

- `PERFECTRAG_CONFIG` — path to `perfectrag.yml` (default: current dir)
- `PERFECTRAG_PROJECT_DIR` — where to find `.perfectrag/api_keys.db`
- `PERFECTRAG_ADMIN_KEY` — enable `/v1/keys` admin routes
