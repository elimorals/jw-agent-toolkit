"""Tests for the validate_citations MCP tool."""

from __future__ import annotations


def test_validate_citations_rejects_missing_input() -> None:
    from jw_mcp.server import validate_citations

    out = validate_citations()
    assert "error" in out


def test_validate_citations_rejects_both_inputs() -> None:
    from jw_mcp.server import validate_citations

    out = validate_citations(urls=["x"], agent_output={"findings": []})
    assert "error" in out


def test_validate_citations_structural_with_urls() -> None:
    from jw_mcp.server import validate_citations

    out = validate_citations(urls=["https://wol.jw.org/es/wol/d/r4/lp-s/1"])
    assert "mode" in out
    assert out["mode"] == "structural"
    assert len(out["checks"]) == 1


def test_validate_citations_with_agent_output() -> None:
    from jw_mcp.server import validate_citations

    agent_out = {
        "findings": [
            {"metadata": {"citation_url": "https://wol.jw.org/es/wol/d/r4/lp-s/1"}},
            {"metadata": {"citation_url": "https://wol.jw.org/es/wol/d/r4/lp-s/2"}},
        ]
    }
    out = validate_citations(agent_output=agent_out)
    assert len(out["checks"]) == 2


def test_validate_citations_live_requires_env_optin(monkeypatch) -> None:
    from jw_mcp.server import validate_citations

    monkeypatch.delenv("JW_CITATIONS_LIVE", raising=False)
    out = validate_citations(urls=["https://wol.jw.org/x"], live=True)
    # Without the env var, the server should refuse to hit the network.
    assert "error" in out
    assert "JW_CITATIONS_LIVE" in out["error"]
