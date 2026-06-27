# perfectRAG

> RAG scaffolder **+ embedded Python library**. Run with Docker, without Docker, or as a SaaS API — your choice.

**v1.2 adds**: 3 new backbones (`code-graph-rag` for Claude Code, `r2r-stack`, `onyx-stack` → 7 total), advanced retrieval in the library (Contextual Retrieval, parent-document, query-expansion + RRF, Corrective RAG), a retrieval-quality eval gate (`eval --retrieval`), a scored advisor, and 6 new wizard questions. See the [changelog](CHANGELOG.md).

**v1.1**: Docker-free local mode (`from perfectrag import RAG`), full component matrix (5 vector DBs × 5 embeddings × 4 rerankers × 6 LLM runtimes), Gemini advisor, and a built-in OpenAI-style Query API with bearer auth + rate limit.

## Three ways to use it

```python
# 1. Embedded Python library (no Docker)
from perfectrag import RAG
rag = RAG.from_config("perfectrag.yml")
rag.ingest("./docs")
print(rag.query("What is RAG?").answer)
```

```bash
# 2. Scaffolded docker-compose stack (same config, same API)
perfectrag init my-rag
cd my-rag && perfectrag up

# 3. SaaS API for external clients
perfectrag key issue --name "prod app" --rate 100 -p .
curl -H "Authorization: Bearer sk-rag-..." \
  -d '{"question":"..."}' http://localhost:8000/v1/query
```

Instead of gluing RAGFlow/Dify/LightRAG docker-compose files by hand, `perfectrag`:

1. **Detects hardware** (CPU / NVIDIA / Apple Silicon / AMD) + VRAM tier.
2. **Asks use-case questions** (Q&A / GraphRAG / agent / multimodal / code / web).
3. **Picks a recipe** (LLM + embedding + reranker + vector DB + parser) tuned to your hardware.
4. **Scaffolds a full project** (`docker-compose.yml` + `.env` + `mcp.yaml` + `skills/` + optional addons).
5. **Orchestrates** with `perfectrag up / doctor / logs / eval / deploy`.
6. **Ships a browser wizard** (Next.js) if you'd rather click than type.

## Install

```bash
pip install perfectrag           # CLI + core
pip install 'perfectrag[web]'    # + FastAPI backend for Next.js UI
```

## Quickstart — the one-liner

```bash
perfectrag init my-rag --with eval,observability,paperclip
cd my-rag
perfectrag up
```

That gives you a RAG service, eval dashboard, observability gateway, and multi-agent orchestrator running on localhost in one shot.

## Commands

| Command | What it does |
|---|---|
| `perfectrag init [DIR]` | Wizard → scaffold a project |
| `perfectrag init DIR --with a,b,c` | Install addons at init time |
| `perfectrag init DIR --template ragflow-stack` | Force a specific backbone |
| `perfectrag add mcp/skill/addon <name>` | Extend a generated project |
| `perfectrag up / down / logs / doctor` | Orchestrate the generated project |
| `perfectrag eval --dataset qa.jsonl` | Generation metrics — RAGAS + DeepEval (needs `eval` addon) |
| `perfectrag eval --retrieval -d golden.jsonl --gate` | Retrieval metrics (recall@k/MRR/nDCG) + CI gate, no Docker |
| `perfectrag advise "..."` | Scored, evaluative recipe recommendation |
| `perfectrag deploy helm/flyio/railway` | Render production deploy assets |
| `perfectrag web` | Start FastAPI backend for Next.js UI |
| `perfectrag list templates/mcp/skills/addons/installed` | Show catalogues |
| `perfectrag hw` | Show detected hardware + tier |

## Templates (7)

| Template | Use-case | Backbone |
|---|---|---|
| `custom-naive-rag` | Learning / CPU-only / tiny corpus | FastAPI + Qdrant + Ollama + open-webui |
| `ragflow-stack` | Production Q&A + hybrid search + agentic | [RAGFlow](https://github.com/infiniflow/ragflow) |
| `lightrag-stack` | GraphRAG / multi-hop reasoning | [LightRAG](https://github.com/HKUDS/LightRAG) |
| `dify-stack` | Workflow / agent / no-code team | [Dify](https://github.com/langgenius/dify) |
| `code-graph-rag` | Code intelligence for Claude Code | Serena (LSP) + ast-grep MCP (+ Memgraph) |
| `r2r-stack` | Production all-in-one + agentic RAG | [R2R](https://github.com/SciPhi-AI/R2R) |
| `onyx-stack` | Enterprise connector search | [Onyx](https://github.com/onyx-dot-app/onyx) |

Third-party templates: publish via `[project.entry-points."perfectrag.templates"]` — users get them after `pip install`.

## Advanced retrieval (v1.2)

The embedded library supports techniques you enable in `perfectrag.yml` (the wizard
turns them on automatically based on your answers):

| Technique | Config | When it helps |
|---|---|---|
| Contextual Retrieval | `contextual: true` | recall on terse chunks (needs a capable LLM) |
| Parent-document | `parent_chunk_size: 2048` | precise match + richer context, free |
| Query expansion + RRF | `query_expansion: 3` | terse / multi-hop queries |
| Corrective RAG (CRAG) | `corrective: true` | re-retrieve when results look off |

Measure them: `perfectrag eval --retrieval -d golden.jsonl --gate`. See [docs/retrieval.md](docs/retrieval.md).

## Addons (v1.0)

| Addon | Purpose | Based on |
|---|---|---|
| `eval` | RAG quality measurement | RAGAS, DeepEval |
| `observability` | LLM gateway + tracing | LiteLLM, Langfuse |
| `context-eng` | Prompt compression + memory | DSPy, LLMLingua, mem0 |
| `ingest-worker` | Scheduled web crawl → vector store | Crawl4AI |
| `notion-sync` | Notion → vector store | notion-client |
| `gdrive-sync` | Google Drive → vector store | google-api-python-client |
| `confluence-sync` | Confluence → vector store | atlassian-python-api |
| `paperclip` | Multi-agent orchestrator | [Paperclip](https://github.com/paperclipai/paperclip) |

Each addon is a `compose.<name>.yml` overlay that `perfectrag up` auto-merges. See [docs/addons.md](docs/addons.md).

## Browser wizard

```bash
pip install 'perfectrag[web]'
perfectrag web           # backend on :7777

# in another terminal
cd ui && pnpm install && pnpm dev    # UI on :3001
```

See [docs/ui.md](docs/ui.md).

## Deploy to production

```bash
perfectrag deploy helm --project ./my-rag --out ./chart
helm lint ./chart
helm install my-rag ./chart
```

Also supports `flyio` and `railway`. See [docs/deploy.md](docs/deploy.md).

## Docs

- [Advanced retrieval](docs/retrieval.md)
- [Code intelligence (code-graph-rag)](docs/code-graph.md)
- [Addons](docs/addons.md)
- [Eval](docs/eval.md)
- [Observability](docs/observability.md)
- [Deploy](docs/deploy.md)
- [Browser UI](docs/ui.md)
- [Templates](docs/templates.md)
- [MCP registry](docs/mcp.md)
- [Skills](docs/skills.md)

## License

Apache-2.0
