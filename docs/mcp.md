# MCP (Model Context Protocol)

perfectRAG uses MCP as the standard way to attach external tools to your RAG service. Each generated project ships with an `mcp.yaml` listing MCP servers the backbone will load.

## Format

```yaml
servers:
  <name>:
    command: <binary or interpreter>
    args: [...]
    env: { VAR: "${VAR}" }   # optional
```

Compatible with Claude Code / Cursor / Claude Desktop MCP config → portable.

## Built-in registry (10 servers)

`perfectrag list mcp` to see the up-to-date list.

| Name | Description | Env vars required |
|---|---|---|
| `filesystem` | Read/write files in whitelisted dir | — |
| `fetch` | Fetch URL → markdown | — |
| `tavily` | Tavily web search | `TAVILY_API_KEY` |
| `brave-search` | Brave web search | `BRAVE_API_KEY` |
| `postgres` | Read-only Postgres query | `POSTGRES_URL` |
| `sqlite` | SQLite query | — |
| `github` | GitHub repos/issues/PRs | `GITHUB_PERSONAL_ACCESS_TOKEN` |
| `memory` | KG memory for agent | — |
| `sequential-thinking` | Structured CoT | — |
| `qdrant` | Qdrant vector MCP | — |

## Add MCP to project

```bash
perfectrag add mcp tavily --project .
```

Adds an entry to `mcp.yaml`, prompting for env vars if needed. Then:

```bash
# If the template has variable substitution for env:
echo "TAVILY_API_KEY=your-key" >> .env.local

docker compose restart
```

## Custom MCP server

Write an MCP server in any language (Python via [FastMCP](https://github.com/jlowin/fastmcp), Node via `@modelcontextprotocol/sdk`, Rust, Go...). Add it to `mcp.yaml`:

```yaml
servers:
  my-tool:
    command: python
    args: ["./mcp_servers/my_tool.py"]
```

MCP servers expose `tools` (callable), `resources` (data), and `prompts` (templates). The backbone (RAGFlow / Dify) auto-detects and surfaces them in the UI.

## When MCP does / doesn't load

- **RAGFlow** (≥v0.13) supports MCP natively via a built-in gateway.
- **Dify** has its own plugin marketplace — `mcp.yaml` is supplementary.
- **LightRAG** / **custom-naive-rag** don't auto-load yet — MCP here is config-only, and you need to write the wire-up in app code (e.g. load MCP servers when FastAPI starts).
