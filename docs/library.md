# Library mode — no Docker

Use perfectrag as a Python library; skip Docker entirely.

## Install

```bash
# Core + one vector DB + one embedding backend + one LLM runtime
pip install 'perfectrag[chroma,embed-torch]'    # minimal local
# or: pip install 'perfectrag[qdrant,llamacpp]'
```

Extras:
- Vector DBs: `[qdrant]` `[milvus]` `[chroma]` `[lancedb]` `[pgvector]`
- Embeddings: `[embed-torch]` (sentence-transformers)
- LLM: `[llamacpp]` (in-process GGUF)
- Gemini advisor: `[advisor]`
- SaaS API + UI backend: `[web]`

## perfectrag.yml

```yaml
collection: documents
chunk_size: 512
top_k: 5

store:
  name: chroma
  path: ./data/chroma

embedding:
  model: BAAI/bge-m3

reranker:
  model: BAAI/bge-reranker-v2-m3

llm:
  runtime: ollama             # or llamacpp, gemini, anthropic, openai, vllm
  model: qwen2.5:7b-instruct-q5_K_M
  url: http://localhost:11434

parser:
  name: markitdown
```

## Python API

```python
from perfectrag import RAG

rag = RAG.from_config("perfectrag.yml")

rag.ingest("./docs")
# or inline:
rag.ingest_text("retrieval-augmented generation is...", source="manual")

result = rag.query("What is RAG?")
print(result.answer)
for h in result.hits:
    print(h.chunk.source, h.score)

# streaming
for ev, payload in rag.stream("Explain in 3 bullets"):
    if ev == "token":
        print(payload, end="", flush=True)
```

## CLI

```bash
perfectrag run --config perfectrag.yml --ingest ./docs
perfectrag run --config perfectrag.yml --query "What is RAG?"
perfectrag run --config perfectrag.yml --serve --port 8000   # starts Query API
```

## Swap backends

Switch vector DB without touching code:

```yaml
# Qdrant (embedded)
store: { name: qdrant, path: ./data/qdrant-storage }

# Milvus-Lite
store: { name: milvus, path: ./data/milvus.db }

# LanceDB
store: { name: lancedb, path: ./data/lancedb }

# pgvector (reuse existing Postgres)
store: { name: pgvector, url: postgresql://user:pw@host/db }
```

Same pattern for LLMs — edit `llm.runtime` + `llm.model`, no code changes.
