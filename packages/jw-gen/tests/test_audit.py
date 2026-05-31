from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from jw_gen.audit import audit_log_path, log_generation, rotate_log


def test_log_generation_appends_jsonl(isolated_jw_gen_home: Path) -> None:
    event = log_generation(
        kind="image",
        provider="fake",
        prompt_sha256="abc123",
        output_path=isolated_jw_gen_home / "out.png",
        watermark_mode="visible+metadata",
        safety_flags={"logo_check": "pass"},
        warnings=[],
    )
    path = audit_log_path()
    raw = path.read_text(encoding="utf-8").strip().splitlines()
    assert len(raw) == 1
    row = json.loads(raw[0])
    assert row["audit_id"] == event["audit_id"]
    assert row["prompt_sha256"] == "abc123"
    assert "prompt" not in row, "audit log must never contain the prompt in plaintext"


def test_log_generation_two_events_distinct_ids(isolated_jw_gen_home: Path) -> None:
    e1 = log_generation(
        kind="image",
        provider="fake",
        prompt_sha256="a",
        output_path=isolated_jw_gen_home / "x.png",
        watermark_mode="visible+metadata",
        safety_flags={},
        warnings=[],
    )
    e2 = log_generation(
        kind="image",
        provider="fake",
        prompt_sha256="b",
        output_path=isolated_jw_gen_home / "y.png",
        watermark_mode="visible+metadata",
        safety_flags={},
        warnings=[],
    )
    assert e1["audit_id"] != e2["audit_id"]


def test_log_generation_timestamp_is_utc(isolated_jw_gen_home: Path) -> None:
    event = log_generation(
        kind="image",
        provider="fake",
        prompt_sha256="z",
        output_path=isolated_jw_gen_home / "z.png",
        watermark_mode="visible+metadata",
        safety_flags={},
        warnings=[],
        now=lambda: datetime(2026, 5, 31, 14, 0, tzinfo=timezone.utc),
    )
    assert event["timestamp"].endswith("Z")
    assert "2026-05-31T14:00" in event["timestamp"]


def test_rotate_log_moves_to_dated_gz(isolated_jw_gen_home: Path) -> None:
    log_generation(
        kind="image",
        provider="fake",
        prompt_sha256="a",
        output_path=isolated_jw_gen_home / "x.png",
        watermark_mode="visible+metadata",
        safety_flags={},
        warnings=[],
    )
    target = rotate_log()
    assert target is not None
    assert target.exists()
    assert target.suffix == ".gz"
    assert not audit_log_path().exists() or audit_log_path().read_text() == ""


def test_rotate_log_noop_when_empty(isolated_jw_gen_home: Path) -> None:
    assert rotate_log() is None
