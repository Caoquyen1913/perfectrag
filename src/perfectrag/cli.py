"""perfectrag CLI — entrypoint wired via pyproject [project.scripts]."""

from __future__ import annotations

import sys
from pathlib import Path

import typer
import yaml
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from perfectrag import hardware, recipes, scaffolder, wizard
from perfectrag.mcp_registry import REGISTRY, add_mcp_to_project
from perfectrag.skills import add_skill_to_project, list_bundled_skills

# Force UTF-8 on Windows legacy consoles (cp1252 can't encode many non-ASCII chars)
for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError):
            pass

app = typer.Typer(
    help="perfectRAG - dynamic RAG framework scaffolder",
    no_args_is_help=True,
    add_completion=False,
)
console = Console(legacy_windows=False)


@app.command()
def init(
    project_dir: Path = typer.Argument(Path("./my-rag"), help="Thư mục project sẽ sinh"),
    answers_file: Path | None = typer.Option(
        None, "--answers-file", "-a",
        help="YAML chứa answers (bỏ qua wizard interactive, dùng cho CI/test)",
    ),
    template: str | None = typer.Option(
        None, "--template", "-t",
        help="Override template gợi ý (custom-naive-rag, ragflow-stack, lightrag-stack, dify-stack)",
    ),
    force: bool = typer.Option(False, "--force", help="Ghi đè nếu project_dir đã có"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview recipe, không scaffold"),
) -> None:
    """Chạy wizard → scaffold project RAG hoàn chỉnh."""
    hw = hardware.detect()
    _show_hardware(hw)

    if answers_file is not None:
        raw = yaml.safe_load(answers_file.read_text(encoding="utf-8"))
        answers = recipes.Answers(**raw)
    else:
        answers = wizard.run_wizard()

    recipe = recipes.recommend(answers, hw)
    if template is not None:
        if template not in scaffolder.available_templates():
            console.print(f"[red]Template '{template}' không tồn tại. Có sẵn: "
                          f"{', '.join(scaffolder.available_templates().keys())}[/red]")
            raise typer.Exit(1)
        recipe.template = template
        recipe.notes.append(f"Template được override bằng --template={template}")
    _show_recipe(recipe)

    if dry_run:
        console.print("[yellow]--dry-run, không scaffold.[/yellow]")
        raise typer.Exit(0)

    if project_dir.exists() and any(project_dir.iterdir()) and not force:
        console.print(f"[red]Thư mục {project_dir} đã tồn tại và không rỗng. Dùng --force để ghi đè.[/red]")
        raise typer.Exit(1)

    scaffolder.render(recipe, hw, answers, project_dir, force=force)
    console.print(
        Panel.fit(
            f"[green]Done![/green]\n\n"
            f"cd {project_dir}\n"
            f"docker compose up -d\n\n"
            f"Edit [cyan]mcp.yaml[/cyan] to add tools, [cyan]skills/[/cyan] to add skills.",
            title="Next steps",
        )
    )


@app.command("add")
def add_cmd(
    kind: str = typer.Argument(..., help="'mcp' hoặc 'skill'"),
    name: str = typer.Argument(..., help="Tên MCP server / skill"),
    project_dir: Path = typer.Option(Path("."), "--project", "-p", help="Project dir"),
) -> None:
    """Add MCP server hoặc skill vào project đã sinh."""
    if kind == "mcp":
        add_mcp_to_project(name, project_dir)
        console.print(f"[green]Added MCP '{name}' vào {project_dir}/mcp.yaml[/green]")
    elif kind == "skill":
        add_skill_to_project(name, project_dir)
        console.print(f"[green]Added skill '{name}' vào {project_dir}/skills/[/green]")
    else:
        console.print(f"[red]Unknown kind: {kind}. Dùng 'mcp' hoặc 'skill'.[/red]")
        raise typer.Exit(1)


@app.command("list")
def list_cmd(
    what: str = typer.Argument(..., help="'templates', 'mcp', 'skills'"),
) -> None:
    """Liệt kê templates / MCP servers / skills có sẵn."""
    if what == "templates":
        _list_templates()
    elif what == "mcp":
        _list_mcp()
    elif what == "skills":
        _list_skills()
    else:
        console.print(f"[red]Unknown: {what}. Dùng 'templates', 'mcp' hoặc 'skills'.[/red]")
        raise typer.Exit(1)


@app.command()
def hw() -> None:
    """Chỉ detect + show hardware, không làm gì khác."""
    _show_hardware(hardware.detect())


# --- helpers ---

def _show_hardware(hw: hardware.HardwareProfile) -> None:
    table = Table(title="Detected hardware", show_header=False)
    table.add_column("Field", style="cyan")
    table.add_column("Value")
    table.add_row("OS / arch", f"{hw.os} ({hw.arch})")
    table.add_row("CPU", f"{hw.cpu_model} — {hw.cpu_cores} cores")
    table.add_row("RAM", f"{hw.ram_gb} GB")
    table.add_row("Disk free", f"{hw.disk_free_gb} GB")
    table.add_row("GPU", f"{hw.gpu_vendor} / {hw.gpu_name or '—'}")
    table.add_row("VRAM", f"{hw.vram_gb} GB")
    if hw.cuda_version:
        table.add_row("CUDA", hw.cuda_version)
    table.add_row("Tier", f"[bold]{hw.tier}[/bold]")
    console.print(table)


def _show_recipe(recipe: recipes.Recipe) -> None:
    table = Table(title=f"Recommended recipe → template: [bold]{recipe.template}[/bold]")
    table.add_column("Component", style="cyan")
    table.add_column("Choice")
    table.add_row("LLM", f"{recipe.llm_model} (via {recipe.llm_runtime})")
    table.add_row("Embedding", recipe.embedding_model)
    table.add_row("Reranker", recipe.reranker or "—")
    table.add_row("Vector DB", recipe.vector_db)
    table.add_row("Doc parser", recipe.doc_parser)
    table.add_row("Chunk", f"{recipe.chunk_strategy} / {recipe.chunk_size} tokens")
    table.add_row("GPU enabled", "yes" if recipe.gpu_enabled else "no")
    table.add_row("VRAM cap", f"{recipe.vram_cap_gb} GB")
    for k, v in recipe.extras.items():
        table.add_row(f"extras.{k}", str(v))
    console.print(table)
    for note in recipe.notes:
        console.print(f"[yellow]![/yellow] {note}")


def _list_templates() -> None:
    from perfectrag.scaffolder import available_templates

    table = Table(title="Templates bundled")
    table.add_column("Name", style="cyan")
    table.add_column("Description")
    for name, desc in available_templates().items():
        table.add_row(name, desc)
    console.print(table)


def _list_mcp() -> None:
    table = Table(title="MCP registry")
    table.add_column("Name", style="cyan")
    table.add_column("Description")
    table.add_column("Requires env")
    for name, info in REGISTRY.items():
        table.add_row(name, info["description"], ", ".join(info.get("env", [])) or "—")
    console.print(table)


def _list_skills() -> None:
    table = Table(title="Bundled skills")
    table.add_column("Name", style="cyan")
    table.add_column("Description")
    for name, desc in list_bundled_skills().items():
        table.add_row(name, desc)
    console.print(table)


if __name__ == "__main__":
    app()
