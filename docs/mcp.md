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

Tương thích với Claude Code / Cursor / Claude Desktop MCP config → portable.

## Built-in registry (10 servers)

`perfectrag list mcp` để xem danh sách cập nhật.

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

Thêm entry vào `mcp.yaml`, prompt env vars nếu cần. Sau đó:

```bash
# Nếu template có variable substitution cho env:
echo "TAVILY_API_KEY=your-key" >> .env.local

docker compose restart
```

## Custom MCP server

Viết MCP server bằng bất kỳ ngôn ngữ nào (Python via [FastMCP](https://github.com/jlowin/fastmcp), Node via `@modelcontextprotocol/sdk`, Rust, Go...). Add vào `mcp.yaml`:

```yaml
servers:
  my-tool:
    command: python
    args: ["./mcp_servers/my_tool.py"]
```

MCP server expose `tools` (callable), `resources` (data), và `prompts` (templates). Backbone (RAGFlow / Dify) tự detect và surface trong UI.

## Khi nào MCP có / không load được

- **RAGFlow** (≥v0.13) hỗ trợ MCP natively qua built-in gateway.
- **Dify** có plugin marketplace riêng — `mcp.yaml` là phần supplementary.
- **LightRAG** / **custom-naive-rag** hiện chưa auto-load — MCP ở đây là config-only, cần viết wire-up trong app code (ví dụ load MCP servers khi start FastAPI).
