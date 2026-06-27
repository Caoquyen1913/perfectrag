# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project purpose

`perfectrag` is a **meta-framework / scaffolder** — not a RAG service itself. It ships a CLI (`perfectrag`) that asks a few questions, detects hardware, and renders a complete project (docker-compose + `.env` + `mcp.yaml` + `skills/`) wrapping one of seven open-source RAG backbones. Users run `docker compose up` and get a working RAG service + UI without writing code.

When editing, keep this meta nature in mind: most "work" happens in the generated project, not here. This repo's job is to pick the right template and fill in the right variables.

## Commands

```bash
# setup
python -m venv .venv && .venv/Scripts/activate      # Windows
pip install -e ".[dev]"

# dev loop
pytest                                              # 146 tests
pytest tests/unit/test_recipes.py -v                # single file
pytest -k "graphrag"                                # single test by substring
ruff check src tests
mypy src

# smoke the CLI end-to-end
perfectrag hw
perfectrag list templates
perfectrag init /tmp/out --answers-file tests/fixtures/qa-cpu.yml --force
perfectrag init /tmp/out --template ragflow-stack --answers-file tests/fixtures/qa-cpu.yml --force

# release (see README for full publish flow)
rm -rf dist build && python -m build && twine check dist/*
```

`perfectrag` is already published on PyPI (`pip install perfectrag`). Version bump required in `pyproject.toml` before each re-publish — PyPI is immutable.

## Architecture

The CLI is a 5-stage pipeline, each stage a pure module in `src/perfectrag/`:

```
hardware.detect()        →  HardwareProfile (+ derived `tier`)
wizard.run_wizard()      →  Answers          (skipped if --answers-file)
recipes.recommend(...)   →  Recipe           (opinionated decision matrix)
scaffolder.render(...)   →  Copier renders templates/<recipe.template>/
```

**`hardware.py`** — cross-platform detection (psutil for CPU/RAM/disk, pynvml + `nvidia-smi` fallback for NVIDIA, `rocm-smi` for AMD, `sysctl` for Apple Silicon). `HardwareProfile.tier` bucketizes into `cpu` / `apple-low` / `apple-high` / `gpu-8gb` / `gpu-12gb` / `gpu-24gb` — this coarse tier drives recipe choices.

**`recipes.py`** — the decision matrix. `recommend(answers, hw)` is a pure function; modify it when adding new routing rules. Hard routing (priority order): `graphrag` or `multi_hop=True` → `lightrag-stack`; `agent_workflow` → `dify-stack`; `multimodal` → `ragflow-stack` with Docling; `qa_docs` on CPU → `custom-naive-rag`; everything else → `ragflow-stack`. LLM/embedding/reranker/vector-db are picked from tier tables at the top of the module.

**`scaffolder.py`** — thin wrapper around `copier.run_copy`. Template data is passed via `recipe.as_template_vars(hw, answers)` which produces three namespaces in Jinja: `{{ recipe.* }}`, `{{ hw.* }}`, `{{ answers.* }}`. Copier is chosen over Cookiecutter specifically to support `copier update` in generated projects.

**`templates/<name>/`** — each template is a self-contained Copier project with `copier.yml` (sets `_templates_suffix: .jinja`), `.jinja` files for everything that needs rendering, and a `skills/` dir mounted into containers. To add a new template: create the dir, register it in `scaffolder._DESCRIPTIONS`, and optionally update `_pick_template()` in `recipes.py` to auto-select it for some use-case. No other code touches template names, so adding a template is a 1-file change in `scaffolder.py` + the new dir.

**`mcp_registry.py`** — static dict of known MCP servers. `add_mcp_to_project()` splices an entry into the generated project's `mcp.yaml`. Format is portable with Claude Code / Cursor / Claude Desktop.

**`skills.py`** — bundled skill markdowns in `templates/_shared/skills/`. Format mirrors Claude Code skill format (YAML frontmatter + body). Mounted read-only into generated containers at backbone-specific paths.

## Things to know

- **Templates get double-included without the explicit `include`/`artifacts` config in `pyproject.toml`.** Hatchling picks up `templates/` both as package data and as force-include → duplicate warnings. The current config uses `[tool.hatch.build.targets.wheel].include + artifacts` to include template files exactly once. Verify with `python -c "import zipfile; print(zipfile.ZipFile('dist/*.whl').namelist())"` after any build config change.

- **Windows console is cp1252 by default, breaks Unicode in Rich tables.** `cli.py` reconfigures `sys.stdout`/`stderr` to UTF-8 at import time and uses `Console(legacy_windows=False)`. Don't remove either — tests on Windows will crash on Vietnamese strings in MCP descriptions.

- **Hardware is detected live on every `perfectrag init`**, so answer-file fixtures alone can't test a specific HW tier. For tests that need a specific template regardless of the test host, use `--template <name>` override (see `test_template_override_scaffolds_ragflow`). The recipe engine itself is tested with constructed `HardwareProfile` instances in `tests/unit/test_recipes.py`.

- **Generated projects reference upstream images (RAGFlow, LightRAG, Dify) at pinned versions** in each template's `docker-compose.yml.jinja`. Bumping these = check upstream breaking changes + update fixtures if compose shape changed.

- **Docker isn't available in this dev env** (no `docker.exe` on PATH). E2E scaffold tests validate compose files by parsing YAML with PyYAML, not by running `docker compose config`. If you add live-Docker tests, gate them behind an opt-in CLI flag / pytest marker.

- **The 7 templates target distinct use-cases**: `custom-naive-rag` (simplest, DIY FastAPI), `ragflow-stack` (production default), `lightrag-stack` (GraphRAG only), `dify-stack` (workflow/agent builder), `code-graph-rag` (code intelligence for Claude Code — auto-routed from `code_rag`), `r2r-stack` (all-in-one agentic, opt-in via `--template`), `onyx-stack` (enterprise connectors, opt-in). Don't let them converge — their reasons to exist are the routing rules in `recipes._pick_template`.
