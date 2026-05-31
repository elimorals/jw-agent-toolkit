from __future__ import annotations

import json
from typing import Any

import pytest
from typer.testing import CliRunner

from jw_cli.main import app


@pytest.fixture
def fake_life_topics(monkeypatch):
    """Patch the agent inside the command module to a deterministic stub."""
    from jw_agents.base import AgentResult, Citation, Finding

    async def fake(query: str, *, language: str = "en", **kwargs: Any) -> AgentResult:
        ar = AgentResult(query=query, agent_name="life_topics")
        ar.metadata["language"] = language
        ar.metadata["topic_id"] = "anxiety"
        ar.metadata["family"] = "sensitive"
        ar.findings.append(
            Finding(
                summary="Excerpt from How to Cope With Anxiety",
                excerpt="Trust in Jehovah brings peace.",
                citation=Citation(
                    url="https://wol.jw.org/x", title="How to Cope", kind="article"
                ),
                metadata={"source": "cdn_search"},
            )
        )
        ar.findings.append(
            Finding(
                summary="Pastoral boundary",
                excerpt="This is published material. Speak with elders.",
                citation=Citation(url="", title="Disclaimer", kind="disclaimer"),
                metadata={"source": "disclaimer", "family": "sensitive"},
            )
        )
        ar.findings.append(
            Finding(
                summary="Talk to your elders",
                excerpt="The elders of your congregation are willing to help.",
                citation=Citation(url="", title="Elders redirect", kind="elders_redirect"),
                metadata={"source": "elders_redirect"},
            )
        )
        return ar

    monkeypatch.setattr("jw_cli.commands.life.life_topics", fake)


def test_life_cmd_renders_disclaimer_and_redirect(fake_life_topics) -> None:
    runner = CliRunner()
    res = runner.invoke(app, ["life", "anxiety", "--lang", "en"])
    assert res.exit_code == 0, res.output
    assert "Trust in Jehovah" in res.output
    assert "elders" in res.output.lower()
    assert "Speak with elders" in res.output or "published material" in res.output.lower()


def test_life_cmd_json_output_contains_all_sources(fake_life_topics) -> None:
    runner = CliRunner()
    res = runner.invoke(app, ["life", "anxiety", "--lang", "en", "--json"])
    assert res.exit_code == 0, res.output
    data = json.loads(res.output)
    sources = [f["metadata"].get("source") for f in data["findings"]]
    assert "disclaimer" in sources
    assert "elders_redirect" in sources
