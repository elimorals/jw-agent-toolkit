"""Tests for the jw-finetune MCP tools."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jw_finetune.mcp_tools import register_jw_finetune_tools


class FakeMCP:
    """Stand-in for FastMCP — captures registered tools."""

    def __init__(self) -> None:
        self.tools: dict[str, Any] = {}

    def tool(self, fn: Any) -> Any:
        """Decorator: capture the function and return it unchanged."""
        self.tools[fn.__name__] = fn
        return fn


def test_register_returns_tool_names(tmp_path: Path) -> None:
    mcp = FakeMCP()
    names = register_jw_finetune_tools(mcp, workspace_root=tmp_path)
    assert "list_finetune_runs" in names
    assert "get_finetune_run" in names
    assert "get_finetune_events" in names
    assert "list_finetune_presets" in names
    assert "chat_with_finetune_checkpoint" in names
    assert "doctor_finetune" in names
    # All names should be registered as tools
    for n in names:
        assert n in mcp.tools


def test_list_finetune_presets(tmp_path: Path) -> None:
    mcp = FakeMCP()
    register_jw_finetune_tools(mcp, workspace_root=tmp_path)
    out = mcp.tools["list_finetune_presets"]()
    assert "presets" in out
    names = [p["name"] for p in out["presets"]]
    assert "doctrinal-qa-es-sft" in names


def test_list_finetune_runs_empty(tmp_path: Path) -> None:
    mcp = FakeMCP()
    register_jw_finetune_tools(mcp, workspace_root=tmp_path)
    out = mcp.tools["list_finetune_runs"]()
    assert out == {"runs": []}


def test_list_finetune_runs_with_runs(tmp_path: Path) -> None:
    run = tmp_path / "run-20260530-120000"
    run.mkdir()
    (run / "dataset_qa.jsonl").write_text(
        json.dumps({"messages": []}) + "\n", encoding="utf-8"
    )
    (run / "events.jsonl").write_text("", encoding="utf-8")

    mcp = FakeMCP()
    register_jw_finetune_tools(mcp, workspace_root=tmp_path)
    out = mcp.tools["list_finetune_runs"]()
    assert len(out["runs"]) == 1
    assert out["runs"][0]["task"] == "sft"


def test_get_finetune_events_empty(tmp_path: Path) -> None:
    run = tmp_path / "run-20260530-120000"
    run.mkdir()
    (run / "events.jsonl").write_text("", encoding="utf-8")

    mcp = FakeMCP()
    register_jw_finetune_tools(mcp, workspace_root=tmp_path)
    out = mcp.tools["get_finetune_events"](run_id="run-20260530-120000")
    assert out == {"events": [], "count": 0}


def test_get_finetune_events_returns_last_n(tmp_path: Path) -> None:
    run = tmp_path / "run-20260530-120000"
    run.mkdir()
    events_path = run / "events.jsonl"
    lines = "\n".join([
        json.dumps({"kind": "step", "step": i, "loss": 1.0 / (i + 1)})
        for i in range(10)
    ]) + "\n"
    events_path.write_text(lines, encoding="utf-8")

    mcp = FakeMCP()
    register_jw_finetune_tools(mcp, workspace_root=tmp_path)
    out = mcp.tools["get_finetune_events"](run_id="run-20260530-120000", limit=3)
    assert out["count"] == 3
    # Should be the last 3 events (steps 7, 8, 9)
    steps = [e["step"] for e in out["events"]]
    assert steps == [7, 8, 9]


def test_get_finetune_run_unknown_returns_error(tmp_path: Path) -> None:
    mcp = FakeMCP()
    register_jw_finetune_tools(mcp, workspace_root=tmp_path)
    out = mcp.tools["get_finetune_run"](run_id="../etc")
    assert "error" in out


def test_doctor_finetune(tmp_path: Path) -> None:
    mcp = FakeMCP()
    register_jw_finetune_tools(mcp, workspace_root=tmp_path)
    out = mcp.tools["doctor_finetune"]()
    assert "ok" in out
    assert "checks" in out
    assert isinstance(out["checks"], list)


def test_chat_with_finetune_checkpoint_missing_run(tmp_path: Path) -> None:
    mcp = FakeMCP()
    register_jw_finetune_tools(mcp, workspace_root=tmp_path)
    out = mcp.tools["chat_with_finetune_checkpoint"](
        run_id="nonexistent", prompt="hello",
    )
    assert "error" in out
