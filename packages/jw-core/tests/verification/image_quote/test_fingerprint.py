"""Visual fingerprint heuristic tests (Fase 70)."""

from __future__ import annotations

from jw_core.verification.image_quote.fingerprint import (
    assess_layout_consistency,
    detect_apparent_era,
    detect_apparent_publication,
    detect_visual_anomalies,
)


def test_detect_apparent_era_from_copyright_year() -> None:
    era = detect_apparent_era("", "Copyright 1985 by Watch Tower")
    assert era == "1980s"


def test_detect_apparent_era_from_unicode_symbol() -> None:
    era = detect_apparent_era("", "© 2024 Watch Tower")
    assert era == "2020s"


def test_detect_apparent_era_from_style_marker() -> None:
    era = detect_apparent_era(
        "Image with primary colors bold lettering", ""
    )
    assert era == "1980s"


def test_detect_apparent_era_returns_none_when_no_signal() -> None:
    assert detect_apparent_era("a person reading", "Some text") is None


def test_detect_apparent_publication_atalaya() -> None:
    assert (
        detect_apparent_publication("Cover of Atalaya magazine", "")
        == "Atalaya"
    )


def test_detect_apparent_publication_unknown_returns_none() -> None:
    assert detect_apparent_publication("random photo", "") is None


def test_detect_visual_anomalies_font_mismatch() -> None:
    anomalies = detect_visual_anomalies(
        "the caption uses font mismatch between header and body", ""
    )
    assert "font_mismatch" in anomalies


def test_detect_visual_anomalies_logo_modified() -> None:
    anomalies = detect_visual_anomalies(
        "altered logo with wrong proportions", ""
    )
    assert "logo_modified" in anomalies


def test_detect_visual_anomalies_returns_empty_on_clean_image() -> None:
    anomalies = detect_visual_anomalies(
        "A clean magazine cover with the Atalaya title", ""
    )
    assert anomalies == []


def test_assess_layout_consistency_inconsistent() -> None:
    assert (
        assess_layout_consistency(
            "font mismatch in the headline", ""
        )
        == "inconsistent"
    )


def test_assess_layout_consistency_consistent() -> None:
    assert (
        assess_layout_consistency("A clean cover with the Atalaya title", "")
        == "consistent"
    )


def test_assess_layout_consistency_unknown_on_empty() -> None:
    assert assess_layout_consistency("", "") == "unknown"
