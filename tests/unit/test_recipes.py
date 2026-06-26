"""Unit tests for the recipe decision matrix."""

from __future__ import annotations

import pytest

from perfectrag.hardware import HardwareProfile
from perfectrag.recipes import Answers, recommend, score_candidates


def _hw(tier: str) -> HardwareProfile:
    table = {
        "cpu":        ("none",   0),
        "gpu-8gb":    ("nvidia", 8),
        "gpu-12gb":   ("nvidia", 16),
        "gpu-24gb":   ("nvidia", 24),
        "apple-low":  ("apple",  16),
        "apple-high": ("apple",  32),
    }
    vendor, vram = table[tier]
    # For Apple Silicon, unified memory = ram_gb, so pass vram as ram too
    ram = vram if vendor == "apple" else 32
    return HardwareProfile(
        os="Linux", arch="x86_64", cpu_model="x", cpu_cores=8,
        ram_gb=ram, disk_free_gb=500,
        gpu_vendor=vendor,  # type: ignore[arg-type]
        gpu_name="test", vram_gb=vram, cuda_version=None,
    )


def _answers(**kw):
    defaults = {
        "use_case": "qa_docs",
        "modality": ["text"],
        "privacy": "fully_local",
        "multi_hop": False,
        "corpus_size": "small",
        "user_scale": "solo",
    }
    defaults.update(kw)
    return Answers(**defaults)


def test_cpu_qa_picks_naive():
    r = recommend(_answers(), _hw("cpu"))
    assert r.template == "custom-naive-rag"
    assert r.llm_runtime == "llamacpp"
    assert r.reranker is None  # naive has no reranker
    assert r.vector_db == "qdrant"


def test_gpu_qa_picks_ragflow():
    r = recommend(_answers(), _hw("gpu-8gb"))
    assert r.template == "ragflow-stack"
    assert r.reranker is not None


def test_graphrag_forces_lightrag():
    r = recommend(_answers(use_case="graphrag"), _hw("gpu-12gb"))
    assert r.template == "lightrag-stack"
    assert r.extras["enable_graphrag"] is True


def test_multi_hop_forces_lightrag():
    r = recommend(_answers(multi_hop=True), _hw("gpu-12gb"))
    assert r.template == "lightrag-stack"


def test_agent_workflow_picks_dify():
    r = recommend(_answers(use_case="agent_workflow"), _hw("gpu-12gb"))
    assert r.template == "dify-stack"


def test_multimodal_picks_ragflow():
    r = recommend(_answers(use_case="multimodal", modality=["text", "images"]),
                  _hw("gpu-12gb"))
    assert r.template == "ragflow-stack"
    assert r.doc_parser == "docling"


def test_large_corpus_picks_milvus():
    r = recommend(_answers(corpus_size="large"), _hw("gpu-12gb"))
    assert r.vector_db == "milvus"


def test_medium_corpus_picks_qdrant():
    r = recommend(_answers(corpus_size="medium"), _hw("gpu-12gb"))
    assert r.vector_db == "qdrant"


def test_production_scale_picks_vllm():
    r = recommend(_answers(user_scale="production"), _hw("gpu-12gb"))
    assert r.llm_runtime == "vllm"


def test_tables_modality_picks_docling():
    r = recommend(_answers(modality=["text", "tables"]), _hw("gpu-8gb"))
    assert r.doc_parser == "docling"


def test_text_only_picks_markitdown():
    r = recommend(_answers(modality=["text"]), _hw("gpu-8gb"))
    assert r.doc_parser == "markitdown"


@pytest.mark.parametrize("tier,expected_llm_prefix", [
    ("cpu",        "qwen2.5:3b"),
    ("gpu-8gb",    "qwen2.5:7b"),
    ("gpu-12gb",   "qwen2.5:14b"),
    ("gpu-24gb",   "qwen2.5:32b"),
    ("apple-low",  "qwen2.5:7b"),
    ("apple-high", "qwen2.5:14b"),
])
def test_llm_sizing_by_tier(tier, expected_llm_prefix):
    r = recommend(_answers(), _hw(tier))
    assert r.llm_model.startswith(expected_llm_prefix), r.llm_model


def test_hybrid_api_on_weak_tier_uses_cloud_llm():
    """privacy=hybrid_api + weak hardware → cloud LLM instead of weak local."""
    r = recommend(_answers(privacy="hybrid_api"), _hw("cpu"))
    assert r.llm_runtime == "gemini"
    assert r.llm_model == "gemini-2.0-flash"
    assert any("hybrid_api" in n for n in r.notes)


