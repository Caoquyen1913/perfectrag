# Addons

Addons are docker-compose overlays that layer on top of a generated project.
Install with `--with` at init time or `perfectrag add addon <name>` afterwards.

## Catalogue

| Addon | What it runs | Port | Env needed |
|---|---|---|---|
| `ingest-worker` | Crawl4AI scheduled crawler → Qdrant | — | — |
| `eval` | RAGAS + DeepEval runner + HTML report viewer | 8081 | — |
| `observability` | LiteLLM gateway + Langfuse tracing | 4000, 3100 | master keys auto-gen |
| `context-eng` | FastAPI wrapping DSPy + LLMLingua + mem0 | 8002 | — |
| `notion-sync` | Notion API → Qdrant on cron | — | `NOTION_API_KEY` |
| `gdrive-sync` | Google Drive → Qdrant on cron | — | `GDRIVE_SERVICE_ACCOUNT_JSON` |
| `confluence-sync` | Confluence → Qdrant on cron | — | `CONFLUENCE_URL`, `CONFLUENCE_API_TOKEN` |
| `paperclip` | Paperclip multi-agent orchestrator | 8888 | `PAPERCLIP_LLM_API_KEY` (or LiteLLM via observability) |

## How it works

Each addon ships:
- `compose.<name>.yml.jinja` — docker-compose overlay
- Optional `<name>/` directory with runtime code, configs, Dockerfiles

On `perfectrag add addon X`:
1. Files copied into project (Jinja rendered using saved `recipe`/`hw`/`answers`).
2. Name appended to `.perfectrag/addons.yml`.

On `perfectrag up`:
```
docker compose -f docker-compose.yml -f compose.eval.yml -f compose.observability.yml ... up -d
```

The orchestrator chains the overlays automatically from `addons.yml`. No manual flag juggling.

## Writing your own addon

1. Create `src/perfectrag/templates/_shared/addons/<name>/compose.<name>.yml.jinja`
2. (Optional) Create `<name>/` sibling folder with scripts, Dockerfile, requirements
3. Register in `src/perfectrag/addons.py:REGISTRY`
4. Add tests in `tests/unit/test_addons.py`

Template variables available in Jinja:
- `{{ recipe.llm_model }}`, `{{ recipe.embedding_model }}`, `{{ recipe.gpu_enabled }}`
- `{{ hw.gpu_vendor }}`, `{{ hw.vram_gb }}`, `{{ hw.tier }}`
- `{{ answers.use_case }}`, `{{ answers.multi_hop }}`
- `{{ project_name }}`

## Installation order

Addons are independent unless they declare `requires=(...)` in their spec.
Good compositions:
- `eval` + `observability` — measure *and* trace
- `ingest-worker` + `notion-sync` — web + Notion into one corpus
- `paperclip` + `observability` — agent calls go via LiteLLM → Langfuse traces every step
