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
        message="Primary use-case for this RAG service?",
        choices=[
            Choice("qa_docs", name="Q&A over documents (PDF / Markdown / docs)"),
            Choice("graphrag", name="GraphRAG — multi-hop reasoning, knowledge graph"),
            Choice("multimodal", name="Multimodal — text + images + tables"),
            Choice("code_rag", name="Code search / code RAG"),
            Choice("agent_workflow", name="Agent / workflow with tool calling"),
        ],
        default="qa_docs",
    ).execute()

    modality = inquirer.checkbox(
        message="Data types in the corpus? (space to toggle, enter to confirm)",
        choices=[
            Choice("text", name="Plain text", enabled=True),
            Choice("tables", name="Tables (PDFs with tables)"),
            Choice("images", name="Images / scanned docs"),
            Choice("code", name="Source code"),
        ],
    ).execute()

    privacy = inquirer.select(
        message="Privacy requirement?",
        choices=[
            Choice("fully_local", name="Fully local (no cloud API calls at all)"),
            Choice("hybrid_api", name="Hybrid — may use a cloud API for large LLMs"),
        ],
        default="fully_local",
    ).execute()

    multi_hop = False
    if use_case != "graphrag":
        multi_hop = inquirer.confirm(
            message="Do queries typically need multi-hop reasoning (reasoning across multiple documents)?",
            default=False,
        ).execute()

    corpus_size = inquirer.select(
        message="Expected corpus size?",
        choices=[
            Choice("small", name="Small (<10k docs)"),
            Choice("medium", name="Medium (10k - 1M docs)"),
            Choice("large", name="Large (>1M docs)"),
        ],
        default="small",
    ).execute()

    user_scale = inquirer.select(
        message="Number of concurrent users?",
        choices=[
            Choice("solo", name="Solo dev / individual"),
            Choice("team", name="Team (<10 users)"),
            Choice("production", name="Production (many users, needs SLA)"),
        ],
        default="solo",
    ).execute()

    latency = inquirer.select(
        message="Acceptable latency per query?",
        choices=[
            Choice("interactive", name="Interactive (<1s — realtime chat)"),
            Choice("standard", name="Standard (a few seconds)"),
            Choice("batch", name="Batch (no rush)"),
        ],
        default="standard",
    ).execute()

    priority = inquirer.select(
        message="Top priority?",
        choices=[
            Choice("balanced", name="Balanced"),
            Choice("accuracy", name="Accuracy"),
            Choice("cost", name="Low cost"),
            Choice("speed", name="Speed"),
        ],
        default="balanced",
    ).execute()

    language = inquirer.select(
        message="Corpus language?",
        choices=[
            Choice("english", name="English"),
            Choice("multilingual", name="Multilingual"),
            Choice("vietnamese", name="Vietnamese"),
        ],
        default="english",
    ).execute()

    freshness = inquirer.select(
        message="How often is the data updated?",
        choices=[
            Choice("static", name="Static (rarely/never changes)"),
            Choice("periodic", name="Periodic (scheduled crawl/sync)"),
            Choice("streaming", name="Streaming (continuous)"),
        ],
        default="static",
    ).execute()

    existing_infra = inquirer.checkbox(
        message="Existing infrastructure? (space to select)",
        choices=[
            Choice("postgres", name="PostgreSQL (can be reused as a vector store)"),
            Choice("elasticsearch", name="Elasticsearch"),
            Choice("k8s", name="Kubernetes"),
        ],
    ).execute()

    needs_citations = inquirer.confirm(
        message="Need source citations / groundedness?",
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
        message="Customize components (vector DB / embed / rerank / LLM runtime)?",
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
