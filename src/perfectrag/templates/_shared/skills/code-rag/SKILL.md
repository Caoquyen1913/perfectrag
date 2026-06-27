---
name: code-rag
description: Retrieval + answer pattern for codebase Q&A with symbol grounding
---

# Code RAG skill

When answering questions about the codebase:
- Always reference `path:line` when mentioning a symbol.
- Read at least 2 relevant snippets before drawing conclusions.
- When explaining a flow, trace the call graph (caller → callee).
- Don't invent APIs — only explain what's in the index.

## Retrieval hints
- Chunk: semantic boundaries (function/class)
- Hybrid search (BM25 + vector) enabled
- Metadata: language, path, symbol type
