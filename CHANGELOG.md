# Changelog

## 1.1.0

### Added
- **Embedded library** (`from perfectrag import RAG`) — run without Docker. `perfectrag run --config perfectrag.yml` or import as Python library.
- **Full component matrix**: 5 vector DBs (Qdrant/Milvus/Chroma/LanceDB/pgvector), 5 embeddings, 4 rerankers, 6 LLM runtimes (Ollama/llama-cpp/vLLM/Gemini/Anthropic/OpenAI), 3 parsers.
- **Gemini advisor** (`perfectrag advise "..."` + `init --advise`) — optional LLM refiner on top of rule-based recipe. Degrades gracefully without key.
- **Provider key storage** (`perfectrag add/remove/list key <provider> <value>`) in `~/.perfectrag/keys.yml` (chmod 600).
- **SaaS Query API** (`/v1/*`) built into every generated project + library `--serve` mode: `/v1/query`, `/v1/ingest`, `/v1/collections`, `/v1/keys`, `/v1/usage`. API key bearer auth, slowapi-style rate limit, SQLite usage tracking.
- **RAG-access key CLI** (`perfectrag key issue/list/revoke/usage`) backed by per-project SQLite.
- **Wizard power-user overrides** — optionally pick specific VDB/embed/rerank/LLM runtime.
- **Pyproject extras**: `[web] [advisor] [qdrant] [milvus] [chroma] [lancedb] [pgvector] [embed-torch] [llamacpp]`.
- **Generated `perfectrag.yml`** — same config drives docker-compose service *and* embedded library mode.

### Changed
- `custom-naive-rag` template rewritten on top of `perfectrag.core.RAG`; mounts `/v1/*` SaaS API at root.

## 1.0.0

Major release — turns perfectrag from a scaffolder into a full RAG-in-a-box platform.

### Added
- **Addon system**: `perfectrag add addon <name>` + `--with eval,observability,...` flag. State tracked in `.perfectrag/addons.yml`. 8 bundled addons.
- **`perfectrag up / down / logs / doctor`**: orchestrate docker compose (base + addons), poll healthchecks, diagnose issues.
- **Eval addon**: RAGAS + DeepEval runner. `perfectrag eval --dataset x.jsonl` produces HTML report at `:8081`.
- **Observability addon**: LiteLLM gateway + Langfuse self-hosted tracing. Routes all LLM calls for free tracing.
- **Context-engineering addon**: DSPy + LLMLingua + mem0 as a FastAPI microservice (`:8002`).
- **Ingest-worker addon**: Crawl4AI on cron → chunks → embeds → Qdrant.
- **Paperclip addon**: multi-agent orchestrator with RAG backbone pre-wired as `rag_query` tool.
- **Data connectors**: Notion / Google Drive / Confluence sync-on-cron addons.
- **Cloud deploy**: `perfectrag deploy helm|flyio|railway --out …` (custom-naive-rag supported in v1.0).
- **Browser wizard**: Next.js 15 SPA in `ui/` + FastAPI backend (`perfectrag web`). Multi-step wizard + live dashboard.
- **Template marketplace**: third-party packages can register templates via Python entry_points group `perfectrag.templates`.
- **New MCP servers in registry**: crawl4ai, firecrawl, notion, gdrive, confluence, slack.
- **Healthchecks** in generated docker-compose for proper `wait_healthy` polling.

### Changed
- `add` command now accepts `addon` as a kind: `perfectrag add addon eval`.
- `list` command takes `addons` and `installed` options.

### Dependencies
- Added optional extras: `[web]` for FastAPI/uvicorn.

## 0.1.0

- Initial release: CLI scaffolder with 4 templates (RAGFlow, Dify, LightRAG, custom-naive-rag), MCP registry, bundled skills, hardware-aware recipe engine.
