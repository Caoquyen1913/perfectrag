# Observability

`observability` addon ships LiteLLM gateway + Langfuse tracing + Postgres.

## Setup

```bash
perfectrag init my-rag --with observability
cd my-rag && perfectrag up
```

Open Langfuse at `http://localhost:3100`. LiteLLM admin at `http://localhost:4000/ui`.

## Routing LLM traffic

Point your RAG service at `http://litellm:4000` instead of Ollama directly.
LiteLLM proxies to Ollama but adds tracing, cost tracking, fallbacks.

In `.env`:
```
OLLAMA_URL=http://litellm:4000
OPENAI_API_BASE=http://litellm:4000/v1
OPENAI_API_KEY=${LITELLM_MASTER_KEY}
```

## Pairing with other addons

- **+ Paperclip**: Paperclip's `OPENAI_API_BASE` defaults to LiteLLM → every agent call traced.
- **+ Eval**: eval runner's LLM calls (judge model) traced in Langfuse.
- **+ Context-eng**: DSPy compile traces visible.

## Secrets

`.env.observability` ships with placeholder master keys. Rotate them before production:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"  # LITELLM_MASTER_KEY
```
