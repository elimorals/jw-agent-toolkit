from __future__ import annotations

import pytest


def test_prepare_lesson_tool_returns_dict(monkeypatch) -> None:
    from jw_mcp import server as srv
    from jw_agents.base import AgentResult, Citation, Finding

    def fake_prepare(*a, **k):
        return AgentResult(
            query="x", agent_name="study_conductor",
            findings=[Finding(
                summary="Lección 1", excerpt="…",
                citation=Citation(url="https://wol.jw.org/x", title="t", kind="chapter"),
                metadata={"source": "wol_chapter"},
            )],
        )

    monkeypatch.setattr(srv, "prepare_lesson_agent", fake_prepare)
    out = srv.prepare_lesson("lff", 1, "es")
    assert "findings" in out
    assert len(out["findings"]) == 1
