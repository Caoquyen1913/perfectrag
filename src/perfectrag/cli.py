"""perfectrag CLI — entrypoint wired via pyproject [project.scripts]."""

from __future__ import annotations

import sys
from pathlib import Path

import typer
import yaml
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from perfectrag import deployer, hardware, orchestrate, recipes, scaffolder, wizard
from perfectrag import doctor as _doctor
from perfectrag.addons import REGISTRY as ADDON_REGISTRY
from perfectrag.addons import add_addon_to_project, list_installed
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
    with_addons: str | None = typer.Option(
        None, "--with", "-w",
        help="Danh sách addons comma-separated: eval,observability,context-eng,ingest-worker,paperclip",
    ),
    advise_flag: bool = typer.Option(
        False, "--advise/--no-advise",
        help="Dùng Gemini để refine recipe (cần `perfectrag add key gemini`)",
    ),
    description: str | None = typer.Option(
        None, "--describe", help="Mô tả use-case bằng text (gợi ý: dùng chung với --advise)",
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
    elif answers_file is None:
        # Interactive cold-start: show the scored comparison + let the user re-choose.
        _show_ranking(answers, hw)
        if not dry_run:
            chosen = _choose_template_interactive(recipe.template)
            if chosen and chosen != recipe.template:
                recipe.template = chosen
                recipe.notes.append(f"Bạn chọn lại template: {chosen}")

    # Optional Gemini refinement
    if advise_flag:
        from perfectrag import advisor as _advisor
        desc = description or (
            f"use_case={answers.use_case}, modality={answers.modality}, "
            f"corpus_size={answers.corpus_size}, user_scale={answers.user_scale}, "
            f"multi_hop={answers.multi_hop}, privacy={answers.privacy}"
        )
        advice = _advisor.advise(desc, hw, recipe)
        if advice.used_provider:
            console.print(Panel.fit(advice.reasoning, title="Gemini advisor"))
            recipe = advice.recipe
        else:
            console.print(f"[yellow]Advisor skipped: {advice.reasoning}[/yellow]")

    _show_recipe(recipe)

    if dry_run:
        console.print("[yellow]--dry-run, không scaffold.[/yellow]")
        raise typer.Exit(0)

    if project_dir.exists() and any(project_dir.iterdir()) and not force:
        console.print(f"[red]Thư mục {project_dir} đã tồn tại và không rỗng. Dùng --force để ghi đè.[/red]")
        raise typer.Exit(1)

    scaffolder.render(recipe, hw, answers, project_dir, force=force)

    installed_addons: list[str] = []
    if with_addons:
        template_vars = recipe.as_template_vars(hw, answers)
        template_vars["project_name"] = project_dir.name
        for addon_name in (a.strip() for a in with_addons.split(",") if a.strip()):
            if addon_name not in ADDON_REGISTRY:
                console.print(f"[red]Unknown addon '{addon_name}'. See `perfectrag list addons`.[/red]")
                raise typer.Exit(1)
            add_addon_to_project(addon_name, project_dir, template_vars)
            installed_addons.append(addon_name)
            console.print(f"[green]Installed addon '{addon_name}'[/green]")

    addons_hint = (f"\nAddons: {', '.join(installed_addons)}" if installed_addons else "")
    console.print(
        Panel.fit(
            f"[green]Done![/green]\n\n"
            f"cd {project_dir}\n"
            f"perfectrag up              # or: docker compose up -d\n\n"
            f"Edit [cyan]mcp.yaml[/cyan] to add tools, [cyan]skills/[/cyan] to add skills."
            f"{addons_hint}",
            title="Next steps",
        )
    )


@app.command("add")
def add_cmd(
    kind: str = typer.Argument(..., help="'mcp', 'skill', 'addon', hoặc 'key'"),
    name: str = typer.Argument(..., help="Tên MCP server / skill / addon / provider"),
    value: str | None = typer.Argument(None, help="API key value (khi kind=key)"),
    project_dir: Path = typer.Option(Path("."), "--project", "-p", help="Project dir"),
) -> None:
    """Add MCP server, skill, addon, hoặc API key vào perfectrag."""
    from perfectrag import keys as _keys
    if kind == "mcp":
        add_mcp_to_project(name, project_dir)
        console.print(f"[green]Added MCP '{name}' vào {project_dir}/mcp.yaml[/green]")
    elif kind == "skill":
        add_skill_to_project(name, project_dir)
        console.print(f"[green]Added skill '{name}' vào {project_dir}/skills/[/green]")
    elif kind == "addon":
        template_vars = _restore_template_vars(project_dir)
        spec = add_addon_to_project(name, project_dir, template_vars)
        console.print(f"[green]Installed addon '{spec.name}': {spec.description}[/green]")
        if spec.env_prompts:
            console.print(
                f"[yellow]Addon requires env vars: {', '.join(spec.env_prompts)}. "
                f"Set them in [cyan].env[/cyan] before `perfectrag up`.[/yellow]"
            )
        if spec.post_up_notes:
            console.print(f"[dim]{spec.post_up_notes}[/dim]")
    elif kind == "key":
        if not value:
            console.print("[red]Provide the key value: `perfectrag add key gemini AIzaSy...`[/red]")
            raise typer.Exit(1)
        _keys.set_key(name, value)
        console.print(f"[green]Saved {name} key to ~/.perfectrag/keys.yml (chmod 600).[/green]")
    else:
        console.print(f"[red]Unknown kind: {kind}. Dùng 'mcp', 'skill', 'addon', 'key'.[/red]")
        raise typer.Exit(1)


@app.command("remove")
def remove_cmd(
    kind: str = typer.Argument(..., help="'key' (mcp/skill/addon removal not yet supported)"),
    name: str = typer.Argument(...),
) -> None:
    """Remove an API key."""
    if kind == "key":
        from perfectrag import keys as _keys
        removed = _keys.remove_key(name)
        if removed:
            console.print(f"[green]Removed {name} key.[/green]")
        else:
            console.print(f"[yellow]No key stored for {name}.[/yellow]")
    else:
        console.print("[red]Only 'key' supported currently.[/red]")
        raise typer.Exit(1)


def _restore_template_vars(project_dir: Path) -> dict:
    """Rebuild recipe/hw/answers namespace for addon rendering in a post-scaffold project."""
    answers_file = project_dir / ".copier-answers.yml"
    template_vars: dict = {"project_name": project_dir.name}
    if answers_file.exists():
        data = yaml.safe_load(answers_file.read_text(encoding="utf-8")) or {}
        # Copier stores all `data` keys flat; we passed recipe/hw/answers as nested dicts
        template_vars.update(data)
    if "hw" not in template_vars:
        template_vars["hw"] = hardware.detect().as_dict()
    return template_vars


@app.command("list")
def list_cmd(
    what: str = typer.Argument(..., help="'templates', 'mcp', 'skills', 'addons', 'installed', 'keys'"),
    project_dir: Path = typer.Option(Path("."), "--project", "-p", help="Project dir (for 'installed')"),
) -> None:
    """Liệt kê templates / MCP / skills / addons / keys có sẵn."""
    if what == "templates":
        _list_templates()
    elif what == "mcp":
        _list_mcp()
    elif what == "skills":
        _list_skills()
    elif what == "addons":
        _list_addons()
    elif what == "installed":
        _list_installed(project_dir)
    elif what == "keys":
        _list_provider_keys()
    else:
        console.print(f"[red]Unknown: {what}. Dùng templates/mcp/skills/addons/installed/keys.[/red]")
        raise typer.Exit(1)


def _list_provider_keys() -> None:
    from perfectrag import keys as _keys
    table = Table(title="Provider API keys (~/.perfectrag/keys.yml)")
    table.add_column("Provider", style="cyan")
    table.add_column("Value")
    for prov, val in _keys.list_keys().items():
        table.add_row(prov, val or "[dim]not set[/dim]")
    console.print(table)


@app.command()
def hw() -> None:
    """Chỉ detect + show hardware, không làm gì khác."""
    _show_hardware(hardware.detect())


@app.command()
def up(
    project_dir: Path = typer.Option(Path("."), "--project", "-p"),
    build: bool = typer.Option(False, "--build", help="Rebuild images trước khi up"),
    wait: bool = typer.Option(True, "--wait/--no-wait", help="Chờ healthchecks pass"),
    timeout: int = typer.Option(300, "--timeout", help="Seconds chờ healthy"),
) -> None:
    """Start tất cả services (base + installed addons) và chờ healthy."""
    if not orchestrate.docker_available():
        console.print("[red]docker không có trên PATH. Cài Docker Desktop/Engine.[/red]")
        raise typer.Exit(1)
    console.print(f"[cyan]Starting services in {project_dir.resolve()}...[/cyan]")
    code = orchestrate.up(project_dir, detach=True, build=build)
    if code != 0:
        raise typer.Exit(code)
    if wait:
        console.print(f"[cyan]Waiting up to {timeout}s for services to become healthy...[/cyan]")
        healthy, rows = orchestrate.wait_healthy(project_dir, timeout=timeout)
        _render_ps_table(rows)
        if not healthy:
            console.print(f"[yellow]Some services did not become healthy in {timeout}s — see `perfectrag logs`.[/yellow]")
            raise typer.Exit(2)
    console.print("[green]All services up.[/green]")
    _show_dashboards(project_dir)


@app.command()
def down(
    project_dir: Path = typer.Option(Path("."), "--project", "-p"),
    volumes: bool = typer.Option(False, "-v", "--volumes", help="Xóa volumes"),
) -> None:
    """Stop và remove services (base + addons)."""
    raise typer.Exit(orchestrate.down(project_dir, volumes=volumes))


@app.command()
def logs(
    service: str | None = typer.Argument(None, help="Service name, hoặc bỏ trống để xem all"),
    project_dir: Path = typer.Option(Path("."), "--project", "-p"),
    follow: bool = typer.Option(False, "-f", "--follow"),
    tail: int = typer.Option(100, "--tail"),
) -> None:
    """Tail service logs."""
    raise typer.Exit(orchestrate.logs(project_dir, service=service, follow=follow, tail=tail))


key_app = typer.Typer(help="Manage RAG-access API keys (sk-rag-*) for a project's Query API.")
app.add_typer(key_app, name="key")


@key_app.command("issue")
def key_issue(
    name: str = typer.Option(..., "--name", "-n", help="Human label, e.g. 'production app'"),
    rate: int = typer.Option(60, "--rate", help="Requests/minute limit"),
    project_dir: Path = typer.Option(Path("."), "--project", "-p"),
) -> None:
    """Issue a new sk-rag-* key in the project's SQLite."""
    from perfectrag import api_keys
    k = api_keys.issue(project_dir, name, rate)
    console.print(Panel.fit(
        f"[green]Key issued (copy it — shown once):[/green]\n\n"
        f"[bold]{k.key}[/bold]\n\n"
        f"Name: {k.name}\nRate: {k.rate_per_minute}/min\nCreated: {k.created_at}\n\n"
        f"Use as: [cyan]Authorization: Bearer {k.key}[/cyan]",
        title="API key",
    ))


@key_app.command("list")
def key_list(
    project_dir: Path = typer.Option(Path("."), "--project", "-p"),
) -> None:
    """List all RAG-access keys (values masked)."""
    from perfectrag import api_keys
    keys_list = api_keys.list_all(project_dir)
    if not keys_list:
        console.print(f"[dim]No keys issued for {project_dir}.[/dim]")
        return
    table = Table(title=f"API keys ({project_dir}/.perfectrag/api_keys.db)")
    table.add_column("Masked key", style="cyan")
    table.add_column("Name")
    table.add_column("Rate/min")
    table.add_column("Status")
    table.add_column("Created")
    for k in keys_list:
        masked = f"sk-rag-…{k.key[-6:]}" if len(k.key) > 10 else k.key
        status = "[red]revoked[/red]" if k.revoked else "[green]active[/green]"
        table.add_row(masked, k.name, str(k.rate_per_minute), status, k.created_at)
    console.print(table)


@key_app.command("revoke")
def key_revoke(
    suffix: str = typer.Argument(..., help="Last chars of key (matches any key ending with this)"),
    project_dir: Path = typer.Option(Path("."), "--project", "-p"),
) -> None:
    """Revoke a key by its trailing characters."""
    from perfectrag import api_keys
    rows = api_keys.list_all(project_dir)
    matches = [k for k in rows if k.key.endswith(suffix)]
    if not matches:
        console.print(f"[red]No key ending with '{suffix}' found.[/red]")
        raise typer.Exit(1)
    for k in matches:
        api_keys.revoke(project_dir, k.key)
        console.print(f"[green]Revoked key …{k.key[-6:]} ({k.name})[/green]")


@key_app.command("usage")
def key_usage(
    suffix: str = typer.Argument(...),
    project_dir: Path = typer.Option(Path("."), "--project", "-p"),
) -> None:
    """Show usage for a key."""
    from perfectrag import api_keys
    rows = api_keys.list_all(project_dir)
    matches = [k for k in rows if k.key.endswith(suffix)]
    if not matches:
        console.print(f"[red]No key ending with '{suffix}'[/red]")
        raise typer.Exit(1)
    summary = api_keys.usage_summary(project_dir, matches[0].key)
    t = Table(title=f"Usage for …{matches[0].key[-6:]}")
    t.add_column("Metric", style="cyan")
    t.add_column("Value")
    for k, v in summary.items():
        t.add_row(k, str(v))
    console.print(t)


@app.command()
def run(
    config: Path = typer.Option(Path("perfectrag.yml"), "--config", "-c"),
    ingest_path: Path | None = typer.Option(None, "--ingest", help="Ingest a file/dir then exit"),
    query_text: str | None = typer.Option(None, "--query", "-q"),
    serve: bool = typer.Option(False, "--serve", help="Start FastAPI query-API server"),
    port: int = typer.Option(8000, "--port"),
    host: str = typer.Option("127.0.0.1", "--host"),
) -> None:
    """Embedded library mode — no Docker. Ingest, query, or serve."""
    from perfectrag import RAG

    if not config.exists():
        console.print(f"[red]Config not found: {config}[/red]")
        raise typer.Exit(1)
    rag = RAG.from_config(config)

    if ingest_path is not None:
        n = rag.ingest(ingest_path)
        console.print(f"[green]Ingested {n} chunks from {ingest_path}[/green]")
    if query_text:
        result = rag.query(query_text)
        console.print(Panel.fit(result.answer, title="Answer"))
        for h in result.hits[:3]:
            console.print(f"[dim]· {h.chunk.source}  (score {h.score:.3f})[/dim]")
        return
    if serve:
        try:
            import uvicorn
        except ImportError:
            console.print("[red]uvicorn missing. `pip install 'perfectrag[web]'`[/red]")
            raise typer.Exit(1)
        import os
        os.environ["PERFECTRAG_CONFIG"] = str(config.resolve())
        uvicorn.run("perfectrag.query_api:app", host=host, port=port, log_level="info")
        return
    console.print("[yellow]Pass --ingest, --query, or --serve.[/yellow]")


@app.command()
def advise(
    description: str = typer.Argument(..., help="Free-form description of your RAG use-case"),
) -> None:
    """Ask Gemini to refine a rule-based recipe given a free-form description."""
    from perfectrag import advisor as _advisor

    hw = hardware.detect()
    base_answers = recipes.Answers(
        use_case="qa_docs", modality=["text"], privacy="fully_local",
        multi_hop=False, corpus_size="small", user_scale="solo",
    )
    base = recipes.recommend(base_answers, hw)
    advice = _advisor.advise(description, hw, base)

    console.print(Panel.fit(advice.reasoning,
                            title=f"Advisor ({advice.used_provider or 'rule-based fallback'})"))
    if advice.changes:
        t = Table(title="Changes")
        t.add_column("Field", style="cyan")
        t.add_column("From")
        t.add_column("To", style="green")
        for f, diff in advice.changes.items():
            t.add_row(f, str(diff.get("from")), str(diff.get("to")))
        console.print(t)
    _show_recipe(advice.recipe)
    _show_ranking(base_answers, hw)


@app.command()
def web(
    port: int = typer.Option(7777, "--port", help="Backend port"),
    open_browser: bool = typer.Option(True, "--open/--no-open"),
    host: str = typer.Option("127.0.0.1", "--host"),
) -> None:
    """Start FastAPI backend for the Next.js UI. Run `cd ui && pnpm dev` separately (port 3001)."""
    try:
        import uvicorn
    except ImportError:
        console.print("[red]uvicorn not installed. Install with `pip install 'perfectrag[web]'`.[/red]")
        raise typer.Exit(1)
    if open_browser:
        import webbrowser
        console.print("[cyan]UI: http://localhost:3001 (run `cd ui && pnpm dev` first)[/cyan]")
        console.print(f"[cyan]API: http://{host}:{port}/docs[/cyan]")
        webbrowser.open_new_tab("http://localhost:3001")
    uvicorn.run("perfectrag.webserver:app", host=host, port=port, log_level="info")


@app.command()
def deploy(
    target: str = typer.Argument(..., help="helm, flyio, hoặc railway"),
    project_dir: Path = typer.Option(Path("."), "--project", "-p"),
    out: Path = typer.Option(Path("./deploy-out"), "--out", "-o"),
    template: str | None = typer.Option(None, "--template", "-t",
                                        help="Override template (default: từ .copier-answers.yml)"),
) -> None:
    """Render deploy assets (Helm chart, fly.toml, railway.json) cho production."""
    template_vars = _restore_template_vars(project_dir)
    tmpl = template or (template_vars.get("recipe", {}) or {}).get("template", "custom-naive-rag")
    available = deployer.available_targets(tmpl)
    if target not in available:
        console.print(f"[red]No {target} assets for template '{tmpl}'. Available: {available}[/red]")
        raise typer.Exit(1)
    deployer.render(target=target, template=tmpl, out_dir=out, template_vars=template_vars)
    console.print(f"[green]Rendered {target} deploy assets for '{tmpl}' into {out.resolve()}[/green]")
    console.print(f"[dim]Next: review files, run `helm lint {out}` / `fly deploy` / `railway up`.[/dim]")


@app.command()
def eval(
    project_dir: Path = typer.Option(Path("."), "--project", "-p"),
    dataset: Path = typer.Option(
        Path("eval/datasets/sample-qa.jsonl"),
        "--dataset", "-d",
        help="JSONL dataset relative to project dir",
    ),
    tier: str = typer.Option("ragas", "--tier", help="ragas|deepeval"),
    retrieval: bool = typer.Option(
        False, "--retrieval",
        help="Offline retrieval metrics (recall@k/MRR/nDCG) via the embedded library — no Docker",
    ),
    k: int = typer.Option(5, "--k", help="top-k for retrieval metrics"),
    gate: bool = typer.Option(
        False, "--gate", help="Exit non-zero if recall@k<0.8 or MRR<0.7 (CI quality gate)",
    ),
) -> None:
    """Run RAG quality eval. Generation metrics via the `eval` addon (RAGAS/DeepEval),
    or offline retrieval metrics with --retrieval."""
    if retrieval:
        _eval_retrieval(project_dir, dataset, k, gate)
        return
    if "eval" not in list_installed(project_dir):
        console.print("[red]Eval addon not installed. Run `perfectrag add addon eval -p .`[/red]")
        raise typer.Exit(1)
    if not orchestrate.docker_available():
        console.print("[red]docker not on PATH.[/red]")
        raise typer.Exit(1)
    import shutil
    docker = shutil.which("docker") or shutil.which("docker.exe")
    import subprocess
    # Path inside container
    container_dataset = f"/app/datasets/{dataset.name}"
    cmd = [
        docker, "compose",
        "-f", "docker-compose.yml", "-f", "compose.eval.yml",
        "run", "--rm", "eval",
        "python", "runner.py", "--dataset", container_dataset, "--tier", tier,
    ]
    code = subprocess.run(cmd, cwd=project_dir).returncode
    raise typer.Exit(code)


@app.command()
def tune(
    docs: Path = typer.Option(..., "--docs", help="Corpus dir/file to ingest for tuning"),
    golden: Path = typer.Option(..., "--golden", "-g",
                                help='JSONL: {"question": "...", "relevant": ["doc.md"]}'),
    config: Path = typer.Option(Path("perfectrag.yml"), "--config", "-c"),
    k: int = typer.Option(5, "--k", help="top-k for metrics"),
    apply: bool = typer.Option(False, "--apply", help="Write the winning flags into the config"),
) -> None:
    """Measure retrieval techniques on YOUR corpus + golden questions, pick the best.

    "Measure, don't guess" — beats the wizard's rule-based defaults because it scores
    each technique on your actual data instead of assuming."""
    import json

    import yaml

    from perfectrag import tune as _tune

    if not config.exists():
        console.print(f"[red]No config at {config}[/red]")
        raise typer.Exit(1)
    if not docs.exists():
        console.print(f"[red]Docs not found: {docs}[/red]")
        raise typer.Exit(1)
    if not golden.exists():
        console.print(f"[red]Golden set not found: {golden}[/red]")
        console.print('[dim]JSONL lines: {"question": "...", "relevant": ["doc.md"]}[/dim]')
        raise typer.Exit(1)

    cfg = yaml.safe_load(config.read_text(encoding="utf-8")) or {}
    data = [json.loads(line) for line in golden.read_text(encoding="utf-8").splitlines() if line.strip()]
    console.print(f"[cyan]Tuning on {docs} with {len(data)} golden queries "
                  f"(reusing one embedder/LLM across configs)...[/cyan]")
    results = _tune.tune_from_config(cfg, docs, data, k=k)
    if not results:
        console.print("[red]No trials ran (check corpus/golden set).[/red]")
        raise typer.Exit(1)

    table = Table(title=f"Tune results — best first (k={k})")
    table.add_column("", style="dim")
    table.add_column("Config", style="cyan")
    table.add_column(f"recall@{k}")
    table.add_column("MRR")
    table.add_column(f"nDCG@{k}")
    table.add_column("LLM cost")
    cost_label = {0: "free", 1: "/query", 2: "/chunk"}
    for i, r in enumerate(results):
        m = r.metrics
        name = f"[bold green]{r.name}[/bold green] ✓" if i == 0 else r.name
        table.add_row(str(i + 1), name, f"{m.recall_at_k:.3f}", f"{m.mrr:.3f}",
                      f"{m.ndcg_at_k:.3f}", cost_label[r.cost])
    console.print(table)

    winner = results[0]
    flags = winner.config_flags or {}
    console.print(f"[green]Winner: {winner.name}[/green] → "
                  f"{flags if flags else 'baseline (no extra technique)'}")
    if apply:
        config.write_text(_tune.apply_flags(config.read_text(encoding="utf-8"), flags),
                          encoding="utf-8")
        console.print(f"[green]Applied to {config}.[/green]")
    else:
        console.print("[dim]Re-run with --apply to write these flags into the config.[/dim]")


@app.command()
def doctor(
    project_dir: Path = typer.Option(Path("."), "--project", "-p"),
) -> None:
    """Chẩn đoán project: Docker, ports, disk, services, Ollama models."""
    results = _doctor.run_all(project_dir)
    table = Table(title="perfectrag doctor", show_header=True)
    table.add_column("Check", style="cyan")
    table.add_column("Status")
    table.add_column("Detail")
    has_fail = False
    for r in results:
        color = {"ok": "green", "warn": "yellow", "fail": "red"}.get(r.status, "white")
        table.add_row(r.name, f"[{color}]{r.status.upper()}[/{color}]", r.detail)
        if r.status == "fail":
            has_fail = True
    console.print(table)
    raise typer.Exit(1 if has_fail else 0)


def _render_ps_table(rows: list[dict]) -> None:
    if not rows:
        return
    table = Table(title="Services")
    table.add_column("Name", style="cyan")
    table.add_column("State")
    table.add_column("Health")
    table.add_column("Ports")
    for r in rows:
        table.add_row(
            r.get("Name", "?"),
            r.get("State", ""),
            r.get("Health", "") or "—",
            r.get("Publishers", "") if isinstance(r.get("Publishers"), str) else "",
        )
    console.print(table)


def _show_dashboards(project_dir: Path) -> None:
    installed = list_installed(project_dir)
    urls = []
    for name in installed:
        spec = ADDON_REGISTRY.get(name)
        if spec and spec.dashboard_url:
            urls.append(f"• {name}: {spec.dashboard_url}")
    if urls:
        console.print(Panel.fit("\n".join(urls), title="Addon dashboards"))


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


def _eval_retrieval(project_dir: Path, dataset: Path, k: int, gate: bool) -> None:
    """Offline retrieval-quality eval against a golden JSONL set, no Docker."""
    import json

    from perfectrag.core.evaluation import evaluate_retrieval, passes_gate
    from perfectrag.core.rag import RAG

    cfg = project_dir / "perfectrag.yml"
    if not cfg.exists():
        console.print(f"[red]No perfectrag.yml at {project_dir} — this needs the embedded library.[/red]")
        raise typer.Exit(1)
    ds_path = project_dir / dataset
    if not ds_path.exists():
        console.print(f"[red]Dataset not found: {ds_path}[/red]")
        console.print('[dim]JSONL lines: {"question": "...", "relevant": ["source1", ...]}[/dim]')
        raise typer.Exit(1)

    data = [json.loads(line) for line in ds_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    rag = RAG.from_config(cfg)
    metrics = evaluate_retrieval(rag, data, k=k)

    table = Table(title=f"Retrieval metrics (k={k}, n={metrics.n})")
    table.add_column("Metric", style="cyan")
    table.add_column("Value")
    for name, val in metrics.as_dict().items():
        table.add_row(name, str(val))
    console.print(table)

    if gate:
        ok, failures = passes_gate(metrics, {"recall_at_k": 0.8, "mrr": 0.7})
        if ok:
            console.print("[green]Quality gate PASSED.[/green]")
        else:
            console.print(f"[red]Quality gate FAILED: {', '.join(failures)}[/red]")
            raise typer.Exit(1)


def _template_choices(default: str) -> list[tuple[str, str]]:
    """(value, label) pairs for the init template picker — recommended first."""
    from perfectrag.scaffolder import available_templates

    avail = available_templates()
    out = [(default, f"✓ Nhận gợi ý: {default} — {avail.get(default, '')}")]
    out += [(name, f"{name} — {desc}") for name, desc in avail.items() if name != default]
    return out


def _choose_template_interactive(default: str) -> str | None:
    """Ask the user to confirm the recommended template or pick another. Enter = accept."""
    from InquirerPy import inquirer
    from InquirerPy.base.control import Choice

    choices = [Choice(value, name=label) for value, label in _template_choices(default)]
    return inquirer.select(
        message="Chọn backbone (Enter = nhận gợi ý, ↑↓ để xem lựa chọn khác):",
        choices=choices, default=default,
    ).execute()


def _show_ranking(answers: recipes.Answers, hw: hardware.HardwareProfile) -> None:
    ranked = recipes.score_candidates(answers, hw)
    table = Table(title="Đánh giá template (xếp hạng theo fit)")
    table.add_column("#", style="dim")
    table.add_column("Template", style="cyan")
    table.add_column("Score")
    table.add_column("Vì sao")
    for i, c in enumerate(ranked, 1):
        name = f"[bold green]{c.template}[/bold green] ✓" if c.recommended else c.template
        table.add_row(str(i), name, str(c.score), "; ".join(c.reasons))
    console.print(table)


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


def _list_addons() -> None:
    table = Table(title="Addons available")
    table.add_column("Name", style="cyan")
    table.add_column("Description")
    table.add_column("Requires env")
    table.add_column("Dashboard")
    for name, spec in ADDON_REGISTRY.items():
        table.add_row(
            name,
            spec.description,
            ", ".join(spec.env_prompts) or "—",
            spec.dashboard_url or "—",
        )
    console.print(table)


def _list_installed(project_dir: Path) -> None:
    installed = list_installed(project_dir)
    if not installed:
        console.print(f"[dim]No addons installed in {project_dir}.[/dim]")
        return
    table = Table(title=f"Addons installed in {project_dir}")
    table.add_column("Name", style="cyan")
    table.add_column("Compose file")
    for name in installed:
        spec = ADDON_REGISTRY.get(name)
        table.add_row(name, spec.compose_file if spec else "—")
    console.print(table)


if __name__ == "__main__":
    app()
