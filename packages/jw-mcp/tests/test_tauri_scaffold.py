"""Verify the Tauri desktop scaffolding (Gap 13) exists and is well-formed."""

from __future__ import annotations

import json
from pathlib import Path


_ROOT = Path(__file__).resolve().parents[3] / "apps" / "desktop"


def test_scaffold_files_exist() -> None:
    must = [
        "README.md",
        "package.json",
        "index.html",
        "src/main.js",
        "src-tauri/Cargo.toml",
        "src-tauri/tauri.conf.json",
        "src-tauri/src/main.rs",
        "src-tauri/build.rs",
    ]
    for rel in must:
        assert (_ROOT / rel).exists(), f"missing scaffolding file: {rel}"


def test_tauri_conf_is_valid_json() -> None:
    conf = json.loads((_ROOT / "src-tauri" / "tauri.conf.json").read_text())
    assert conf["productName"] == "jw-agent-toolkit"
    assert "windows" in conf["app"]


def test_main_rs_spawns_uvicorn() -> None:
    code = (_ROOT / "src-tauri" / "src" / "main.rs").read_text()
    assert "uvicorn" in code
    assert "jw_mcp.rest_api:app" in code
