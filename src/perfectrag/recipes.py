"""Decision matrix: (user answers + hardware) -> concrete techstack recipe.

The mapping is opinionated but documented. Users can override any field in the
wizard's final confirmation step.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from perfectrag.hardware import HardwareProfile

UseCase = Literal["qa_docs", "graphrag", "multimodal", "code_rag", "agent_workflow"]
Privacy = Literal["fully_local", "hybrid_api"]
CorpusSize = Literal["small", "medium", "large"]  # <10k, 10k-1M, >1M
UserScale = Literal["solo", "team", "production"]
Latency = Literal["interactive", "standard", "batch"]
Priority = Literal["accuracy", "cost", "speed", "balanced"]
Language = Literal["english", "multilingual", "vietnamese"]
Freshness = Literal["static", "periodic", "streaming"]
LLMRuntime = Literal["ollama", "vllm", "llamacpp", "gemini", "anthropic", "openai"]
VectorDB = Literal["qdrant", "milvus", "chroma", "lancedb", "pgvector"]
DocParser = Literal["docling", "markitdown", "unstructured", "llamaparse"]
ChunkStrategy = Literal["recursive", "semantic", "late"]


@dataclass(frozen=True)
class Answers:
    use_case: UseCase
    modality: list[str]  # ["text", "tables", "images", "code"]
    privacy: Privacy
    multi_hop: bool
    corpus_size: CorpusSize
    user_scale: UserScale
    # --- v1.2 evaluative inputs (optional; defaults keep old behavior) ---
    latency: Latency = "standard"
    priority: Priority = "balanced"
    language: Language = "english"
    freshness: Freshness = "static"
    existing_infra: list[str] = field(default_factory=list)  # e.g. ["postgres", "k8s"]
    needs_citations: bool = False


@dataclass
class Recipe:
    template: str
    llm_model: str
    llm_runtime: LLMRuntime
    embedding_model: str
    reranker: str | None
    vector_db: VectorDB
    doc_parser: DocParser
    chunk_strategy: ChunkStrategy
    chunk_size: int
    gpu_enabled: bool
    vram_cap_gb: int
    notes: list[str] = field(default_factory=list)
    extras: dict[str, Any] = field(default_factory=dict)

    def as_template_vars(self, hw: HardwareProfile, answers: Answers) -> dict[str, Any]:
        """Flatten to vars Copier/Jinja can consume."""
        return {
            "recipe": {
                "template": self.template,
                "llm_model": self.llm_model,
                "llm_runtime": self.llm_runtime,
                "embedding_model": self.embedding_model,
                "reranker": self.reranker,
                "vector_db": self.vector_db,
                "doc_parser": self.doc_parser,
                "chunk_strategy": self.chunk_strategy,
                "chunk_size": self.chunk_size,
                "gpu_enabled": self.gpu_enabled,
                "vram_cap_gb": self.vram_cap_gb,
                "extras": self.extras,
            },
            "hw": hw.as_dict(),
            "answers": {
                "use_case": answers.use_case,
                "modality": answers.modality,
                "privacy": answers.privacy,
                "multi_hop": answers.multi_hop,
                "corpus_size": answers.corpus_size,
                "user_scale": answers.user_scale,
                "latency": answers.latency,
                "priority": answers.priority,
                "language": answers.language,
                "freshness": answers.freshness,
                "existing_infra": answers.existing_infra,
                "needs_citations": answers.needs_citations,
            },
        }


# --- Model tables by hardware tier ---

_LLM_BY_TIER: dict[str, tuple[str, LLMRuntime]] = {
    "cpu":        ("qwen2.5:3b-instruct-q4_K_M",  "llamacpp"),
    "apple-low":  ("qwen2.5:7b-instruct-q4_K_M",  "ollama"),
    "apple-high": ("qwen2.5:14b-instruct-q4_K_M", "ollama"),
    "gpu-8gb":    ("qwen2.5:7b-instruct-q5_K_M",  "ollama"),
    "gpu-12gb":   ("qwen2.5:14b-instruct-q4_K_M", "ollama"),
    "gpu-24gb":   ("qwen2.5:32b-instruct-q4_K_M", "vllm"),
}

_EMBED_BY_TIER = {
    "cpu":        "nomic-embed-text",
    "apple-low":  "BAAI/bge-m3",
    "apple-high": "BAAI/bge-m3",
    "gpu-8gb":    "BAAI/bge-m3",
    "gpu-12gb":   "BAAI/bge-m3",
    "gpu-24gb":   "BAAI/bge-m3",
}

_VECTORDB_BY_CORPUS: dict[str, VectorDB] = {
    "small":  "chroma",
    "medium": "qdrant",
    "large":  "milvus",
}

# Tiers too weak to run a useful local LLM at interactive speed. When the user
# allows cloud (privacy=hybrid_api), recommend() upgrades these to a cloud LLM.
_WEAK_TIERS = {"cpu", "apple-low"}

# Default cloud LLM when hardware is weak and privacy allows it. Cheap + fast;
# the user can swap the model/runtime in perfectrag.yml. Needs an API key.
_CLOUD_LLM: tuple[str, LLMRuntime] = ("gemini-2.0-flash", "gemini")

_PARSER_BY_MODALITY: list[tuple[set[str], DocParser]] = [
    ({"images", "tables"}, "docling"),
    ({"tables"},           "docling"),
    ({"images"},           "docling"),
    (set(),                "markitdown"),
]


def _pick_parser(modality: list[str]) -> DocParser:
    mod = set(modality)
    for needed, parser in _PARSER_BY_MODALITY:
        if needed and needed.issubset(mod):
            return parser
    return "markitdown"


def _pick_chunking(answers: Answers) -> tuple[ChunkStrategy, int]:
    """Pick (strategy, size). Recursive ~512 is the cost/quality default — 2025-26
    benchmarks show semantic chunking rarely beats it. Code corpora use larger
    chunks so functions/classes stay intact (cAST-style)."""
    if "code" in answers.modality:
        return "recursive", 768
    return "recursive", 512


def _pick_template(answers: Answers, tier: str) -> tuple[str, list[str]]:
    notes: list[str] = []

    # Hard routing rules (in priority order)
    if answers.use_case == "graphrag" or answers.multi_hop:
        if tier in ("cpu", "apple-low"):
            notes.append(
                "GraphRAG yêu cầu LLM mạnh; hardware hiện tại có thể chạy chậm. "
                "Cân nhắc upgrade hoặc giảm corpus."
            )
        return "lightrag-stack", notes

    if answers.use_case == "agent_workflow":
        return "dify-stack", notes

    if answers.use_case == "multimodal":
        if tier in ("cpu", "apple-low", "gpu-8gb"):
            notes.append("Multimodal RAG cần VRAM cao; có thể giảm chất lượng hình ảnh.")
        return "ragflow-stack", notes

    if answers.use_case == "code_rag":
        return "code-graph-rag", notes

    # qa_docs default
    if tier == "cpu":
        return "custom-naive-rag", notes
    return "ragflow-stack", notes


def recommend(answers: Answers, hw: HardwareProfile) -> Recipe:
    tier = hw.tier
    llm_model, llm_runtime = _LLM_BY_TIER[tier]
    embed = _EMBED_BY_TIER[tier]
    vector_db = _VECTORDB_BY_CORPUS[answers.corpus_size]
    parser = _pick_parser(answers.modality)
    template, notes = _pick_template(answers, tier)

    # Privacy allows cloud + hardware too weak for a good local LLM → use cloud.
    if answers.privacy == "hybrid_api" and tier in _WEAK_TIERS:
        llm_model, llm_runtime = _CLOUD_LLM
        notes.append(
            f"Hardware tier '{tier}' yếu cho LLM local; privacy=hybrid_api nên dùng "
            f"cloud LLM ({llm_model}). Cần API key — đổi model/runtime trong perfectrag.yml nếu muốn."
        )

    # Production scale → prefer vLLM if GPU has room
    if answers.user_scale == "production" and tier in ("gpu-12gb", "gpu-24gb"):
        llm_runtime = "vllm"

    # Naive template uses smaller vector db / no reranker for simplicity
    if template == "custom-naive-rag":
        vector_db = "qdrant"  # bundled in template
        reranker: str | None = None
    else:
        reranker = "jinaai/jina-reranker-v2-base-multilingual"

    # --- v1.2 evaluative overrides ---
    # Multilingual corpus → multilingual embedding regardless of the tier default.
    if answers.language in ("multilingual", "vietnamese"):
        embed = "BAAI/bge-m3"
        notes.append(f"Corpus {answers.language} → embedding đa ngữ BAAI/bge-m3.")

    # Reuse existing Postgres as the vector store (naive template bundles qdrant).
    if "postgres" in answers.existing_infra and template != "custom-naive-rag":
        vector_db = "pgvector"
        notes.append("Có 'postgres' trong infra → dùng pgvector (tái dùng Postgres).")

    # Interactive latency / speed priority → drop the reranker to cut a model hop.
    if (answers.latency == "interactive" or answers.priority == "speed") and reranker:
        notes.append("Ưu tiên tốc độ → bỏ reranker để giảm latency.")
        reranker = None

    chunk_strategy, chunk_size = _pick_chunking(answers)

    gpu_enabled = hw.gpu_vendor in ("nvidia", "amd", "apple")
    vram_cap = hw.vram_gb if hw.gpu_vendor == "nvidia" else max(hw.ram_gb // 2, 4)

    extras: dict[str, Any] = {
        "enable_graphrag": answers.use_case == "graphrag" or answers.multi_hop,
        "enable_hybrid_search": answers.use_case in ("qa_docs", "code_rag"),
        # Contextual Retrieval (Anthropic) — big quality win, one LLM call/chunk at
        # ingest. Enable for doc/code Q&A on small/medium corpora; off for large
        # (cost) and for graph/agent use-cases that retrieve differently.
        "enable_contextual_retrieval": (
            answers.use_case in ("qa_docs", "code_rag")
            and answers.corpus_size in ("small", "medium")
        ),
        # Citations/groundedness when the user needs source attribution.
        "enable_citations": answers.needs_citations,
        # Changing corpus → suggest the scheduled ingest-worker addon.
        "enable_ingest_worker": answers.freshness in ("periodic", "streaming"),
    }
    if answers.freshness in ("periodic", "streaming"):
        notes.append("Dữ liệu cập nhật thường xuyên → cân nhắc addon `ingest-worker`.")
    if answers.needs_citations:
        notes.append("Cần trích dẫn nguồn → bật citation/groundedness gate.")

    return Recipe(
        template=template,
        llm_model=llm_model,
        llm_runtime=llm_runtime,
        embedding_model=embed,
        reranker=reranker,
        vector_db=vector_db,
        doc_parser=parser,
        chunk_strategy=chunk_strategy,
        chunk_size=chunk_size,
        gpu_enabled=gpu_enabled,
        vram_cap_gb=vram_cap,
        notes=notes,
        extras=extras,
    )


# --- Scored ranking (advisor): show WHY the pick won + the runner-ups ---

@dataclass
class ScoredCandidate:
    template: str
    score: int
    reasons: list[str]
    recommended: bool = False


# What each template is built for. Used to score fit and explain trade-offs.
_TEMPLATE_FIT: dict[str, dict[str, Any]] = {
    "custom-naive-rag": {
        "use_cases": {"qa_docs"}, "scales": {"solo", "team"}, "corpora": {"small"},
        "note": "đơn giản nhất, CPU-friendly, fully-local",
    },
    "ragflow-stack": {
        "use_cases": {"qa_docs", "multimodal", "code_rag"},
        "scales": {"team", "production"}, "corpora": {"small", "medium", "large"},
        "note": "production: hybrid search + deep doc parsing",
    },
    "lightrag-stack": {
        "use_cases": {"graphrag"}, "scales": {"solo", "team", "production"},
        "corpora": {"small", "medium"}, "note": "graph / multi-hop reasoning",
    },
    "dify-stack": {
        "use_cases": {"agent_workflow"}, "scales": {"team", "production"},
        "corpora": {"small", "medium"}, "note": "visual agent/workflow builder",
    },
    "code-graph-rag": {
        "use_cases": {"code_rag"}, "scales": {"solo", "team", "production"},
        "corpora": {"small", "medium", "large"}, "note": "LSP symbol nav cho Claude Code",
    },
}


def score_candidates(answers: Answers, hw: HardwareProfile, top_n: int = 3) -> list[ScoredCandidate]:
    """Rank templates by fit and explain why — for an evaluative recommendation.

    The #1 always matches `recommend()`'s authoritative routing; the rest are
    scored runner-ups with reasons so users see the trade-offs."""
    authoritative, _ = _pick_template(answers, hw.tier)
    mod = set(answers.modality)
    out: list[ScoredCandidate] = []
    for tmpl, fit in _TEMPLATE_FIT.items():
        score = 0
        reasons: list[str] = []
        if answers.use_case in fit["use_cases"]:
            score += 5
            reasons.append(f"khớp use-case '{answers.use_case}'")
        if (answers.use_case == "graphrag" or answers.multi_hop) and tmpl == "lightrag-stack":
            score += 5
            reasons.append("xử lý graph / multi-hop")
        if answers.user_scale in fit["scales"]:
            score += 2
            reasons.append(f"hợp scale '{answers.user_scale}'")
        if answers.corpus_size in fit["corpora"]:
            score += 1
            reasons.append(f"hợp corpus '{answers.corpus_size}'")
        if {"images", "tables"} & mod and tmpl == "ragflow-stack":
            score += 2
            reasons.append("multimodal parsing (docling)")
        reasons.append(fit["note"])
        out.append(ScoredCandidate(template=tmpl, score=score, reasons=reasons))

    # Authoritative routing is decisive → pin it to #1, then sort the rest by fit.
    out.sort(key=lambda c: (c.template == authoritative, c.score), reverse=True)
    if out:
        out[0].recommended = True
        if out[0].template == authoritative:
            out[0].reasons.insert(0, "khớp routing rule (lựa chọn chính)")
    return out[:top_n]
