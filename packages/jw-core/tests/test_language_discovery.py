"""Tests for language discovery (Gap 4)."""

from __future__ import annotations

import asyncio

import pytest

from jw_core.language_discovery import (
    DEFAULT_PROBE_CANDIDATES,
    LanguageProbeResult,
    discover_wol_resource,
    validate_jw_code,
)
from jw_core.languages import get_language


class _FakeResp:
    def __init__(self, status_code: int, json_data: dict | None = None) -> None:
        self.status_code = status_code
        self._json = json_data or {}

    def json(self) -> dict:
        return self._json


class _FakeClient:
    def __init__(self, plan: list) -> None:
        self._plan = list(plan)
        self.calls: list[str] = []

    async def get(self, url: str, **kwargs) -> _FakeResp:
        self.calls.append(url)
        if not self._plan:
            return _FakeResp(404)
        return self._plan.pop(0)

    async def aclose(self) -> None:
        pass


def test_validate_jw_code_true_when_files_exist() -> None:
    fake = _FakeClient([_FakeResp(200, {"files": {"F": {"EPUB": [{"file": {}}]}}})])
    ok = asyncio.run(validate_jw_code("F", http=fake))
    assert ok is True


def test_validate_jw_code_false_when_no_epub_block() -> None:
    fake = _FakeClient([_FakeResp(200, {"files": {"F": {}}})])
    ok = asyncio.run(validate_jw_code("F", http=fake))
    assert ok is False


def test_validate_jw_code_false_on_non_200() -> None:
    fake = _FakeClient([_FakeResp(503)])
    ok = asyncio.run(validate_jw_code("F", http=fake))
    assert ok is False


def test_discover_wol_resource_finds_first_200() -> None:
    fake = _FakeClient(
        [
            # 1: pub-media OK
            _FakeResp(200, {"files": {"F": {"EPUB": [{"file": {}}]}}}),
            # 2..N: WOL probes — first miss, then hit
            _FakeResp(404),
            _FakeResp(200),
        ]
    )
    result = asyncio.run(discover_wol_resource(get_language("fr"), http=fake, candidates=[30, 40]))
    assert isinstance(result, LanguageProbeResult)
    assert result.wol_resource == "r40"
    assert result.pub_media_ok is True


def test_discover_wol_resource_reports_no_match() -> None:
    fake = _FakeClient(
        [
            _FakeResp(200, {"files": {"F": {"EPUB": [{"file": {}}]}}}),
            _FakeResp(404),
            _FakeResp(404),
        ]
    )
    result = asyncio.run(discover_wol_resource(get_language("fr"), http=fake, candidates=[30, 40]))
    assert result.wol_resource == ""
    assert "No 200" in result.error


def test_default_candidates_cover_tier1() -> None:
    for iso in ("fr", "de", "it", "ru", "ja", "ko", "zh"):
        assert DEFAULT_PROBE_CANDIDATES.get(iso), f"missing candidate set for {iso}"
