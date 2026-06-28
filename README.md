<div align="center">

<img src="https://raw.githubusercontent.com/Caoquyen1913/perfectrag/HEAD/assets/logo-wordmark.png" alt="perfectRAG" width="640">

### Stop gluing RAG docker-compose files by hand.

**A RAG scaffolder _and_ an embedded Python library** — run it with Docker, without Docker, or as a SaaS API. Your hardware, your backbone, your call.

[![PyPI](https://img.shields.io/pypi/v/perfectrag?color=4c8bf5&label=pypi)](https://pypi.org/project/perfectrag/)
[![Python](https://img.shields.io/badge/python-3.10%2B-3776ab)](https://pypi.org/project/perfectrag/)
[![License](https://img.shields.io/badge/license-Apache--2.0-green)](https://github.com/Caoquyen1913/perfectrag/blob/HEAD/LICENSE)
[![Tests](https://img.shields.io/badge/tests-153%20passing-brightgreen)](https://github.com/Caoquyen1913/perfectrag/tree/HEAD/tests)
[![Backbones](https://img.shields.io/badge/backbones-7-orange)](https://github.com/Caoquyen1913/perfectrag/blob/HEAD/docs/templates.md)

</div>

---

`perfectrag` detects your hardware, asks what you're building, picks an opinionated recipe, and renders a **complete project** — `docker-compose.yml` + `.env` + `mcp.yaml` + `skills/` — wrapping one of **7 open-source RAG backbones**. Run `perfectrag up` and you have a RAG service + UI. No YAML archaeology.

Don't want Docker? The same engine ships as a pip-installable library: `from perfectrag import RAG`.

## ✨ Three ways to use it

```python
# 1️⃣  Embedded Python library — zero Docker
from perfectrag import RAG

rag = RAG.from_config("perfectrag.yml")
rag.ingest("./docs")
print(rag.query("What is RAG?").answer)
```

```bash
# 2️⃣  Scaffolded docker-compose stack — same config, same API
perfectrag init my-rag
cd my-rag && perfectrag up
```

```bash
# 3️⃣  SaaS API for external clients — bearer auth + rate limit built in
perfectrag key issue --name "prod app" --rate 100 -p .
curl -H "Authorization: Bearer sk-rag-..." \
  -d '{"question":"..."}' http://localhost:8000/v1/query
```

## 🧠 How it works

Five pure stages, from bare metal to a running stack:

```
   detect hardware  →  ask use-case  →  pick recipe  →  scaffold  →  orchestrate
   CPU/GPU/Apple       Q&A/graph/         LLM+embed+      compose+     up · doctor ·
   + VRAM tier         agent/code         reranker+db     env+mcp      logs · eval · deploy
```

1. **Detects hardware** — CPU / NVIDIA / Apple Silicon / AMD, with a VRAM tier.
2. **Asks use-case questions** — Q&A · GraphRAG · agent · multimodal · code · web.
3. **Picks a recipe** — LLM + embedding + reranker + vector DB + parser, tuned to your tier.
4. **Scaffolds a full project** — `docker-compose.yml` + `.env` + `mcp.yaml` + `skills/` + optional addons.
5. **Orchestrates** — `perfectrag up / doctor / logs / eval / deploy`, or a **Next.js browser wizard** if you'd rather click than type.

## 📦 Install

```bash
pip install perfectrag           # CLI + embedded library
pip install 'perfectrag[web]'    # + FastAPI backend for the Next.js UI
```

## 🚀 Quickstart — the one-liner

```bash
perfectrag init my-rag --with eval,observability,paperclip
cd my-rag
perfectrag up
```

…and you have a RAG service, an eval dashboard, an observability gateway, and a multi-agent orchestrator running on localhost — in one shot.

## 🧩 The 7 backbones

| Template | Best for | Backbone |
|---|---|---|
| `custom-naive-rag` | Learning · CPU-only · tiny corpus | FastAPI + Qdrant + Ollama + open-webui |
| `ragflow-stack` | Production Q&A · hybrid search · agentic | [RAGFlow](https://github.com/infiniflow/ragflow) |
| `lightrag-stack` | GraphRAG · multi-hop reasoning | [LightRAG](https://github.com/HKUDS/LightRAG) |
| `dify-stack` | Workflow / agent builder · no-code teams | [Dify](https://github.com/langgenius/dify) |
| `code-graph-rag` | Code intelligence for AI coding agents | Serena (LSP) + ast-grep MCP (+ Memgraph) |
| `r2r-stack` | All-in-one agentic RAG | [R2R](https://github.com/SciPhi-AI/R2R) |
| `onyx-stack` | Enterprise connector search | [Onyx](https://github.com/onyx-dot-app/onyx) |

> The wizard auto-routes to the right one (GraphRAG → LightRAG, code → code-graph-rag, …) — or force any with `--template`. Bring your own via `[project.entry-points."perfectrag.templates"]`; users get it after `pip install`. See [docs/templates.md](https://github.com/Caoquyen1913/perfectrag/blob/HEAD/docs/templates.md).

## 🎯 Advanced retrieval — measure, don't guess

The embedded library ships techniques you toggle in `perfectrag.yml` (the wizard turns them on based on your answers):

| Technique | Config | When it helps |
|---|---|---|
| Contextual Retrieval | `contextual: true` | recall on terse chunks (needs a capable LLM) |
| Parent-document | `parent_chunk_size: 2048` | precise match + richer context, free |
| Query expansion + RRF | `query_expansion: 3` | terse / multi-hop queries |
| Corrective RAG (CRAG) | `corrective: true` | re-retrieve when results look off |

Then let the data decide which to keep:

```bash
perfectrag tune --docs ./docs --golden ./golden.jsonl --apply   # benchmarks each technique on YOUR corpus, writes the winner
perfectrag eval --retrieval -d golden.jsonl --gate              # recall@k / MRR / nDCG as a CI gate — no Docker
```

See [docs/retrieval.md](https://github.com/Caoquyen1913/perfectrag/blob/HEAD/docs/retrieval.md).

## 🛠️ Commands

| Command | What it does |
|---|---|
| `perfectrag init [DIR]` | Wizard → scaffold a project |
| `perfectrag init DIR --with a,b,c` | Install addons at init time |
| `perfectrag init DIR --template ragflow-stack` | Force a specific backbone |
| `perfectrag add mcp/skill/addon <name>` | Extend a generated project |
| `perfectrag up / down / logs / doctor` | Orchestrate the generated project |
| `perfectrag eval --dataset qa.jsonl` | Generation metrics — RAGAS + DeepEval (needs `eval` addon) |
| `perfectrag eval --retrieval -d golden.jsonl --gate` | Retrieval metrics + CI gate, no Docker |
| `perfectrag tune --docs ./docs --golden g.jsonl --apply` | Auto-pick the best retrieval technique **on your data** |
| `perfectrag advise "..."` | Scored, evaluative recipe recommendation |
| `perfectrag deploy helm/flyio/railway` | Render production deploy assets |
| `perfectrag web` | Start the FastAPI backend for the Next.js UI |
| `perfectrag list templates/mcp/skills/addons/installed` | Show catalogues |
| `perfectrag hw` | Show detected hardware + tier |

## 🔌 Addons

One-flag overlays that `perfectrag up` auto-merges (`compose.<name>.yml`):

| Addon | Purpose | Based on |
|---|---|---|
| `eval` | RAG quality measurement | RAGAS, DeepEval |
| `observability` | LLM gateway + tracing | LiteLLM, Langfuse |
| `context-eng` | Prompt compression + memory | DSPy, LLMLingua, mem0 |
| `ingest-worker` | Scheduled web crawl → vector store | Crawl4AI |
| `notion-sync` · `gdrive-sync` · `confluence-sync` | Sources → vector store | official SDKs |
| `paperclip` | Multi-agent orchestrator | [Paperclip](https://github.com/paperclipai/paperclip) |

See [docs/addons.md](https://github.com/Caoquyen1913/perfectrag/blob/HEAD/docs/addons.md).

## 🖥️ Browser wizard

Prefer clicking to typing?

```bash
pip install 'perfectrag[web]'
perfectrag web                        # backend on :7777
cd ui && pnpm install && pnpm dev     # UI on :3001
```

See [docs/ui.md](https://github.com/Caoquyen1913/perfectrag/blob/HEAD/docs/ui.md).

## ☁️ Deploy to production

```bash
perfectrag deploy helm --project ./my-rag --out ./chart
helm lint ./chart && helm install my-rag ./chart
```

Also renders `flyio` and `railway` assets. See [docs/deploy.md](https://github.com/Caoquyen1913/perfectrag/blob/HEAD/docs/deploy.md).

## 📚 Docs

[Retrieval](https://github.com/Caoquyen1913/perfectrag/blob/HEAD/docs/retrieval.md) · [Code intelligence](https://github.com/Caoquyen1913/perfectrag/blob/HEAD/docs/code-graph.md) · [Templates](https://github.com/Caoquyen1913/perfectrag/blob/HEAD/docs/templates.md) · [Addons](https://github.com/Caoquyen1913/perfectrag/blob/HEAD/docs/addons.md) · [Eval](https://github.com/Caoquyen1913/perfectrag/blob/HEAD/docs/eval.md) · [Observability](https://github.com/Caoquyen1913/perfectrag/blob/HEAD/docs/observability.md) · [Deploy](https://github.com/Caoquyen1913/perfectrag/blob/HEAD/docs/deploy.md) · [Browser UI](https://github.com/Caoquyen1913/perfectrag/blob/HEAD/docs/ui.md) · [MCP registry](https://github.com/Caoquyen1913/perfectrag/blob/HEAD/docs/mcp.md) · [Skills](https://github.com/Caoquyen1913/perfectrag/blob/HEAD/docs/skills.md) · [Stack-boot test findings](https://github.com/Caoquyen1913/perfectrag/blob/HEAD/docs/stack-testing-findings.md) · [Changelog](https://github.com/Caoquyen1913/perfectrag/blob/HEAD/CHANGELOG.md)

## 📄 License

[Apache-2.0](https://github.com/Caoquyen1913/perfectrag/blob/HEAD/LICENSE)

<div align="center">
<sub>Built for people who want a working RAG stack, not a weekend of YAML.</sub>
</div>
