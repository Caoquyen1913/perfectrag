"""Skills = markdown files describing domain-specific RAG behavior.

Mirrors Claude Code's skill format: `skills/<name>/SKILL.md` with YAML frontmatter
(`name`, `description`) + instructional body. Backbones (RAGFlow/Dify/LightRAG) can
mount the skills/ directory and surface skills as selectable prompts.
"""

from __future__ import annotations

from importlib.resources import files
from pathlib import Path

BUNDLED_SKILLS_PKG = "perfectrag.templates._shared.skills"


def list_bundled_skills() -> dict[str, str]:
    """Scan bundled skills dir → {name: description (from frontmatter)}."""
    try:
        root = files(BUNDLED_SKILLS_PKG)
    except ModuleNotFoundError:
        return {}
    out: dict[str, str] = {}
    for entry in root.iterdir():
        if not entry.is_dir():
            continue
        skill_md = entry.joinpath("SKILL.md")
        if not skill_md.is_file():
            continue
        out[entry.name] = _extract_description(skill_md.read_text(encoding="utf-8"))
    return out


def _extract_description(content: str) -> str:
    if not content.startswith("---"):
        return ""
    parts = content.split("---", 2)
    if len(parts) < 3:
        return ""
    for line in parts[1].splitlines():
        line = line.strip()
        if line.startswith("description:"):
            return line.split(":", 1)[1].strip().strip('"').strip("'")
    return ""


def add_skill_to_project(name: str, project_dir: Path) -> None:
    bundled = list_bundled_skills()
    if name not in bundled:
        raise KeyError(f"Không có bundled skill '{name}'. Chạy `perfectrag list skills`.")
    src_root = files(BUNDLED_SKILLS_PKG).joinpath(name)
    dst_root = project_dir / "skills" / name
    dst_root.mkdir(parents=True, exist_ok=True)
    for entry in src_root.iterdir():
        if entry.is_file():
            (dst_root / entry.name).write_text(entry.read_text(encoding="utf-8"), encoding="utf-8")
