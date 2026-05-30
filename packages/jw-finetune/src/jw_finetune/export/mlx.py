"""MLX export (Apple Silicon) via `mlx_lm.convert` subprocess.

We call the `mlx_lm.convert` CLI rather than its Python API because the
Python API moves around between mlx-lm versions and the CLI is stable.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


def export_mlx(
    checkpoint_dir: Path,
    output_dir: Path,
    *,
    quant: str | None = "q4",  # "q4" → 4-bit; "q8" → 8-bit; None → fp16
) -> Path:
    """Convert HF checkpoint to MLX format. Returns `output_dir`."""
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    if output_dir.exists():
        shutil.rmtree(output_dir)

    cmd = [
        sys.executable, "-m", "mlx_lm.convert",
        "--hf-path", str(checkpoint_dir),
        "--mlx-path", str(output_dir),
    ]
    if quant:
        bits = "4" if quant.lower().startswith("q4") else "8"
        cmd += ["--quantize", "--q-bits", bits]

    logger.info("Running: %s", " ".join(cmd))
    subprocess.run(cmd, check=True)
    return output_dir
