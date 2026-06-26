"""Tests for Gemini advisor — mocked google-generativeai."""

from __future__ import annotations

import json

import pytest

from perfectrag import advisor, keys
from perfectrag.hardware import HardwareProfile
from perfectrag.recipes import Answers, recommend


@pytest.fixture
def isolated_keys(tmp_path, monkeypatch):
    monkeypatch.setattr(keys, "KEYS_DIR", tmp_path / ".perfectrag")
    monkeypatch.setattr(keys, "KEYS_FILE", tmp_path / ".perfectrag" / "keys.yml")


def _base():
    hw = HardwareProfile(
        os="Linux", arch="x86_64", cpu_model="x", cpu_cores=8,
        ram_gb=32, disk_free_gb=500,
        gpu_vendor="nvidia", gpu_name="RTX", vram_gb=16, cuda_version="12.4",
    )
    answers = Answers(use_case="qa_docs", modality=["text"], privacy="fully_local",
                      multi_hop=False, corpus_size="small", user_scale="solo")
    return hw, answers, recommend(answers, hw)


def test_advise_no_key_fallback(isolated_keys):
    hw, _, base = _base()
    adv = advisor.advise("legal docs", hw, base)
    assert adv.used_provider is None
    assert adv.recipe is base
    assert "No Gemini key" in adv.reasoning


def test_advise_with_mocked_gemini(isolated_keys, monkeypatch):
    import sys
    import types

    keys.set_key("gemini", "fake-key")

    class FakeResp:
        text = json.dumps({
            "reasoning": "Code RAG needs a different chunking strategy.",
            "changes": {"chunk_size": 1024},
        })

    class FakeModel:
        def __init__(self, *a, **kw): pass
        def generate_content(self, *a, **kw):
            return FakeResp()

    fake_module = types.ModuleType("google.generativeai")
    fake_module.GenerativeModel = FakeModel  # type: ignore[attr-defined]
    fake_module.configure = lambda **kw: None  # type: ignore[attr-defined]
    google_pkg = types.ModuleType("google")
    google_pkg.generativeai = fake_module  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "google", google_pkg)
    monkeypatch.setitem(sys.modules, "google.generativeai", fake_module)

    hw, _, base = _base()
    adv = advisor.advise("Legal documents PDF", hw, base)
    assert adv.used_provider == "gemini"
    assert adv.recipe.chunk_size == 1024
    assert "chunk_size" in adv.changes
