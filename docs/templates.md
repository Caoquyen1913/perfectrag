# Templates

Mỗi template là một thư mục Copier chứa docker-compose + env + skeleton files. Được render với 3 context namespaces: `recipe`, `hw`, `answers`.

## Available

### custom-naive-rag

Minimal DIY stack cho CPU-only / learning.

- **Services**: Qdrant, Ollama, FastAPI app, open-webui, ollama-pull helper
- **UI**: open-webui tại `:3000`, FastAPI `/docs` tại `:8000`
- **Ingest**: `POST /ingest` (multipart file)
- **Query**: `POST /query` JSON hoặc OpenAI-compatible `/v1/chat/completions`
- **Khi nào chọn**: CPU-only + corpus nhỏ + qa_docs

### ragflow-stack

Production-grade RAG với hybrid search, deep doc parsing, agentic, MCP-native.

- **Backbone**: [RAGFlow v0.17.2](https://github.com/infiniflow/ragflow)
- **Services**: Elasticsearch, MySQL, Redis, MinIO, Ollama, ragflow-server
- **UI**: RAGFlow Console tại `:80`
- **Khi nào chọn**: Q&A hybrid search, cần ingest PDF phức tạp, cần agent + tool-calling, team/production

### lightrag-stack

GraphRAG cost-efficient với dual-level retrieval.

- **Backbone**: [LightRAG](https://github.com/HKUDS/LightRAG)
- **Services**: Ollama, lightrag server, open-webui chat
- **UI**: LightRAG WebUI tại `:9621` (graph visualize + ingest), open-webui tại `:3000`
- **Modes**: `naive`, `local`, `global`, `hybrid`
- **Khi nào chọn**: multi-hop reasoning, knowledge graph, cần entity/relation

### dify-stack

Visual workflow + agent builder với marketplace.

- **Backbone**: [Dify v1.3.1](https://github.com/langgenius/dify)
- **Services**: Postgres, Redis, Qdrant, Ollama, api, worker, web, nginx
- **UI**: Dify Console tại `:80`
- **Khi nào chọn**: workflow/chatflow bằng UI kéo-thả, team không code

### code-graph-rag

Code intelligence cho AI coding agent (Claude Code / Cursor) — symbol-level
navigation thay vì naive vector search.

- **Core (no Docker)**: `mcp.yaml` cắm sẵn **Serena** (LSP, 30+ ngôn ngữ) + **ast-grep**
- **Optional graph**: Memgraph + Lab UI (`docker compose up`)
- **Optional semantic**: `perfectrag add mcp claude-context` (Milvus)
- **Khi nào chọn**: use-case `code_rag` (tự động route vào đây). Xem [code-graph.md](code-graph.md).

### r2r-stack

Production all-in-one RAG: hybrid+RRF, GraphRAG, multimodal, agentic Deep Research.

- **Backbone**: [R2R](https://github.com/SciPhi-AI/R2R) (`sciphiai/r2r`)
- **Services**: Postgres+pgvector, Ollama, r2r (REST API + dashboard `:7272`)
- **Khi nào chọn**: muốn agentic RAG all-in-one (opt-in qua `--template r2r-stack`)

### onyx-stack

Enterprise connector-based search (Slack/Drive/GitHub/Confluence, permission-aware).

- **Backbone**: [Onyx](https://github.com/onyx-dot-app/onyx) (ex-Danswer)
- **Services**: Postgres, Vespa, Redis, Onyx api/web; README trỏ upstream compose cho production
- **Khi nào chọn**: "chat trên data công ty" thay vì PDF upload (opt-in qua `--template onyx-stack`)

## Contribute a template

1. Tạo thư mục `src/perfectrag/templates/<name>/`
2. Add `copier.yml`:
   ```yaml
   _templates_suffix: .jinja
   _envops: { keep_trailing_newline: true }
   _answers_file: .copier-answers.yml
   _exclude: [copier.yml, __init__.py]
   project_name: { type: str, default: my-rag }
   ```
3. Add template files với extension `.jinja`: `docker-compose.yml.jinja`, `.env.jinja`, `README.md.jinja`, `mcp.yaml.jinja`.
4. Dùng variables: `{{ recipe.llm_model }}`, `{{ hw.gpu_vendor }}`, `{{ answers.use_case }}`.
5. Add entry vào `_DESCRIPTIONS` trong `src/perfectrag/scaffolder.py`.
6. (Optional) Update `_pick_template()` trong `src/perfectrag/recipes.py` để wizard tự gợi ý template mới cho use-case nào.
7. Add test fixture + e2e test trong `tests/e2e/test_scaffold.py`.

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
