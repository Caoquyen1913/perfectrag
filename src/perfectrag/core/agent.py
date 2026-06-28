"""A minimal, dependency-free ReAct agent loop over registered ``@tool`` extensions.

The embedded ``LLM`` protocol only exposes ``generate(prompt)``, so tool-calling is
done with a tiny text protocol the LLM fills in (ACTION / ACTION_INPUT / FINAL). It is
deliberately lenient — if the model doesn't emit a tool call, its text is taken as the
final answer. Works with any backend (Ollama/llama.cpp/Gemini/Anthropic/OpenAI).

    rag.agent("What is 12*9, and what does the changelog say about tools?")
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from perfectrag.core import extensions as ext

_SEARCH_TOOL = {
    "name": "search_kb",
    "description": "Search the indexed knowledge base and return relevant passages.",
    "parameters": {
        "type": "object",
        "properties": {"query": {"type": "string"}},
        "required": ["query"],
    },
}

_ACTION_RE = re.compile(r"ACTION:\s*([A-Za-z0-9_\-]+)")
_INPUT_RE = re.compile(r"ACTION_INPUT:\s*(\{.*?\})", re.DOTALL)
_FINAL_RE = re.compile(r"FINAL:\s*(.+)", re.DOTALL)
_THOUGHT_RE = re.compile(r"THOUGHT:\s*(.+)")


@dataclass
class AgentStep:
    thought: str
    action: str
    action_input: dict[str, Any]
    observation: str


@dataclass
class AgentResult:
    answer: str
    steps: list[AgentStep] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "answer": self.answer,
            "steps": [
                {"thought": s.thought, "action": s.action,
                 "action_input": s.action_input, "observation": s.observation}
                for s in self.steps
            ],
        }


def _tool_specs(rag: Any, tools: list[str] | None, include_search: bool) -> list[dict[str, Any]]:
    names = tools if tools is not None else rag.tool_names()
    specs = [e.schema() for e in (ext.REGISTRY.get(ext.TOOL, n) for n in names) if e]
    if include_search:
        specs = [_SEARCH_TOOL, *specs]
    return specs


def _render_tools(specs: list[dict[str, Any]]) -> str:
    lines = []
    for s in specs:
        props = s["parameters"].get("properties", {})
        args = ", ".join(f"{k}: {v.get('type', 'string')}" for k, v in props.items())
        lines.append(f"- {s['name']}({args}) — {s['description']}")
    return "\n".join(lines)


def _build_prompt(question: str, specs: list[dict[str, Any]], transcript: str,
                  force_final: bool) -> str:
    head = (
        "You answer the user's question, using tools when helpful.\n\n"
        f"Available tools:\n{_render_tools(specs)}\n\n"
        "To call a tool, reply EXACTLY in this form:\n"
        "ACTION: <tool_name>\n"
        'ACTION_INPUT: {"arg": "value"}\n\n'
        "When you can answer, reply EXACTLY:\n"
        "FINAL: <your answer>\n\n"
    )
    if force_final:
        head += "You have gathered enough information. Reply now with FINAL: <answer>.\n\n"
    return f"{head}Question: {question}\n{transcript}"


def _parse(out: str) -> tuple[str | None, str | None, dict[str, Any]]:
    """Return (final_answer, action_name, action_input)."""
    fm = _FINAL_RE.search(out)
    if fm:
        return fm.group(1).strip(), None, {}
    am = _ACTION_RE.search(out)
    if not am:
        return None, None, {}
    action = am.group(1)
    args: dict[str, Any] = {}
    im = _INPUT_RE.search(out)
    if im:
        try:
            parsed = json.loads(im.group(1))
            if isinstance(parsed, dict):
                args = parsed
        except (ValueError, TypeError):
            args = {}
    return None, action, args


def _run_tool(rag: Any, action: str, args: dict[str, Any], question: str) -> str:
    try:
        if action == "search_kb":
            hits = rag.retrieve(args.get("query") or question)
            return "\n".join(h.chunk.text[:300] for h in hits) or "(no results)"
        result = rag.call_tool(action, **args)
        return str(result)
    except Exception as exc:                       # never crash the loop
        return f"error calling {action}: {exc}"


def run_agent(rag: Any, question: str, *, max_steps: int = 5,
              tools: list[str] | None = None, include_search: bool = True,
              max_tokens: int = 512) -> AgentResult:
    specs = _tool_specs(rag, tools, include_search)
    steps: list[AgentStep] = []
    transcript = ""
    for _ in range(max_steps):
        out = rag.llm.generate(_build_prompt(question, specs, transcript, False),
                               max_tokens=max_tokens)
        final, action, args = _parse(out)
        if final is not None:
            return AgentResult(answer=final, steps=steps)
        if not action:                             # no tool + no FINAL → take as answer
            return AgentResult(answer=out.strip(), steps=steps)
        obs = _run_tool(rag, action, args, question)
        tm = _THOUGHT_RE.search(out)
        steps.append(AgentStep(tm.group(1).strip() if tm else "", action, args, obs))
        transcript += (
            f"\nACTION: {action}\nACTION_INPUT: {json.dumps(args)}\nOBSERVATION: {obs}\n"
        )
    # steps exhausted → force a final answer from what we gathered
    out = rag.llm.generate(_build_prompt(question, specs, transcript, True),
                           max_tokens=max_tokens)
    final, _, _ = _parse(out)
    return AgentResult(answer=final if final is not None else out.strip(), steps=steps)
