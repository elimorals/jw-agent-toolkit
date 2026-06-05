"""F57 — Presenter session manager (server-side state)."""

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
)
from jw_meeting_media.presenter_state import PresenterManager


def make_program() -> MeetingProgram:
    return MeetingProgram(
        language="es",
        week_start=date(2026, 6, 1),
        kind=MeetingKind.MIDWEEK,
        sections=[
            MeetingSection(
                section_id="s1",
                title="Sec1",
                items=[
                    MeetingItem(
                        item_id=f"i{j}",
                        title=f"Item {j}",
                        position=j,
                        bible_refs=[],
                        media_refs=[
                            MediaRef(
                                kind=MediaKind.IMAGE,
                                title=f"img{j}",
                                url=f"https://x/{j}.jpg",
                            )
                        ],
                    )
                    for j in range(1, 4)
                ],
            ),
        ],
        source_url="x",
    )


def test_create_session_flattens_items():
    mgr = PresenterManager()
    session_id = mgr.create_session(program=make_program())
    state = mgr.get_state(session_id)
    assert len(state.queue) == 3


def test_play_pause_toggles_state():
    mgr = PresenterManager()
    sid = mgr.create_session(program=make_program())
    mgr.play(sid)
    assert mgr.get_state(sid).playing is True
    mgr.pause(sid)
    assert mgr.get_state(sid).playing is False


def test_next_advances_cursor():
    mgr = PresenterManager()
    sid = mgr.create_session(program=make_program())
    mgr.next_(sid)
    assert mgr.get_state(sid).cursor == 1
    mgr.next_(sid)
    assert mgr.get_state(sid).cursor == 2


def test_next_at_end_clamps():
    mgr = PresenterManager()
    sid = mgr.create_session(program=make_program())
    mgr.next_(sid)
    mgr.next_(sid)
    mgr.next_(sid)
    assert mgr.get_state(sid).cursor == 2


def test_stop_resets_cursor_and_pauses():
    mgr = PresenterManager()
    sid = mgr.create_session(program=make_program())
    mgr.next_(sid)
    mgr.play(sid)
    mgr.stop(sid)
    state = mgr.get_state(sid)
    assert state.cursor == 0 and state.playing is False


def test_unknown_session_raises():
    mgr = PresenterManager()
    with pytest.raises(KeyError):
        mgr.get_state("does-not-exist")
