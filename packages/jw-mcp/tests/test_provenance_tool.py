"""Tests for the `verify_provenance` MCP tool."""

from __future__ import annotations

from typing import Any

from jw_core.provenance.hashing import content_sha256
from jw_mcp.tools.provenance import verify_provenance


def _build_agent_output(body: str, *, url: str = "https://wol.jw.org/x") -> dict[str, Any]:
    return {
        "query": "q",
        "agent_name": "verse_explainer",
        "warnings": [],
        "metadata": {},
        "findings": [
            {
                "summary": "s",
                "excerpt": body,
                "metadata": {"source": "verse_text"},
                "citation": {
                    "url": url,
                    "title": "t",
                    "kind": "verse",
                    "metadata": {
                        "accessed_at": "2026-05-30T10:00:00Z",
                        "content_hash": content_sha256(body),
                        "published_date": None,
                        "revision": "rev. 2023",
                    },
                },
            }
        ],
    }


class _FakeFetcher:
    def __init__(self, body: str) -> None:
        self._body = body

    async def __call__(self, url: str):
        from jw_core.provenance.validator import FetcherResponse

        return FetcherResponse(final_url=url, status=200, body=self._body)


async def test_verify_provenance_returns_dict_with_summary() -> None:
    body = "stable text"
    agent_output = _build_agent_output(body)

    out = await verify_provenance(
        agent_output,
        since=None,
        with_nli=False,
        fetcher=_FakeFetcher(body),
    )

    assert isinstance(out, dict)
    assert out["summary"]["match"] == 1


async def test_verify_provenance_changed_in_summary() -> None:
    body_orig = "x"
    body_new = "y"
    agent_output = _build_agent_output(body_orig)

    out = await verify_provenance(
        agent_output,
        since=None,
        with_nli=False,
        fetcher=_FakeFetcher(body_new),
    )

    assert out["summary"]["changed"] == 1


async def test_verify_provenance_since_filters() -> None:
    body = "x"
    agent_output = _build_agent_output(body)

    out = await verify_provenance(
        agent_output,
        since="2024-01-01",
        with_nli=False,
        fetcher=_FakeFetcher(body),
    )
    # accessed_at=2026-05-30 >= since=2024-01-01 → skipped
    assert out["summary"].get("skipped", 0) == 1


async def test_verify_provenance_with_nli_flag_without_provider_no_op() -> None:
    """`with_nli=True` with no NLI configured → still works, just no nli_rerun."""

    body_orig = "x"
    body_new = "y"
    agent_output = _build_agent_output(body_orig)

    out = await verify_provenance(
        agent_output,
        since=None,
        with_nli=True,
        fetcher=_FakeFetcher(body_new),
    )
    verdicts = out["verdicts"]
    assert verdicts[0]["status"] == "changed"
    assert verdicts[0].get("nli_rerun") is None
