"""`jw-finetune doctor` — health check of the local environment.

Verifies what's needed for each major function:
  * Python and uv versions
  * GPU backend (NVIDIA/Apple/AMD/none)
  * Unsloth / transformers / trl available
  * Ollama service reachable
  * JW Library backup or app installed
  * Workspace path writable

Returns a structured report and a rich-renderable table.
"""

from __future__ import annotations

import platform
import shutil
import socket
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class CheckResult:
    name: str
    status: str  # "ok" | "warn" | "fail" | "info"
    detail: str = ""


@dataclass
class DoctorReport:
    checks: list[CheckResult] = field(default_factory=list)

    def add(self, name: str, status: str, detail: str = "") -> None:
        self.checks.append(CheckResult(name=name, status=status, detail=detail))

    @property
    def ok(self) -> bool:
        return not any(c.status == "fail" for c in self.checks)


def _check_python_version() -> CheckResult:
    v = sys.version_info
    if v >= (3, 13):
        return CheckResult("python", "ok", f"{v.major}.{v.minor}.{v.micro}")
    return CheckResult("python", "warn", f"{v.major}.{v.minor} (3.13+ recommended)")


def _check_uv() -> CheckResult:
    if shutil.which("uv"):
        try:
            out = subprocess.run(["uv", "--version"], capture_output=True, text=True, timeout=2, check=False)
            return CheckResult("uv", "ok", out.stdout.strip() or "installed")
        except Exception as e:  # noqa: BLE001
            return CheckResult("uv", "warn", str(e))
    return CheckResult("uv", "warn", "not on PATH (you can still use pip)")


def _check_gpu() -> CheckResult:
    # NVIDIA
    try:
        import pynvml  # type: ignore[import-untyped]

        pynvml.nvmlInit()
        h = pynvml.nvmlDeviceGetHandleByIndex(0)
        name = pynvml.nvmlDeviceGetName(h)
        if isinstance(name, bytes):
            name = name.decode()
        mem = pynvml.nvmlDeviceGetMemoryInfo(h)
        gb = round(mem.total / (1024**3), 1)
        return CheckResult("gpu", "ok", f"NVIDIA {name} ({gb} GB)")
    except Exception:
        pass

    # Apple Silicon
    if platform.system() == "Darwin" and platform.machine() == "arm64":
        return CheckResult("gpu", "ok", f"Apple Silicon ({platform.processor()})")

    return CheckResult("gpu", "warn", "no NVIDIA / Apple Silicon detected (CPU only)")


def _check_module(name: str, label: str | None = None) -> CheckResult:
    label = label or name
    try:
        __import__(name)
        return CheckResult(label, "ok", "installed")
    except ImportError:
        return CheckResult(label, "info", "not installed (optional extra)")


def _check_ollama() -> CheckResult:
    # Quick TCP probe on default port; full HTTP probe is heavier.
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(0.4)
    try:
        sock.connect(("127.0.0.1", 11434))
        sock.close()
        return CheckResult("ollama", "ok", "reachable on :11434")
    except OSError:
        return CheckResult("ollama", "info", "not running (run `ollama serve` to enable)")
    finally:
        sock.close()


def _check_jw_library() -> CheckResult:
    """Detect JW Library app on macOS via the toolkit's existing helper."""
    try:
        from jw_core.parsers import jw_library_backup  # noqa: F401
    except ImportError:
        return CheckResult("jw_library", "info", "parser not available")
    # macOS app bundle check
    if platform.system() == "Darwin":
        candidate = Path("/Applications/JW Library.app")
        if candidate.exists():
            return CheckResult("jw_library", "ok", "app installed (macOS)")
    # On any OS, check ~/Documents for .jwlibrary backups
    home_docs = Path.home() / "Documents"
    if home_docs.exists():
        backups = list(home_docs.glob("*.jwlibrary"))
        if backups:
            return CheckResult("jw_library", "ok", f"{len(backups)} backup file(s) in ~/Documents")
    return CheckResult("jw_library", "info", "no app / backups detected")


def _check_workspace_writable() -> CheckResult:
    ws = Path("./jw-finetune-workspace")
    try:
        ws.mkdir(parents=True, exist_ok=True)
        test = ws / ".doctor-write-test"
        test.write_text("ok", encoding="utf-8")
        test.unlink()
        return CheckResult("workspace", "ok", str(ws.resolve()))
    except OSError as e:
        return CheckResult("workspace", "fail", f"cannot write to {ws}: {e}")


def run_doctor() -> DoctorReport:
    """Run all health checks and return the report."""
    report = DoctorReport()
    report.checks.append(_check_python_version())
    report.checks.append(_check_uv())
    report.checks.append(_check_gpu())
    report.checks.append(_check_module("unsloth"))
    report.checks.append(_check_module("transformers"))
    report.checks.append(_check_module("trl"))
    report.checks.append(_check_module("anthropic"))
    report.checks.append(_check_module("ollama", label="ollama-sdk"))
    report.checks.append(_check_module("fastapi"))
    report.checks.append(_check_module("textual"))
    report.checks.append(_check_ollama())
    report.checks.append(_check_jw_library())
    report.checks.append(_check_workspace_writable())
    return report


def render_report(report: DoctorReport) -> str:
    """Format the report as a text table for printing."""
    icons = {"ok": "✓", "warn": "⚠", "fail": "✗", "info": "·"}
    lines = ["jw-finetune doctor", "==================="]
    for c in report.checks:
        icon = icons.get(c.status, "?")
        lines.append(f"  {icon} {c.name:<14} {c.status:<5} {c.detail}")
    lines.append("")
    lines.append("OK" if report.ok else "FAIL — see above")
    return "\n".join(lines)
