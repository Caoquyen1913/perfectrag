# perfectRAG — Roadmap & Feature Backlog

> Nguồn: research landscape RAG + code-intelligence (cuối 2025 / đầu 2026) kết hợp phân tích `recipes.py` / `wizard.py`.
> Mục tiêu: làm perfectRAG hoàn chỉnh hơn — kỹ thuật RAG mới, cải thiện phần hỏi đầu để "đánh giá & chọn tốt nhất", và hỗ trợ Claude Code (code graph).
> Format checklist để theo dõi, tránh sót. `[ ]` = chưa làm, `[~]` = đang làm, `[x]` = xong.

---

## 0. Bug / nợ kỹ thuật trong recipe engine (làm trước — rẻ, ảnh hưởng đúng đắn khuyến nghị)

- [x] **`privacy=hybrid_api` đang bị bỏ qua** → đã fix: `recommend()` đọc privacy; tier yếu (cpu/apple-low) + hybrid_api → cloud LLM (`gemini-2.0-flash`). Mở rộng `Recipe.llm_runtime` Literal + guard `ollama pull` ở 4 compose (không pull model cloud) + placeholder `*_API_KEY` trong `.env` (custom-naive-rag).
- [x] **`chunk_strategy` luôn hardcode `recursive`/512** → đã fix: helper `_pick_chunking(answers)` (recursive/512 mặc định; code modality → recursive/768; KHÔNG default semantic).
- [ ] **`code_rag` không làm gì đặc biệt** — route thẳng `ragflow-stack` naive chunk. → route sang track Code Graph (Track A).
- [ ] **Khuyến nghị là 1 pick cứng, không điểm số** — `recommend()` trả 1 `Recipe`. → biến thành scored advisor (Track C).
- [x] Thêm unit test cho privacy + chunking trong `tests/unit/test_recipes.py` (6 test mới, tổng 101 pass).
- [ ] **Follow-up**: cloud LLM hiện chỉ wire vào app dùng perfectrag core (custom-naive-rag). Wiring cloud LLM vào upstream backbone (RAGFlow/Dify/LightRAG) cần config riêng của từng backbone — để Track D / sau.

---

## TRACK A — Code Graph backbone cho Claude Code  ⭐ (ưu tiên cao nhất)

**Bối cảnh research:** ngành đã rời embeddings cho code RAG → chuyển sang **agentic grep + LSP/AST symbol navigation**. Claude Code v2.0.74 (12/2025) có native LSP; Aider dùng tree-sitter repo-map + PageRank; Cursor giữ embeddings làm lớp phụ. Với Claude Code, thứ đáng xây là **code-intelligence expose qua MCP**, KHÔNG phải vector index naive.

> Bạn muốn nhiều option — dưới đây là **6 lựa chọn backbone**, kèm bảng so sánh. Ý tưởng: wizard hỏi thêm "mức code-intelligence" và route vào 1 trong các option này.

### A.1 — Bảng so sánh option (chọn 1 hoặc cho phép chọn nhiều)

| # | Option | Cơ chế | Store / Infra | MCP sẵn? | Ngôn ngữ | License | Khi nào dùng | Verdict |
|---|---|---|---|---|---|---|---|---|
| 1 | **Serena** (oraios) | LSP-based, **không embeddings** | Không cần DB (chạy LSP) | ✅ MCP, Claude-Code-native (`serena setup claude-code`) | 30–40+ | MIT | Mặc định nhẹ, chính xác symbol-level | ⭐ Tốt nhất để default |
| 2 | **code-graph-rag** (vitali87) | tree-sitter AST → graph | **Memgraph** (Docker) | ✅ MCP, ~10 tools (`query_code_graph`, `semantic_search`, surgical edit) | 10 (C/C++/Java/JS/TS/Go/Py/Rust/Lua/PHP) | MIT | Muốn graph truy vấn được + compose | ⭐ Hợp scaffold (docker-compose) |
| 3 | **Blarify** (blarApp) | tree-sitter + **LSP/SCIP** (refs nhanh 330x) | **Neo4j** | một phần | nhiều | OSS | Graph chất lượng cao, refs lớn | Mạnh nhưng nặng ops |
| 4 | **Repo-map generator** (Aider-style / RepoMapper) | tree-sitter + **PageRank**, render token-budget map | Không infra | tự build/skill | 130+ (tree-sitter) | Apache/MIT | Seed overview rẻ cho agent | ⭐ Bổ trợ rẻ, nên kèm option nào cũng được |
| 5 | **Claude Context** (zilliztech) | AST chunk + **embeddings** hybrid dense+BM25, Merkle incremental | **Milvus/Zilliz** | ✅ MCP | nhiều | OSS | Repo rất lớn / tìm kiếm khái niệm | Lớp phụ opt-in |
| 6 | **Potpie** | AST → property graph (calls/imports/inheritance) | **Neo4j** + agents | platform | nhiều | OSS (~5k★) | Muốn "platform" + agent built-in | Nặng, ít drop-in |

