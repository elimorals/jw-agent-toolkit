from __future__ import annotations

from typing import Any

import pytest


@pytest.mark.asyncio
async def test_life_topic_info_returns_dict_with_disclaimer(monkeypatch) -> None:
    from jw_agents.base import AgentResult, Citation, Finding

    async def fake(query: str, *, language: str = "en", **_: Any) -> AgentResult:
        ar = AgentResult(query=query, agent_name="life_topics")
        ar.metadata["topic_id"] = "anxiety"
        ar.metadata["family"] = "sensitive"
        ar.findings.append(
            Finding(
                summary="Disclaimer",
                excerpt="Speak with elders.",
                citation=Citation(url="", title="Disclaimer", kind="disclaimer"),
                metadata={"source": "disclaimer", "family": "sensitive"},
            )
        )
        ar.findings.append(
            Finding(
                summary="Redirect",
                excerpt="Talk to your family.",
                citation=Citation(url="", title="Redirect", kind="elders_redirect"),
                metadata={"source": "elders_redirect"},
            )
        )
        return ar

    monkeypatch.setattr("jw_mcp.server.life_topics_agent", fake)

    from jw_mcp.server import life_topic_info

    out = await life_topic_info("ansiedad", language="es")
    sources = [f["metadata"].get("source") for f in out["findings"]]
    assert "disclaimer" in sources
    assert "elders_redirect" in sources
    assert out["metadata"]["topic_id"] == "anxiety"


@pytest.mark.asyncio
async def test_life_topic_info_unknown_topic_still_has_disclaimer(monkeypatch) -> None:
    """Even for unknown topics, disclaimer must be emitted.

    We stub the agent here too to keep the test offline.
    """
    from jw_agents.base import AgentResult, Citation, Finding

    async def fake(query: str, *, language: str = "en", **_: Any) -> AgentResult:
        ar = AgentResult(query=query, agent_name="life_topics")
        ar.warnings.append(f"No matching life topic for query: {query!r}")
        ar.findings.append(
            Finding(
                summary="Pastoral boundary",
                excerpt="This information is published material from the Watchtower.",
                citation=Citation(url="", title="Disclaimer", kind="disclaimer"),
                metadata={"source": "disclaimer", "family": "general"},
            )
        )
        return ar

    monkeypatch.setattr("jw_mcp.server.life_topics_agent", fake)

    from jw_mcp.server import life_topic_info

    out = await life_topic_info("zzzzzqqq", language="en")
    sources = [f["metadata"].get("source") for f in out["findings"]]
    assert "disclaimer" in sources
    assert "elders_redirect" not in sources
