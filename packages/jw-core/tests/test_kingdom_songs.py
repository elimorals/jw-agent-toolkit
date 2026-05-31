"""Tests for jw_core.songs — Kingdom Songs metadata registry."""

from __future__ import annotations

import pytest


def test_model_round_trip_minimum_fields() -> None:
    from jw_core.songs import KingdomSong

    s = KingdomSong(
        number=5,
        title="Christ's Self-Sacrificing Love",
        theme="Christ's self-sacrificing love as a pattern.",
        scriptures=["John 13:34-35"],
        language="en",
    )
    assert s.number == 5
    assert s.pub_symbol == "sjj"
    assert s.canonical_url == ""


def test_model_rejects_out_of_range_number() -> None:
    from jw_core.songs import KingdomSong

    with pytest.raises(ValueError):
        KingdomSong(number=999, title="x", theme="y", scriptures=[], language="en")


def test_song_lookup_error_is_lookup_error() -> None:
    from jw_core.songs import SongLookupError

    assert issubclass(SongLookupError, LookupError)


def test_resolved_scriptures_filters_unparseable() -> None:
    from jw_core.songs import KingdomSong

    s = KingdomSong(
        number=5,
        title="x",
        theme="y",
        scriptures=["Juan 13:34-35", "not-a-ref"],
        language="es",
    )
    refs = s.resolved_scriptures()
    assert len(refs) == 1
    assert refs[0].book_num == 43  # John


def test_get_registry_loads_three_languages() -> None:
    from jw_core.songs import get_registry

    for lang in ["en", "es", "pt"]:
        reg = get_registry(lang)
        assert len(reg.all()) >= 10, f"{lang} registry too small"


def test_get_registry_caches_per_language() -> None:
    from jw_core.songs import get_registry

    a = get_registry("en")
    b = get_registry("en")
    assert a is b


def test_lookup_returns_song() -> None:
    from jw_core.songs import get_registry

    reg = get_registry("es")
    song = reg.lookup(5)
    assert song.number == 5
    assert "amor" in song.title.lower() or "amor" in song.theme.lower()


def test_lookup_unknown_raises() -> None:
    from jw_core.songs import SongLookupError, get_registry

    reg = get_registry("en")
    with pytest.raises(SongLookupError):
        reg.lookup(999)


def test_unknown_language_returns_empty_registry() -> None:
    from jw_core.songs import get_registry

    reg = get_registry("xx")
    assert reg.all() == []


def test_canonical_url_falls_back_to_finder_pattern() -> None:
    from jw_core.songs import get_registry

    reg = get_registry("es")
    song = reg.lookup(5)
    # Spanish wtlocale = "S".
    assert song.canonical_url == "https://www.jw.org/finder?wtlocale=S&pub=sjj"


def test_seed_integrity() -> None:
    """Invariants that protect the seed from accidentally storing lyrics."""

    from jw_core.songs import get_registry

    # Heuristic anti-lyrics tokens — flag obvious copy-paste from a lyric sheet.
    FORBIDDEN_TOKENS = [
        "verse 1",
        "estrofa",
        "estribillo",
        "refrão",
        "refrain",
        "chorus",
        "stanza",
        "©",
        "copyright watch tower",
    ]

    parallel_numbers: dict[str, set[int]] = {}
    for lang in ["en", "es", "pt"]:
        reg = get_registry(lang)
        nums = set()
        for s in reg.all():
            assert 1 <= s.number <= 200, f"{lang}/#{s.number}: out of 1..200"
            assert len(s.theme) <= 200, f"{lang}/#{s.number}: theme too long"
            assert len(s.title) <= 200, f"{lang}/#{s.number}: title too long"
            lower_blob = (s.title + " " + s.theme).lower()
            for tok in FORBIDDEN_TOKENS:
                assert tok not in lower_blob, f"{lang}/#{s.number}: forbidden token {tok!r}"
            # Every scripture must parse cleanly.
            assert s.resolved_scriptures() or not s.scriptures, (
                f"{lang}/#{s.number}: scriptures {s.scriptures} all unparseable"
            )
            nums.add(s.number)
        parallel_numbers[lang] = nums

    # All three languages cover the same numbers (parallel coverage).
    assert parallel_numbers["en"] == parallel_numbers["es"] == parallel_numbers["pt"], (
        f"language coverage mismatch: {parallel_numbers}"
    )


def _make_workbook_result(songs_dict: dict[str, int | None]):
    """Build a minimal AgentResult mirroring what workbook_helper emits."""

    from jw_agents.base import AgentResult, Citation, Finding

    result = AgentResult(query="2026-W23", agent_name="workbook_helper")
    result.findings.append(
        Finding(
            summary="Workbook week of 2026-06-08",
            excerpt="PROVERBIOS 1-3",
            citation=Citation(
                url="https://wol.jw.org/example",
                title="Reunión",
                kind="workbook_week",
                metadata={"songs": songs_dict},
            ),
            metadata={"source": "workbook_week"},
        )
    )
    return result


def test_enrich_adds_three_findings_when_all_slots_present() -> None:
    from jw_core.songs.integration import enrich_with_songs

    result = _make_workbook_result({"opening": 5, "middle": 47, "closing": 151})
    out = enrich_with_songs(result, language="es")
    song_findings = [f for f in out.findings if f.metadata.get("source") == "kingdom_song"]
    assert len(song_findings) == 3
    assert {f.citation.metadata["slot"] for f in song_findings} == {"opening", "middle", "closing"}


def test_enrich_is_idempotent() -> None:
    from jw_core.songs.integration import enrich_with_songs

    result = _make_workbook_result({"opening": 5, "middle": 47, "closing": 151})
    enrich_with_songs(result, language="en")
    enrich_with_songs(result, language="en")
    song_findings = [f for f in result.findings if f.metadata.get("source") == "kingdom_song"]
    assert len(song_findings) == 3


def test_enrich_handles_unknown_song_gracefully() -> None:
    from jw_core.songs.integration import enrich_with_songs

    result = _make_workbook_result({"opening": 999, "middle": 5, "closing": None})
    out = enrich_with_songs(result, language="en")
    song_findings = [f for f in out.findings if f.metadata.get("source") == "kingdom_song"]
    # Only #5 should land as a finding.
    assert len(song_findings) == 1
    assert song_findings[0].citation.metadata["number"] == 5
    # The unknown number surfaces as a warning.
    assert any("999" in w for w in out.warnings)


def test_enrich_no_workbook_week_finding_is_noop() -> None:
    from jw_agents.base import AgentResult
    from jw_core.songs.integration import enrich_with_songs

    result = AgentResult(query="x", agent_name="other")
    enrich_with_songs(result, language="en")
    assert result.findings == []
    assert result.warnings == []


def test_cli_song_number_renders_table() -> None:
    from jw_cli.main import app
    from typer.testing import CliRunner

    runner = CliRunner()
    result = runner.invoke(app, ["song", "5", "--lang", "es"])
    assert result.exit_code == 0, result.stdout
    assert "5" in result.stdout
    assert "amor" in result.stdout.lower() or "amor" in result.stdout.lower()


def test_cli_song_unknown_number_reports_error() -> None:
    from jw_cli.main import app
    from typer.testing import CliRunner

    runner = CliRunner()
    result = runner.invoke(app, ["song", "999", "--lang", "en"])
    assert result.exit_code != 0
    assert "not in registry" in result.stdout.lower() or "999" in result.stdout
