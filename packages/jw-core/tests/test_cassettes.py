"""Cassette-backed tests for the most critical HTTP endpoints.

These tests use `pytest-recording` to record the response shape of each
endpoint into a YAML cassette under `tests/cassettes/test_cassettes/`.
On subsequent runs the cassette is replayed instead of hitting the
network, so the test suite stays offline-capable.

To record (or re-record) all cassettes after an API shape change:

    uv run pytest packages/jw-core/tests/test_cassettes.py --record-mode=rewrite

The cassettes serve two purposes:

  1. They lock in the SHAPE of every endpoint we depend on. If jw.org
     changes a field, the cassette replay will still pass parsers
     against the OLD shape but the recorded cassette stays as
     documentation of how it used to look.
  2. They make the CI fast: no network, no flakiness.

The cassettes themselves are checked into the repo (~10-50KB each).
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

_CASSETTE_DIR = (
    Path(__file__).parent / "cassettes" / "test_cassettes"
)

# pytest-recording requires the cassette file present. Mark tests as skip
# when running outside CI/replay context with no cassette on disk.
def _cassette_present(name: str) -> bool:
    return (_CASSETTE_DIR / f"{name}.yaml").exists()


pytestmark = pytest.mark.asyncio


@pytest.mark.vcr
@pytest.mark.skipif(
    not _cassette_present("test_mediator_languages_shape"),
    reason="No cassette; run with --record-mode=rewrite once to capture.",
)
async def test_mediator_languages_shape() -> None:
    """Replay the mediator language-list response and check our parser."""
    from jw_core.clients.mediator import MediatorClient
    client = MediatorClient()
    try:
        langs = await client.list_languages(in_language="E")
    finally:
        await client.aclose()
    # We don't pin a specific count (JW adds languages over time); we
    # just assert that the parser produces useful entries.
    assert len(langs) >= 50, f"Expected many languages, got {len(langs)}"
    en = next((l for l in langs if l.code == "E"), None)
    assert en is not None
    assert en.locale == "en"
    assert en.name in ("English",)


@pytest.mark.vcr
@pytest.mark.skipif(
    not _cassette_present("test_weblang_languages_shape"),
    reason="No cassette; run with --record-mode=rewrite once to capture.",
)
async def test_weblang_languages_shape() -> None:
    """Replay the www.jw.org/{iso}/languages response."""
    from jw_core.clients.weblang import WeblangClient
    client = WeblangClient()
    try:
        langs = await client.list_languages(in_language_iso="en")
    finally:
        await client.aclose()
    assert len(langs) >= 50
    en = next((l for l in langs if l.code == "E"), None)
    assert en is not None


@pytest.mark.vcr
@pytest.mark.skipif(
    not _cassette_present("test_cdn_search_shape"),
    reason="No cassette; run with --record-mode=rewrite once to capture.",
)
async def test_cdn_search_shape() -> None:
    """Replay a CDN search response and verify result schema."""
    from jw_core.clients.cdn import CDNClient
    client = CDNClient()
    try:
        data = await client.search("love", filter_type="bible", language="E", limit=3)
    finally:
        await client.aclose()
    assert "results" in data
    assert isinstance(data["results"], list)


@pytest.mark.vcr
@pytest.mark.skipif(
    not _cassette_present("test_pub_media_catalog_shape"),
    reason="No cassette; run with --record-mode=rewrite once to capture.",
)
async def test_pub_media_catalog_shape() -> None:
    """Replay a GETPUBMEDIALINKS response for the Trinity brochure."""
    from jw_core.clients.pub_media import PubMediaClient
    client = PubMediaClient()
    try:
        pub = await client.get_publication("ti", language="E", file_format="EPUB")
    finally:
        await client.aclose()
    assert pub.pub_code == "ti"
    assert pub.files
