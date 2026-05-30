from __future__ import annotations

import pytest
from pydantic import ValidationError

from jw_agents.study_progress import (
    GoalKind,
    LessonRow,
    LessonStatus,
    StudentGoal,
)


def test_lesson_status_enum_values() -> None:
    assert LessonStatus.NOT_STARTED.value == "not_started"
    assert LessonStatus.IN_PROGRESS.value == "in_progress"
    assert LessonStatus.COMPLETED.value == "completed"
    assert LessonStatus.SKIPPED.value == "skipped"


def test_goal_kind_enum_includes_taxonomy() -> None:
    assert GoalKind.ATTEND_MEETINGS in GoalKind
    assert GoalKind.DROP_ADDICTION_SMOKING in GoalKind
    assert GoalKind.DROP_ADDICTION_ALCOHOL in GoalKind
    assert GoalKind.PRAY_DAILY in GoalKind
    assert GoalKind.FAMILY_WORSHIP in GoalKind
    assert GoalKind.BAPTISM in GoalKind


def test_lesson_row_validates_student_id() -> None:
    LessonRow(
        student_id="amelia2024",
        book_pub="lff",
        lesson=1,
        updated_at_iso="2026-05-30T00:00:00",
    )


def test_lesson_row_rejects_invalid_student_id() -> None:
    with pytest.raises(ValidationError):
        LessonRow(
            student_id="Amelia García",
            book_pub="lff",
            lesson=1,
            updated_at_iso="2026-05-30T00:00:00",
        )


def test_lesson_row_default_status_not_started() -> None:
    row = LessonRow(
        student_id="x_y_z",
        book_pub="lff",
        lesson=1,
        updated_at_iso="2026-05-30T00:00:00",
    )
    assert row.status == LessonStatus.NOT_STARTED


def test_student_goal_minimal() -> None:
    g = StudentGoal(kind=GoalKind.BAPTISM, set_at_iso="2026-05-30T00:00:00")
    assert g.kind == GoalKind.BAPTISM
    assert g.achieved_at_iso is None


# --- Task 5: salt + passphrase --------------------------------------------

from pathlib import Path

from jw_agents.study_progress import (
    PrivacyState,
    derive_encryptor_for_passphrase,
    load_or_create_salt,
)


def test_load_or_create_salt_creates_when_missing(tmp_path: Path) -> None:
    target = tmp_path / "salt.bin"
    state = load_or_create_salt(target)
    assert state == PrivacyState.CREATED
    assert target.exists()
    assert len(target.read_bytes()) == 16


def test_load_or_create_salt_returns_existing(tmp_path: Path) -> None:
    target = tmp_path / "salt.bin"
    load_or_create_salt(target)
    state2 = load_or_create_salt(target)
    assert state2 == PrivacyState.LOADED


def test_derive_encryptor_round_trip(tmp_path: Path) -> None:
    salt_path = tmp_path / "salt.bin"
    load_or_create_salt(salt_path)
    enc = derive_encryptor_for_passphrase("hunter2", salt_path=salt_path)
    assert enc.enabled
    token = enc.encrypt("nota sensible")
    assert enc.decrypt(token) == "nota sensible"


# --- Task 6: StudentProgressStore ----------------------------------------

from jw_agents.study_progress import StudentProgressStore


def test_store_round_trip_without_encryption(tmp_path: Path) -> None:
    store = StudentProgressStore(db_path=tmp_path / "p.db")
    row = LessonRow(
        student_id="demo_user",
        book_pub="lff",
        lesson=1,
        status=LessonStatus.IN_PROGRESS,
        notes="alpha",
        updated_at_iso="2026-05-30T00:00:00",
    )
    store.upsert(row)
    got = store.get("demo_user", "lff", 1)
    assert got is not None
    assert got.status == LessonStatus.IN_PROGRESS
    assert got.notes == "alpha"


def test_store_encrypted_notes_round_trip(tmp_path: Path) -> None:
    salt_path = tmp_path / "salt.bin"
    load_or_create_salt(salt_path)
    enc = derive_encryptor_for_passphrase("hunter2", salt_path=salt_path)
    store = StudentProgressStore(db_path=tmp_path / "p.db", encryptor=enc)
    row = LessonRow(
        student_id="demo_user",
        book_pub="lff",
        lesson=2,
        notes="nota privada con áéíóú",
        updated_at_iso="2026-05-30T00:00:00",
    )
    store.upsert(row)
    got = store.get("demo_user", "lff", 2)
    assert got is not None
    assert got.notes == "nota privada con áéíóú"

    # Sanity: opening DB without key returns ciphertext for notes.
    plain_store = StudentProgressStore(db_path=tmp_path / "p.db")
    raw = plain_store.get("demo_user", "lff", 2)
    assert raw is not None
    assert raw.notes != "nota privada con áéíóú"


def test_store_list_for_student(tmp_path: Path) -> None:
    store = StudentProgressStore(db_path=tmp_path / "p.db")
    for n in (1, 2, 3):
        store.upsert(LessonRow(
            student_id="demo_user", book_pub="lff", lesson=n,
            updated_at_iso="2026-05-30T00:00:00",
        ))
    rows = store.list_for_student("demo_user")
    assert [r.lesson for r in rows] == [1, 2, 3]


# --- Task 7: crisis scanner integration + set_goal helper ----------------

from jw_agents.study_progress import scan_lesson_for_crisis, set_goal_for_student


def test_scan_lesson_for_crisis_hits() -> None:
    row = LessonRow(
        student_id="demo_user", book_pub="lff", lesson=1,
        notes="Mencionó suicidio en la última visita",
        updated_at_iso="2026-05-30T00:00:00",
    )
    hits = scan_lesson_for_crisis(row, language="es")
    assert "suicidio" in hits


def test_set_goal_for_student_appends(tmp_path: Path) -> None:
    store = StudentProgressStore(db_path=tmp_path / "p.db")
    row = LessonRow(
        student_id="demo_user", book_pub="lff", lesson=1,
        updated_at_iso="2026-05-30T00:00:00",
    )
    store.upsert(row)
    updated = set_goal_for_student(
        store, "demo_user", "lff", 1,
        kind=GoalKind.BAPTISM, target_iso="2026-12-31T00:00:00",
    )
    assert any(g.kind == GoalKind.BAPTISM for g in updated.goals)
    assert updated.baptism_target_iso == "2026-12-31T00:00:00"
