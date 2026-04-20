"""Unit tests for MCP registry splicing."""

from __future__ import annotations

import pytest
import yaml

from perfectrag import mcp_registry


def test_registry_has_known_servers():
    assert "filesystem" in mcp_registry.REGISTRY
    assert "tavily" in mcp_registry.REGISTRY
    for name, info in mcp_registry.REGISTRY.items():
        assert "description" in info, name
        assert "command" in info, name
        assert "args" in info, name
        assert isinstance(info["args"], list), name


def test_add_mcp_creates_file(tmp_path):
    mcp_registry.add_mcp_to_project("filesystem", tmp_path)
    p = tmp_path / "mcp.yaml"
    assert p.exists()
    data = yaml.safe_load(p.read_text())
    assert "filesystem" in data["servers"]
    assert data["servers"]["filesystem"]["command"] == "npx"


def test_add_mcp_appends_to_existing(tmp_path):
    mcp_registry.add_mcp_to_project("filesystem", tmp_path)
    mcp_registry.add_mcp_to_project("tavily", tmp_path)
    data = yaml.safe_load((tmp_path / "mcp.yaml").read_text())
    assert set(data["servers"].keys()) == {"filesystem", "tavily"}
    assert data["servers"]["tavily"]["env"] == {"TAVILY_API_KEY": "${TAVILY_API_KEY}"}


def test_add_unknown_mcp_raises(tmp_path):
    with pytest.raises(KeyError):
        mcp_registry.add_mcp_to_project("does-not-exist", tmp_path)
