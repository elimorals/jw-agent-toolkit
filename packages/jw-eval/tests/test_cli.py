from __future__ import annotations

from pathlib import Path
from typing import Any

from jw_eval.cli import default_agent_registry, run_from_cli


def test_default_agent_registry_has_known_agents() -> None:
    reg = default_agent_registry()
    assert "apologetics" in reg
    assert "verse_explainer" in reg
    assert "life_topics" in reg
    assert "research_topic" in reg
    assert "meeting_helper" in reg
    assert "conversation_assistant" in reg


def test_run_from_cli_returns_report(tmp_path: Path) -> None:
    cases_dir = tmp_path / "golden_qa"
    cases_dir.mkdir()
    (cases_dir / "demo.yaml").write_text(
        """
id: demo
agent: __fake__
layer: l1
input: {}
expected: {}
""",
        encoding="utf-8",
    )

    def fake_agent(_: dict[str, Any]):
        class _R:
            findings = []

        return _R()

    report = run_from_cli(
        cases_root=cases_dir,
        snapshots_root=tmp_path,
        layers=["l1"],
        agent_registry={"__fake__": fake_agent},
    )
    assert report.summary["l1"]["pass"] == 1
