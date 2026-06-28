"""Starter extension pack for perfectRAG — copy this file and make it yours.

Load it in three ways:

  # 1. programmatically
  import my_extensions
  rag = RAG(..., transforms=["boost_recent"])

  # 2. via perfectrag.yml
  #    extensions: [./my_extensions.py]
  #    transforms: [boost_recent]

  # 3. from the CLI of a generated project, point its config at this file.

Run a quick demo:  python my_extensions.py
"""

from __future__ import annotations

from perfectrag import Document, inject, skill, tool, transform
from perfectrag.core.protocols import Hit


# --------------------------------------------------------------- @inject
@inject("faq")
def faq(topic: str):
    """A toy data source: yields a couple of FAQ entries for a topic."""
    yield Document(
        text=f"Q: What is {topic}? A: {topic} is a feature of perfectRAG.",
        source=f"faq:{topic}",
        metadata={"topic": topic, "kind": "faq"},
    )
    yield Document(
        text=f"Q: How do I enable {topic}? A: set it in perfectrag.yml.",
        source=f"faq:{topic}:howto",
        metadata={"topic": topic, "kind": "howto"},
    )


# --------------------------------------------------------------- @transform
@transform("dedupe")
def dedupe(query: str, hits: list[Hit]) -> list[Hit]:
    """Drop hits with duplicate text (no ctx needed)."""
    seen: set[str] = set()
    out: list[Hit] = []
    for h in hits:
        if h.chunk.text not in seen:
            seen.add(h.chunk.text)
            out.append(h)
    return out


@transform("boost_recent")
def boost_recent(ctx, query: str, hits: list[Hit]) -> list[Hit]:
    """Push more recent docs up (expects a numeric `date` in metadata)."""
    return sorted(hits, key=lambda h: h.chunk.metadata.get("date", 0), reverse=True)


# --------------------------------------------------------------- @tool
@tool
def calculator(expression: str) -> str:
    """Evaluate a basic arithmetic expression, e.g. '2 * (3 + 4)'."""
    return str(eval(expression, {"__builtins__": {}}, {}))  # sandboxed builtins


@tool
def kb_search(ctx, query: str, k: int = 3) -> list[str]:
    """Search the indexed knowledge base and return the matching chunk texts."""
    return [h.chunk.text for h in ctx.rag.retrieve(query, k)]


# --------------------------------------------------------------- @skill
@skill("tldr")
def tldr(ctx, text: str) -> str:
    """Summarize text into three bullet points using the configured LLM."""
    return ctx.llm.generate("Summarize the following in 3 bullet points:\n\n" + text)


if __name__ == "__main__":
    # Tiny self-contained demo with in-memory fakes (no model downloads).
    from perfectrag import RAG

    class _Emb:
        dim = 8
        def embed(self, t): return self.embed_batch([t])[0]
        def embed_batch(self, ts): return [[float(len(t) % 9)] + [1.0] * 7 for t in ts]

    class _LLM:
        def generate(self, p, **k): return "- point one\n- point two\n- point three"
        def stream(self, p, **k): yield "..."

    try:
        from perfectrag.core.stores import build as build_store
        store = build_store("chroma")
    except Exception:
        raise SystemExit("install chromadb to run the demo: pip install chromadb")

    rag = RAG(store=store, embedder=_Emb(), llm=_LLM(), collection="demo",
              chunk_size=40, top_k=5, transforms=["dedupe"])

    print("ingested:", rag.ingest_from("faq", topic="contextual retrieval"), "chunks")
    hits = rag.retrieve("how do I enable it")
    print("top source:", hits[0].chunk.source)
    print("tools:", rag.tool_names())
    print("2*(3+4) =", rag.call_tool("calculator", expression="2 * (3 + 4)"))
    print("tldr:", rag.run_skill("tldr", text="long document " * 20).split(chr(10))[0])
    print("registered:", rag.extensions())
