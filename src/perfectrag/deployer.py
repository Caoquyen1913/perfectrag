"""Render cloud-deploy templates (Helm / Fly.io / Railway) into an output dir."""

from __future__ import annotations

from importlib.resources import files
from pathlib import Path
from typing import Literal

from jinja2 import Environment

DEPLOY_PKG = "perfectrag.deploy"
Target = Literal["helm", "flyio", "railway"]


def available_targets(template: str) -> list[str]:
    """Which deploy targets have assets for this template."""
    root = files(DEPLOY_PKG)
    out = []
    for t in ("helm", "flyio", "railway"):
        if root.joinpath(t).joinpath(template).is_dir():
            out.append(t)
    return out


def render(target: Target, template: str, out_dir: Path, template_vars: dict) -> None:
    src_root = files(DEPLOY_PKG).joinpath(target).joinpath(template)
    if not src_root.is_dir():
        raise ValueError(
            f"No {target} assets for template '{template}'. "
            f"Available: {available_targets(template)}"
        )
    env = Environment(keep_trailing_newline=True, autoescape=False)
    for entry in Path(str(src_root)).rglob("*"):
        if entry.is_dir():
            continue
        rel = entry.relative_to(Path(str(src_root)))
        dst_rel = str(rel)
        if dst_rel.endswith(".jinja"):
            dst_rel = dst_rel[: -len(".jinja")]
            content = env.from_string(entry.read_text(encoding="utf-8")).render(**template_vars)
            mode = "text"
        else:
            content = entry.read_bytes()
            mode = "binary"
        dst = out_dir / dst_rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if mode == "text":
            dst.write_text(content, encoding="utf-8")
        else:
            dst.write_bytes(content)