> Bonus kỹ thuật (áp dụng cho option nào có embeddings): **cAST chunking** (arXiv 2506.15655) — AST chunk thắng naive (RepoEval Recall@5 +1.8–4.3). Đừng dùng naive chunk cho code.

### A.2 — Đề xuất thiết kế template `code-graph-rag`
- [ ] Wizard `code_rag` hỏi thêm **"mức code-intelligence"**: `repo-map` (rẻ) / `lsp-symbols` (Serena) / `full-graph` (code-graph-rag/Memgraph) / `+embeddings` (Claude Context). *(để Track C — wizard overhaul)*
- [x] Template mới `templates/code-graph-rag/`: docker-compose (Memgraph + Lab, opt-in) + `mcp.yaml` (Serena + ast-grep) + skills/.
- [x] **Mặc định = Serena (LSP, no-infra)**; **opt-in** = full-graph (Memgraph) hoặc embeddings (`add mcp claude-context`).
- [x] Đăng ký template trong `scaffolder._BUILTIN_DESCRIPTIONS` + route `code_rag` trong `recipes._pick_template`.
- [x] Thêm MCP code-intel vào `mcp_registry.py` (serena, ast-grep, claude-context). *(code-graph-rag bundled qua Memgraph compose thay vì registry)*
- [x] Test scaffold + `docker compose config` VALID + routing test.
- [ ] (Nice-to-have) docs `docs/code-graph.md` + bundled skill `code-graph`.

---

## TRACK B — Contextual Retrieval + Eval quality gate (quick-win chất lượng lớn nhất)

### B.1 Contextual Retrieval (Anthropic) — backbone-agnostic
- [ ] Ingest option: LLM prepend 1–2 câu context cho mỗi chunk **trước khi embed + BM25** (giảm 35–67% lỗi retrieval). Dùng prompt caching để rẻ.
- [ ] Thêm cờ `extras.enable_contextual_retrieval`, áp cho cả 4 template.
- [ ] Pairs tốt với **parent-document retrieval** (embed chunk nhỏ, trả parent lớn).

### B.2 Eval harness + CI quality gate (đóng "trust gap")
- [ ] Bake `eval/` vào **mọi** project sinh ra (không chỉ khi add addon): RAGAS (CI nhẹ) hoặc DeepEval (pytest gate).
- [ ] Golden Q&A set template + threshold: `faithfulness ≥ 0.85`, `context_recall ≥ 0.8` → fail build nếu dưới.
- [ ] **Tách metric**: retrieval (recall@k, MRR, nDCG) vs generation (faithfulness, answer-relevancy) — để biết lỗi do chunk hay do prompt.
- [ ] Citation / groundedness gate trước khi trả lời.

---

## TRACK C — Scored Advisor wizard ("đánh giá & chọn tốt nhất")

### C.1 Thêm câu hỏi thật sự lái quyết định
- [ ] **Độ trễ chấp nhận** (interactive <1s / vài giây / batch) → reranker, vLLM vs ollama, CAG vs RAG.
- [ ] **Ưu tiên: accuracy vs cost vs speed** (chọn 1–2) → cloud vs local, contextual retrieval on/off.
- [ ] **Ngôn ngữ corpus** (Anh / đa ngữ / VN) → embedding (bge-m3 vs e5), reranker đa ngữ.
- [ ] **Tần suất cập nhật dữ liệu** (tĩnh / định kỳ / streaming) → ingest-worker addon, CAG (tĩnh) vs RAG (động).
- [ ] **Hạ tầng sẵn có** (Postgres? Elastic? K8s?) → pgvector tái dùng PG, deploy target.
- [ ] **Cần trích dẫn / tuân thủ?** → citation gate, backbone permission-aware (Onyx).
- [ ] **Ngân sách API/tháng** (nếu hybrid) → cap model size, fallback local.

### C.2 Biến `recommend()` thành scored evaluator
- [ ] Chấm điểm từng template theo trục (fit use-case, latency, cost, privacy, scale).
- [ ] Trả **top-3 ranking + lý do + trade-off**, highlight #1 (thay vì 1 pick cứng).
- [ ] Mở rộng `advisor.py` (đang chỉ gọi Gemini refine) để render bảng so sánh có điểm.

---

## TRACK D — Backbone / template mới (lấp use-case 4 template chưa có)

