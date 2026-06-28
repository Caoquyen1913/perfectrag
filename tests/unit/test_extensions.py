"""Tests for the decorator-based extension framework (@inject/@retrieve/@transform/@tool/@skill)."""

from __future__ import annotations

import pytest

from perfectrag import (
    RAG,
    Context,
    Document,
    inject,
    retrieve,
    skill,
    tool,
    transform,
)
from perfectrag.core import extensions as ext
from perfectrag.core.protocols import Hit


# ----------------------------------------------------------------- fakes
class FakeStore:
    def __init__(self):
        self._points = []

    def ensure_collection(self, name, dim): pass

    def upsert(self, collection, chunks, vectors):
        for c, v in zip(chunks, vectors):
            self._points.append((c, v))

    def search(self, collection, query_vec, k):
        scored = [(c, sum(a * b for a, b in zip(query_vec, v))) for c, v in self._points]
        scored.sort(key=lambda x: x[1], reverse=True)
        return [Hit(chunk=c, score=float(s)) for c, s in scored[:k]]

    def list_collections(self): return ["documents"]
    def delete_collection(self, name): pass


class FakeEmbedder:
    dim = 3
    def embed(self, text): return self.embed_batch([text])[0]
    def embed_batch(self, texts): return [[float(len(t) % 7), float(len(t) % 5), 1.0] for t in texts]


class FakeLLM:
    def generate(self, prompt, **kw): return f"ANSWER[{len(prompt)}]"
    def stream(self, prompt, **kw): yield "A"


def make_rag(**kw):
    return RAG(store=FakeStore(), embedder=FakeEmbedder(), llm=FakeLLM(),
               chunk_size=4, top_k=5, **kw)


@pytest.fixture(autouse=True)
def clean_registry():
    """Isolate every test — the registry is process-global."""
    ext.REGISTRY.clear()
    yield
    ext.REGISTRY.clear()


# ----------------------------------------------------------------- @inject
def test_inject_named_source_ingests_documents():
    @inject("memo")
    def memo(topic: str):
        yield Document(text=f"note about {topic} " * 3, source=f"memo:{topic}",
                       metadata={"topic": topic})

    rag = make_rag()
    n = rag.ingest_from("memo", topic="rag")
    assert n >= 1
    hits = rag.retrieve("anything")
    assert hits and hits[0].chunk.source == "memo:rag"
    assert hits[0].chunk.metadata.get("topic") == "rag"   # metadata carried through


def test_inject_accepts_str_dict_tuple():
    @inject("mixed")
    def mixed():
        yield "plain string chunk"                       # 1 chunk (<= chunk_size words)
        yield {"text": "dict chunk here", "source": "d", "metadata": {"k": 1}}
        yield ("tuple chunk now", "t")

    rag = make_rag()
    n = rag.ingest_from("mixed")
    assert n == 3
    sources = {h.chunk.source for h in rag.retrieve("x", k=10)}
    assert {"mixed", "d", "t"} <= sources


def test_inject_with_ctx_receives_context():
    seen = {}

    @inject("with_ctx")
    def with_ctx(ctx, label: str):
        seen["is_ctx"] = isinstance(ctx, Context)
        seen["collection"] = ctx.collection
        yield Document(text=f"{label} body text here", source=label)

    rag = make_rag(collection="kb")
    rag.ingest_from("with_ctx", label="hello")
    assert seen["is_ctx"] is True
    assert seen["collection"] == "kb"


def test_ingest_from_unknown_source_raises():
    rag = make_rag()
    with pytest.raises(KeyError):
        rag.ingest_from("nope")


# ----------------------------------------------------------------- @transform
def test_transform_runs_after_retrieval():
    @transform("reverse")
    def reverse(ctx, query, hits):
        return list(reversed(hits))

    rag = make_rag(transforms=["reverse"])
    rag.ingest_text("aaaa bbbb cccc dddd eeee ffff", source="x")
    base = rag._default_retrieve("q", k=5)
    out = rag.retrieve("q", k=5)
    assert [h.chunk.id for h in out] == [h.chunk.id for h in reversed(base)]


def test_transform_can_filter():
    @transform("only_two")
    def only_two(query, hits):          # no ctx — should still work
        return hits[:2]

    rag = make_rag(transforms=["only_two"])
    rag.ingest_text("a1 b2 c3 d4 e5 f6 g7 h8", source="x")
    assert len(rag.retrieve("q", k=10)) == 2


# ----------------------------------------------------------------- @retrieve
def test_custom_retriever_replaces_default():
    sentinel = []

    @retrieve("fixed")
    def fixed(ctx, query, k):
        sentinel.append(query)
        return []                        # always empty

    rag = make_rag(retriever="fixed")
    rag.ingest_text("a b c d e f g h", source="x")
    assert rag.retrieve("hello") == []
    assert sentinel == ["hello"]


# ----------------------------------------------------------------- @tool
def test_tool_schema_inferred_from_type_hints():
    @tool
    def add(a: int, b: int = 1) -> int:
        "Add two integers."
        return a + b

    rag = make_rag()
    (schema,) = [s for s in rag.tool_schemas() if s["name"] == "add"]
    assert schema["description"] == "Add two integers."
    assert schema["parameters"]["properties"]["a"]["type"] == "integer"
    assert schema["parameters"]["properties"]["b"]["default"] == 1
    assert schema["parameters"]["required"] == ["a"]       # b has a default
    assert rag.call_tool("add", a=2, b=3) == 5


