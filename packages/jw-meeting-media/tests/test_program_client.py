"""F57 — MeetingProgramClient. Tests con HTML fixture local + cassettes opt-in."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from jw_meeting_media.models import MeetingKind
from jw_meeting_media.program_client import MeetingProgramClient

FIXTURE = Path(__file__).parent / "fixtures" / "wol_mwb_2026_w23_es.html"


@pytest.fixture()
def client() -> MeetingProgramClient:
    return MeetingProgramClient()


def test_parse_midweek_fixture_sections(client):
    """El parser detecta las 3 secciones canónicas del workbook:
    Tesoros / Seamos mejores / Nuestra vida cristiana."""
    html = FIXTURE.read_text(encoding="utf-8")
    program = client.parse_html(
        html,
        language="es",
        week_start=date(2026, 6, 1),
        kind=MeetingKind.MIDWEEK,
        source_url="https://wol.jw.org/es/wol/meetings/r4/lp-s/2026/23",
    )
    assert len(program.sections) >= 3


def test_parse_midweek_items_have_titles(client):
    html = FIXTURE.read_text(encoding="utf-8")
    program = client.parse_html(
        html,
        language="es",
        week_start=date(2026, 6, 1),
        kind=MeetingKind.MIDWEEK,
        source_url="x",
    )
    total_items = sum(len(s.items) for s in program.sections)
    assert total_items > 0
    for sec in program.sections:
        for item in sec.items:
            assert item.title.strip() != ""


def test_parse_extracts_bible_refs(client):
    """El workbook tiene refs bíblicas inline; el parser las captura."""
    html = FIXTURE.read_text(encoding="utf-8")
    program = client.parse_html(
        html,
        language="es",
        week_start=date(2026, 6, 1),
        kind=MeetingKind.MIDWEEK,
        source_url="x",
    )
    total_refs = sum(len(item.bible_refs) for sec in program.sections for item in sec.items)
    assert total_refs > 0


def test_parse_extracts_media_refs(client):
    """El workbook tiene videos y JWPUB linkeados."""
    html = FIXTURE.read_text(encoding="utf-8")
    program = client.parse_html(
        html,
        language="es",
        week_start=date(2026, 6, 1),
        kind=MeetingKind.MIDWEEK,
        source_url="x",
    )
    total_media = sum(len(item.media_refs) for sec in program.sections for item in sec.items)
    assert total_media >= 1


def test_week_url_pattern(client):
    url = client.build_week_url(language="es", year=2026, week=23)
    assert url.startswith("https://wol.jw.org/es/wol/meetings/")
    assert "/2026/23" in url


def test_week_url_uses_correct_resource_per_language(client):
    """Recurso r1 para inglés, r4 para español, r5 para portugués."""
    assert "/r1/" in client.build_week_url(language="en", year=2026, week=23)
    assert "/r4/" in client.build_week_url(language="es", year=2026, week=23)
    assert "/r5/" in client.build_week_url(language="pt", year=2026, week=23)