- [ ] **R2R (SciPhi, MIT)** — all-in-one production: hybrid+RRF+GraphRAG+multimodal+**agentic RAG** sẵn. Lấp gap "agentic". ⭐
- [ ] **Onyx (ex-Danswer, MIT)** — **enterprise connectors** (40+: Slack/Drive/GitHub/Confluence), permission-aware, air-gapped Helm/K8s. Use-case "chat trên data công ty". ⭐
- [ ] **Cognee** (tuỳ chọn) — graph+vector "AI memory" + ontology, persistent agent memory.
- [ ] Mỗi template: dir + `copier.yml` + đăng ký `scaffolder._DESCRIPTIONS` + route `recipes._pick_template` + docs.

---

## TRACK E — Kỹ thuật RAG bổ sung (proven, thêm dần)

- [ ] **RRF (Reciprocal Rank Fusion)** cho hybrid search — chuẩn mực; xác nhận hybrid hiện có dùng.
- [ ] **Query rewriting / decomposition** (multi-hop, hội thoại) — nên default.
- [ ] **Parent-document / hierarchical retrieval** — default, pairs với contextual retrieval.
- [ ] **CRAG (Corrective RAG)** agentic loop — opt-in (thắng Self-RAG vì model-agnostic).
- [ ] **Modernize reranker**: chọn theo leaderboard (Cohere v4 / Voyage 2.5 / Zerank-2 / bge-reranker-v2-m3 / Jina v3) thay vì 3 tên cứng.
- [ ] **CAG (Cache-Augmented Generation)** flag cho corpus nhỏ/ổn định; router CAG hot-path + RAG cold-path.
- [ ] ⚠️ **KHÔNG default semantic chunking** — recursive 512 thắng cost/quality theo benchmark 2025-26. Chỉ offer, không push.
- [ ] (Tham khảo, không default) RAPTOR (multi-doc summary tree), HyDE (chỉ opt-in — hại query số/chính xác), ColBERT late-interaction (niche, tốn storage), RAFT (sau khi đã có RAG chạy + lỗi behavior).

---

## Thứ tự đề xuất (sequencing)

1. **Track 0** (bug fixes) — rẻ, nền tảng cho mọi thứ sau.
2. **Track A** (Code Graph) — khác biệt nhất, đúng đối tượng Claude Code. ⭐
3. **Track B** (Contextual Retrieval + Eval) — quick-win chất lượng + trust.
4. **Track C** (Scored Advisor) — đúng trọng tâm "chọn tốt nhất".
5. **Track D** (R2R / Onyx) — mở rộng độ phủ use-case.
6. **Track E** — bổ sung dần theo nhu cầu.

---

## Nguồn chính (research)

**RAG techniques / frameworks**
- Contextual Retrieval — https://www.anthropic.com/news/contextual-retrieval
- Reranker 2025 guide — https://www.zeroentropy.dev/articles/ultimate-guide-to-choosing-the-best-reranking-model-in-2025
- CRAG — https://openreview.net/pdf?id=JnWJbrnaUE
- Chunking benchmark (recursive > semantic) — https://arxiv.org/abs/2504.19754
- RAG vs CAG 2026 — https://futureagi.com/blog/rag-vs-cag-cache-augmented-generation-2026/ · CAG — https://arxiv.org/html/2412.15605v2
- R2R — https://github.com/SciPhi-AI/R2R · Onyx — https://github.com/onyx-dot-app/onyx · Cognee — https://github.com/topoteretes/cognee
- Eval frameworks — https://callsphere.ai/blog/rag-evaluation-frameworks-2026-ragas-trulens-deepeval

**Code graph / code RAG**
- Claude Code no-index — https://vadim.blog/claude-code-no-indexing/ · grep backbone — https://yage.ai/share/why-coding-agents-still-use-grep-en-20260327.html
- Claude Code LSP v2.0.74 — https://www.how2shout.com/news/claude-code-v2-0-74-lsp-language-server-protocol-update.html
- cAST chunking — https://arxiv.org/html/2506.15655v1 · Aider repo-map — https://aider.chat/2023/10/22/repomap.html
- Serena — https://github.com/oraios/serena · code-graph-rag — https://github.com/vitali87/code-graph-rag · Blarify — https://github.com/blarApp/blarify · Potpie — https://github.com/potpie-ai/potpie
- Claude Context — https://github.com/zilliztech/claude-context · CocoIndex — https://cocoindex.io/cocoindex-code/ · ast-grep MCP — https://github.com/ast-grep/ast-grep-mcp
- SCIP — https://sourcegraph.com/blog/announcing-scip · Cursor semantic search — https://cursor.com/blog/semsearch
