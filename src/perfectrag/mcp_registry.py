"""Registry of well-known MCP servers + helper to splice them into a project's mcp.yaml.

mcp.yaml format mirrors the Claude Code / Cursor / Claude Desktop MCP config so that
configs are portable: each server has `command`, `args`, optional `env`, and transport.
"""

from __future__ import annotations

from pathlib import Path

import yaml

REGISTRY: dict[str, dict] = {
    "filesystem": {
        "description": "Đọc/ghi file trong thư mục được whitelist (read-only by default)",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-filesystem", "${PWD}/data"],
        "env": [],
    },
    "fetch": {
        "description": "Fetch URL và convert sang markdown cho LLM",
        "command": "uvx",
        "args": ["mcp-server-fetch"],
        "env": [],
    },
    "tavily": {
        "description": "Tavily web search (cần TAVILY_API_KEY)",
        "command": "npx",
        "args": ["-y", "mcp-tavily"],
        "env": ["TAVILY_API_KEY"],
    },
    "brave-search": {
        "description": "Brave web search (cần BRAVE_API_KEY)",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-brave-search"],
        "env": ["BRAVE_API_KEY"],
    },
    "postgres": {
        "description": "Query Postgres read-only (cần POSTGRES_URL)",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-postgres", "${POSTGRES_URL}"],
        "env": ["POSTGRES_URL"],
    },
    "sqlite": {
        "description": "Query SQLite database local",
        "command": "uvx",
        "args": ["mcp-server-sqlite", "--db-path", "${PWD}/data/app.db"],
        "env": [],
    },
    "github": {
        "description": "GitHub repos / issues / PRs (cần GITHUB_PERSONAL_ACCESS_TOKEN)",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-github"],
        "env": ["GITHUB_PERSONAL_ACCESS_TOKEN"],
    },
    "memory": {
        "description": "Persistent knowledge-graph memory cho agent",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-memory"],
        "env": [],
    },
    "sequential-thinking": {
        "description": "Chain-of-thought structured reasoning tool",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-sequential-thinking"],
        "env": [],
    },
    "qdrant": {
        "description": "Qdrant vector-db MCP server (read/write vectors)",
        "command": "uvx",
        "args": ["mcp-server-qdrant", "--qdrant-url", "${QDRANT_URL:-http://localhost:6333}"],
        "env": [],
    },
    "crawl4ai": {
        "description": "Crawl4AI — LLM-optimized web crawler (JS rendering, markdown output)",
        "command": "uvx",
        "args": ["crawl4ai-mcp"],
        "env": [],
    },
    "firecrawl": {
        "description": "Firecrawl MCP — JS rendering, sitemap crawl (cần FIRECRAWL_API_KEY nếu dùng cloud)",
        "command": "npx",
        "args": ["-y", "firecrawl-mcp"],
        "env": ["FIRECRAWL_API_KEY"],
    },
    "notion": {
        "description": "Notion API — read pages/databases (cần NOTION_API_KEY)",
        "command": "npx",
        "args": ["-y", "@notionhq/notion-mcp-server"],
        "env": ["NOTION_API_KEY"],
    },
    "gdrive": {
        "description": "Google Drive MCP — search + read files",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-gdrive"],
        "env": ["GDRIVE_SERVICE_ACCOUNT_JSON"],
    },
    "confluence": {
        "description": "Confluence/Jira Atlassian MCP",
        "command": "npx",
        "args": ["-y", "@sooperset/mcp-atlassian"],
        "env": ["CONFLUENCE_URL", "CONFLUENCE_API_TOKEN"],
    },
    "slack": {
        "description": "Slack channels + messages (cần SLACK_BOT_TOKEN)",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-slack"],
        "env": ["SLACK_BOT_TOKEN", "SLACK_TEAM_ID"],
    },
    # --- Code intelligence (for code_rag / Claude Code) ---
    "serena": {
        "description": "Serena — LSP-based code intelligence: find_symbol, find_referencing_symbols, "
                       "call hierarchy, symbol-level edits (30+ ngôn ngữ, không cần embeddings)",
        "command": "uvx",
        "args": ["--from", "git+https://github.com/oraios/serena", "serena-mcp-server"],
        "env": [],
    },
    "ast-grep": {
        "description": "ast-grep — structural AST search/rewrite theo pattern (find_code, dump_syntax_tree)",
        "command": "uvx",
        "args": ["ast-grep-mcp"],
        "env": [],
    },
    "claude-context": {
        "description": "Claude Context (Zilliz) — semantic code search: AST chunking + Milvus, "
                       "hybrid dense+BM25, incremental reindex (cho repo lớn)",
        "command": "npx",
        "args": ["-y", "@zilliz/claude-context-mcp@latest"],
        "env": ["OPENAI_API_KEY", "MILVUS_ADDRESS"],
    },
}


def _mcp_path(project_dir: Path) -> Path:
    return project_dir / "mcp.yaml"


def _load(path: Path) -> dict:
    if not path.exists():
        return {"servers": {}}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    data.setdefault("servers", {})
    return data


def add_mcp_to_project(name: str, project_dir: Path) -> None:
    if name not in REGISTRY:
        raise KeyError(f"Không biết MCP '{name}'. Chạy `perfectrag list mcp` để xem.")
    info = REGISTRY[name]
    path = _mcp_path(project_dir)
    data = _load(path)
    data["servers"][name] = {
        "command": info["command"],
        "args": info["args"],
        **({"env": {k: f"${{{k}}}" for k in info["env"]}} if info["env"] else {}),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
