"""Tests for jw_core.integrations.jw_library (Layer 1)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest
from jw_core.integrations.jw_library import (
    JWLibraryError,
    VerseRange,
    _assert_safe_jwlibrary_url,
    _build_open_command,
    build_bible_url,
    build_bible_urls,
    build_publication_url,
    build_url_for_ref,
    detect_platform,
    open_jw_library,
)
from jw_core.parsers.reference import parse_reference

# ── URL builders ─────────────────────────────────────────────────────────


def test_bible_url_single_verse_no_locale() -> None:
    # John 3:16 → book=43, chap=003, verse=016.
    assert build_bible_url(43, 3, 16) == "jwlibrary:///finder?bible=43003016"


def test_bible_url_single_verse_with_iso_locale_normalizes_to_jw_code() -> None:
    # ISO "es" must be rewritten to JW code "S".
    url = build_bible_url(43, 3, 16, wtlocale="es")
    assert url == "jwlibrary:///finder?bible=43003016&wtlocale=S"


def test_bible_url_accepts_jw_code_directly() -> None:
    url = build_bible_url(40, 24, 14, wtlocale="E")
    assert url == "jwlibrary:///finder?bible=40024014&wtlocale=E"


def test_bible_url_pads_to_2_3_3_widths() -> None:
    # Genesis 1:1 — book pads to 2, chapter/verse to 3.
    assert build_bible_url(1, 1, 1) == "jwlibrary:///finder?bible=01001001"


def test_bible_url_verse_range_within_chapter() -> None:
    url = build_bible_url(45, 8, 28, verse_end=30)
    assert url == "jwlibrary:///finder?bible=45008028-45008030"


def test_bible_url_multi_chapter_range() -> None:
    # Matthew 3:1–4:11
    url = build_bible_url(40, 3, 1, verse_end=11, end_chapter=4)
    assert url == "jwlibrary:///finder?bible=40003001-40004011"


def test_bible_url_no_verse_defaults_to_verse_1() -> None:
    url = build_bible_url(58, 13)
    assert url == "jwlibrary:///finder?bible=58013001"


def test_bible_url_single_chapter_book_jude_3() -> None:
    # Jude 1:3 → 65/001/003. Single-chapter books still use chapter=1.
    assert build_bible_url(65, 1, 3) == "jwlibrary:///finder?bible=65001003"


def test_bible_url_collapses_equal_start_end() -> None:
    # If verse_end == verse_start and chapters match, emit single-token form.
    assert build_bible_url(43, 3, 16, verse_end=16) == "jwlibrary:///finder?bible=43003016"


def test_bible_url_rejects_book_out_of_range() -> None:
    with pytest.raises(JWLibraryError):
        build_bible_url(0, 1, 1)
    with pytest.raises(JWLibraryError):
        build_bible_url(67, 1, 1)


def test_bible_url_rejects_descending_range() -> None:
    with pytest.raises(JWLibraryError):
        build_bible_url(45, 8, 30, verse_end=28)


def test_bible_url_rejects_end_chapter_before_start() -> None:
    with pytest.raises(JWLibraryError):
        build_bible_url(40, 5, 1, verse_end=2, end_chapter=4)


def test_bible_urls_disjoint_ranges_returns_list() -> None:
    # "John 1:1, 4, 7-8" — three independent ranges.
    urls = build_bible_urls(
        43,
        1,
        ranges=[VerseRange(1, 1), VerseRange(4, 4), VerseRange(7, 8)],
        wtlocale="en",
    )
    assert urls == [
        "jwlibrary:///finder?bible=43001001&wtlocale=E",
        "jwlibrary:///finder?bible=43001004&wtlocale=E",
        "jwlibrary:///finder?bible=43001007-43001008&wtlocale=E",
    ]


def test_bible_urls_empty_ranges_raises() -> None:
    with pytest.raises(JWLibraryError):
        build_bible_urls(43, 1, ranges=[])


# ── Publication URLs ─────────────────────────────────────────────────────


def test_publication_url_minimal() -> None:
    # docid only — wtlocale and par omitted.
    assert build_publication_url(1102021201) == "jwlibrary:///finder?docid=1102021201"


def test_publication_url_full() -> None:
    url = build_publication_url(1102021201, paragraph=2, wtlocale="en")
    assert url == "jwlibrary:///finder?wtlocale=E&docid=1102021201&par=2"


def test_publication_url_rejects_non_numeric_docid() -> None:
    with pytest.raises(JWLibraryError):
        build_publication_url("not-a-number")  # type: ignore[arg-type]


def test_publication_url_rejects_non_positive_paragraph() -> None:
    with pytest.raises(JWLibraryError):
        build_publication_url(1, paragraph=0)


# ── BibleRef → URL ───────────────────────────────────────────────────────


def test_url_for_ref_picks_up_detected_language() -> None:
    ref = parse_reference("Juan 3:16")
    assert ref is not None
    url = build_url_for_ref(ref)
    # Spanish detected → wtlocale=S.
    assert url == "jwlibrary:///finder?bible=43003016&wtlocale=S"


def test_url_for_ref_explicit_wtlocale_wins() -> None:
    ref = parse_reference("John 3:16")
    assert ref is not None
    url = build_url_for_ref(ref, wtlocale="pt")
    assert url == "jwlibrary:///finder?bible=43003016&wtlocale=T"


def test_url_for_ref_range() -> None:
    ref = parse_reference("Romanos 8:28-30")
    assert ref is not None
    url = build_url_for_ref(ref)
    assert url == "jwlibrary:///finder?bible=45008028-45008030&wtlocale=S"


# ── Safety ───────────────────────────────────────────────────────────────


def test_open_rejects_non_jwlibrary_url() -> None:
    with pytest.raises(JWLibraryError):
        open_jw_library("https://example.com/evil", dry_run=True)


def test_open_rejects_url_with_control_chars() -> None:
    with pytest.raises(JWLibraryError):
        _assert_safe_jwlibrary_url("jwlibrary://x\x00injected")


def test_detect_platform_returns_known_value() -> None:
    assert detect_platform() in {"darwin", "win32", "linux", "unknown"}


# ── open() dispatch ──────────────────────────────────────────────────────


@dataclass
class _FakeResult:
    returncode: int = 0
    stdout: str = ""
    stderr: str = ""


class _FakeRunner:
    """Captures the argv each subprocess.run call would have used."""

    def __init__(self, returncode: int = 0, stderr: str = "") -> None:
        self.calls: list[dict[str, Any]] = []
        self._result = _FakeResult(returncode=returncode, stderr=stderr)

    def run(self, argv: list[str], **kwargs: Any) -> _FakeResult:
        self.calls.append({"argv": argv, "kwargs": kwargs})
        return self._result


def test_open_dry_run_does_not_invoke_runner() -> None:
    runner = _FakeRunner()
    out = open_jw_library(
        "jwlibrary:///finder?bible=43003016",
        dry_run=True,
        platform="darwin",
        runner=runner,
    )
    assert out["dispatched"] is False
    assert out["dry_run"] is True
    assert runner.calls == []


def test_open_darwin_invokes_open_command(monkeypatch: pytest.MonkeyPatch) -> None:
    # Pretend `open` is on PATH so the shutil.which guard passes.
    monkeypatch.setattr(
        "jw_core.integrations.jw_library.shutil.which",
        lambda _name: "/usr/bin/open",
    )
    runner = _FakeRunner()
    out = open_jw_library(
        "jwlibrary:///finder?bible=43003016",
        platform="darwin",
        runner=runner,
    )
    assert out["dispatched"] is True
    assert runner.calls[0]["argv"] == ["open", "jwlibrary:///finder?bible=43003016"]


def test_open_windows_uses_cmd_start() -> None:
    runner = _FakeRunner()
    out = open_jw_library(
        "jwlibrary:///finder?bible=43003016",
        platform="win32",
        runner=runner,
    )
    assert out["dispatched"] is True
    # `cmd /c start "" <url>` keeps URL as last token, with empty window title.
    assert runner.calls[0]["argv"] == [
        "cmd",
        "/c",
        "start",
        "",
        "jwlibrary:///finder?bible=43003016",
    ]


def test_open_linux_requires_xdg_open(monkeypatch: pytest.MonkeyPatch) -> None:
    # Simulate xdg-open missing.
    monkeypatch.setattr(
        "jw_core.integrations.jw_library.shutil.which",
        lambda _name: None,
    )
    with pytest.raises(JWLibraryError, match="xdg-open"):
        open_jw_library(
            "jwlibrary:///finder?bible=43003016",
            platform="linux",
            runner=_FakeRunner(),
        )


def test_open_unknown_platform_raises() -> None:
    with pytest.raises(JWLibraryError):
        open_jw_library(
            "jwlibrary:///finder?bible=43003016",
            platform="unknown",
            runner=_FakeRunner(),
        )


def test_build_open_command_shapes() -> None:
    # Sanity-check the platform→argv mapping in isolation.
    assert _build_open_command("jwlibrary://x", "darwin").argv == ["open", "jwlibrary://x"]
    assert _build_open_command("jwlibrary://x", "linux").argv == ["xdg-open", "jwlibrary://x"]
    win = _build_open_command("jwlibrary://x", "win32").argv
    assert win[:4] == ["cmd", "/c", "start", ""]
    assert win[-1] == "jwlibrary://x"
