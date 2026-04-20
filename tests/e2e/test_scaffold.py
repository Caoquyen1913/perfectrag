"""End-to-end scaffolding tests: run perfectrag init, assert generated project shape + YAML syntax."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from perfectrag.cli import app

FIXTURES = Path(__file__).parent.parent / "fixtures"


@pytest.fixture
def runner():
    return CliRunner()


def _invoke_init(runner: CliRunner, dst: Path, fixture: str):
    result = runner.invoke(
        app,
        ["init", str(dst), "--answers-file", str(FIXTURES / fixture), "--force"],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.output
    return result


def test_cpu_qa_scaffolds_naive_template(tmp_path, runner):
    dst = tmp_path / "cpu-rag"
    _invoke_init(runner, dst, "qa-cpu.yml")

    # Required files present
    for expected in ["docker-compose.yml", ".env", "README.md", "mcp.yaml",
                     "app/main.py", "app/Dockerfile", "app/requirements.txt"]:
        assert (dst / expected).exists(), expected

    # docker-compose.yml is valid YAML + has expected services
    compose = yaml.safe_load((dst / "docker-compose.yml").read_text())
    assert "services" in compose
    assert set(compose["services"].keys()) == {
        "qdrant", "ollama", "ollama-pull", "app", "open-webui"
    }

    # .env has model names substituted
    env = (dst / ".env").read_text()
    assert "qwen2.5:3b" in env
    assert "nomic-embed-text" in env


def test_graphrag_scaffolds_lightrag_stack(tmp_path, runner):
    dst = tmp_path / "graph-rag"
    result = runner.invoke(
        app,
        ["init", str(dst), "--answers-file", str(FIXTURES / "graphrag.yml"), "--force"],
    )
    assert result.exit_code == 0, result.output
    # LightRAG-specific files
    compose = yaml.safe_load((dst / "docker-compose.yml").read_text())
    assert "lightrag" in compose["services"]
    assert (dst / "inputs").exists()
    assert (dst / "rag_storage").exists()


def test_template_override_scaffolds_ragflow(tmp_path, runner):
    """Even on CPU-only HW, --template ragflow-stack should scaffold RAGFlow."""
    dst = tmp_path / "ragflow-override"
    result = runner.invoke(
        app,
        ["init", str(dst),
         "--answers-file", str(FIXTURES / "qa-cpu.yml"),
         "--template", "ragflow-stack",
         "--force"],
    )
    assert result.exit_code == 0, result.output
    compose_text = (dst / "docker-compose.yml").read_text()
    assert "infiniflow/ragflow" in compose_text
    assert "elasticsearch" in compose_text


def test_unknown_template_override_fails(tmp_path, runner):
    dst = tmp_path / "bad"
    result = runner.invoke(
        app,
        ["init", str(dst),
         "--answers-file", str(FIXTURES / "qa-cpu.yml"),
         "--template", "does-not-exist",
         "--force"],
    )
    assert result.exit_code == 1


def test_agent_workflow_scaffolds_dify_stack(tmp_path, runner):
    dst = tmp_path / "dify-app"
    result = runner.invoke(
        app,
        ["init", str(dst), "--answers-file", str(FIXTURES / "agent-workflow.yml"), "--force"],
    )
    assert result.exit_code == 0, result.output
    compose = yaml.safe_load((dst / "docker-compose.yml").read_text())
    for svc in ("db", "redis", "qdrant", "api", "worker", "web", "nginx"):
        assert svc in compose["services"], svc


def test_dry_run_shows_recipe_without_scaffolding(tmp_path, runner):
    dst = tmp_path / "preview-only"
    result = runner.invoke(
        app,
        ["init", str(dst), "--answers-file", str(FIXTURES / "qa-cpu.yml"), "--dry-run"],
    )
    assert result.exit_code == 0
    assert not dst.exists() or not any(dst.iterdir())


def test_hw_command_runs(runner):
    result = runner.invoke(app, ["hw"])
    assert result.exit_code == 0
    assert "Detected hardware" in result.output or "Tier" in result.output


def test_list_templates_shows_naive(runner):
    result = runner.invoke(app, ["list", "templates"])
    assert result.exit_code == 0
    assert "custom-naive-rag" in result.output


def test_add_mcp_to_generated_project(tmp_path, runner):
    dst = tmp_path / "with-mcp"
    _invoke_init(runner, dst, "qa-cpu.yml")

    result = runner.invoke(app, ["add", "mcp", "filesystem", "--project", str(dst)])
    assert result.exit_code == 0

    data = yaml.safe_load((dst / "mcp.yaml").read_text())
    assert "filesystem" in data["servers"]


def test_add_skill_to_generated_project(tmp_path, runner):
    dst = tmp_path / "with-skill"
    _invoke_init(runner, dst, "qa-cpu.yml")

    result = runner.invoke(app, ["add", "skill", "legal-rag", "--project", str(dst)])
    assert result.exit_code == 0
    assert (dst / "skills" / "legal-rag" / "SKILL.md").exists()