def test_tool_decorator_forms():
    @tool
    def bare():
        "bare"
        return 1

    @tool("renamed")
    def original():
        "named"
        return 2

    @tool(name="kw", description="desc override")
    def kwform():
        return 3

    rag = make_rag()
    assert set(rag.tool_names()) == {"bare", "renamed", "kw"}
    (kw,) = [s for s in rag.tool_schemas() if s["name"] == "kw"]
    assert kw["description"] == "desc override"


def test_tool_with_ctx_excluded_from_schema():
    @tool
    def kb_search(ctx, query: str) -> int:
        "Search the knowledge base."
        return len(ctx.rag.retrieve(query))

    rag = make_rag()
    rag.ingest_text("a b c d e f", source="x")
    (schema,) = rag.tool_schemas()
    assert "ctx" not in schema["parameters"]["properties"]   # ctx hidden from the LLM
    assert "query" in schema["parameters"]["properties"]
    assert isinstance(rag.call_tool("kb_search", query="hi"), int)


# ----------------------------------------------------------------- @skill
def test_skill_runs():
    @skill("shout")
    def shout(ctx, text: str) -> str:
        "Uppercase the text."
        return text.upper()

    rag = make_rag()
    assert rag.skill_names() == ["shout"]
    assert rag.run_skill("shout", text="hi") == "HI"


# ----------------------------------------------------------------- discovery
def test_load_extensions_from_file(tmp_path):
    f = tmp_path / "my_ext.py"
    f.write_text(
        "from perfectrag import tool\n"
        "@tool\n"
        "def ping(): 'ping'\n"
        "    \n",
        encoding="utf-8",
    )
    added = ext.load_extensions(str(f))
    assert added == 1
    assert "ping" in ext.REGISTRY.names(ext.TOOL)


def test_extensions_loaded_via_constructor(tmp_path):
    f = tmp_path / "ext2.py"
    f.write_text(
        "from perfectrag import inject, Document\n"
        "@inject('lipsum')\n"
        "def lipsum(n: int = 1):\n"
        "    for i in range(n):\n"
        "        yield Document(text='lorem ipsum dolor sit', source=f'lipsum:{i}')\n",
        encoding="utf-8",
    )
    rag = make_rag(extensions=[str(f)])
    assert "lipsum" in rag.extensions()["inject"]
    assert rag.ingest_from("lipsum", n=2) == 2


# ----------------------------------------------------------------- normalization
# ----------------------------------------------------------------- agent loop
class ScriptLLM:
    """Emits a scripted sequence of generate() outputs."""
    def __init__(self, *outputs):
        self.outputs = list(outputs)
        self.i = 0

    def generate(self, prompt, **kw):
        out = self.outputs[min(self.i, len(self.outputs) - 1)]
        self.i += 1
        return out

    def stream(self, prompt, **kw):
        yield ""


def test_agent_calls_tool_then_finishes():
    @tool
    def double(n: int) -> int:
        "Double a number."
        return n * 2

    llm = ScriptLLM(
        'THOUGHT: double it.\nACTION: double\nACTION_INPUT: {"n": 21}',
        "FINAL: The answer is 42.",
    )
    rag = RAG(store=FakeStore(), embedder=FakeEmbedder(), llm=llm, top_k=3)
    res = rag.agent("double 21", include_search=False)
    assert res.answer == "The answer is 42."
    assert len(res.steps) == 1
    assert res.steps[0].action == "double"
    assert res.steps[0].observation == "42"


def test_agent_uses_builtin_search_kb():
    llm = ScriptLLM(
        'ACTION: search_kb\nACTION_INPUT: {"query": "alpha"}',
        "FINAL: done",
    )
    rag = RAG(store=FakeStore(), embedder=FakeEmbedder(), llm=llm, chunk_size=4, top_k=2)
    rag.ingest_text("alpha beta gamma delta epsilon zeta", source="x")
    res = rag.agent("find alpha")
    assert res.steps[0].action == "search_kb"
    assert res.steps[0].observation != "(no results)"   # retrieved something
    assert res.answer == "done"


def test_agent_plain_text_is_taken_as_answer():
    llm = ScriptLLM("It is 4.")             # no ACTION / no FINAL
    rag = RAG(store=FakeStore(), embedder=FakeEmbedder(), llm=llm)
    res = rag.agent("2+2?", include_search=False)
    assert res.answer == "It is 4."
    assert res.steps == []


def test_agent_tool_error_is_observed_not_raised():
    @tool
    def boom(x: int) -> int:
        "Always fails."
        raise ValueError("nope")

    llm = ScriptLLM(
        'ACTION: boom\nACTION_INPUT: {"x": 1}',
        "FINAL: handled",
    )
    rag = RAG(store=FakeStore(), embedder=FakeEmbedder(), llm=llm)
    res = rag.agent("run boom", include_search=False)
    assert "error calling boom" in res.steps[0].observation
    assert res.answer == "handled"


def test_normalize_doc_variants():
    assert ext.normalize_doc("hi").text == "hi"
    assert ext.normalize_doc({"text": "a", "source": "s"}).source == "s"
    assert ext.normalize_doc(("body", "src")).source == "src"
    d = Document(text="x", source="y")
    assert ext.normalize_doc(d) is d
    with pytest.raises(TypeError):
        ext.normalize_doc(12345)
