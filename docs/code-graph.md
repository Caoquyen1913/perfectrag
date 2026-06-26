# Code intelligence — `code-graph-rag` template

For the `code_rag` use-case, perfectRAG scaffolds the `code-graph-rag` template
instead of a generic vector stack. It gives AI coding agents (Claude Code,
Cursor) **precise, structural** code navigation — symbols, references, call
hierarchy — which is what raises task success, not naive vector search over
code.

```bash
perfectrag init ./my-code-rag --template code-graph-rag
```

## What you get

| Layer | Tool | Infra |
|---|---|---|
| Primary (default) | **Serena** — LSP symbol nav, 30+ languages | none (runs via `uvx`) |
| Structural search | **ast-grep** — AST pattern match/rewrite | none |
| Optional graph | Memgraph + Lab UI | `docker compose up` |
| Optional semantic | `claude-context` (Milvus) | `perfectrag add mcp claude-context` |

## Wire into Claude Code (no Docker)

1. Point the repo to index:

   ```bash
   export REPO_PATH=/path/to/your/repo
   ```

2. Register the generated `mcp.yaml` with Claude Code. Serena launches on demand
   and answers things grep can't: *"find all references to `recommend`"*, *"show
   the call hierarchy of `render`"*.

## Optional persistent graph

```bash
docker compose up -d   # Memgraph (bolt :7687) + Lab UI (:3000)
```

Index the repo into Memgraph with a graph indexer such as
[code-graph-rag](https://github.com/vitali87/code-graph-rag), then explore the
AST/call graph visually. Opt-in — Serena alone covers most navigation.

## Why not vector RAG over code?

The field (Claude Code, Aider, Cognition's SWE-grep) has largely moved from
embeddings to **agentic search + LSP/AST**. Naive vector chunking splits
functions mid-body and loses signatures. If you do embed code, use AST-aware
chunking (cAST), exposed via `claude-context`, and treat it as a secondary
semantic layer for large repos — not the primary mechanism.
