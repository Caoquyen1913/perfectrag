"""Cross-platform hardware detection for recipe selection.

Detects CPU, RAM, disk, and GPU (NVIDIA / AMD ROCm / Apple Silicon / none) so the
recipe engine can pick an appropriate stack tier.
"""

from __future__ import annotations

import json
import platform
import shutil
import subprocess
from dataclasses import asdict, dataclass
from typing import Literal

import psutil

GpuVendor = Literal["nvidia", "amd", "apple", "none"]


@dataclass(frozen=True)
class HardwareProfile:
    os: str
    arch: str
    cpu_model: str
    cpu_cores: int
    ram_gb: int
    disk_free_gb: int
    gpu_vendor: GpuVendor
    gpu_name: str | None
    vram_gb: int
    cuda_version: str | None

    @property
    def tier(self) -> str:
        """Coarse tier used by the recipe engine."""
        if self.gpu_vendor == "none":
            return "cpu"
        if self.gpu_vendor == "apple":
            # Apple Silicon uses unified memory; treat RAM as VRAM budget.
            if self.ram_gb >= 24:
                return "apple-high"
            return "apple-low"
        if self.vram_gb >= 24:
            return "gpu-24gb"
        if self.vram_gb >= 12:
            return "gpu-12gb"
        if self.vram_gb >= 6:
            return "gpu-8gb"
        return "cpu"

    def as_dict(self) -> dict:
        return asdict(self)


def _run(cmd: list[str], timeout: int = 5) -> str | None:
    try:
        out = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, check=False
        )
        if out.returncode == 0:
            return out.stdout
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return None
    return None


def _detect_cpu_model() -> str:
    try:
        from cpuinfo import get_cpu_info

        return get_cpu_info().get("brand_raw", platform.processor() or "unknown")
    except Exception:
        return platform.processor() or "unknown"


def _detect_nvidia() -> tuple[str, int, str | None] | None:
    """Return (gpu_name, vram_gb, cuda_version) via NVML, else None."""
    try:
        import pynvml

        pynvml.nvmlInit()
        try:
            count = pynvml.nvmlDeviceGetCount()
            if count == 0:
                return None
            handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            name = pynvml.nvmlDeviceGetName(handle)
            if isinstance(name, bytes):
                name = name.decode()
            mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
            vram_gb = int(mem.total / (1024**3))
            try:
                cuda = pynvml.nvmlSystemGetCudaDriverVersion_v2()
                cuda_str = f"{cuda // 1000}.{(cuda % 1000) // 10}"
            except Exception:
                cuda_str = None
            return name, vram_gb, cuda_str
        finally:
            try:
                pynvml.nvmlShutdown()
            except Exception:
                pass
    except Exception:
        # Fallback: parse nvidia-smi
        smi = _run(["nvidia-smi", "--query-gpu=name,memory.total,driver_version",
                    "--format=csv,noheader,nounits"])
        if not smi:
            return None
        line = smi.strip().splitlines()[0]
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 2:
            return None
        name = parts[0]
        try:
            vram_mb = int(parts[1])
            vram_gb = vram_mb // 1024
        except ValueError:
            vram_gb = 0
        return name, vram_gb, None


def _detect_amd() -> tuple[str, int] | None:
    """Return (gpu_name, vram_gb) via rocm-smi, else None."""
    if not shutil.which("rocm-smi"):
        return None
    out = _run(["rocm-smi", "--showproductname", "--showmeminfo", "vram", "--json"])
    if not out:
        return None
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        return None
    for _card_key, info in data.items():
        if not isinstance(info, dict):
            continue
        name = info.get("Card series") or info.get("Card model") or "AMD GPU"
        vram_bytes_str = info.get("VRAM Total Memory (B)")
        try:
            vram_gb = int(vram_bytes_str) // (1024**3) if vram_bytes_str else 0
        except (TypeError, ValueError):
            vram_gb = 0
        return str(name), vram_gb
    return None


def _detect_apple() -> tuple[str, int] | None:
    """Return (chip_name, unified_memory_gb) on Apple Silicon macOS, else None."""
    if platform.system() != "Darwin":
        return None
    if platform.machine() not in ("arm64", "aarch64"):
        return None
    chip = _run(["sysctl", "-n", "machdep.cpu.brand_string"])
    mem = _run(["sysctl", "-n", "hw.memsize"])
    chip_name = (chip or "Apple Silicon").strip()
    try:
        ram_gb = int(mem.strip()) // (1024**3) if mem else 0
    except ValueError:
        ram_gb = 0
    return chip_name, ram_gb


def detect() -> HardwareProfile:
    """Detect the current machine's hardware profile."""
    os_name = platform.system()
    arch = platform.machine()
    cpu_cores = psutil.cpu_count(logical=False) or psutil.cpu_count() or 1
    ram_gb = int(psutil.virtual_memory().total / (1024**3))
    disk_free_gb = int(psutil.disk_usage(".").free / (1024**3))
    cpu_model = _detect_cpu_model()

    gpu_vendor: GpuVendor = "none"
    gpu_name: str | None = None
    vram_gb = 0
    cuda_version: str | None = None

    nv = _detect_nvidia()
    if nv is not None:
        gpu_vendor = "nvidia"
        gpu_name, vram_gb, cuda_version = nv
    else:
        amd = _detect_amd()
        if amd is not None:
            gpu_vendor = "amd"
            gpu_name, vram_gb = amd
        else:
            apple = _detect_apple()
            if apple is not None:
                gpu_vendor = "apple"
                gpu_name, vram_gb = apple  # unified memory

    return HardwareProfile(
        os=os_name,
        arch=arch,
        cpu_model=cpu_model,
        cpu_cores=cpu_cores,
        ram_gb=ram_gb,
        disk_free_gb=disk_free_gb,
        gpu_vendor=gpu_vendor,
        gpu_name=gpu_name,
        vram_gb=vram_gb,
        cuda_version=cuda_version,
    )
