"""--trace on the apologetics CLI command produces a parseable JSONL."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from jw_cli.main import app
from typer.testing import CliRunner


class _FakeTopic:
    async def search_subjects(self, *_a, **_k) -> list[dict[str, Any]]:
        return []

    async def aclose(self) -> None:
        pass


class _FakeCdn:
    async def search(self, *_a, **_k) -> dict[str, Any]:
        return {"results": []}

    async def aclose(self) -> None:
        pass


class _FakeWol:
    async def get_bible_chapter(self, *_a, **_k):
        return ("", "<html></html>")

    async def fetch(self, *_a, **_k) -> str:
        return "<html></html>"

    async def aclose(self) -> None:
        pass


@pytest.fixture(autouse=True)
def _patch_agent_clients(monkeypatch: pytest.MonkeyPatch) -> None:
    """Force the apologetics agent offline by stubbing its HTTP clients."""

    import importlib

    ap = importlib.import_module("jw_agents.apologetics")
    monkeypatch.setattr(ap, "CDNClient", lambda: _FakeCdn())
    monkeypatch.setattr(ap, "WOLClient", lambda: _FakeWol())
    monkeypatch.setattr(ap, "TopicIndexClient", lambda **_k: _FakeTopic())


def test_apologetics_trace_writes_jsonl(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("JW_TRACE_DIR", str(tmp_path))
    out = tmp_path / "t.jsonl"
    runner = CliRunner()
    res = runner.invoke(
        app,
        [
            "apologetics",
            "demo",
            "--fidelity",
            "off",
            "--trace",
            str(out),
        ],
    )
    assert res.exit_code == 0, res.output
    assert out.exists()
    lines = out.read_text().splitlines()
    assert lines, "trace file is empty"
    envelope = json.loads(lines[-1])
    assert envelope["type"] == "trace_complete"
    assert envelope["agent"] == "apologetics"
