---
name: legal-rag
description: Retrieval prompts tuned for legal documents — contracts, statutes, case law
---

# Legal RAG skill

Khi trả lời câu hỏi về tài liệu pháp lý:
- Luôn trích nguồn (§ section / clause / page) khi có.
- Phân biệt rõ *quy định gốc* vs *giải thích*.
- Không đưa ra tư vấn pháp lý trực tiếp — gợi ý người dùng tham vấn luật sư.
- Khi có mâu thuẫn giữa các nguồn, ưu tiên văn bản mới nhất và có hiệu lực cao hơn.

## Retrieval hints
- Top-k: 10-15 (legal queries cần context rộng)
- Chunk size: 1024 tokens (giữ nguyên điều khoản)
- Rerank: bật
