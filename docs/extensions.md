# Extensions — make perfectRAG your own framework

perfectRAG's embedded library is **pluggable by decorator**. Five decorators let you
add custom data sources, retrieval logic, post-processing, tools, and skills to the
RAG pipeline — with **one line and no subclassing**.

```python
from perfectrag import inject, retrieve, transform, tool, skill, Document
```

| Decorator | Purpose | Signature |
|---|---|---|
| `@inject` | a custom data source for ingestion | `(…) -> yield Document/str/dict/(text, source)` |
| `@retrieve` | a full custom retriever (replaces the built-in) | `(ctx, query, k) -> list[Hit]` |
| `@transform` | a post-retrieval hook (rerank / filter / expand) | `(ctx, query, hits) -> list[Hit]` |
| `@tool` | a callable the LLM/agent can invoke | `(…typed args…) -> result` |
| `@skill` | a higher-level reusable capability | `(ctx, …) -> result` |

## The `ctx` convention

Any extension whose **first parameter is named `ctx`** receives a `Context` — your
handle to the running RAG (`ctx.rag`, `ctx.store`, `ctx.embedder`, `ctx.llm`,
`ctx.collection`, plus `ctx.embed(text)` and `ctx.search(vec, k)`). It's **optional** —
omit it if you don't need it. Everything after `ctx` (with type hints) becomes the
tool's JSON schema; params without a default are required; the first docstring line is
the description. (Same conventions as LangChain `@tool` / Pydantic AI / FastMCP.)

## `@inject` — custom data sources

```python
@inject("notion")
def notion(database_id: str):
    "Pull pages from a Notion database into the corpus."
    for page in notion_client.query(database_id):
        yield Document(text=page.plain_text,
                       source=f"notion:{page.id}",
                       metadata={"title": page.title, "url": page.url})

rag.ingest_from("notion", database_id="abc123")   # -> chunk count
```

Yield whatever is convenient — `Document`, a plain `str`, a `dict`
(`{"text", "source", "metadata"}`), or a `(text, source)` tuple. Metadata rides along
onto every chunk, so `@transform` / filters can use it later.

## `@retrieve` — a custom retriever

Replace the built-in retriever entirely (e.g. hybrid search, an external API, a graph
walk). Return a list of `Hit`.

```python
from perfectrag.core.protocols import Hit

@retrieve("hybrid")
def hybrid(ctx, query, k):
    "Dense + keyword hybrid retrieval."
    dense = ctx.search(ctx.embed(query), k)
    keyword = my_bm25(query, k)
    return merge(dense, keyword)[:k]

rag = RAG.from_config("perfectrag.yml")   # retriever: hybrid  (in the yaml)
# or: RAG(..., retriever="hybrid")
```

## `@transform` — post-retrieval hooks

Run after retrieval, in order. Great for reranking, de-duping, recency boosts, PII
redaction, or metadata filters. Each gets the hits and returns hits.

```python
@transform("boost_recent")
def boost_recent(ctx, query, hits):
    "Push more recent documents up."
    return sorted(hits, key=lambda h: h.chunk.metadata.get("date", 0), reverse=True)

@transform("only_public")
def only_public(query, hits):            # no ctx needed
    return [h for h in hits if h.chunk.metadata.get("acl") == "public"]

rag = RAG(..., transforms=["only_public", "boost_recent"])   # applied in order
```

## `@tool` — callable tools

Turn any function into an LLM/agent-callable tool. The JSON schema is inferred from
type hints — export it for OpenAI/Anthropic tool-calling or an MCP server.

```python
@tool
def calculator(expression: str) -> str:
    "Evaluate a basic arithmetic expression."
    return str(eval(expression, {"__builtins__": {}}, {}))

@tool
def kb_search(ctx, query: str, k: int = 3) -> list[str]:
    "Search the indexed knowledge base."
    return [h.chunk.text for h in ctx.rag.retrieve(query, k)]

rag.tool_names()                    # -> ["calculator", "kb_search"]
rag.tool_schemas()                  # -> OpenAI/Anthropic function schemas (ctx hidden)
rag.call_tool("calculator", expression="2+2")   # -> "4"
```

`tool_schemas()` returns exactly the shape OpenAI/Anthropic function-calling and MCP
expect, so you can hand your tools to any agent loop or export them into a generated
project's `mcp.yaml`.

## `@skill` — reusable capabilities

A higher-level, named capability (prompt-driven or pure-Python).

```python
@skill("tldr")
def tldr(ctx, text: str) -> str:
    "Summarize text into 3 bullets."
    return ctx.llm.generate("Summarize in 3 bullets:\n\n" + text)

rag.run_skill("tldr", text=long_doc)
```

## Agentic tool-calling — `rag.agent(...)`

Let the LLM decide which tools to call to answer a question. `rag.agent()` runs a
lenient ReAct loop over your registered `@tool`s plus a built-in `search_kb`
(knowledge-base retrieval). Works with any LLM backend — no function-calling API needed.

```python
@tool
def multiply(a: int, b: int) -> int:
    "Multiply two integers."
    return a * b

result = rag.agent("What's 12 × 9, and what do the docs say about CRAG?")
print(result.answer)
for step in result.steps:          # full trace
    print(step.action, step.action_input, "->", step.observation[:60])
```

- `max_steps` (default 5) caps the loop; `tools=[...]` limits which tools are exposed;
  `include_search=False` drops the built-in KB search.
- If the model just answers (no tool call), that text is the answer — it never gets stuck.
- Tool errors are captured into the observation, never raised.

## Export your tools to MCP

Turn your `@tool`s into a real MCP server so a generated project's agentic backbone,
Claude Code, or Cursor can call them:

```bash
perfectrag export-tools --from ./extensions.py --project .
```

This writes `perfectrag_tools_server.py` (a tiny [FastMCP](https://gofastmcp.com) server)
and adds a `perfectrag-tools` entry to the project's `mcp.yaml`. Pure tools run
standalone; `ctx`-tools are served against a RAG built from `perfectrag.yml`. Run it with:

```bash
pip install fastmcp && python perfectrag_tools_server.py
```

## Wiring extensions in

**1. Programmatically** — just import the module that defines them, then name them:

```python
import my_extensions            # runs the decorators
rag = RAG(..., retriever="hybrid", transforms=["boost_recent"])
```

**2. Via `perfectrag.yml`** — perfectRAG loads the files and applies the names:

```yaml
extensions:                     # files/modules to import (decorators run on load)
  - ./my_extensions.py
retriever: hybrid               # a registered @retrieve
transforms: [only_public, boost_recent]   # registered @transform, in order
```

**3. As a pip package** — publish a registration hook so others get your extensions
after `pip install`:

```toml
[project.entry-points."perfectrag.extensions"]
my_pack = "my_pack:register"    # a callable whose import/run registers extensions
```

```python
from perfectrag.core.extensions import load_entry_point_extensions
load_entry_point_extensions()
```

## Inspecting what's registered

```python
rag.extensions()
# {'inject': ['notion'], 'retrieve': ['hybrid'], 'transform': ['boost_recent'],
#  'tool': ['calculator', 'kb_search'], 'skill': ['tldr']}
```

See [`examples/my_extensions.py`](../examples/my_extensions.py) for a complete, runnable
starter you can copy.
