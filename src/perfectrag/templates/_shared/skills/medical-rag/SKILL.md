---
name: medical-rag
description: Cautious retrieval for medical docs with strong disclaimers
---

# Medical RAG skill

Khi trả lời câu hỏi y khoa:
- Bắt đầu bằng disclaimer: không thay thế bác sĩ.
- Trích nguồn (paper title, PMID, year) cho mỗi claim.
- Phân biệt evidence level: systematic review > RCT > case study > opinion.
- Khi có bằng chứng mâu thuẫn, trình bày cả 2 phía.

## Retrieval hints
- Top-k: 8
- Rerank bật
- Prefer: abstracts + conclusion sections
