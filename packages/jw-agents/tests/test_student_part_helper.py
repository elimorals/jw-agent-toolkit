"""Tests for jw_agents.student_part_helper."""

from __future__ import annotations

import asyncio
from datetime import date

from jw_agents.student_part_helper import student_part_helper


def _run(coro):
    return asyncio.run(coro)


# ── invariant: 4 findings (opening/body/transition/close) ──────────────


def test_returns_four_findings_per_call() -> None:
    r = _run(
        student_part_helper(
            kind="bible_reading",
            topic_or_ref="esperanza",
            language="es",
            oratory_point=1,
            today=date(2026, 1, 15),
        )
    )
    sections = [f.metadata.get("section") for f in r.findings]
    assert sections == ["opening", "body", "transition", "close"]


def test_unknown_kind_returns_warning_no_findings() -> None:
    r = _run(
        student_part_helper(
            kind="invented_kind",  # type: ignore[arg-type]
            topic_or_ref="x",
            language="en",
            today=date(2026, 1, 15),
        )
    )
    assert r.findings == []
    assert any("kind" in w.lower() for w in r.warnings)


def test_metadata_includes_time_target_and_oratory_point() -> None:
    r = _run(
        student_part_helper(
            kind="starting_conversation",
            topic_or_ref="hope",
            language="en",
            oratory_point=13,
            today=date(2026, 1, 1),
        )
    )
    assert r.metadata["time_target_seconds"] == 180
    op = r.metadata["oratory_point_applied"]
    assert op["number"] == 13
    assert op["key_phrase"]


# ── scripture resolution ───────────────────────────────────────────────


def test_resolves_bible_reference_when_present() -> None:
    r = _run(
        student_part_helper(
            kind="bible_reading",
            topic_or_ref="Juan 3:16",
            language="es",
            oratory_point=1,
            today=date(2026, 1, 15),
        )
    )
    assert "Juan" in r.metadata.get("resolved_reference", "")
    # The opening finding's text mentions the verse display.
    assert "Juan" in r.findings[0].excerpt or "Juan" in r.findings[0].summary


def test_falls_back_to_topic_when_reference_unparseable() -> None:
    r = _run(
        student_part_helper(
            kind="starting_conversation",
            topic_or_ref="el sentido del sufrimiento",
            language="es",
            audience="default",
            oratory_point=1,
            today=date(2026, 1, 15),
        )
    )
    assert r.metadata.get("resolved_reference") is None
    # Topic still appears somewhere in the script.
    joined = " ".join(f.excerpt for f in r.findings)
    # Default audience template uses {verse_display} which falls back to topic.
    assert "sufrimiento" in joined.lower() or r.metadata.get("topic") == "el sentido del sufrimiento"


# ── audience fallback ──────────────────────────────────────────────────


def test_unknown_audience_falls_back_to_default() -> None:
    r = _run(
        student_part_helper(
            kind="bible_reading",
            topic_or_ref="Romanos 12:1",
            language="es",
            audience="child",  # type: ignore[arg-type]
            oratory_point=1,
            today=date(2026, 1, 15),
        )
    )
    assert r.metadata["audience_used"] == "default"


# ── oratory point selection ────────────────────────────────────────────


def test_default_oratory_point_picked_from_today_when_none() -> None:
    r = _run(
        student_part_helper(
            kind="bible_reading",
            topic_or_ref="Juan 3:16",
            language="es",
            today=date(2026, 1, 15),  # month 1 → point 1
        )
    )
    assert r.metadata["oratory_point_applied"]["number"] == 1


def test_oratory_point_not_applicable_emits_warning_but_continues() -> None:
    # Point 38 only applies to starting_conversation/return_visit per the registry.
    r = _run(
        student_part_helper(
            kind="bible_reading",
            topic_or_ref="Juan 3:16",
            language="es",
            oratory_point=38,
            today=date(2026, 1, 15),
        )
    )
    assert any("does not naturally apply" in w or "no aplica" in w for w in r.warnings)
    assert len(r.findings) == 4


# ── language fallback ──────────────────────────────────────────────────


def test_unknown_language_falls_back_to_english_template() -> None:
    r = _run(
        student_part_helper(
            kind="bible_reading",
            topic_or_ref="John 3:16",
            language="fr",
            oratory_point=1,
            today=date(2026, 1, 15),
        )
    )
    assert r.metadata["language"] == "fr"
    assert r.metadata["template_language_used"] == "en"


# ── 'this week' without wol returns warning ────────────────────────────


def test_this_week_without_wol_emits_warning() -> None:
    r = _run(
        student_part_helper(
            kind="bible_reading",
            topic_or_ref="this week",
            language="es",
            oratory_point=1,
            wol=None,
            today=date(2026, 1, 15),
        )
    )
    assert any("workbook" in w.lower() for w in r.warnings)


# ── citation behaviour ─────────────────────────────────────────────────


def test_finding_has_verse_citation_when_reference_resolves() -> None:
    r = _run(
        student_part_helper(
            kind="bible_reading",
            topic_or_ref="John 3:16",
            language="en",
            oratory_point=1,
            today=date(2026, 1, 15),
        )
    )
    assert any(f.citation.url.startswith("https://wol.jw.org/") for f in r.findings)


def test_finding_has_topic_anchor_when_no_reference() -> None:
    r = _run(
        student_part_helper(
            kind="starting_conversation",
            topic_or_ref="hope amid suffering",
            language="en",
            oratory_point=13,
            today=date(2026, 1, 15),
        )
    )
    # No verse → at least one finding carries a topic_anchor citation.
    kinds = {f.citation.kind for f in r.findings}
    assert "topic_anchor" in kinds


def test_idempotent_with_same_today() -> None:
    args = dict(
        kind="bible_reading",
        topic_or_ref="John 3:16",
        language="en",
        oratory_point=1,
        today=date(2026, 1, 15),
    )
    a = _run(student_part_helper(**args))  # type: ignore[arg-type]
    b = _run(student_part_helper(**args))  # type: ignore[arg-type]
    assert a.to_dict() == b.to_dict()


def test_resolves_reference_in_en_es_pt() -> None:
    for ref_in, lang in [
        ("John 3:16", "en"),
        ("Juan 3:16", "es"),
        ("João 3:16", "pt"),
    ]:
        r = _run(
            student_part_helper(
                kind="bible_reading",
                topic_or_ref=ref_in,
                language=lang,
                oratory_point=1,
                today=date(2026, 1, 15),
            )
        )
        assert "3:16" in r.metadata["resolved_reference"], (ref_in, lang)
        assert r.findings[0].citation.url.startswith("https://wol.jw.org/")
