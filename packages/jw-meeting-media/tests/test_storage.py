"""F57 — Storage sqlite para programas semanales + tracking descargas."""

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
from jw_meeting_media.storage import MeetingStorage


@pytest.fixture()
def storage(tmp_path) -> MeetingStorage:
    return MeetingStorage(db_path=tmp_path / "meetings.db")


def test_save_and_load_program(storage):
    prog = MeetingProgram(
        language="es",
        week_start=date(2026, 6, 1),
        kind=MeetingKind.MIDWEEK,
        sections=[
            MeetingSection(
                section_id="s1",
                title="Tesoros",
                items=[
                    MeetingItem(
                        item_id="i1",
                        title="Lectura",
                        position=1,
                        bible_refs=[],
                        media_refs=[
                            MediaRef(
                                kind=MediaKind.IMAGE,
                                title="x",
                                url="https://example.com/x.jpg",
                            ),
                        ],
                    ),
                ],
            ),
        ],
        source_url="https://wol.jw.org/.../2026/23",
    )
    storage.save_program(prog)
    loaded = storage.load_program(
        language="es", year=2026, week=23, kind=MeetingKind.MIDWEEK
    )
    assert loaded is not None
    assert loaded.language == "es"
    assert len(loaded.sections) == 1
    assert loaded.sections[0].items[0].media_refs[0].kind == MediaKind.IMAGE


def test_load_unknown_program_returns_none(storage):
    assert (
        storage.load_program(
            language="es", year=1999, week=1, kind=MeetingKind.MIDWEEK
        )
        is None
    )


def test_mark_download_complete(storage, tmp_path):
    ref = MediaRef(
        kind=MediaKind.IMAGE,
        title="t",
        url="https://example.com/x.jpg",
        sha256="abc",
    )
    storage.mark_downloaded(ref, local_path=tmp_path / "x.jpg")
    assert storage.is_downloaded(ref) is True
    info = storage.get_download_info(ref)
    assert info is not None
    assert info["sha256"] == "abc"


def test_save_program_replaces_existing(storage):
    prog1 = MeetingProgram(
        language="es",
        week_start=date(2026, 6, 1),
        kind=MeetingKind.MIDWEEK,
        sections=[],
        source_url="x",
    )
    storage.save_program(prog1)
    prog2 = MeetingProgram(
        language="es",
        week_start=date(2026, 6, 1),
        kind=MeetingKind.MIDWEEK,
        sections=[MeetingSection(section_id="s1", title="t", items=[])],
        source_url="x",
    )
    storage.save_program(prog2)
    loaded = storage.load_program(
        language="es", year=2026, week=23, kind=MeetingKind.MIDWEEK
    )
    assert loaded is not None
    assert len(loaded.sections) == 1
