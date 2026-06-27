"""Tests for the auto-tune retrieval engine."""

from __future__ import annotations

from perfectrag.core.protocols import Hit
from perfectrag.tune import TRIALS, apply_flags, rank, run_trials

# --- pure helpers ---

def test_apply_flags_inserts_after_top_k():
    text = "collection: docs\nchunk_size: 512\ntop_k: 5\nstore:\n  name: chroma\n"
    out = apply_flags(text, {"contextual": True, "query_expansion": 3})
    lines = out.splitlines()
    assert "contextual: true" in lines
    assert "query_expansion: 3" in lines
    # inserted right after top_k, before store
    assert lines.index("contextual: true") == lines.index("top_k: 5") + 1
    assert lines.index("store:") > lines.index("query_expansion: 3")


def test_apply_flags_replaces_existing_managed_keys():
    text = "top_k: 5\ncontextual: true\nparent_chunk_size: 999\n"
    out = apply_flags(text, {"corrective": True})
    assert "contextual: true" not in out      # old managed key dropped
    assert "parent_chunk_size: 999" not in out
    assert "corrective: true" in out


def test_apply_flags_baseline_clears_all():
    text = "top_k: 5\ncontextual: true\n"
    out = apply_flags(text, {})
    assert "contextual" not in out
    assert "top_k: 5" in out


class _R:
    def __init__(self, recall, mrr, ndcg, cost):
        from perfectrag.core.evaluation import RetrievalMetrics
        self.name = f"r{recall}"
        self.metrics = RetrievalMetrics(recall, mrr, ndcg, 3, 1)
        self.cost = cost


def test_rank_prefers_quality_then_cheaper():
    a = _R(1.0, 0.9, 0.9, 2)   # best quality but expensive
    b = _R(1.0, 0.9, 0.9, 0)   # same quality, free → should win the tie
    c = _R(0.5, 0.5, 0.5, 0)   # worse quality
    ordered = rank([a, b, c])
    assert ordered[0] is b      # cheaper wins the tie
    assert ordered[-1] is c


# --- integration with fakes ---

class _CollStore:
    """Collection-aware fake store (each trial gets its own collection)."""
    def __init__(self):
        self.colls: dict = {}

    def ensure_collection(self, name, dim):
        self.colls.setdefault(name, [])

    def upsert(self, collection, chunks, vectors):
        self.colls.setdefault(collection, []).extend(zip(chunks, vectors))

    def search(self, collection, qvec, k):
        scored = [(c, sum(a * b for a, b in zip(qvec, v))) for c, v in self.colls.get(collection, [])]
        scored.sort(key=lambda x: x[1], reverse=True)
        return [Hit(chunk=c, score=float(s)) for c, s in scored[:k]]

    def delete_collection(self, name):
        self.colls.pop(name, None)


class _Embedder:
    dim = 3

    def embed(self, text):
        return self.embed_batch([text])[0]

    def embed_batch(self, texts):
        return [[float(len(t) % 7), float(len(t) % 5), 1.0] for t in texts]


class _LLM:
    def generate(self, prompt, **kw):
        return "alt one\nalt two"

    def stream(self, prompt, **kw):  # pragma: no cover
        yield ""


class _Parser:
    def parse(self, path):
        from pathlib import Path
        return Path(path).read_text(encoding="utf-8")


def _corpus(tmp_path):
    d = tmp_path / "docs"
    d.mkdir()
    (d / "a.md").write_text("alpha beta gamma delta epsilon", encoding="utf-8")
    (d / "b.md").write_text("one two three four five six seven", encoding="utf-8")
    return d


def test_run_trials_all_configs_with_llm(tmp_path):
    store = _CollStore()
    golden = [{"question": "alpha?", "relevant": ["a.md"]}]
    results = run_trials(store, _Embedder(), _LLM(), _Parser(), _corpus(tmp_path), golden,
                         chunk_size=4, top_k=3, k=3)
    assert len(results) == len(TRIALS)           # all 5 ran (llm provided)
    assert results == rank(results)              # returned best-first
    assert all(r.metrics.n == 1 for r in results)
    assert not store.colls                        # trial collections cleaned up


def test_run_trials_skips_llm_configs_without_llm(tmp_path):
    store = _CollStore()
    golden = [{"question": "one?", "relevant": ["b.md"]}]
    results = run_trials(store, _Embedder(), None, _Parser(), _corpus(tmp_path), golden,
                         chunk_size=4, top_k=3, k=3)
    names = {r.name for r in results}
    assert names == {"baseline", "parent-doc"}   # LLM-based trials skipped