def test_hybrid_api_on_apple_low_uses_cloud_llm():
    r = recommend(_answers(privacy="hybrid_api"), _hw("apple-low"))
    assert r.llm_runtime == "gemini"


def test_hybrid_api_on_strong_gpu_keeps_local():
    """Strong GPU runs local fine even when cloud is allowed."""
    r = recommend(_answers(privacy="hybrid_api"), _hw("gpu-12gb"))
    assert r.llm_runtime in ("ollama", "vllm")
    assert r.llm_model.startswith("qwen2.5")


def test_fully_local_weak_tier_stays_local():
    """Default privacy must never reach for the cloud."""
    r = recommend(_answers(privacy="fully_local"), _hw("cpu"))
    assert r.llm_runtime == "llamacpp"
    assert r.llm_model.startswith("qwen2.5")


def test_chunking_default_is_recursive_512():
    r = recommend(_answers(), _hw("gpu-8gb"))
    assert r.chunk_strategy == "recursive"
    assert r.chunk_size == 512


def test_code_rag_picks_code_graph_template():
    r = recommend(_answers(use_case="code_rag", modality=["code"]), _hw("gpu-8gb"))
    assert r.template == "code-graph-rag"


def test_code_modality_uses_larger_chunks():
    r = recommend(_answers(use_case="code_rag", modality=["code"]), _hw("gpu-8gb"))
    assert r.chunk_strategy == "recursive"
    assert r.chunk_size == 768


def test_multilingual_forces_bge_m3_even_on_cpu():
    r = recommend(_answers(language="vietnamese"), _hw("cpu"))
    assert r.embedding_model == "BAAI/bge-m3"


def test_existing_postgres_uses_pgvector():
    r = recommend(_answers(existing_infra=["postgres"]), _hw("gpu-8gb"))
    assert r.vector_db == "pgvector"


def test_existing_postgres_skipped_for_naive_template():
    # cpu qa_docs → custom-naive-rag, which bundles qdrant; pgvector not applied.
    r = recommend(_answers(existing_infra=["postgres"]), _hw("cpu"))
    assert r.template == "custom-naive-rag"
    assert r.vector_db == "qdrant"


def test_speed_priority_drops_reranker():
    base = recommend(_answers(), _hw("gpu-8gb"))
    assert base.reranker is not None
    fast = recommend(_answers(priority="speed"), _hw("gpu-8gb"))
    assert fast.reranker is None


def test_interactive_latency_drops_reranker():
    r = recommend(_answers(latency="interactive"), _hw("gpu-8gb"))
    assert r.reranker is None


def test_freshness_streaming_enables_ingest_worker():
    r = recommend(_answers(freshness="streaming"), _hw("gpu-8gb"))
    assert r.extras["enable_ingest_worker"] is True


def test_needs_citations_extra():
    r = recommend(_answers(needs_citations=True), _hw("gpu-8gb"))
    assert r.extras["enable_citations"] is True


def test_new_answer_fields_default_safely():
    """Old-style Answers (6 fields) still construct and recommend."""
    r = recommend(_answers(), _hw("gpu-8gb"))
    assert r.embedding_model and r.template


def test_score_candidates_top_matches_recommend():
    answers = _answers()
    hw = _hw("gpu-8gb")
    ranked = score_candidates(answers, hw)
    assert ranked[0].recommended is True
    assert ranked[0].template == recommend(answers, hw).template
    assert len(ranked) == 3
    assert all(c.reasons for c in ranked)  # every candidate explains itself


def test_score_candidates_graphrag_ranks_lightrag_first():
    ranked = score_candidates(_answers(use_case="graphrag"), _hw("gpu-12gb"))
    assert ranked[0].template == "lightrag-stack"
    assert ranked[0].recommended is True


def test_score_candidates_code_rag_ranks_code_graph_first():
    ranked = score_candidates(_answers(use_case="code_rag", modality=["code"]), _hw("gpu-8gb"))
    assert ranked[0].template == "code-graph-rag"


def test_score_candidates_orders_by_score_after_pick():
    ranked = score_candidates(_answers(), _hw("gpu-8gb"), top_n=5)
    scores = [c.score for c in ranked[1:]]  # runner-ups
    assert scores == sorted(scores, reverse=True)


def test_recipe_template_vars_shape():
    hw = _hw("gpu-8gb")
    answers = _answers()
    r = recommend(answers, hw)
    data = r.as_template_vars(hw, answers)
    assert set(data.keys()) == {"recipe", "hw", "answers"}
    assert data["recipe"]["llm_model"] == r.llm_model
    assert data["hw"]["gpu_vendor"] == "nvidia"
