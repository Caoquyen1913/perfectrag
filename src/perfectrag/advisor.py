"""Gemini-backed recipe advisor — optional enhancer on top of rule-based `recipes.recommend`.

Degrades to a no-op if no Gemini key is available. The advisor gets (description,
hardware profile, base_recipe) and can override any recipe field with reasoning.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from perfectrag import keys
from perfectrag.hardware import HardwareProfile
from perfectrag.recipes import Recipe

GEMINI_MODEL = "gemini-2.5-flash"  # latest flash, cheap + fast enough for advisor


@dataclass
class Advice:
    recipe: Recipe
    reasoning: str
    changes: dict[str, Any]  # {field: {from, to}}
    used_provider: str | None  # "gemini" | None (degraded)


def is_available() -> bool:
    return keys.get_key("gemini") is not None


def _prompt(description: str, hw: HardwareProfile, base: Recipe) -> str:
    return f"""You are a RAG stack architect. A user wants to build a RAG service and has a rule-based recipe from a decision matrix. Your job: refine the recipe if the user's free-form description reveals details the matrix missed.

USER DESCRIPTION:
{description}

DETECTED HARDWARE:
- OS/arch: {hw.os} ({hw.arch})
- CPU: {hw.cpu_model}, {hw.cpu_cores} cores
- RAM: {hw.ram_gb} GB
- GPU: {hw.gpu_vendor} / {hw.gpu_name or 'none'} / {hw.vram_gb} GB VRAM
- Tier: {hw.tier}

BASE RECIPE (from rule engine):
- template: {base.template}
- llm_model: {base.llm_model} (runtime: {base.llm_runtime})
- embedding_model: {base.embedding_model}
- reranker: {base.reranker}
- vector_db: {base.vector_db}
- doc_parser: {base.doc_parser}
- chunk: {base.chunk_strategy} / {base.chunk_size} tokens
- extras: {base.extras}

AVAILABLE OPTIONS:
- template: custom-naive-rag, ragflow-stack, lightrag-stack, dify-stack, code-graph-rag
- vector_db: qdrant, milvus, chroma, lancedb, pgvector
- embedding_model: BAAI/bge-m3, nomic-embed-text, jinaai/jina-embeddings-v3, intfloat/e5-large-v2, Qwen/Qwen3-Embedding-0.6B
- reranker: BAAI/bge-reranker-v2-m3, jinaai/jina-reranker-v2-base-multilingual, mixedbread-ai/mxbai-rerank-large-v1, colbert-ir/colbertv2.0, null
- llm_runtime: ollama, llamacpp, vllm, gemini, anthropic, openai
- doc_parser: docling, markitdown, unstructured, llamaparse
- chunk_strategy: recursive, semantic, late

Return ONLY a JSON object with these keys:
- "reasoning": 1-3 sentence explanation of changes (or "base recipe is optimal")
- "changes": dict of field overrides (empty if no changes)

Example: {{"reasoning": "User mentioned legal docs; bge-m3 better handles legal jargon than nomic.", "changes": {{"embedding_model": "BAAI/bge-m3"}}}}
"""


def advise(description: str, hw: HardwareProfile, base: Recipe) -> Advice:
    """Run the advisor. Returns base recipe unchanged if no Gemini key."""
    api_key = keys.get_key("gemini")
    if not api_key:
        return Advice(
            recipe=base,
            reasoning="No Gemini key configured — using rule-based recipe as-is. "
                      "Run `perfectrag add key gemini <your-key>` to enable advisor.",
            changes={},
            used_provider=None,
        )

    try:
        import google.generativeai as genai  # lazy import; not a core dep
    except ImportError:
        return Advice(
            recipe=base,
            reasoning="google-generativeai not installed. Install with `pip install 'perfectrag[advisor]'`.",
            changes={},
            used_provider=None,
        )

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(GEMINI_MODEL)
    prompt = _prompt(description, hw, base)

    try:
        resp = model.generate_content(
            prompt,
            generation_config={"response_mime_type": "application/json", "temperature": 0.3},
        )
        parsed = json.loads(resp.text)
    except Exception as e:
        return Advice(
            recipe=base,
            reasoning=f"Advisor call failed ({e}); falling back to base recipe.",
            changes={},
            used_provider=None,
        )

    changes = parsed.get("changes", {}) or {}
    reasoning = parsed.get("reasoning", "")

    # Apply changes to a copy of base recipe
    new_recipe = Recipe(
        template=changes.get("template", base.template),
        llm_model=changes.get("llm_model", base.llm_model),
        llm_runtime=changes.get("llm_runtime", base.llm_runtime),
        embedding_model=changes.get("embedding_model", base.embedding_model),
        reranker=changes.get("reranker", base.reranker),
        vector_db=changes.get("vector_db", base.vector_db),
        doc_parser=changes.get("doc_parser", base.doc_parser),
        chunk_strategy=changes.get("chunk_strategy", base.chunk_strategy),
        chunk_size=changes.get("chunk_size", base.chunk_size),
        gpu_enabled=base.gpu_enabled,
        vram_cap_gb=base.vram_cap_gb,
        notes=list(base.notes) + [f"Advisor: {reasoning}"] if reasoning else list(base.notes),
        extras=dict(base.extras),
    )
    # Diff for display
    diff: dict[str, dict] = {}
    for field, new_val in changes.items():
        old_val = getattr(base, field, None)
        if old_val != new_val:
            diff[field] = {"from": old_val, "to": new_val}

    return Advice(recipe=new_recipe, reasoning=reasoning, changes=diff, used_provider="gemini")
