"""Unit tests for hardware detection (all subprocess calls mocked)."""

from __future__ import annotations

import pytest

from perfectrag import hardware


def test_tier_cpu_only():
    hw = hardware.HardwareProfile(
        os="Linux", arch="x86_64", cpu_model="Intel Xeon", cpu_cores=8,
        ram_gb=16, disk_free_gb=200,
        gpu_vendor="none", gpu_name=None, vram_gb=0, cuda_version=None,
    )
    assert hw.tier == "cpu"


@pytest.mark.parametrize("vram,expected", [
    (4, "cpu"),        # insufficient GPU VRAM → fall through
    (8, "gpu-8gb"),
    (12, "gpu-12gb"),
    (16, "gpu-12gb"),
    (24, "gpu-24gb"),
    (48, "gpu-24gb"),
])
def test_tier_nvidia(vram, expected):
    hw = hardware.HardwareProfile(
        os="Linux", arch="x86_64", cpu_model="x", cpu_cores=8,
        ram_gb=32, disk_free_gb=500,
        gpu_vendor="nvidia", gpu_name="RTX", vram_gb=vram, cuda_version="12.4",
    )
    assert hw.tier == expected


@pytest.mark.parametrize("ram,expected", [
    (8, "apple-low"),
    (16, "apple-low"),
    (24, "apple-high"),
    (64, "apple-high"),
])
def test_tier_apple(ram, expected):
    hw = hardware.HardwareProfile(
        os="Darwin", arch="arm64", cpu_model="Apple M2", cpu_cores=8,
        ram_gb=ram, disk_free_gb=500,
        gpu_vendor="apple", gpu_name="Apple M2", vram_gb=ram, cuda_version=None,
    )
    assert hw.tier == expected


def test_detect_returns_profile(mocker):
    """Smoke: detect() runs without raising on this host."""
    # Force no-GPU path so detect() works reproducibly on CI
    mocker.patch("perfectrag.hardware._detect_nvidia", return_value=None)
    mocker.patch("perfectrag.hardware._detect_amd", return_value=None)
    mocker.patch("perfectrag.hardware._detect_apple", return_value=None)
    hw = hardware.detect()
    assert hw.cpu_cores >= 1
    assert hw.ram_gb > 0
    assert hw.gpu_vendor == "none"
    assert hw.tier == "cpu"


def test_detect_nvidia_path(mocker):
    mocker.patch("perfectrag.hardware._detect_nvidia",
                 return_value=("RTX 4090", 24, "12.4"))
    hw = hardware.detect()
    assert hw.gpu_vendor == "nvidia"
    assert hw.vram_gb == 24
    assert hw.cuda_version == "12.4"
    assert hw.tier == "gpu-24gb"


def test_detect_nvidia_fallback_nvidia_smi(mocker):
    """When pynvml unavailable, parse nvidia-smi output."""
    mocker.patch("pynvml.nvmlInit", side_effect=ImportError)
    mocker.patch("perfectrag.hardware._run",
                 return_value="NVIDIA GeForce RTX 4070, 12282, 550.67\n")
    result = hardware._detect_nvidia()
    assert result is not None
    name, vram_gb, _ = result
    assert "RTX 4070" in name
    assert vram_gb == 11  # 12282 MiB / 1024 = 11
