"""Addon overlay system.

An addon is a docker-compose overlay + optional service code that layers on top of
a generated project. Users install addons via `perfectrag add addon <name>` or the
`--with eval,observability,...` flag on init. `perfectrag up` then composes
`docker compose -f docker-compose.yml -f compose.<addon>.yml ...`.

State of installed addons is persisted in `<project>/.perfectrag/addons.yml` so that
`up`, `down`, `doctor`, and `update` can reconstruct the compose chain.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from importlib.resources import files
from pathlib import Path

import yaml

ADDONS_PKG = "perfectrag.templates._shared.addons"
STATE_DIR = ".perfectrag"
STATE_FILE = "addons.yml"


@dataclass(frozen=True)
class AddonSpec:
    name: str
    description: str
    compose_file: str                # e.g. "compose.eval.yml"
    dashboard_url: str | None = None  # shown post-up
    requires: tuple[str, ...] = ()   # other addons this needs
    post_up_notes: str | None = None  # hints after `perfectrag up`
    env_prompts: tuple[str, ...] = field(default_factory=tuple)  # env vars user must supply


REGISTRY: dict[str, AddonSpec] = {
    "ingest-worker": AddonSpec(
        name="ingest-worker",
        description="Scheduled web-crawl ingester (Crawl4AI → chunk → embed → Qdrant/ES)",
        compose_file="compose.ingest.yml",
        post_up_notes="Edit ingest/config.yml to set URLs + schedule; restart to apply.",
    ),
    "eval": AddonSpec(
        name="eval",
        description="RAG quality eval (RAGAS default, DeepEval tier via --tier)",
        compose_file="compose.eval.yml",
        dashboard_url="http://localhost:8081",
        post_up_notes="Run `perfectrag eval --dataset fixtures/sample-qa.jsonl`.",
    ),
    "observability": AddonSpec(
        name="observability",
        description="LiteLLM gateway + Langfuse tracing + cost tracking",
        compose_file="compose.observability.yml",
        dashboard_url="http://localhost:3100",
        post_up_notes="Langfuse: http://localhost:3100 · LiteLLM admin: http://localhost:4000/ui",
    ),
    "context-eng": AddonSpec(
        name="context-eng",
        description="DSPy prompt optimization + LLMLingua compression + mem0 session memory",
        compose_file="compose.context-eng.yml",
        post_up_notes="Endpoints at http://localhost:8002 (optimize/compress/memory).",
    ),
    "notion-sync": AddonSpec(
        name="notion-sync",
        description="Pull docs from Notion into the vector store on a schedule",
        compose_file="compose.notion-sync.yml",
        env_prompts=("NOTION_API_KEY",),
    ),
    "gdrive-sync": AddonSpec(
        name="gdrive-sync",
        description="Pull docs from Google Drive on a schedule",
        compose_file="compose.gdrive-sync.yml",
        env_prompts=("GDRIVE_SERVICE_ACCOUNT_JSON",),
    ),
    "confluence-sync": AddonSpec(
        name="confluence-sync",
        description="Pull pages from Confluence on a schedule",
        compose_file="compose.confluence-sync.yml",
        env_prompts=("CONFLUENCE_URL", "CONFLUENCE_API_TOKEN"),
    ),
    "paperclip": AddonSpec(
        name="paperclip",
        description="Paperclip multi-agent orchestrator (RAG backbone wired as tool)",
        compose_file="compose.paperclip.yml",
        dashboard_url="http://localhost:8888",
        requires=(),  # works standalone; optional synergy with `observability`
        post_up_notes="Agents at http://localhost:8888. If observability enabled, LLM calls route via LiteLLM.",
        env_prompts=("PAPERCLIP_LLM_API_KEY",),
    ),
}


def _addon_src(name: str) -> Path:
    root = files(ADDONS_PKG).joinpath(name)
    if not root.is_dir():
        raise ValueError(f"Addon source not packaged: {name}")
    return Path(str(root))


def _state_path(project_dir: Path) -> Path:
    return project_dir / STATE_DIR / STATE_FILE


def load_state(project_dir: Path) -> dict:
    path = _state_path(project_dir)
    if not path.exists():
        return {"installed": []}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    data.setdefault("installed", [])
    return data


def save_state(project_dir: Path, state: dict) -> None:
    path = _state_path(project_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(state, sort_keys=False), encoding="utf-8")


def list_installed(project_dir: Path) -> list[str]:
    return list(load_state(project_dir).get("installed", []))


def add_addon_to_project(
    name: str,
    project_dir: Path,
    template_vars: dict | None = None,
) -> AddonSpec:
    """Copy addon files into project + update `.perfectrag/addons.yml`.

    `template_vars` is the same recipe/hw/answers namespace used by Copier for the
    base template; addon .jinja files get rendered with it.
    """
    if name not in REGISTRY:
        raise KeyError(f"Unknown addon '{name}'. See `perfectrag list addons`.")
    spec = REGISTRY[name]

    state = load_state(project_dir)
    for req in spec.requires:
        if req not in state["installed"]:
            raise ValueError(f"Addon '{name}' requires '{req}' — install it first.")

    src = _addon_src(name)
    _copy_addon_tree(src, project_dir, template_vars or {})

    if name not in state["installed"]:
        state["installed"].append(name)
        save_state(project_dir, state)
    return spec


def _copy_addon_tree(src: Path, project_dir: Path, template_vars: dict) -> None:
    """Recursively copy addon files, rendering .jinja files through Jinja2."""
    from jinja2 import Environment

    env = Environment(keep_trailing_newline=True, autoescape=False)

    for entry in src.rglob("*"):
        if entry.is_dir():
            continue
        rel = entry.relative_to(src)
        dst_name = str(rel)
        if dst_name.endswith(".jinja"):
            rendered_name = dst_name[: -len(".jinja")]
            dst = project_dir / rendered_name
            dst.parent.mkdir(parents=True, exist_ok=True)
            template = env.from_string(entry.read_text(encoding="utf-8"))
            dst.write_text(template.render(**template_vars), encoding="utf-8")
        else:
            dst = project_dir / dst_name
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(entry.read_bytes())


def compose_args(project_dir: Path) -> list[str]:
    """Build `-f compose.yml -f compose.<addon>.yml ...` args for `docker compose`."""
    args = ["-f", "docker-compose.yml"]
    for name in list_installed(project_dir):
        spec = REGISTRY.get(name)
        if spec is None:
            continue
        compose_file = project_dir / spec.compose_file
        if compose_file.exists():
            args.extend(["-f", spec.compose_file])
    return args
