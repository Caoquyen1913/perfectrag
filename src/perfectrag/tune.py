"""Auto-tune retrieval: measure several techniques on the USER's own corpus +
golden questions, then pick the empirically best one. "Measure, don't guess."

    perfectrag tune --docs ./docs --golden ./golden.jsonl --apply

The heavy embedder/LLM are built once and shared across trials (so we don't
reload models per config — which is both slow and a memory risk).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from perfectrag.core import embeddings, llms, parsers, stores
from perfectrag.core.evaluation import RetrievalMetrics, evaluate_retrieval
from perfectrag.core.protocols import LLM, Chunk, Embedder, Hit, Parser, VectorStore
from perfectrag.core.rag import RAG, _expand_env

# (name, flags, cost) — cost 0 = free (no LLM), 1 = LLM/query, 2 = LLM/chunk at ingest.
TRIALS: list[tuple[str, dict[str, Any], int]] = [
    ("baseline", {}, 0),
    ("parent-doc", {"parent_mult": 4}, 0),
    ("contextual", {"contextual": True}, 2),
    ("query-expansion", {"query_expansion": 3}, 1),
    ("crag", {"corrective": True}, 1),
]

# Top-level perfectrag.yml keys this tool manages.
_MANAGED = ("contextual", "parent_chunk_size", "query_expansion", "corrective")


@dataclass
class TuneResult:
    name: str
    metrics: RetrievalMetrics
    cost: int
    config_flags: dict[str, Any] = field(default_factory=dict)


class _BasenameRAG:
    """Match retrieved sources to the golden set by basename, so users can write
    `"relevant": ["doc.md"]` without full paths."""

    def __init__(self, rag: RAG):
        self._rag = rag

    def retrieve(self, question: str, k: int | None = None) -> list[Hit]:
        out = []
        for h in self._rag.retrieve(question, k):
            c = h.chunk
            out.append(Hit(chunk=Chunk(id=c.id, text=c.text, source=Path(c.source).name,
                                       metadata=c.metadata), score=h.score))
        return out


def _normalize_golden(golden: list[dict[str, Any]]) -> list[dict[str, Any]]:
    norm = []
    for item in golden:
        rel = [Path(str(r)).name for r in (item.get("relevant") or [])]
        norm.append({"question": item.get("question"), "relevant": rel})
    return norm


def run_trials(store: VectorStore, embedder: Embedder, llm: LLM | None, parser: Parser,
               docs: Path, golden: list[dict[str, Any]],
               *, chunk_size: int, top_k: int, k: int) -> list[TuneResult]:
    """Ingest the corpus under each trial config and score it. Components are
    reused across trials; each trial uses its own collection (cleaned up after)."""
    golden = _normalize_golden(golden)
    results: list[TuneResult] = []
    created: list[str] = []
    for i, (name, flags, cost) in enumerate(TRIALS):
        needs_llm = flags.get("contextual") or flags.get("query_expansion") or flags.get("corrective")
        if needs_llm and llm is None:
            continue  # can't run LLM-based techniques without an LLM
        kwargs = dict(flags)
        parent = kwargs.pop("parent_mult", 0) * chunk_size
        coll = f"tune_{i}_{name}".replace("-", "_")
        rag = RAG(store=store, embedder=embedder, llm=llm, parser=parser, collection=coll,
                  chunk_size=chunk_size, top_k=top_k, parent_chunk_size=parent, **kwargs)
        rag.ingest(docs)
        created.append(coll)
        m = evaluate_retrieval(_BasenameRAG(rag), golden, k=k)
        results.append(TuneResult(name=name, metrics=m, cost=cost,
                                  config_flags=_winner_flags(name, chunk_size)))
    for coll in created:
        try:
            store.delete_collection(coll)
        except Exception:
            pass
    return rank(results)


def rank(results: list[TuneResult]) -> list[TuneResult]:
    """Best first: higher recall@k, then MRR, then nDCG, then CHEAPER on ties."""
    return sorted(results, key=lambda r: (r.metrics.recall_at_k, r.metrics.mrr,
                                          r.metrics.ndcg_at_k, -r.cost), reverse=True)


def _winner_flags(name: str, chunk_size: int) -> dict[str, Any]:
    table: dict[str, dict[str, Any]] = {
        "baseline": {},
        "parent-doc": {"parent_chunk_size": chunk_size * 4},
        "contextual": {"contextual": True},
        "query-expansion": {"query_expansion": 3},
        "crag": {"corrective": True},
    }
    return table[name]


def tune_from_config(cfg: dict[str, Any], docs: Path, golden: list[dict[str, Any]],
                     *, k: int = 5) -> list[TuneResult]:
    cfg = _expand_env(cfg)
    store_cfg = dict(cfg.get("store", {"name": "chroma"}))
    emb_cfg = dict(cfg.get("embedding", {"model": "BAAI/bge-m3"}))
    llm_cfg = dict(cfg.get("llm", {"runtime": "ollama", "model": "qwen2.5:3b-instruct-q4_K_M"}))
    store = stores.build(store_cfg.pop("name"), **store_cfg)
    embedder = embeddings.build(emb_cfg.pop("model"), **emb_cfg)
    try:
        llm = llms.build(llm_cfg.pop("runtime"), llm_cfg.pop("model"), **llm_cfg)
    except Exception:
        llm = None  # LLM-based trials are skipped; baseline/parent-doc still run
    parser = parsers.build(cfg.get("parser", {"name": "simple"}).get("name", "simple"))
    return run_trials(store, embedder, llm, parser, docs, golden,
                      chunk_size=int(cfg.get("chunk_size", 512)),
                      top_k=int(cfg.get("top_k", k)), k=k)


def apply_flags(yaml_text: str, flags: dict[str, Any]) -> str:
    """Write the winner's retrieval flags into perfectrag.yml text, preserving the
    rest of the file. Drops any existing managed keys, then inserts after `top_k:`."""
    kept = [ln for ln in yaml_text.splitlines()
            if not any(re.match(rf"\s*{re.escape(key)}\s*:", ln) for key in _MANAGED)]
    new_lines = [f"{key}: {_yaml_val(val)}" for key, val in flags.items()]
    out: list[str] = []
    inserted = False
    for ln in kept:
        out.append(ln)
        if not inserted and re.match(r"\s*top_k\s*:", ln):
            out.extend(new_lines)
            inserted = True
    if not inserted:  # no top_k line — append at end
        out.extend(new_lines)
    text = "\n".join(out)
    return text if text.endswith("\n") else text + "\n"


def _yaml_val(v: Any) -> str:
    return "true" if v is True else ("false" if v is False else str(v))
