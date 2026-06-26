"""CLI test for `perfectrag eval --retrieval` (offline retrieval metrics)."""

from __future__ import annotations

import json

from typer.testing import CliRunner

from perfectrag.cli import app
from perfectrag.core.protocols import Chunk, Hit


class _FakeRAG:
    def __init__(self, mapping):
        self._m = mapping

    def retrieve(self, question, k=5):
        return [Hit(chunk=Chunk(id=s, text=s, source=s, metadata={}), score=1.0)
                for s in self._m.get(question, [])[:k]]


def _setup(tmp_path, relevant):
    (tmp_path / "perfectrag.yml").write_text("collection: x\n", encoding="utf-8")
    (tmp_path / "golden.jsonl").write_text(
        json.dumps({"question": "q1", "relevant": relevant}) + "\n", encoding="utf-8"
    )


def test_eval_retrieval_passes_gate(tmp_path, monkeypatch):
    _setup(tmp_path, ["a.md"])
    fake = _FakeRAG({"q1": ["a.md", "b.md"]})
    monkeypatch.setattr("perfectrag.core.rag.RAG.from_config",
                        classmethod(lambda cls, cfg: fake))
    result = CliRunner().invoke(
        app, ["eval", "--retrieval", "-p", str(tmp_path), "-d", "golden.jsonl", "--gate"]
    )
    assert result.exit_code == 0, result.output
    assert "recall_at_k" in result.output
    assert "PASSED" in result.output


def test_eval_retrieval_fails_gate(tmp_path, monkeypatch):
    _setup(tmp_path, ["missing.md"])  # never retrieved → recall 0
    fake = _FakeRAG({"q1": ["a.md", "b.md"]})
    monkeypatch.setattr("perfectrag.core.rag.RAG.from_config",
                        classmethod(lambda cls, cfg: fake))
    result = CliRunner().invoke(
        app, ["eval", "--retrieval", "-p", str(tmp_path), "-d", "golden.jsonl", "--gate"]
    )
    assert result.exit_code == 1
    assert "FAILED" in result.output


def test_eval_retrieval_missing_dataset(tmp_path):
    (tmp_path / "perfectrag.yml").write_text("collection: x\n", encoding="utf-8")
    result = CliRunner().invoke(
        app, ["eval", "--retrieval", "-p", str(tmp_path), "-d", "nope.jsonl"]
    )
    assert result.exit_code == 1
    assert "not found" in result.output.lower()
