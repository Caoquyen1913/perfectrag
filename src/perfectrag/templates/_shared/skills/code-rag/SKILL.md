---
name: code-rag
description: Retrieval + answer pattern for codebase Q&A with symbol grounding
---

# Code RAG skill

Khi trả lời câu hỏi về codebase:
- Luôn reference `path:line` khi nhắc đến symbol.
- Đọc tối thiểu 2 snippet liên quan trước khi kết luận.
- Khi giải thích flow, trace theo call graph (caller → callee).
- Không bịa API — chỉ giải thích những gì có trong index.

## Retrieval hints
- Chunk: semantic boundaries (function/class)
- Hybrid search (BM25 + vector) bật
- Metadata: language, path, symbol type
