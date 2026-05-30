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
