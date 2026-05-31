"""Tests for the external (non-NWT) Bible client."""

from __future__ import annotations

import asyncio

import pytest
from jw_core.clients.external_bibles import (
    SUPPORTED_TRANSLATIONS,
    ExternalBiblesClient,
    ExternalVerse,
)


class _FakeResp:
    def __init__(self, status_code: int, json_data: dict | None = None) -> None:
        self.status_code = status_code
        self._json = json_data or {}

    def json(self) -> dict:
        return self._json


class _FakeHttp:
    def __init__(self, plan: list) -> None:
        self._plan = list(plan)
        self.calls: list[tuple[str, dict]] = []

    async def get(self, url: str, **kwargs) -> _FakeResp:
        self.calls.append((url, kwargs))
        if not self._plan:
            return _FakeResp(404)
        return self._plan.pop(0)

    async def aclose(self) -> None:
        pass


def test_supported_translations_table() -> None:
    assert "kjv" in SUPPORTED_TRANSLATIONS
    assert "rv1909" in SUPPORTED_TRANSLATIONS
    assert "web" in SUPPORTED_TRANSLATIONS


def test_get_verse_happy_path() -> None:
    fake = _FakeHttp([_FakeResp(200, {"text": "For God so loved...", "reference": "John 3:16"})])
    client = ExternalBiblesClient(http=fake)
    v = asyncio.run(client.get_verse(43, 3, 16, translation="kjv"))
    assert isinstance(v, ExternalVerse)
    assert v.text.startswith("For God so loved")
    assert v.translation == "kjv"


def test_get_verse_404_returns_none() -> None:
    fake = _FakeHttp([_FakeResp(404)])
    v = asyncio.run(ExternalBiblesClient(http=fake).get_verse(43, 3, 16, translation="web"))
    assert v is None


def test_invalid_translation_raises() -> None:
    client = ExternalBiblesClient(http=_FakeHttp([]))
    with pytest.raises(ValueError):
        asyncio.run(client.get_verse(43, 3, 16, translation="xyz"))


def test_invalid_book_num_raises() -> None:
    client = ExternalBiblesClient(http=_FakeHttp([]))
    with pytest.raises(ValueError):
        asyncio.run(client.get_verse(0, 1, 1))


def test_compare_translations_runs_all() -> None:
    fake = _FakeHttp(
        [
            _FakeResp(200, {"text": "WEB text"}),
            _FakeResp(200, {"text": "KJV text"}),
            _FakeResp(404),
        ]
    )
    client = ExternalBiblesClient(http=fake)
    out = asyncio.run(client.compare_translations(43, 3, 16, translations=["web", "kjv", "rv1909"]))
    assert out["web"].text == "WEB text"
    assert out["kjv"].text == "KJV text"
    assert out["rv1909"] is None


def test_compare_swallows_500_errors() -> None:
    fake = _FakeHttp([_FakeResp(500), _FakeResp(200, {"text": "ok"})])
    client = ExternalBiblesClient(http=fake)
    out = asyncio.run(client.compare_translations(43, 3, 16, translations=["web", "kjv"]))
    assert out["web"] is None
    assert out["kjv"].text == "ok"
