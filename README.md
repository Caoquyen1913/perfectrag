# perfectRAG


> Dynamic RAG framework scaffolder — wizard hỏi vài câu, detect hardware, rồi sinh ra service RAG hoàn chỉnh (docker-compose + UI + API) chạy ngay.

Thay vì copy–paste docker-compose từ RAGFlow/Dify/LightRAG rồi loay hoay sửa `.env`, `perfectrag init` sẽ:

1. Detect hardware (CPU/GPU/RAM/VRAM).
2. Hỏi bạn 6 câu về use-case (Q&A / GraphRAG / agentic / multimodal / code RAG).
3. Tự chọn tech stack phù hợp: LLM, embedding, reranker, vector DB, parser.
4. Scaffold project hoàn chỉnh: `docker-compose.yml` + `.env` + `mcp.yaml` + `skills/` + README.
5. `docker compose up -d` → có ngay UI + API chạy trên localhost.

Tất cả **free & open-source**, không vendor lock-in.

## Install

```bash
pip install perfectrag
# hoặc từ source: pip install -e ".[dev]"
```

## Quickstart

```bash
perfectrag init my-rag
cd my-rag
docker compose up -d
```

Mở UI theo stack đã chọn:
- `custom-naive-rag` → http://localhost:3000 (open-webui)
- `ragflow-stack` → http://localhost (RAGFlow)
- `lightrag-stack` → http://localhost:9621 (LightRAG WebUI)
- `dify-stack` → http://localhost (Dify)

## Commands

| Command | Mô tả |
|---|---|
| `perfectrag init [DIR]` | Wizard → scaffold project |
| `perfectrag init DIR --template ragflow-stack` | Force template, skip recommendation |
| `perfectrag init DIR --answers-file a.yml` | Non-interactive (CI) |
| `perfectrag init DIR --dry-run` | Preview recipe, không ghi file |
| `perfectrag hw` | Detect hardware + show tier |
| `perfectrag list templates` | Liệt kê templates bundled |
| `perfectrag list mcp` | Liệt kê MCP servers trong registry |
| `perfectrag list skills` | Liệt kê skills bundled |
| `perfectrag add mcp <name> --project DIR` | Thêm MCP server vào project |
| `perfectrag add skill <name> --project DIR` | Thêm skill vào project |

## Templates

| Template | Use-case | Key components | UI |
|---|---|---|---|
| `custom-naive-rag` | Q&A nhỏ, CPU-only, học | FastAPI + Qdrant + Ollama | open-webui |
| `ragflow-stack` | Q&A hybrid search, agentic, MCP-native | RAGFlow + Elasticsearch + MySQL + Redis + MinIO + Ollama | RAGFlow |
| `lightrag-stack` | GraphRAG / multi-hop reasoning | LightRAG + Ollama + open-webui | LightRAG WebUI |
| `dify-stack` | Workflow / agent / no-code team | Dify + Postgres + Qdrant + Redis + Ollama | Dify Console |

Chọn template khác? `perfectrag init DIR --template <name>`.

## Hardware → tier mapping

| Tier | Khi nào | Default stack |
|---|---|---|
| `cpu` | Không có GPU | `custom-naive-rag` + Qwen2.5 3B (q4) + nomic-embed |
| `apple-low` | Apple Silicon ≤16 GB RAM | `ragflow-stack` + Qwen2.5 7B (q4) |
| `apple-high` | Apple Silicon ≥24 GB RAM | `ragflow-stack` + Qwen2.5 14B (q4) |
| `gpu-8gb` | NVIDIA 6–11 GB VRAM | `ragflow-stack` + Qwen2.5 7B (q5) + BGE-M3 |
| `gpu-12gb` | NVIDIA 12–23 GB VRAM | `ragflow-stack` + Qwen2.5 14B (q4) |
| `gpu-24gb` | NVIDIA ≥24 GB VRAM | `lightrag-stack`/`ragflow-stack` + Qwen2.5 32B (q4) + vLLM |

Routing override hard rules:
- `use_case=graphrag` **or** `multi_hop=true` → `lightrag-stack`
- `use_case=agent_workflow` → `dify-stack`
- `use_case=multimodal` → `ragflow-stack` (với Docling parser)

## Extensibility

### Add MCP tool

Drop vào `mcp.yaml` của project, hoặc dùng CLI:

```bash
perfectrag add mcp tavily --project .
# set TAVILY_API_KEY trong .env
docker compose restart
```

Xem `perfectrag list mcp` cho 10 MCP servers có sẵn (filesystem, fetch, tavily, brave-search, postgres, sqlite, github, memory, sequential-thinking, qdrant).

Thêm MCP tùy ý: edit `mcp.yaml` trực tiếp — format tương thích Claude Code / Cursor / Claude Desktop.

### Add skill

```bash
perfectrag add skill legal-rag --project .
```

Bundled skills: `legal-rag`, `code-rag`, `medical-rag`, `research-rag`. Skill = `skills/<name>/SKILL.md` với YAML frontmatter — copy từ Claude Code skill format.

Tự viết skill? Tạo file `skills/<name>/SKILL.md`:

```markdown
---
name: my-skill
description: short one-liner
---
# my skill
Retrieval / prompt instructions here...
```

### Contribute template

Template = một thư mục Copier trong `src/perfectrag/templates/<name>/`:

```
<name>/
├── copier.yml                    # _templates_suffix: .jinja
├── docker-compose.yml.jinja     # dùng {{ recipe.* }}, {{ hw.* }}, {{ answers.* }}
├── .env.jinja
├── README.md.jinja
├── mcp.yaml.jinja
└── skills/.gitkeep
```

Thêm vào `_DESCRIPTIONS` trong `src/perfectrag/scaffolder.py` — xong.

## Architecture

```
perfectrag CLI
     │
     ├─ hardware.py   (psutil + nvml + sysctl)
     ├─ wizard.py     (InquirerPy conditional questions)
     ├─ recipes.py    (decision matrix: answers+hw → recipe)
     ├─ scaffolder.py (copier wrapper)
     └─ templates/
         ├─ custom-naive-rag/
         ├─ ragflow-stack/
         ├─ lightrag-stack/
         ├─ dify-stack/
         └─ _shared/skills/
```

## Development

```bash
pip install -e ".[dev]"
pytest              # 49 tests
ruff check src tests
mypy src
```

## License

Apache-2.0
