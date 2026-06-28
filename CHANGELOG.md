# Changelog

## 1.3.3

### Docs
- New **octopus mascot logo** (`assets/logo.png` mark + `assets/logo-wordmark.png`);
  the wordmark is now the README hero and the social card uses the octopus.
- Fixed README links to absolute GitHub URLs so they resolve on the PyPI page.

## 1.3.2

### Docs
- Reworked README (hero, badges, pipeline diagram, tighter tables) and added the
  Apache-2.0 `LICENSE` file. Patch release so the refreshed README ships as the
  PyPI project description (1.3.1 was built before the rewrite).

## 1.3.1

Theme: **template fixes from a full live `docker compose up` test pass.**

### Fixed
- **code-graph-rag**: memgraph crash-looped (exit 12) on a root-owned host bind-mount → switched to a named volume.
- **r2r-stack**: (a) `R2R_PROJECT_NAME` took the raw project dir name, so a hyphen crashed Postgres table creation (`syntax error at or near "-"`) → sanitized to underscores; (b) R2R listened on `:8000` but compose mapped `7272:7272` → pinned `R2R_PORT=7272`.
- **dify-stack**: (a) `MIGRATION_ENABLED` unset → no DB schema, every console call 500 (`relation "dify_setups" does not exist`); (b) `CELERY_BROKER_URL` unset → worker fell back to amqp/RabbitMQ and crashed → pointed broker/result backend at Redis.

### Docs
- `docs/stack-testing-findings.md`: per-stack live-boot results (6/7 booted) + the onyx api_server limitation (needs the upstream-complete deployment incl. model_server) + the host-disk workflow.

## 1.3.0

Theme: **help users pick the right config — measure, don't guess.**

### Added
- **Auto-tune** (`perfectrag tune --docs ... --golden ... --apply`) — ingests your corpus under each retrieval technique (baseline / parent-doc / contextual / query-expansion / CRAG), scores them on your golden questions (recall@k / MRR / nDCG), and writes the empirically best config (cheapest on ties). One embedder/LLM is reused across trials for stability. Beats rule-based defaults because it measures on *your* data.
- **Interactive backbone picker at `init`** — in interactive mode, `init` shows the scored template ranking with reasons and lets you confirm the recommendation or pick another backbone (Enter = accept). Rule-based, **no API key needed**; CI / `--answers-file` / `--template` paths unchanged.
- docs/retrieval.md: "Auto-tune" section.

## 1.2.0

### Added
- **3 new templates (now 7)**:
  - `code-graph-rag` — code intelligence for AI coding agents (Claude Code): Serena (LSP) + ast-grep over MCP, optional Memgraph graph. `code_rag` use-case routes here.
  - `r2r-stack` — [R2R](https://github.com/SciPhi-AI/R2R) production all-in-one (hybrid+RRF, GraphRAG, multimodal, agentic) on Postgres/pgvector.
  - `onyx-stack` — [Onyx](https://github.com/onyx-dot-app/onyx) enterprise connector search (Slack/Drive/GitHub/Confluence).
- **Advanced retrieval in the embedded library** (all opt-in via `perfectrag.yml` / `RAG(...)`):
  - **Contextual Retrieval** (`contextual: true`) — Anthropic-style per-chunk situating context before embedding.
  - **Parent-document retrieval** (`parent_chunk_size: N`) — embed small chunks, feed the larger parent to the LLM.
  - **Query expansion + Reciprocal Rank Fusion** (`query_expansion: N`) — N alternate phrasings fused with RRF.
  - **Corrective RAG / CRAG** (`corrective: true`) — grade results, re-retrieve once if irrelevant.
  - The wizard auto-enables these based on answers (e.g. `priority: accuracy` / `multi_hop` → expansion + CRAG).
- **Retrieval-quality metrics + CI gate**: `perfectrag.core.evaluation` (recall@k / MRR / nDCG) and `perfectrag eval --retrieval [--k N --gate]` — measures retrieval separately from generation, no Docker.
- **Scored advisor**: `recipes.score_candidates()` ranks all templates with reasons; `perfectrag advise` shows an evaluative table, not just one pick.
- **6 new wizard questions** driving the recipe: `latency`, `priority`, `language`, `freshness`, `existing_infra`, `needs_citations` (e.g. multilingual→bge-m3, postgres infra→pgvector, interactive→drop reranker).
- **3 code-intelligence MCP servers**: `serena`, `ast-grep`, `claude-context`.
- **CAG recommendation** — `extras.cag_candidate` flagged for small + static corpora (see docs/retrieval.md).
- Docs: `docs/retrieval.md`, `docs/code-graph.md`.

### Fixed
- `privacy=hybrid_api` is now honored — weak tiers (cpu/apple-low) recommend a cloud LLM instead of a too-weak local one.
- `chunk_strategy`/`chunk_size` are now derived from answers (was hardcoded `recursive`/512).
- `RAG.from_config` expands `${VAR:-default}` env vars, so `perfectrag.yml` works inside containers (fixes Dockerized-app store URL parse error).
- Template `ollama-pull` no longer tries to pull a cloud model name when `privacy=hybrid_api` selects a cloud runtime.

### Changed
- `code_rag` use-case routes to `code-graph-rag` (was `ragflow-stack`).

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
