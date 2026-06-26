"""Context engineering microservice: prompt compress, prompt optimize, session memory."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="perfectrag context-eng", version="0.1.0")

# Lazy globals — heavy imports on first use only
_lingua: Any = None
_mem0: Any = None


def get_lingua() -> Any:
    global _lingua
    if _lingua is None:
        from llmlingua import PromptCompressor

        _lingua = PromptCompressor(
            model_name="microsoft/llmlingua-2-xlm-roberta-large-meetingbank",
            use_llmlingua2=True,
        )
    return _lingua


def get_mem() -> Any:
    global _mem0
    if _mem0 is None:
        from mem0 import Memory

        _mem0 = Memory()
    return _mem0


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


class CompressReq(BaseModel):
    text: str
    target_token: int = 200
    instruction: str | None = None


@app.post("/compress")
def compress(req: CompressReq) -> dict:
    """LLMLingua prompt compression."""
    try:
        result = get_lingua().compress_prompt(
            req.text,
            instruction=req.instruction or "",
            question="",
            target_token=req.target_token,
        )
        return {
            "compressed_prompt": result.get("compressed_prompt", ""),
            "origin_tokens": result.get("origin_tokens", 0),
            "compressed_tokens": result.get("compressed_tokens", 0),
            "ratio": result.get("ratio", ""),
        }
    except Exception as e:
        raise HTTPException(500, str(e))


class MemWriteReq(BaseModel):
    session: str
    content: str
    metadata: dict | None = None


@app.post("/memory/{session}/add")
def mem_add(session: str, req: MemWriteReq) -> dict:
    mem = get_mem()
    mem.add(req.content, user_id=session, metadata=req.metadata or {})
    return {"ok": True}


@app.get("/memory/{session}/search")
def mem_search(session: str, q: str, limit: int = 5) -> dict:
    mem = get_mem()
    hits = mem.search(q, user_id=session, limit=limit)
    return {"hits": hits}


class OptimizeReq(BaseModel):
    task: str
    examples: list[dict] = []


@app.post("/optimize")
def optimize(req: OptimizeReq) -> dict:
    """Placeholder: DSPy compile needs data + metric. Return a templated prompt."""
    # Full DSPy program compilation belongs in user code — we return scaffolded prompt.
    nl = "\n"
    ex_block = nl.join(
        f"Q: {e.get('q','')}{nl}A: {e.get('a','')}" for e in req.examples[:3]
    )
    examples_section = f"Examples:{nl}{ex_block}{nl}" if ex_block else ""
    return {
        "prompt_template": (
            f"Task: {req.task}{nl}"
            f"{examples_section}"
            "Input: {input}\nOutput:"
        ),
        "note": "Replace with DSPy MIPROv2 compile in your code for real optimization.",
    }
