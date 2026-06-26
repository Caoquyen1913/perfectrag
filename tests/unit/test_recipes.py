"""Unit tests for the recipe decision matrix."""

from __future__ import annotations

import pytest

from perfectrag.hardware import HardwareProfile
from perfectrag.recipes import Answers, recommend


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


def test_recipe_template_vars_shape():
    hw = _hw("gpu-8gb")
    answers = _answers()
    r = recommend(answers, hw)
    data = r.as_template_vars(hw, answers)
    assert set(data.keys()) == {"recipe", "hw", "answers"}
    assert data["recipe"]["llm_model"] == r.llm_model
    assert data["hw"]["gpu_vendor"] == "nvidia"
