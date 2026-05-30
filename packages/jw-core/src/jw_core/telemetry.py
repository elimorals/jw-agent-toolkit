"""Opt-in API drift detection.

When enabled, every API response gets fingerprinted (a hash of its
structural shape: keys, types, depth). The fingerprint is compared to a
baseline learned at first use and persisted to a small JSON file. If a
subsequent response's fingerprint differs, a `drift detected` event is
recorded — that's our canary for "JW.org changed its API shape and our
parsers may break".

Opt in via env var:

    JW_TELEMETRY_ENABLED=1
    JW_TELEMETRY_PATH=/path/to/telemetry.json   (optional; default ~/.jw-agent-toolkit/telemetry.json)

No data leaves the user's machine — fingerprints + drift events stay in
the local JSON file. Inspect with `Telemetry.report()`.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _shape_hash(obj: Any, depth: int = 0, max_depth: int = 6) -> str:
    """Hash the SHAPE of a JSON value, not its content.

    For a dict: hash of sorted (key, child_shape) tuples.
    For a list: hash of the shape of the first 3 elements + length.
    For a scalar: type name.

    Same shape, different values → same hash. New key → different hash.
    """
    if depth > max_depth:
        return "depth-cap"
    if isinstance(obj, dict):
        parts = sorted(
            f"{k}:{_shape_hash(v, depth + 1, max_depth)}"
            for k, v in obj.items()
        )
        h = hashlib.sha256("|".join(parts).encode()).hexdigest()[:16]
        return f"dict({len(obj)})[{h}]"
    if isinstance(obj, list):
        if not obj:
            return "list(0)"
        # Hash the shape of the first 3 elements as a sample.
        sample_hashes = [_shape_hash(o, depth + 1, max_depth) for o in obj[:3]]
        h = hashlib.sha256("|".join(sample_hashes).encode()).hexdigest()[:8]
        return f"list[{h}]"
    return type(obj).__name__


class Telemetry:
    """Disk-backed drift tracker. Disabled unless JW_TELEMETRY_ENABLED is set."""

    def __init__(self, path: Path | str | None = None) -> None:
        env_path = os.environ.get("JW_TELEMETRY_PATH")
        default = Path("~/.jw-agent-toolkit/telemetry.json").expanduser()
        self.path = Path(path or env_path or default)
        self.enabled = os.environ.get("JW_TELEMETRY_ENABLED", "").lower() in (
            "1", "true", "yes",
        )
        self._state: dict[str, Any] = {"baselines": {}, "drift_events": []}
        if self.enabled and self.path.exists():
            try:
                self._state = json.loads(self.path.read_text())
            except Exception as e:
                logger.warning(f"Failed to load telemetry state: {e}")

    def record(self, endpoint: str, response: Any) -> bool:
        """Compare `response` shape to the learned baseline for `endpoint`.

        Returns True if a drift was just observed (new shape vs baseline).
        First call for an endpoint learns the baseline and returns False.
        """
        if not self.enabled:
            return False
        shape = _shape_hash(response)
        baselines = self._state.setdefault("baselines", {})
        baseline = baselines.get(endpoint)
        drift = False
        if baseline is None:
            baselines[endpoint] = shape
        elif baseline != shape:
            drift = True
            self._state.setdefault("drift_events", []).append({
                "endpoint": endpoint,
                "expected": baseline,
                "got": shape,
                "ts": time.time(),
            })
            logger.warning(
                f"API drift detected on {endpoint}: shape changed "
                f"({baseline} → {shape})"
            )
        self._save()
        return drift

    def report(self) -> dict[str, Any]:
        """Return a summary of recorded baselines + drift events."""
        return {
            "enabled": self.enabled,
            "path": str(self.path),
            "baselines": dict(self._state.get("baselines", {})),
            "drift_events": list(self._state.get("drift_events", [])),
        }

    def _save(self) -> None:
        if not self.enabled:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self._state, indent=2))


_singleton: Telemetry | None = None


def get_telemetry() -> Telemetry:
    """Return a process-wide Telemetry instance (lazily constructed)."""
    global _singleton
    if _singleton is None:
        _singleton = Telemetry()
    return _singleton
