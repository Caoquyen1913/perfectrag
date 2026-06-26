"""Diagnostic checks for a generated project.

Run before or after `perfectrag up` to catch issues: Docker daemon, port conflicts,
disk space, Ollama models pulled, service health.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import psutil
import yaml

from perfectrag import orchestrate

OK = "ok"
WARN = "warn"
FAIL = "fail"


@dataclass
class CheckResult:
    name: str
    status: str  # "ok" | "warn" | "fail"
    detail: str


def run_all(project_dir: Path) -> list[CheckResult]:
    results: list[CheckResult] = []
    results.append(_check_project_dir(project_dir))
    if results[-1].status == FAIL:
        return results

    results.append(_check_docker())
    results.append(_check_ports(project_dir))
    results.append(_check_disk_space(project_dir))

    if orchestrate.docker_available():
        results.append(_check_services_running(project_dir))
        results.append(_check_ollama_models(project_dir))
    return results


def _check_project_dir(project_dir: Path) -> CheckResult:
    compose = project_dir / "docker-compose.yml"
    if not compose.exists():
        return CheckResult(
            "Project dir",
            FAIL,
            f"No docker-compose.yml at {project_dir}. Run `perfectrag init` first.",
        )
    return CheckResult("Project dir", OK, f"{project_dir.resolve()}")


def _check_docker() -> CheckResult:
    if not orchestrate.docker_available():
        return CheckResult("Docker", FAIL, "docker not found on PATH")
    exe = shutil.which("docker") or shutil.which("docker.exe")
    try:
        info = subprocess.run(
            [exe, "info", "--format", "{{.ServerVersion}}"],
            capture_output=True, text=True, timeout=5,
        )
        if info.returncode != 0:
            return CheckResult("Docker", FAIL, "daemon not reachable — start Docker Desktop/Engine")
        return CheckResult("Docker", OK, f"daemon v{info.stdout.strip()}")
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        return CheckResult("Docker", FAIL, str(e))


def _iter_ports(project_dir: Path) -> list[tuple[str, int]]:
    """Parse all compose files (base + installed addons) for published ports."""
    from perfectrag.addons import compose_args

    ports: list[tuple[str, int]] = []
    args = compose_args(project_dir)
    files = [project_dir / p for p in args if p.endswith(".yml")]
    for path in files:
        if not path.exists():
            continue
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            continue
        for svc_name, svc in (data.get("services") or {}).items():
            for entry in svc.get("ports", []) or []:
                port = _parse_host_port(entry)
                if port is not None:
                    ports.append((svc_name, port))
    return ports


def _parse_host_port(entry: object) -> int | None:
    if isinstance(entry, int):
        return entry
    if isinstance(entry, str):
        # "80:80" or "127.0.0.1:80:80" or "80"
        parts = entry.split(":")
        try:
            return int(parts[-2] if len(parts) >= 2 else parts[0])
        except ValueError:
            return None
    if isinstance(entry, dict):
        published = entry.get("published")
        if isinstance(published, int):
            return published
        if isinstance(published, str):
            try:
                return int(published)
            except ValueError:
                return None
    return None


def _check_ports(project_dir: Path) -> CheckResult:
    wanted = _iter_ports(project_dir)
    if not wanted:
        return CheckResult("Ports", OK, "no published ports in compose")

    try:
        in_use = {c.laddr.port for c in psutil.net_connections(kind="inet")
                  if c.status == psutil.CONN_LISTEN and c.laddr}
    except (psutil.AccessDenied, PermissionError):
        return CheckResult("Ports", WARN, "skipped (need elevated permissions to list listeners)")

    conflicts = [(svc, port) for svc, port in wanted if port in in_use]
    if conflicts:
        detail = ", ".join(f"{svc}→:{port}" for svc, port in conflicts)
        return CheckResult("Ports", WARN, f"already in use: {detail}")
    return CheckResult("Ports", OK, f"all {len(wanted)} ports free")


def _check_disk_space(project_dir: Path) -> CheckResult:
    free_gb = psutil.disk_usage(str(project_dir)).free // (1024**3)
    if free_gb < 10:
        return CheckResult("Disk", FAIL, f"only {free_gb} GB free — need ≥20 GB for models")
    if free_gb < 20:
        return CheckResult("Disk", WARN, f"{free_gb} GB free — tight if pulling large models")
    return CheckResult("Disk", OK, f"{free_gb} GB free")


def _check_services_running(project_dir: Path) -> CheckResult:
    rows = orchestrate.ps(project_dir)
    if not rows:
        return CheckResult("Services", WARN, "no services running — run `perfectrag up`")
    bad = [r for r in rows if r.get("State", "").lower() not in ("running", "exited")]
    if bad:
        names = ", ".join(r.get("Name", "?") for r in bad)
        return CheckResult("Services", FAIL, f"not running: {names}")
    unhealthy = [r for r in rows if r.get("Health", "").lower() not in ("", "healthy", "starting")]
    if unhealthy:
        names = ", ".join(f"{r.get('Name')}={r.get('Health')}" for r in unhealthy)
        return CheckResult("Services", WARN, f"unhealthy: {names}")
    return CheckResult("Services", OK, f"{len(rows)} services running")


def _check_ollama_models(project_dir: Path) -> CheckResult:
    """Check that the LLM model configured in .env is pulled in the Ollama container."""
    env_file = project_dir / ".env"
    if not env_file.exists():
        return CheckResult("Ollama", WARN, "no .env to read LLM_MODEL / DEFAULT_LLM from")

    model = None
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("LLM_MODEL=") or line.startswith("DEFAULT_LLM="):
            model = line.split("=", 1)[1].strip()
            break
    if not model:
        return CheckResult("Ollama", OK, "no LLM_MODEL in .env — skipping")

    exe = shutil.which("docker") or shutil.which("docker.exe")
    try:
        result = subprocess.run(
            [exe, "compose", "exec", "-T", "ollama", "ollama", "list"],
            cwd=project_dir, capture_output=True, text=True, timeout=10,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return CheckResult("Ollama", WARN, "container not reachable (maybe `up` not run yet)")
    if result.returncode != 0:
        return CheckResult("Ollama", WARN, "ollama container not running")
    if model.split(":")[0] not in result.stdout:
        return CheckResult(
            "Ollama", WARN,
            f"model {model} not pulled; ollama-pull service handles this on first up",
        )
    return CheckResult("Ollama", OK, f"model {model} available")
