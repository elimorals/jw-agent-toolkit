"""Unit tests for the letter_composer agent.

All tests are sync-friendly via `asyncio.run`; no network is required.
"""

from __future__ import annotations

import asyncio

import pytest

from jw_agents.letter_composer import letter_composer


def _run(**kwargs):
    return asyncio.run(letter_composer(**kwargs))


def test_compose_letter_returns_4_sections_in_order() -> None:
    result = _run(
        kind="letter",
        language="es",
        topic_or_question="esperanza para una madre en duelo",
        audience="grieving",
    )
    sections = [f.metadata.get("section") for f in result.findings]
    assert sections[:4] == ["opener", "bridge", "scripture", "closing"]


def test_compose_letter_metadata_contains_required_fields() -> None:
    result = _run(
        kind="letter",
        language="es",
        topic_or_question="esperanza",
        audience="default",
    )
    md = result.metadata
    assert md["kind"] == "letter"
    assert md["audience"] == "default"
    assert md["language"] == "es"
    assert md["word_count_target"] == 150
    assert md["time_target_seconds"] == 0
    assert md["topic_family"] == "hope"


def test_compose_phone_has_time_target_75s() -> None:
    result = _run(
        kind="phone",
        language="es",
        topic_or_question="ansiedad",
        audience="default",
    )
    assert result.metadata["time_target_seconds"] == 75
    assert result.metadata["word_count_target"] == 0


def test_compose_cart_has_time_target_30s() -> None:
    result = _run(
        kind="cart",
        language="en",
        topic_or_question="family",
        audience="parents",
    )
    assert result.metadata["time_target_seconds"] == 30


def test_scripture_finding_carries_wol_url() -> None:
    result = _run(
        kind="letter",
        language="es",
        topic_or_question="esperanza",
        audience="default",
    )
    scrip = next(f for f in result.findings if f.metadata.get("section") == "scripture")
    assert scrip.citation.url.startswith("https://wol.jw.org/")
    assert scrip.metadata["source"] == "verse_text"


def test_territory_hint_inserted_in_opener_only() -> None:
    result = _run(
        kind="letter",
        language="es",
        topic_or_question="esperanza",
        audience="default",
        territory_hint="Lima, Perú",
    )
    opener = next(f for f in result.findings if f.metadata.get("section") == "opener")
    assert "Lima, Perú" in opener.summary
    bridge = next(f for f in result.findings if f.metadata.get("section") == "bridge")
    assert "Lima, Perú" not in bridge.summary


def test_jw_link_override_wins_over_template_default() -> None:
    custom = "https://www.jw.org/custom/path"
    result = _run(
        kind="letter",
        language="en",
        topic_or_question="hope",
        audience="default",
        jw_link=custom,
    )
    assert result.metadata["jw_link_suggested"] == custom
    closing = next(f for f in result.findings if f.metadata.get("section") == "closing")
    assert closing.citation.url == custom


def test_audience_fallback_to_default_when_unknown() -> None:
    result = _run(
        kind="letter",
        language="es",
        topic_or_question="esperanza",
        audience="no_such_audience",
    )
    # No exception; warning emitted; metadata captures effective audience.
    assert result.metadata["audience"] == "default"
    assert any("audience" in w.lower() for w in result.warnings)


def test_topic_family_fallback_to_generic_when_no_match() -> None:
    result = _run(
        kind="letter",
        language="es",
        topic_or_question="zzz totally unrelated zzz",
        audience="default",
    )
    assert result.metadata["topic_family"] == "generic"


def test_unknown_language_warns_and_uses_english() -> None:
    result = _run(
        kind="letter",
        language="xx",
        topic_or_question="hope",
        audience="default",
    )
    opener = next(f for f in result.findings if f.metadata.get("section") == "opener")
    # English fallback prose is present.
    assert "Hello" in opener.summary
    assert any("language" in w.lower() for w in result.warnings)


def test_every_finding_carries_a_citation_url() -> None:
    result = _run(
        kind="letter",
        language="es",
        topic_or_question="esperanza",
        audience="default",
    )
    for f in result.findings:
        assert f.citation.url, f"empty citation in section={f.metadata.get('section')!r}"


def test_invalid_kind_raises() -> None:
    with pytest.raises(ValueError):
        asyncio.run(
            letter_composer(
                kind="email",  # type: ignore[arg-type]
                language="es",
                topic_or_question="x",
            )
        )


def test_topic_client_optional_adds_topic_anchor() -> None:
    class StubTopic:
        async def search_subjects(self, q, *, language="E", limit=1):
            return [{"url": "https://wol.jw.org/topic/x", "title": "Stub topic"}]

        async def aclose(self) -> None:
            pass

    result = asyncio.run(
        letter_composer(
            kind="letter",
            language="es",
            topic_or_question="paz",
            audience="default",
            topic=StubTopic(),  # type: ignore[arg-type]
        )
    )
    anchors = [f for f in result.findings if f.metadata.get("section") == "topic_anchor"]
    assert len(anchors) == 1
    assert anchors[0].citation.url == "https://wol.jw.org/topic/x"


def test_topic_client_failure_emits_warning_not_raise() -> None:
    class BrokenTopic:
        async def search_subjects(self, q, *, language="E", limit=1):
            raise RuntimeError("network down")

    result = asyncio.run(
        letter_composer(
            kind="letter",
            language="es",
            topic_or_question="paz",
            audience="default",
            topic=BrokenTopic(),  # type: ignore[arg-type]
        )
    )
    # Still produces a usable scaffold.
    assert len(result.findings) >= 4
    assert any("topic index" in w.lower() for w in result.warnings)


def test_letter_composer_importable_from_package_root() -> None:
    import jw_agents

    assert hasattr(jw_agents, "letter_composer")
