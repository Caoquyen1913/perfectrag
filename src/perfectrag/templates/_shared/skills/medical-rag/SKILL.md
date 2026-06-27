---
name: medical-rag
description: Cautious retrieval for medical docs with strong disclaimers
---

# Medical RAG skill

When answering medical questions:
- Start with a disclaimer: this is not a substitute for a doctor.
- Cite the source (paper title, PMID, year) for each claim.
- Distinguish evidence levels: systematic review > RCT > case study > opinion.
- When evidence conflicts, present both sides.

## Retrieval hints
- Top-k: 8
- Rerank enabled
- Prefer: abstracts + conclusion sections
