"""Interactive wizard: conditional prompts that produce an `Answers` object.

v1.1: `run_component_wizard()` offers optional power-user overrides for specific
tech picks (vector DB, embedding, reranker, LLM runtime) after the base wizard.
"""

from __future__ import annotations

from dataclasses import dataclass

from InquirerPy import inquirer
from InquirerPy.base.control import Choice

from perfectrag.recipes import Answers


@dataclass
class ComponentOverrides:
    vector_db: str | None = None
    embedding_model: str | None = None
    reranker: str | None = None
    llm_runtime: str | None = None


def run_wizard() -> Answers:
    use_case = inquirer.select(
        message="Use-case chính của RAG service này?",
        choices=[
            Choice("qa_docs", name="Q&A trên tài liệu (PDF / Markdown / docs)"),
            Choice("graphrag", name="GraphRAG — multi-hop reasoning, knowledge graph"),
            Choice("multimodal", name="Multimodal — text + images + tables"),
            Choice("code_rag", name="Code search / code RAG"),
            Choice("agent_workflow", name="Agent / workflow with tool calling"),
        ],
        default="qa_docs",
    ).execute()

    modality = inquirer.checkbox(
        message="Loại dữ liệu trong corpus? (space to toggle, enter to confirm)",
        choices=[
            Choice("text", name="Text thuần", enabled=True),
            Choice("tables", name="Bảng (PDF có table)"),
            Choice("images", name="Hình ảnh / scanned docs"),
            Choice("code", name="Source code"),
        ],
    ).execute()

    privacy = inquirer.select(
        message="Yêu cầu privacy?",
        choices=[
            Choice("fully_local", name="Fully local (không gọi API cloud nào)"),
            Choice("hybrid_api", name="Hybrid — có thể dùng API cloud cho LLM lớn"),
        ],
        default="fully_local",
    ).execute()

    multi_hop = False
    if use_case != "graphrag":
        multi_hop = inquirer.confirm(
            message="Câu hỏi thường cần multi-hop reasoning (suy luận qua nhiều tài liệu)?",
            default=False,
        ).execute()

    corpus_size = inquirer.select(
        message="Corpus size dự kiến?",
        choices=[
            Choice("small", name="Nhỏ (<10k docs)"),
            Choice("medium", name="Vừa (10k - 1M docs)"),
            Choice("large", name="Lớn (>1M docs)"),
        ],
        default="small",
    ).execute()

    user_scale = inquirer.select(
        message="Số lượng user đồng thời?",
        choices=[
            Choice("solo", name="Solo dev / cá nhân"),
            Choice("team", name="Team (<10 users)"),
            Choice("production", name="Production (nhiều user, cần SLA)"),
        ],
        default="solo",
    ).execute()

    latency = inquirer.select(
        message="Độ trễ chấp nhận cho mỗi truy vấn?",
        choices=[
            Choice("interactive", name="Interactive (<1s — chat realtime)"),
            Choice("standard", name="Standard (vài giây)"),
            Choice("batch", name="Batch (không gấp)"),
        ],
        default="standard",
    ).execute()

    priority = inquirer.select(
        message="Ưu tiên cao nhất?",
        choices=[
            Choice("balanced", name="Cân bằng"),
            Choice("accuracy", name="Độ chính xác"),
            Choice("cost", name="Chi phí thấp"),
            Choice("speed", name="Tốc độ"),
        ],
        default="balanced",
    ).execute()

    language = inquirer.select(
        message="Ngôn ngữ corpus?",
        choices=[
            Choice("english", name="Tiếng Anh"),
            Choice("multilingual", name="Đa ngữ"),
            Choice("vietnamese", name="Tiếng Việt"),
        ],
        default="english",
    ).execute()

    freshness = inquirer.select(
        message="Tần suất cập nhật dữ liệu?",
        choices=[
            Choice("static", name="Tĩnh (ít/không đổi)"),
            Choice("periodic", name="Định kỳ (crawl/sync theo lịch)"),
            Choice("streaming", name="Streaming (liên tục)"),
        ],
        default="static",
    ).execute()

    existing_infra = inquirer.checkbox(
        message="Hạ tầng đã có sẵn? (space để chọn)",
        choices=[
            Choice("postgres", name="PostgreSQL (có thể tái dùng làm vector store)"),
            Choice("elasticsearch", name="Elasticsearch"),
            Choice("k8s", name="Kubernetes"),
        ],
    ).execute()

    needs_citations = inquirer.confirm(
        message="Cần trích dẫn nguồn / groundedness?",
        default=False,
    ).execute()

    return Answers(
        use_case=use_case,
        modality=modality or ["text"],
        privacy=privacy,
        multi_hop=multi_hop,
        corpus_size=corpus_size,
        user_scale=user_scale,
        latency=latency,
        priority=priority,
        language=language,
        freshness=freshness,
        existing_infra=existing_infra or [],
        needs_citations=needs_citations,
    )


