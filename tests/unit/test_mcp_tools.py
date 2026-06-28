"""Tests for exporting @tool extensions to an MCP server + the related CLI commands."""

from __future__ import annotations

import inspect

import pytest
import yaml
from typer.testing import CliRunner

from perfectrag import tool
from perfectrag.cli import app
from perfectrag.core import extensions as ext
from perfectrag.mcp_tools import (
    SERVER_FILENAME,
    build_server,
    export_tools_to_mcp,
    render_server_script,
)

runner = CliRunner()


@pytest.fixture(autouse=True)
def clean_registry():
    ext.REGISTRY.clear()
    yield
    ext.REGISTRY.clear()


class FakeMCP:
    """Records FastMCP-style .tool(name=..., description=...)(fn) registrations."""
    def __init__(self):
        self.registered = {}

    def tool(self, name, description):
        def deco(fn):
            self.registered[name] = fn
            return fn
        return deco


def _write_ext(tmp_path):
    f = tmp_path / "ext.py"
    f.write_text(
        "from perfectrag import tool\n"
        "@tool\n"
        "def greet(name: str) -> str:\n"
        "    'Say hello.'\n"
        "    return 'hi ' + name\n",
        encoding="utf-8",
    )
    return f


def test_render_server_script_is_minimal():
    src = render_server_script(["./ext.py"], config="perfectrag.yml")
    assert "from perfectrag.mcp_tools import serve" in src
    assert "serve(['./ext.py'], config='perfectrag.yml')" in src


def test_build_server_registers_pure_tools():
    @tool
    def square(x: int) -> int:
        "Square a number."
        return x * x

    mcp = FakeMCP()
    names = build_server(mcp, [], rag=None)
    assert names == ["square"]
    assert mcp.registered["square"](x=5) == 25


def test_build_server_binds_ctx_tools_and_hides_ctx():
    @tool
    def needs_ctx(ctx, query: str) -> str:
        "Echo using ctx."
        return f"{ctx}:{query}"

    class FakeRAG:
        def _ctx(self):
            return "CTX"

    mcp = FakeMCP()
    names = build_server(mcp, [], rag=FakeRAG())
    assert names == ["needs_ctx"]
    fn = mcp.registered["needs_ctx"]
    # ctx is bound and hidden from the exposed signature
    assert "ctx" not in inspect.signature(fn).parameters
    assert fn(query="hi") == "CTX:hi"


def test_build_server_skips_ctx_tools_without_rag():
    @tool
    def needs_ctx(ctx, q: str) -> str:
        "needs ctx"
        return q

    mcp = FakeMCP()
    names = build_server(mcp, [], rag=None)
    assert names == []          # skipped — nothing to bind ctx to


def test_export_writes_script_and_updates_mcp_yaml(tmp_path):
    # pre-existing mcp.yaml with another server
    (tmp_path / "mcp.yaml").write_text(
        yaml.safe_dump({"servers": {"filesystem": {"command": "npx", "args": []}}}),
        encoding="utf-8",
    )
    path = export_tools_to_mcp(tmp_path, ["./ext.py"])
    assert (tmp_path / SERVER_FILENAME).exists()
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert "filesystem" in data["servers"]                       # preserved
    assert data["servers"]["perfectrag-tools"]["command"] == "python"
    assert data["servers"]["perfectrag-tools"]["args"] == [SERVER_FILENAME]


# ----------------------------------------------------------------- CLI
def test_cli_list_extensions(tmp_path):
    f = _write_ext(tmp_path)
    res = runner.invoke(app, ["list", "extensions", "--from", str(f)])
    assert res.exit_code == 0
    assert "greet" in res.stdout


def test_cli_export_tools(tmp_path):
    f = _write_ext(tmp_path)
    res = runner.invoke(app, ["export-tools", "--from", str(f), "--project", str(tmp_path)])
    assert res.exit_code == 0
    assert (tmp_path / SERVER_FILENAME).exists()
    data = yaml.safe_load((tmp_path / "mcp.yaml").read_text(encoding="utf-8"))
    assert "perfectrag-tools" in data["servers"]


def test_cli_export_tools_no_tools_errors(tmp_path):
    f = tmp_path / "empty.py"
    f.write_text("x = 1\n", encoding="utf-8")
    res = runner.invoke(app, ["export-tools", "--from", str(f), "--project", str(tmp_path)])
    assert res.exit_code == 1
