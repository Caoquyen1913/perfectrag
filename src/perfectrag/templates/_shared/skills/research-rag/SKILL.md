---
name: research-rag
description: Deep-research pattern — synthesize multiple papers into a briefing
---

# Research RAG skill

When the user asks a research-level question:
1. Retrieve broadly (top-k=20), then rerank.
2. Group by topic / method / result.
3. Synthesize a bullet-point briefing, with a citation on each bullet.
4. Clearly state gaps in the corpus / questions that lack evidence.

## Retrieval hints
- Chunk: 512, with 100-token metadata overlap
- Rerank enabled
- Enable GraphRAG if the corpus has many entities/relations
