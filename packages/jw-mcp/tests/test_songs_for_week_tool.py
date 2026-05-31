from __future__ import annotations

from typing import Any

import pytest


@pytest.mark.asyncio
async def test_songs_for_week_with_stubbed_workbook(monkeypatch) -> None:
    """Stub workbook_helper so the test stays offline; verify the tool
    extracts the kingdom_song findings produced by enrich_with_songs."""

    from jw_agents.base import AgentResult, Citation, Finding
    from jw_mcp import server as srv

    async def fake_workbook_helper(*args: Any, **kwargs: Any):
        result = AgentResult(query="2026-W23", agent_name="workbook_helper")
        result.metadata["week_of"] = "2026-06-08"
        result.findings.append(
            Finding(
                summary="Workbook week",
                excerpt="Proverbios 1-3",
                citation=Citation(
                    url="https://wol.jw.org/example",
                    title="x",
                    kind="workbook_week",
                    metadata={"songs": {"opening": 5, "middle": 47, "closing": 151}},
                ),
                metadata={"source": "workbook_week"},
            )
        )
        return result

    monkeypatch.setattr(srv, "_workbook_helper_agent", fake_workbook_helper, raising=False)

    out = await srv.songs_for_week(date="2026-06-08", language="es")
    assert out["week_of"] == "2026-06-08"
    assert len(out["songs"]) == 3
    slots = {s["slot"] for s in out["songs"]}
    assert slots == {"opening", "middle", "closing"}
    numbers = {s["number"] for s in out["songs"]}
    assert numbers == {5, 47, 151}
