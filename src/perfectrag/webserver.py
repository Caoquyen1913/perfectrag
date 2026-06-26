"""FastAPI backend the Next.js UI (`perfectrag-ui`) calls via REST.

Endpoints intentionally mirror CLI capabilities so the UI is a browser-side CLI:
- GET  /api/hw                    → detected hardware profile
- GET  /api/templates             → built-in + entry-point templates
- GET  /api/addons                → addon registry
- GET  /api/mcp                   → MCP registry
- POST /api/recommend             → recipe preview from answers
- POST /api/scaffold              → scaffold project on disk
- POST /api/up                    → docker compose up (background task)
- POST /api/down                  → docker compose down
- GET  /api/doctor                → diagnose a project dir
- GET  /api/ps                    → running services
- GET  /api/logs/{service}        → stream logs (chunked response)

Start via `perfectrag web` or `uvicorn perfectrag.webserver:app --port 7777`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from perfectrag import (
    addons,
    deployer,
    doctor,
    hardware,
    mcp_registry,
    orchestrate,
    recipes,
    scaffolder,
)
from perfectrag.skills import list_bundled_skills

app = FastAPI(title="perfectRAG backend", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3001", "http://localhost:3000", "*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/hw")
def hw() -> dict:
    return hardware.detect().as_dict() | {"tier": hardware.detect().tier}


@app.get("/api/templates")
def templates() -> dict:
    return scaffolder.available_templates()


@app.get("/api/addons")
def addons_list() -> list[dict]:
    return [
        {
            "name": s.name,
            "description": s.description,
            "compose_file": s.compose_file,
            "dashboard_url": s.dashboard_url,
            "env_prompts": list(s.env_prompts),
            "post_up_notes": s.post_up_notes,
        }
        for s in addons.REGISTRY.values()
    ]


@app.get("/api/mcp")
def mcp_list() -> dict:
    return mcp_registry.REGISTRY


@app.get("/api/skills")
def skills_list() -> dict:
    return list_bundled_skills()


class RecommendReq(BaseModel):
    use_case: str
    modality: list[str] = ["text"]
    privacy: str = "fully_local"
    multi_hop: bool = False
    corpus_size: str = "small"
    user_scale: str = "solo"
    latency: str = "standard"
    priority: str = "balanced"
    language: str = "english"
    freshness: str = "static"
    existing_infra: list[str] = []
    needs_citations: bool = False


@app.post("/api/recommend")
def recommend(req: RecommendReq) -> dict:
    hw = hardware.detect()
    answers = recipes.Answers(**req.model_dump())
    r = recipes.recommend(answers, hw)
    return {
        "recipe": {
            "template": r.template,
            "llm_model": r.llm_model,
            "llm_runtime": r.llm_runtime,
            "embedding_model": r.embedding_model,
            "reranker": r.reranker,
            "vector_db": r.vector_db,
            "doc_parser": r.doc_parser,
            "chunk_strategy": r.chunk_strategy,
            "chunk_size": r.chunk_size,
            "gpu_enabled": r.gpu_enabled,
            "vram_cap_gb": r.vram_cap_gb,
            "extras": r.extras,
        },
        "notes": r.notes,
        "hw_tier": hw.tier,
    }


class ScaffoldReq(BaseModel):
    project_dir: str
    answers: RecommendReq
    template_override: str | None = None
    addons: list[str] = []
    force: bool = False


@app.post("/api/scaffold")
def scaffold(req: ScaffoldReq) -> dict:
    project_dir = Path(req.project_dir).expanduser().resolve()
    hw = hardware.detect()
    answers = recipes.Answers(**req.answers.model_dump())
    recipe = recipes.recommend(answers, hw)
    if req.template_override:
        if req.template_override not in scaffolder.available_templates():
            raise HTTPException(400, f"Unknown template: {req.template_override}")
        recipe.template = req.template_override

    project_dir.mkdir(parents=True, exist_ok=True)
    scaffolder.render(recipe, hw, answers, project_dir, force=req.force)

    installed: list[str] = []
    if req.addons:
        template_vars = recipe.as_template_vars(hw, answers)
        template_vars["project_name"] = project_dir.name
        for a in req.addons:
            if a not in addons.REGISTRY:
                raise HTTPException(400, f"Unknown addon: {a}")
            addons.add_addon_to_project(a, project_dir, template_vars)
            installed.append(a)

    return {
        "project_dir": str(project_dir),
        "template": recipe.template,
        "addons_installed": installed,
    }


class ProjectReq(BaseModel):
    project_dir: str


@app.post("/api/up")
def api_up(req: ProjectReq, build: bool = False) -> dict:
    project_dir = Path(req.project_dir).expanduser()
    if not orchestrate.docker_available():
        raise HTTPException(500, "docker not on PATH")
    code = orchestrate.up(project_dir, detach=True, build=build)
    return {"exit_code": code}


@app.post("/api/down")
def api_down(req: ProjectReq, volumes: bool = False) -> dict:
    project_dir = Path(req.project_dir).expanduser()
    code = orchestrate.down(project_dir, volumes=volumes)
    return {"exit_code": code}


@app.get("/api/doctor")
def api_doctor(project_dir: str) -> dict:
    p = Path(project_dir).expanduser()
    rows = doctor.run_all(p)
    return {"checks": [{"name": r.name, "status": r.status, "detail": r.detail} for r in rows]}


@app.get("/api/ps")
def api_ps(project_dir: str) -> dict:
    return {"services": orchestrate.ps(Path(project_dir).expanduser())}


@app.get("/api/logs/{service}")
def api_logs(service: str, project_dir: str, tail: int = 200) -> StreamingResponse:
    """Stream recent logs as a chunked text response."""
    import shutil
    import subprocess

    p = Path(project_dir).expanduser()
    docker = shutil.which("docker") or shutil.which("docker.exe")
    if not docker:
        raise HTTPException(500, "docker not available")
    args = [docker, "compose", *addons.compose_args(p), "logs", f"--tail={tail}", service]

    def gen():
        proc = subprocess.Popen(args, cwd=p, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        assert proc.stdout is not None
        for line in proc.stdout:
            yield line
        proc.wait()

    return StreamingResponse(gen(), media_type="text/plain")


@app.get("/api/deploy/targets")
def deploy_targets(template: str) -> list[str]:
    return deployer.available_targets(template)


class DeployReq(BaseModel):
    project_dir: str
    target: str
    out_dir: str
    template: str | None = None


@app.post("/api/deploy")
def api_deploy(req: DeployReq) -> dict:
    p = Path(req.project_dir).expanduser()
    answers_file = p / ".copier-answers.yml"
    template_vars: dict[str, Any] = {"project_name": p.name}
    if answers_file.exists():
        import yaml as _y
        template_vars.update(_y.safe_load(answers_file.read_text()) or {})
    tmpl = req.template or (template_vars.get("recipe", {}) or {}).get("template", "custom-naive-rag")
    deployer.render(
        target=req.target,  # type: ignore[arg-type]
        template=tmpl,
        out_dir=Path(req.out_dir).expanduser(),
        template_vars=template_vars,
    )
    return {"out_dir": req.out_dir, "template": tmpl, "target": req.target}
