"""Wraps Copier to render a chosen template with recipe + hardware + answers vars."""

from __future__ import annotations

from importlib.resources import files
from pathlib import Path

import copier

from perfectrag.hardware import HardwareProfile
from perfectrag.recipes import Answers, Recipe

TEMPLATES_PKG = "perfectrag.templates"

_DESCRIPTIONS = {
    "custom-naive-rag": "FastAPI + Qdrant + Ollama + open-webui — minimal DIY stack",
    "ragflow-stack":    "RAGFlow — hybrid search, deep doc parsing, agentic, MCP-ready",
    "lightrag-stack":   "LightRAG — GraphRAG với dual-level retrieval + WebUI",
    "dify-stack":       "Dify — visual workflow/agent builder với marketplace",
}


def available_templates() -> dict[str, str]:
    root = files(TEMPLATES_PKG)
    out: dict[str, str] = {}
    for name in _DESCRIPTIONS:
        if root.joinpath(name).is_dir():
            out[name] = _DESCRIPTIONS[name]
    return out


def template_path(template: str) -> Path:
    root = files(TEMPLATES_PKG)
    path = root.joinpath(template)
    if not path.is_dir():
        raise ValueError(f"Template không tồn tại: {template}")
    return Path(str(path))


def render(
    recipe: Recipe,
    hw: HardwareProfile,
    answers: Answers,
    project_dir: Path,
    *,
    force: bool = False,
) -> None:
    src = template_path(recipe.template)
    data = recipe.as_template_vars(hw, answers)
    # Flatten some vars so Copier's questions can reuse them
    data["project_name"] = project_dir.name

    project_dir.mkdir(parents=True, exist_ok=True)

    copier.run_copy(
        src_path=str(src),
        dst_path=str(project_dir),
        data=data,
        defaults=True,
        overwrite=force,
        unsafe=True,  # allow Jinja filters/extensions inside template
    )
