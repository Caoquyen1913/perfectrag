---
name: legal-rag
description: Retrieval prompts tuned for legal documents — contracts, statutes, case law
---

# Legal RAG skill

When answering questions about legal documents:
- Always cite the source (§ section / clause / page) when available.
- Clearly distinguish *the original provision* from *interpretation*.
- Don't give direct legal advice — suggest the user consult a lawyer.
- When sources conflict, prefer the most recent text and the one with higher legal authority.

## Retrieval hints
- Top-k: 10-15 (legal queries need broad context)
- Chunk size: 1024 tokens (keep clauses intact)
- Rerank: enabled
