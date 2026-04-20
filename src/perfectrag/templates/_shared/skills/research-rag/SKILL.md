---
name: research-rag
description: Deep-research pattern — synthesize multiple papers into a briefing
---

# Research RAG skill

Khi user hỏi câu research-level:
1. Retrieve rộng (top-k=20), sau đó rerank.
2. Group theo chủ đề / phương pháp / kết quả.
3. Synthesize bullet-point briefing, mỗi bullet có citation.
4. Nêu rõ những gaps trong corpus / câu hỏi chưa có evidence.

## Retrieval hints
- Chunk: 512, với metadata overlap 100 tokens
- Rerank bật
- Enable GraphRAG nếu corpus có nhiều entity/relation
