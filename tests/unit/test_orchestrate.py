"""Tests for orchestrate.py — mostly mocked (Docker not required)."""

from __future__ import annotations

from perfectrag import addons, orchestrate


def test_compose_args_with_no_installed(tmp_path):
    assert orchestrate.compose_args(tmp_path) == ["-f", "docker-compose.yml"]


def test_docker_available_is_bool():
    # Either true or false on this machine; just assert it doesn't raise
    assert orchestrate.docker_available() in (True, False)


def test_compose_args_reflects_state(tmp_path):
    addons.save_state(tmp_path, {"installed": ["eval"]})
    (tmp_path / "compose.eval.yml").write_text("services: {}")
    args = orchestrate.compose_args(tmp_path)
    assert "compose.eval.yml" in args
