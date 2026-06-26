# Gemini advisor

The rule-based recipe engine is free + offline. The Gemini advisor refines it
with LLM reasoning — useful when your use-case has specifics the matrix missed
(legal jargon, code-heavy docs, specific languages).

## Setup

```bash
perfectrag add key gemini AIzaSy...
perfectrag list keys       # shows masked values
```

Key stored in `~/.perfectrag/keys.yml` (chmod 600 on Unix).

## Use it

One-off:
```bash
perfectrag advise "RAG for 10GB of Vietnamese legal PDFs, team of 5, need multi-hop"
```

Inside `init`:
```bash
perfectrag init my-rag --advise --describe "code search across monorepo, 500k files"
```

## What it can change

- `template` (custom-naive-rag, ragflow-stack, lightrag-stack, dify-stack)
- `llm_model`, `llm_runtime`
- `embedding_model`
- `reranker`
- `vector_db`
- `doc_parser`
- `chunk_strategy`, `chunk_size`

The advisor outputs reasoning + a diff vs the base recipe. You see changes
before scaffold.

## Degrades gracefully

No key → prints "No Gemini key" and uses rule-based recipe unchanged. Network
failure → same. Advisor never breaks the build.

## Cost

Uses `gemini-2.5-flash` — typical call ~1k tokens. A few VND per advise call.

## Privacy

Your description is sent to Google Gemini. If that's not acceptable, skip
the advisor — rule-based engine has no outbound calls.
