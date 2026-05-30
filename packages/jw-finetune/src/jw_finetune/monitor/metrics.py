"""System metrics collectors — GPU/CPU/RAM/throughput.

All collectors gracefully degrade when their backend isn't available:
no NVIDIA driver, no Apple Silicon, no `psutil` — each returns
None/empty rather than raising. The dashboard renders whatever it gets.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
from dataclasses import asdict, dataclass

logger = logging.getLogger(__name__)


@dataclass
class SystemMetrics:
    cpu_percent: float | None = None
    ram_used_mb: float | None = None
    ram_total_mb: float | None = None
    gpu_name: str | None = None
    gpu_mem_used_mb: float | None = None
    gpu_mem_total_mb: float | None = None
    gpu_util_percent: float | None = None
    gpu_kind: str | None = None  # "nvidia" | "apple" | None

    def to_dict(self) -> dict:
        return asdict(self)


def _try_psutil() -> tuple[float | None, float | None, float | None]:
    """Returns (cpu_percent, ram_used_mb, ram_total_mb)."""
    try:
        import psutil  # type: ignore[import-untyped]
    except ImportError:
        return None, None, None
    try:
        cpu = float(psutil.cpu_percent(interval=None))
        mem = psutil.virtual_memory()
        return cpu, mem.used / (1024 * 1024), mem.total / (1024 * 1024)
    except Exception as e:  # noqa: BLE001
        logger.debug("psutil error: %s", e)
        return None, None, None


def _try_nvidia() -> dict | None:
    """Returns GPU dict if NVIDIA driver+pynvml are available, else None."""
    try:
        import pynvml  # type: ignore[import-untyped]
    except ImportError:
        return None
    try:
        pynvml.nvmlInit()
        h = pynvml.nvmlDeviceGetHandleByIndex(0)
        name_raw = pynvml.nvmlDeviceGetName(h)
        name = name_raw.decode() if isinstance(name_raw, bytes) else str(name_raw)
        mem = pynvml.nvmlDeviceGetMemoryInfo(h)
        util = pynvml.nvmlDeviceGetUtilizationRates(h)
        return {
            "gpu_name": name,
            "gpu_mem_used_mb": mem.used / (1024 * 1024),
            "gpu_mem_total_mb": mem.total / (1024 * 1024),
            "gpu_util_percent": float(util.gpu),
            "gpu_kind": "nvidia",
        }
    except Exception as e:  # noqa: BLE001
        logger.debug("nvml error: %s", e)
        return None


def _try_apple() -> dict | None:
    """Best-effort Apple Silicon metrics via `system_profiler` (no extra deps).

    We surface GPU name only; bytes-used is not freely queryable without
    private APIs. The dashboard shows "n/a" for the missing fields.
    """
    if not shutil.which("system_profiler"):
        return None
    try:
        out = subprocess.run(
            ["system_profiler", "SPDisplaysDataType"],
            capture_output=True, text=True, timeout=2, check=False,
        )
        for line in out.stdout.splitlines():
            line = line.strip()
            if line.startswith("Chipset Model:"):
                name = line.split(":", 1)[1].strip()
                return {
                    "gpu_name": name,
                    "gpu_mem_used_mb": None,
                    "gpu_mem_total_mb": None,
                    "gpu_util_percent": None,
                    "gpu_kind": "apple",
                }
    except Exception as e:  # noqa: BLE001
        logger.debug("system_profiler error: %s", e)
    return None


def collect() -> SystemMetrics:
    """Collect what we can; fields stay None if a backend isn't available."""
    cpu, used, total = _try_psutil()
    gpu = _try_nvidia() or _try_apple() or {}
    return SystemMetrics(
        cpu_percent=cpu,
        ram_used_mb=used,
        ram_total_mb=total,
        gpu_name=gpu.get("gpu_name"),
        gpu_mem_used_mb=gpu.get("gpu_mem_used_mb"),
        gpu_mem_total_mb=gpu.get("gpu_mem_total_mb"),
        gpu_util_percent=gpu.get("gpu_util_percent"),
        gpu_kind=gpu.get("gpu_kind"),
    )
