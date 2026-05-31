from __future__ import annotations

from dataclasses import dataclass

import pytest
from jw_core.study.lesson_extractor import (
    LessonContent,
    LessonExtractionError,
    extract_lesson,
)


def test_lesson_content_shape() -> None:
    lc = LessonContent(
        pub_code="lff",
        chapter=1,
        language="es",
        title="¿Existe alguien que se preocupe por usted?",
        paragraphs=["P1...", "P2..."],
        scripture_refs={1: ["1 Pedro 5:6, 7"], 2: []},
        source="jwpub_local",
        citation_url="https://wol.jw.org/es/wol/publication/r4/lp-s/lff/1",
    )
    assert lc.pub_code == "lff"
    assert lc.source == "jwpub_local"
    assert len(lc.paragraphs) == 2


def test_extract_lesson_unknown_pub_raises() -> None:
    with pytest.raises(LessonExtractionError):
        extract_lesson("nope", chapter=1, language="es")


def test_extract_lesson_chapter_out_of_range() -> None:
    with pytest.raises(LessonExtractionError):
        extract_lesson("lff", chapter=999, language="es")


def test_extract_lesson_wol_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    # Force JWPUB lookup to return None → must fall back to WOL.

    def fake_find_jwpub(*args: object, **kwargs: object) -> None:
        return None

    @dataclass
    class _FakeHTMLPage:
        title: str = "Capítulo 1"
        paragraphs: tuple[str, ...] = ("Texto del párrafo 1.", "Texto del párrafo 2.")

    def fake_wol_get(*args: object, **kwargs: object) -> _FakeHTMLPage:
        return _FakeHTMLPage()

    monkeypatch.setattr(
        "jw_core.study.lesson_extractor._find_jwpub_path",
        fake_find_jwpub,
    )
    monkeypatch.setattr(
        "jw_core.study.lesson_extractor._fetch_chapter_from_wol",
        fake_wol_get,
    )

    lc = extract_lesson("lff", chapter=1, language="es")
    assert lc.source == "wol_fallback"
    assert len(lc.paragraphs) == 2
    assert lc.citation_url.startswith("https://wol.jw.org/")


def test_fetch_chapter_from_wol_uses_correct_kwarg_and_parses_article(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression: lesson_extractor must call get_publication_page with
    `number=` (not `n=`), await it (async), and parse the returned HTML
    into an Article-shaped object with .title/.paragraphs.

    Bug discovered by eval (Fase 22 calibration) — the previous impl used
    `n=chapter` (TypeError) AND treated the awaitable's tuple return as
    an object with .title/.paragraphs (silent empty fallback).
    """

    from jw_core.study.lesson_extractor import _fetch_chapter_from_wol

    captured_kwargs: dict[str, object] = {}

    fake_html = (
        "<html><body>"
        "<article id='article'>"
        "<h1>Capítulo 1</h1>"
        "<p id='p1' data-pid='1'>Párrafo uno.</p>"
        "<p id='p2' data-pid='2'>Párrafo dos.</p>"
        "</article>"
        "</body></html>"
    )

    class _FakeWOLClient:
        async def get_publication_page(
            self,
            pub_code: str,
            number: int | None = None,
            *,
            language: str = "en",
        ) -> tuple[str, str]:
            captured_kwargs["pub_code"] = pub_code
            captured_kwargs["number"] = number
            captured_kwargs["language"] = language
            return ("https://wol.jw.org/example", fake_html)

    class _FakeSuite:
        wol = _FakeWOLClient()

        async def aclose(self) -> None:
            return None

    monkeypatch.setattr(
        "jw_core.clients.factory.build_clients",
        lambda: _FakeSuite(),
    )

    page = _fetch_chapter_from_wol("lff", chapter=3, language="es")

    # Must use `number=`, not `n=`.
    assert captured_kwargs.get("number") == 3
    assert captured_kwargs.get("n") is None
    assert captured_kwargs["language"] == "es"

    # The returned object must look Article-shaped so _extract_from_wol's
    # getattr(page, "title", "")/getattr(page, "paragraphs", []) produce
    # real values rather than silently empty strings/lists.
    assert hasattr(page, "title")
    assert hasattr(page, "paragraphs")
    assert page.title
    assert len(page.paragraphs) >= 1
