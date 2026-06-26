"""Thin wrapper around `docker compose` that honors installed addons.

Builds the `-f compose.yml -f compose.<addon>.yml ...` chain from
`.perfectrag/addons.yml` so `up`, `down`, `logs`, `ps` operate on the full stack.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import time
from pathlib import Path

from perfectrag.addons import compose_args


class DockerNotFoundError(RuntimeError):
    """Raised when `docker` is not on PATH."""


def _docker_exe() -> str:
    exe = shutil.which("docker") or shutil.which("docker.exe")
    if exe is None:
        raise DockerNotFoundError(
            "docker not found on PATH. Install Docker Desktop or Docker Engine."
        )
    return exe


def _run_compose(project_dir: Path, *args: str, capture: bool = False) -> subprocess.CompletedProcess:
    cmd = [_docker_exe(), "compose", *compose_args(project_dir), *args]
    return subprocess.run(
        cmd,
        cwd=project_dir,
        capture_output=capture,
        text=True,
        check=False,
    )


def up(project_dir: Path, detach: bool = True, build: bool = False) -> int:
    args = ["up"]
    if detach:
        args.append("-d")
    if build:
        args.append("--build")
    return _run_compose(project_dir, *args).returncode


def down(project_dir: Path, volumes: bool = False) -> int:
    args = ["down"]
    if volumes:
        args.append("-v")
    return _run_compose(project_dir, *args).returncode


def logs(project_dir: Path, service: str | None = None, follow: bool = False, tail: int = 100) -> int:
    args = ["logs", f"--tail={tail}"]
    if follow:
        args.append("-f")
    if service:
        args.append(service)
    return _run_compose(project_dir, *args).returncode


def ps(project_dir: Path) -> list[dict]:
    """Return parsed `docker compose ps --format json` rows."""
    result = _run_compose(project_dir, "ps", "--format", "json", capture=True)
    if result.returncode != 0:
        return []
    rows: list[dict] = []
    # Newer docker compose emits one JSON object per line
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            parsed = json.loads(line)
            if isinstance(parsed, list):
                rows.extend(parsed)
            else:
                rows.append(parsed)
        except json.JSONDecodeError:
            continue
    return rows


def wait_healthy(project_dir: Path, timeout: int = 300, poll_interval: int = 3) -> tuple[bool, list[dict]]:
    """Poll until every service with a healthcheck is healthy, or timeout.

    Returns (all_healthy, last_ps_rows). Services without healthchecks only need
    to be in state "running".
    """
    deadline = time.time() + timeout
    last: list[dict] = []
    while time.time() < deadline:
        last = ps(project_dir)
        if not last:
            time.sleep(poll_interval)
            continue
        all_ok = True
        for svc in last:
            health = svc.get("Health", "").lower()
            state = svc.get("State", "").lower()
            if health:
                if health != "healthy":
                    all_ok = False
                    break
            elif state not in ("running", "exited"):
                all_ok = False
                break
        if all_ok:
            return True, last
        time.sleep(poll_interval)
    return False, last


def docker_available() -> bool:
    try:
        _docker_exe()
        return True
    except DockerNotFoundError:
        return False
