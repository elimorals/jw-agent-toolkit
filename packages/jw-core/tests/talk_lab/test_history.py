"""SessionHistory tests."""

from __future__ import annotations

from pathlib import Path

from jw_core.talk_lab.history import SessionHistory


def test_session_history_round_trip(tmp_path: Path) -> None:
    h = SessionHistory(tmp_path / "history.sqlite")
    h.track(
        recording_hash="abc",
        report_id="r1",
        scores={"cp-01": 3, "cp-02": 2},
        part_kind="bible_reading",
        language="es",
    )
    rows = h.list()
    assert len(rows) == 1
    assert rows[0].report_id == "r1"
    assert rows[0].scores["cp-01"] == 3


def test_session_history_compare_returns_deltas(tmp_path: Path) -> None:
    h = SessionHistory(tmp_path / "history.sqlite")
    h.track(
        recording_hash="a",
        report_id="r1",
        scores={"cp-01": 1},
        part_kind="bible_reading",
        language="es",
    )
    h.track(
        recording_hash="b",
        report_id="r2",
        scores={"cp-01": 3},
        part_kind="bible_reading",
        language="es",
    )
    deltas = h.compare("r1", "r2")
    assert deltas["cp-01"] == 2


def test_session_history_replace_same_report_id(tmp_path: Path) -> None:
    h = SessionHistory(tmp_path / "history.sqlite")
    h.track(
        recording_hash="a",
        report_id="r1",
        scores={"cp-01": 1},
        part_kind="bible_reading",
        language="es",
    )
    h.track(
        recording_hash="a2",
        report_id="r1",
        scores={"cp-01": 3},
        part_kind="bible_reading",
        language="es",
    )
    rows = h.list()
    assert len(rows) == 1
    assert rows[0].scores["cp-01"] == 3
