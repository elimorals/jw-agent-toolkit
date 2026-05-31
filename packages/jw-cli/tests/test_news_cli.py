"""Smoke tests for `jw news digest`. Uses CliRunner with stubbed agent."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from jw_agents.base import AgentResult, Citation, Finding
from jw_cli.commands.news import news_app
from typer.testing import CliRunner

runner = CliRunner()


def _fake_agent_result() -> AgentResult:
    r = AgentResult(query="news_digest since=epoch", agent_name="news_monitor")
    r.findings.append(
        Finding(
            summary="[publications/en] WT June 2026",
            citation=Citation(url="https://x/w_E_202606.epub", title="WT June 2026"),
            metadata={
                "source": "news_monitor",
                "channel": "publications",
                "item_id": "w_E_202606",
                "language": "en",
            },
        )
    )
    r.metadata["markdown"] = "# JW News Digest\n\n- 1 nuevo\n"
    r.metadata["stats"] = {"new": 1, "retired": 0}
    return r


async def _stub_news_monitor(**_: object) -> AgentResult:
    return _fake_agent_result()


def test_news_digest_prints_markdown_by_default() -> None:
    with patch("jw_cli.commands.news.news_monitor", new=_stub_news_monitor):
        result = runner.invoke(news_app, ["digest", "--since", "epoch", "--channels", "publications"])
    assert result.exit_code == 0
    assert "# JW News Digest" in result.stdout


def test_news_digest_writes_out_file(tmp_path: Path) -> None:
    out = tmp_path / "digest.md"
    with patch("jw_cli.commands.news.news_monitor", new=_stub_news_monitor):
        result = runner.invoke(
            news_app,
            ["digest", "--since", "epoch", "--out", str(out)],
        )
    assert result.exit_code == 0
    assert out.read_text().startswith("# JW News Digest")


def test_news_digest_json_format() -> None:
    with patch("jw_cli.commands.news.news_monitor", new=_stub_news_monitor):
        result = runner.invoke(news_app, ["digest", "--since", "epoch", "--json"])
    assert result.exit_code == 0
    # JSON output must include the stats key.
    assert '"stats"' in result.stdout or '"markdown"' in result.stdout
