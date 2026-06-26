"""Wraps Copier to render a chosen template with recipe + hardware + answers vars.

Built-in templates live in `perfectrag.templates.<name>`. Third-party templates may
be published as separate pip packages and registered via entry_points:

    [project.entry-points."perfectrag.templates"]
    my-template = "my_pkg.my_template:provide"

where `provide` is a callable returning a dict: `{"path": Path, "description": str}`.
"""

from __future__ import annotations

from importlib.metadata import entry_points
from importlib.resources import files
from pathlib import Path

import copier

from perfectrag.hardware import HardwareProfile
from perfectrag.recipes import Answers, Recipe

TEMPLATES_PKG = "perfectrag.templates"
ENTRY_POINT_GROUP = "perfectrag.templates"

_BUILTIN_DESCRIPTIONS = {
    "custom-naive-rag": "FastAPI + Qdrant + Ollama + open-webui — minimal DIY stack",
    "ragflow-stack":    "RAGFlow — hybrid search, deep doc parsing, agentic, MCP-ready",
    "lightrag-stack":   "LightRAG — GraphRAG với dual-level retrieval + WebUI",
    "dify-stack":       "Dify — visual workflow/agent builder với marketplace",
    "code-graph-rag":   "Code intelligence — Serena LSP + ast-grep MCP (+ Memgraph graph), cho Claude Code",
}


def _third_party_templates() -> dict[str, dict]:
    """Discover templates registered via pip entry points."""
    found: dict[str, dict] = {}
    try:
        eps = entry_points(group=ENTRY_POINT_GROUP)
    except TypeError:  # pragma: no cover — older Python
        eps = entry_points().get(ENTRY_POINT_GROUP, [])  # type: ignore[assignment]
    for ep in eps:
        try:
            provider = ep.load()
            info = provider() if callable(provider) else provider
            if isinstance(info, dict) and "path" in info:
                found[ep.name] = {
                    "path": Path(str(info["path"])),
                    "description": info.get("description", f"Third-party template '{ep.name}'"),
                }
        except Exception:  # skip broken plugins
            continue
    return found


def available_templates() -> dict[str, str]:
    root = files(TEMPLATES_PKG)
    out: dict[str, str] = {}
    for name, desc in _BUILTIN_DESCRIPTIONS.items():
        if root.joinpath(name).is_dir():
            out[name] = desc
    for name, info in _third_party_templates().items():
        # Third-party can't shadow built-in names (safer UX)
        if name not in out:
            out[name] = info["description"]
    return out


def template_path(template: str) -> Path:
    root = files(TEMPLATES_PKG)
    builtin = root.joinpath(template)
    if builtin.is_dir():
        return Path(str(builtin))
    third = _third_party_templates().get(template)
    if third is not None and third["path"].is_dir():
        return third["path"]
    raise ValueError(f"Template không tồn tại: {template}")


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
