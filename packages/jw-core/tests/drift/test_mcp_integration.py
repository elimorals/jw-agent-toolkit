"""F72 MCP tool integration."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path


def _call(tool, **kwargs):
    fn = getattr(tool, "fn", tool)
    return asyncio.run(fn(**kwargs))


def test_mcp_drift_analyze_round_trip(tmp_path: Path) -> None:
    from jw_mcp.server import drift_analyze

    path = tmp_path / "chunks.jsonl"
    lines = [
        {"text": "x", "year": 1985, "embedding": [1.0, 0.0]},
        {"text": "y", "year": 1986, "embedding": [0.99, 0.01]},
        {"text": "z", "year": 1987, "embedding": [1.0, 0.05]},
        {"text": "a", "year": 2024, "embedding": [0.0, 1.0]},
        {"text": "b", "year": 2025, "embedding": [0.05, 0.99]},
        {"text": "c", "year": 2026, "embedding": [0.0, 1.0]},
    ]
    path.write_text("\n".join(json.dumps(d) for d in lines))
    out = _call(
        drift_analyze, query="x", chunks_path=str(path), language="es"
    )
    assert isinstance(out, dict)
    assert out["insufficient_data"] is False
    assert out["drift_events"]
