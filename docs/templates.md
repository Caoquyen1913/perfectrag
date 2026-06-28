# Templates

Each template is a Copier directory containing docker-compose + env + skeleton files. It's rendered with 3 context namespaces: `recipe`, `hw`, `answers`.

## Available

### custom-naive-rag

Minimal DIY stack for CPU-only / learning.

- **Services**: Qdrant, Ollama, FastAPI app, open-webui, ollama-pull helper
- **UI**: open-webui at `:3000`, FastAPI `/docs` at `:8000`
- **Ingest**: `POST /ingest` (multipart file)
- **Query**: `POST /query` JSON or OpenAI-compatible `/v1/chat/completions`
- **When to choose**: CPU-only + small corpus + qa_docs

### ragflow-stack

Production-grade RAG with hybrid search, deep doc parsing, agentic, MCP-native.

- **Backbone**: [RAGFlow v0.17.2](https://github.com/infiniflow/ragflow)
- **Services**: Elasticsearch, MySQL, Redis, MinIO, Ollama, ragflow-server
- **UI**: RAGFlow Console at `:80`
- **When to choose**: Q&A hybrid search, need to ingest complex PDFs, need agent + tool-calling, team/production

### lightrag-stack

Cost-efficient GraphRAG with dual-level retrieval.

- **Backbone**: [LightRAG](https://github.com/HKUDS/LightRAG)
- **Services**: Ollama, lightrag server, open-webui chat
- **UI**: LightRAG WebUI at `:9621` (graph visualize + ingest), open-webui at `:3000`
- **Modes**: `naive`, `local`, `global`, `hybrid`
- **When to choose**: multi-hop reasoning, knowledge graph, need entities/relations

### dify-stack

Visual workflow + agent builder with marketplace.

- **Backbone**: [Dify v1.3.1](https://github.com/langgenius/dify)
- **Services**: Postgres, Redis, Qdrant, Ollama, api, worker, web, nginx
- **UI**: Dify Console at `:80`
- **When to choose**: workflow/chatflow via drag-and-drop UI, non-coding teams

### code-graph-rag

Code intelligence for AI coding agents (Claude Code / Cursor) — symbol-level
navigation instead of naive vector search.

- **Core (no Docker)**: `mcp.yaml` pre-wired with **Serena** (LSP, 30+ languages) + **ast-grep**
- **Optional graph**: Memgraph + Lab UI (`docker compose up`)
- **Optional semantic**: `perfectrag add mcp claude-context` (Milvus)
- **When to choose**: the `code_rag` use-case (auto-routed here). See [code-graph.md](code-graph.md).

### r2r-stack

Production all-in-one RAG: hybrid+RRF, GraphRAG, multimodal, agentic Deep Research.

- **Backbone**: [R2R](https://github.com/SciPhi-AI/R2R) (`sciphiai/r2r`)
- **Services**: Postgres+pgvector, Ollama, r2r (REST API + dashboard `:7272`)
- **When to choose**: you want all-in-one agentic RAG (opt-in via `--template r2r-stack`)

### onyx-stack

Enterprise connector-based search (Slack/Drive/GitHub/Confluence, permission-aware).

- **Backbone**: [Onyx](https://github.com/onyx-dot-app/onyx) (ex-Danswer)
- **Services**: Postgres, Vespa, Redis, Onyx api/web; README points to the upstream compose for production
- **When to choose**: "chat over company data" instead of PDF upload (opt-in via `--template onyx-stack`)
- **Heads-up**: this is a **minimal starting point** — the web UI + data tier boot, but Onyx's `api_server` needs additional services (a `model_server`, indexing model server, background workers) to fully start. For a working deployment, vendor Onyx's [upstream compose](https://github.com/onyx-dot-app/onyx/tree/main/deployment/docker_compose). See [stack-testing-findings.md](stack-testing-findings.md).

## Stack-boot test status

All seven templates' compose files are validated, and the stacks were live-booted
to verify the generated config. See **[stack-testing-findings.md](stack-testing-findings.md)**
for per-stack results (UI / logs / MCP) and the fixes that came out of it.

## Contribute a template

1. Create the directory `src/perfectrag/templates/<name>/`
2. Add `copier.yml`:
   ```yaml
   _templates_suffix: .jinja
   _envops: { keep_trailing_newline: true }
   _answers_file: .copier-answers.yml
   _exclude: [copier.yml, __init__.py]
   project_name: { type: str, default: my-rag }
   ```
3. Add template files with the `.jinja` extension: `docker-compose.yml.jinja`, `.env.jinja`, `README.md.jinja`, `mcp.yaml.jinja`.
4. Use variables: `{{ recipe.llm_model }}`, `{{ hw.gpu_vendor }}`, `{{ answers.use_case }}`.
5. Add an entry to `_DESCRIPTIONS` in `src/perfectrag/scaffolder.py`.
6. (Optional) Update `_pick_template()` in `src/perfectrag/recipes.py` so the wizard auto-suggests the new template for a given use-case.
7. Add a test fixture + e2e test in `tests/e2e/test_scaffold.py`.

## Template variables reference

Recipe (`recipe.*`):
- `template`, `llm_model`, `llm_runtime`, `embedding_model`, `reranker`
- `vector_db`, `doc_parser`, `chunk_strategy`, `chunk_size`
- `gpu_enabled`, `vram_cap_gb`
- `extras.enable_graphrag`, `extras.enable_hybrid_search`

Hardware (`hw.*`):
- `os`, `arch`, `cpu_model`, `cpu_cores`, `ram_gb`, `disk_free_gb`
- `gpu_vendor` (`nvidia`/`amd`/`apple`/`none`), `gpu_name`, `vram_gb`, `cuda_version`

Answers (`answers.*`):
- `use_case`, `modality` (list), `privacy`, `multi_hop`, `corpus_size`, `user_scale`
