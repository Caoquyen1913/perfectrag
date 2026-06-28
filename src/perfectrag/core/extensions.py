"""Decorator-based extension system — turn perfectRAG into a pluggable framework.

Five decorators let users plug their own behavior into the embedded RAG with one
line and **no subclassing**:

    from perfectrag import inject, retrieve, transform, tool, skill, Document

    @inject("notion")                 # a custom data source for ingestion
    def notion(database_id: str):
        for page in notion_client.query(database_id):
            yield Document(text=page.text, source=f"notion:{page.id}")

    @transform("boost_recent")        # a post-retrieval hook (rerank/filter/expand)
    def boost_recent(ctx, query, hits):
        return sorted(hits, key=lambda h: h.chunk.metadata.get("date", 0), reverse=True)

    @retrieve("hybrid")               # a full custom retriever
    def hybrid(ctx, query, k):
        return ctx.search(ctx.embed(query), k)

    @tool                             # a callable the LLM/agent can invoke
    def calculator(expression: str) -> str:
        "Evaluate a basic arithmetic expression."
        return str(eval(expression, {"__builtins__": {}}, {}))

    @skill("tldr")                    # a higher-level, reusable capability
    def tldr(ctx, text: str) -> str:
        "Summarize text in 3 bullet points."
        return ctx.llm.generate("TL;DR in 3 bullets:\n" + text)

Then wire them in via config or kwargs:

    rag = RAG.from_config("perfectrag.yml")          # extensions: [./my_ext.py] in yaml
    rag.ingest_from("notion", database_id="...")     # uses @inject
    rag.query("...", )                               # transforms/retriever auto-applied
    rag.call_tool("calculator", expression="2+2")    # -> "4"

Conventions (matching LangChain / Pydantic AI / FastMCP):
- The first parameter named `ctx` (or `context`) receives a `Context` (rag, store,
  embedder, llm, ...). It is optional — omit it if you don't need it.
- Remaining parameters + type hints become the tool's JSON schema. Params without a
  default are required.
- The first docstring line becomes the description.
"""

from __future__ import annotations

import importlib
import importlib.util
import inspect
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, get_type_hints

# ----------------------------------------------------------------- kinds
INJECT, RETRIEVE, TRANSFORM, TOOL, SKILL = "inject", "retrieve", "transform", "tool", "skill"
KINDS = (INJECT, RETRIEVE, TRANSFORM, TOOL, SKILL)


