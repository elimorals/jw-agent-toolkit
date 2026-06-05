"""F57 — modelos del programa semanal y sesión de presenter."""

from __future__ import annotations

from datetime import date

import pytest
from jw_meeting_media.models import (
    MediaKind,
    MediaRef,
    MeetingItem,
    MeetingKind,
    MeetingProgram,
    MeetingSection,
    PresenterSession,
)


def test_meeting_program_basic():
    prog = MeetingProgram(
        language="es",
        week_start=date(2026, 6, 1),
        kind=MeetingKind.MIDWEEK,
        sections=[],
        source_url="https://wol.jw.org/es/wol/meetings/r4/lp-s/2026/23",
    )
    assert prog.language == "es"
    assert prog.kind == MeetingKind.MIDWEEK


def test_media_ref_image():
    ref = MediaRef(
        kind=MediaKind.IMAGE,
        title="Ilustración Génesis",
        url="https://cms-imgp.jw-cdn.org/img/p/.../some.jpg",
        sha256=None,
    )
    assert ref.kind == MediaKind.IMAGE
    assert ref.url.startswith("https://")


def test_media_ref_video_with_track():
    ref = MediaRef(
        kind=MediaKind.VIDEO,
        title="Ejemplo en video",
        url="",  # se resuelve via PubMediaClient
        pub_code="pk",
        track=12,
        sha256=None,
    )
    assert ref.pub_code == "pk"


def test_meeting_section_with_items():
    sec = MeetingSection(
        section_id="treasures",
        title="Tesoros de la Palabra de Dios",
        items=[
            MeetingItem(
                item_id="t1",
                title="Lectura bíblica",
                position=1,
                bible_refs=[],
                media_refs=[],
            ),
        ],
    )
    assert len(sec.items) == 1


def test_presenter_session_starts_paused():
    s = PresenterSession(
        session_id="s-123",
        program_url="https://wol.jw.org/...",
        queue=[],
        cursor=0,
        playing=False,
    )
    assert s.playing is False
    assert s.cursor == 0


def test_presenter_session_advance_within_bounds():
    item = MeetingItem(item_id="i1", title="x", position=1, bible_refs=[], media_refs=[])
    s = PresenterSession(
        session_id="s1", program_url="x", queue=[item, item, item], cursor=0, playing=False
    )
    s.advance()
    assert s.cursor == 1
    s.advance()
    assert s.cursor == 2
    with pytest.raises(IndexError):
        s.advance()


def test_meeting_kind_values():
    assert MeetingKind.MIDWEEK.value == "midweek"
    assert MeetingKind.WEEKEND.value == "weekend"
    assert MeetingKind.MEMORIAL.value == "memorial"
    assert MeetingKind.SPECIAL_EVENT.value == "special_event"
