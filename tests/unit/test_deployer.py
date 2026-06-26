"""Tests for deploy target rendering."""

from __future__ import annotations

import pytest

from perfectrag import deployer


def test_available_targets_for_naive():
    targets = deployer.available_targets("custom-naive-rag")
    assert set(targets) == {"helm", "flyio", "railway"}


def test_render_helm_produces_chart(tmp_path):
    deployer.render(
        target="helm",
        template="custom-naive-rag",
        out_dir=tmp_path,
        template_vars={"project_name": "demo", "recipe": {"llm_model": "qwen2.5:3b-instruct-q4_K_M",
                                                          "embedding_model": "nomic-embed-text",
                                                          "gpu_enabled": False}},
    )
    chart = (tmp_path / "Chart.yaml").read_text()
    assert "name: demo" in chart
    assert (tmp_path / "values.yaml").exists()
    assert (tmp_path / "templates" / "app.yaml").exists()


def test_render_flyio_produces_toml(tmp_path):
    deployer.render(
        target="flyio",
        template="custom-naive-rag",
        out_dir=tmp_path,
        template_vars={"project_name": "demo", "recipe": {"llm_model": "qwen2.5:3b-instruct-q4_K_M",
                                                          "embedding_model": "nomic-embed-text"}},
    )
    toml = (tmp_path / "fly.toml").read_text()
    assert 'app = "demo"' in toml


def test_unknown_target_raises(tmp_path):
    with pytest.raises(ValueError):
        deployer.render("helm", "unknown-template", tmp_path, {})  # type: ignore[arg-type]
