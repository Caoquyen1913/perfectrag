# Live stack-boot testing — findings (2026-06-28)

Booted each generated stack with `docker compose up` on a CPU-only Windows host
(Docker Desktop / WSL2), checked container health, UI endpoints, logs, and MCP.

## Results

| Stack | Live boot | UI | Notes |
|---|---|---|---|
| code-graph-rag | ✅ | Memgraph Lab :3000 → 200 | Fixed: memgraph crash-loop (root-owned bind-mount → named volume) |
| custom-naive-rag | ✅ | open-webui :3000 → 200, app :8000 → 200 | Clean (one benign upstream open-webui SQLAlchemy warning) |
| lightrag-stack | ✅ | lightrag :9621 → 307→/webui | Clean startup (Uvicorn up) |
| r2r-stack | ✅ | :7272/v3/health → 200 | Fixed 2: hyphen in `R2R_PROJECT_NAME` (Postgres syntax error); `R2R_PORT` mismatch (8000 vs mapped 7272) |
| dify-stack | ✅ | nginx :80 → /install 200, /console/api/setup 200 | Fixed 2: missing `MIGRATION_ENABLED` (no tables); missing `CELERY_BROKER_URL` (worker → amqp refused) |
| onyx-stack | ⚠️ partial | web :3000 → 200, data tier up | api backend can't fully boot — see below |
| ragflow-stack | ⛔ disk | — | compose valid (parses + storage tier ES/MySQL/Redis/MinIO booted healthy); ragflow's 9 GB image + its first-run model downloads need ~25-30 GB free, exceeding this host's ~20 GB reclaimable. Not a template bug — host-disk capacity. |

## Host-disk constraint

Testing ran on a host whose C: drive was ~99% full (≈0.4 GB free initially). Docker
Desktop's data vhdx repeatedly hit read-only when it filled. Workflow used: purge the
vhdx (~20 GB reclaimed) → boot one stack → verify → tear down → repeat. The two shared
images (ollama 8 GB + open-webui 6.7 GB) plus a stack's own images fit within ~20 GB
for the light stacks; ragflow's footprint does not. The vhdx grows but does not
auto-shrink on teardown, and `diskpart compact` needs admin — so each heavy stack
required a full purge + re-pull. For full ragflow coverage, free ~30 GB on the host.

## onyx-stack — outstanding (needs upstream-version work)

The web UI (:3000) serves and the data tier (Postgres/Vespa/Redis) comes up, but
`api_server` does not fully start. Three issues, in order of discovery:

1. **`api_server` has no `command:`** — the `onyxdotapp/onyx-backend` image's default
   CMD is `tail -f /dev/null` (it's a shared base image). The service sits idle and
   nothing listens on :8080. Onyx's real command is roughly:
   `alembic upgrade head && uvicorn onyx.main:app --host 0.0.0.0 --port 8080`.
2. **`USER_AUTH_SECRET` unset** — api refuses to start: "USER_AUTH_SECRET is empty".
   Needs a generated secret in `.env` (`openssl rand -hex 32`).
3. **Index drift (root cause): images are unpinned (`:latest`).** With the real
   command + secret, migrations run but the api then fails connecting to a document
   index on `localhost:9200` — current `onyx-backend:latest` expects **OpenSearch**,
   while the template pins a **Vespa** `index` service. CLAUDE.md already requires
   upstream images to be pinned; pin `onyx-backend` / `onyx-web-server` to a
   Vespa-era tag (and add the command + secret), or switch the index to OpenSearch
   to match `:latest`.

This was left as-is (documented "starting point, use upstream for the complete
deployment") rather than committing a partial fix that would crash-loop the api.