# ----------------------------------------------------------------- data types
@dataclass
class Document:
    """A unit of text to ingest. `@inject` functions yield these (str/dict/tuple ok too)."""
    text: str
    source: str = "inject"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Extension:
    name: str
    kind: str
    fn: Callable[..., Any]
    description: str
    params: dict[str, Any]               # JSON-schema 'properties'
    required: list[str]                  # required param names
    wants_ctx: bool
    meta: dict[str, Any] = field(default_factory=dict)

    def schema(self) -> dict[str, Any]:
        """OpenAI/Anthropic-style function schema — for tool-calling or MCP export."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": self.params,
                "required": self.required,
            },
        }


# ----------------------------------------------------------------- schema inference
_PY_TO_JSON = {
    str: "string", int: "integer", float: "number",
    bool: "boolean", list: "array", dict: "object",
}


def _wants_ctx(fn: Callable[..., Any]) -> bool:
    params = list(inspect.signature(fn).parameters.values())
    return bool(params) and params[0].name in ("ctx", "context")


def _describe_params(fn: Callable[..., Any]) -> tuple[dict[str, Any], list[str]]:
    """Build JSON-schema properties + required list from a function signature.

    Skips a leading `ctx`/`context` param and *args/**kwargs."""
    sig = inspect.signature(fn)
    try:
        hints = get_type_hints(fn)
    except Exception:
        hints = {}
    params = list(sig.parameters.values())
    if params and params[0].name in ("ctx", "context"):
        params = params[1:]
    props: dict[str, dict[str, Any]] = {}
    required: list[str] = []
    for p in params:
        if p.kind in (p.VAR_POSITIONAL, p.VAR_KEYWORD):
            continue
        jtype = _PY_TO_JSON.get(hints.get(p.name, str), "string")
        entry: dict[str, Any] = {"type": jtype}
        if p.default is inspect.Parameter.empty:
            required.append(p.name)
        else:
            entry["default"] = p.default
        props[p.name] = entry
    return props, required


# ----------------------------------------------------------------- registry
class Registry:
    """Global registry that the decorators populate."""

    def __init__(self) -> None:
        self._items: dict[str, dict[str, Extension]] = {k: {} for k in KINDS}

    def add(self, ext: Extension) -> None:
        self._items[ext.kind][ext.name] = ext

    def get(self, kind: str, name: str) -> Extension | None:
        return self._items.get(kind, {}).get(name)

    def names(self, kind: str) -> list[str]:
        return sorted(self._items.get(kind, {}))

    def all(self, kind: str) -> list[Extension]:
        return list(self._items.get(kind, {}).values())

    def clear(self, kind: str | None = None) -> None:
        for k in (KINDS if kind is None else [kind]):
            self._items[k] = {}

    def summary(self) -> dict[str, list[str]]:
        return {k: self.names(k) for k in KINDS}


REGISTRY = Registry()


def _make_decorator(kind: str) -> Callable[..., Any]:
    def decorator(name_or_fn: Any = None, *, name: str | None = None,
                  description: str | None = None, **meta: Any) -> Any:
        explicit_name: str | None = name

        def wrap(fn: Callable[..., Any]) -> Callable[..., Any]:
            props, required = _describe_params(fn)
            doc = (inspect.getdoc(fn) or "").strip()
            resolved_name: str = explicit_name if explicit_name else getattr(fn, "__name__", "anon")
            ext = Extension(
                name=resolved_name,
                kind=kind,
                fn=fn,
                description=description or (doc.splitlines()[0] if doc else ""),
                params=props,
                required=required,
                wants_ctx=_wants_ctx(fn),
                meta=meta,
            )
            REGISTRY.add(ext)
            fn.__perfectrag_ext__ = ext  # type: ignore[attr-defined]
            return fn

        if callable(name_or_fn):            # bare:   @inject
            return wrap(name_or_fn)
        if isinstance(name_or_fn, str):     # named:  @inject("notion")
            explicit_name = name_or_fn
        return wrap                         # parens: @inject(name=..., description=...)

    decorator.__name__ = kind
    return decorator


#: Register a custom data source. The function yields ``Document`` (or str/dict/tuple).
inject = _make_decorator(INJECT)
#: Register a full custom retriever ``(ctx, query, k) -> list[Hit]``.
retrieve = _make_decorator(RETRIEVE)
#: Register a post-retrieval hook ``(ctx, query, hits) -> list[Hit]`` (rerank/filter/expand).
transform = _make_decorator(TRANSFORM)
#: Register a callable tool the LLM/agent can invoke; schema is inferred from type hints.
tool = _make_decorator(TOOL)
#: Register a higher-level, reusable capability (prompt-driven or pure-Python).
skill = _make_decorator(SKILL)


# ----------------------------------------------------------------- context
@dataclass
class Context:
    """Handed to any extension whose first parameter is named ``ctx``."""
    rag: Any
    config: dict[str, Any] = field(default_factory=dict)

    @property
    def store(self) -> Any:       return self.rag.store
    @property
    def embedder(self) -> Any:    return self.rag.embedder
    @property
    def llm(self) -> Any:         return self.rag.llm
    @property
    def reranker(self) -> Any:    return self.rag.reranker
    @property
    def collection(self) -> Any:  return self.rag.collection

    def embed(self, text: str) -> list[float]:
        return list(self.rag.embedder.embed(text))

    def search(self, vector: list[float], k: int) -> Any:
        return self.rag.store.search(self.rag.collection, vector, k)


# ----------------------------------------------------------------- helpers
def normalize_doc(item: Any, default_source: str = "inject") -> Document:
    """Coerce a value yielded by an ``@inject`` function into a ``Document``."""
    if isinstance(item, Document):
        return item
    if isinstance(item, str):
        return Document(text=item, source=default_source)
    if isinstance(item, dict):
        return Document(
            text=item.get("text", ""),
            source=item.get("source", default_source),
            metadata=item.get("metadata", {}) or {},
        )
    if isinstance(item, tuple) and len(item) == 2 and isinstance(item[0], str):
        return Document(text=item[0], source=str(item[1]))
    text = getattr(item, "text", None)   # Chunk-like duck typing
    if text is not None:
        return Document(
            text=text,
            source=getattr(item, "source", default_source),
            metadata=getattr(item, "metadata", {}) or {},
        )
    raise TypeError(f"@inject yielded an unsupported item of type {type(item)!r}")


def iter_docs(result: Any, default_source: str = "inject") -> Iterator[Document]:
    """Normalize an @inject return value (single item or iterable) into Documents."""
    if isinstance(result, (str, Document, dict)):
        items: Any = [result]
    elif isinstance(result, tuple) and len(result) == 2 and isinstance(result[0], str):
        items = [result]
    else:
        items = result
    for item in items:
        yield normalize_doc(item, default_source)


def load_extensions(target: str | Path) -> int:
    """Import a module (dotted name) or a ``.py`` file so its decorators register.

    Returns the number of extensions added by the import (best-effort)."""
    before = sum(len(REGISTRY.all(k)) for k in KINDS)
    t = str(target)
    if t.endswith(".py") or "/" in t or "\\" in t:
        path = Path(t).expanduser()
        spec = importlib.util.spec_from_file_location(path.stem, path)
        if not (spec and spec.loader):
            raise ImportError(f"Cannot load extension file: {path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    else:
        importlib.import_module(t)
    after = sum(len(REGISTRY.all(k)) for k in KINDS)
    return after - before


def load_entry_point_extensions(group: str = "perfectrag.extensions") -> int:
    """Load extensions published by other pip packages via entry points.

    Each entry point should resolve to a callable that registers extensions when
    invoked (its decorators run on import / call)."""
    from importlib.metadata import entry_points

    count = 0
    for ep in entry_points(group=group):   # `group=` selection: Python >= 3.10
        try:
            obj = ep.load()
            if callable(obj):
                obj()
            count += 1
        except Exception:
            continue
    return count