def run_component_wizard(base_recipe) -> ComponentOverrides:
    """Optional power-user pass — pick specific tech. Each prompt offers 'auto' (keep base)."""
    override = inquirer.confirm(
        message="Muốn custom components (vector DB / embed / rerank / LLM runtime)?",
        default=False,
    ).execute()
    if not override:
        return ComponentOverrides()

    vdb = inquirer.select(
        message="Vector DB?",
        choices=[
            Choice(None, name=f"auto ({base_recipe.vector_db})"),
            Choice("qdrant", name="Qdrant — embedded or remote, fast"),
            Choice("milvus", name="Milvus-Lite — embedded, scale-ready"),
            Choice("chroma", name="Chroma — zero-config, file-backed"),
            Choice("lancedb", name="LanceDB — columnar, disk-efficient"),
            Choice("pgvector", name="pgvector — reuse existing Postgres"),
        ],
        default=None,
    ).execute()

    emb = inquirer.select(
        message="Embedding model?",
        choices=[
            Choice(None, name=f"auto ({base_recipe.embedding_model})"),
            Choice("BAAI/bge-m3", name="BGE-M3 — multilingual, 8K context"),
            Choice("nomic-embed-text", name="nomic-embed-text — via Ollama"),
            Choice("jinaai/jina-embeddings-v3", name="Jina v3 — multilingual, task-aware"),
            Choice("intfloat/e5-large-v2", name="E5-large — English, fast"),
            Choice("Qwen/Qwen3-Embedding-0.6B", name="Qwen3 Embed — long context"),
        ],
        default=None,
    ).execute()

    rer = inquirer.select(
        message="Reranker?",
        choices=[
            Choice(None, name=f"auto ({base_recipe.reranker or 'none'})"),
            Choice("BAAI/bge-reranker-v2-m3", name="BGE reranker v2 m3"),
            Choice("jinaai/jina-reranker-v2-base-multilingual", name="Jina reranker v2"),
            Choice("mixedbread-ai/mxbai-rerank-large-v1", name="mxbai rerank large"),
            Choice("colbert-ir/colbertv2.0", name="ColBERT late-interaction"),
            Choice("none", name="No reranker"),
        ],
        default=None,
    ).execute()

    llm_rt = inquirer.select(
        message="LLM runtime?",
        choices=[
            Choice(None, name=f"auto ({base_recipe.llm_runtime})"),
            Choice("ollama", name="Ollama — HTTP server"),
            Choice("llamacpp", name="llama-cpp-python — in-process GGUF"),
            Choice("vllm", name="vLLM — production batching"),
            Choice("gemini", name="Gemini — cloud, needs API key"),
            Choice("anthropic", name="Anthropic Claude — cloud, needs API key"),
            Choice("openai", name="OpenAI-compat — cloud or LiteLLM proxy"),
        ],
        default=None,
    ).execute()

    return ComponentOverrides(
        vector_db=vdb,
        embedding_model=emb,
        reranker=rer,
        llm_runtime=llm_rt,
    )
