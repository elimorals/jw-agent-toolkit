"""Tests for ProvenanceRecord — the read-only typed view over Citation.metadata."""

from __future__ import annotations

from typing import Any

import pytest
from jw_core.provenance.models import ProvenanceRecord


def test_from_citation_metadata_returns_none_when_keys_absent() -> None:
    """Backwards compat: a legacy citation with no provenance keys → None."""

    assert ProvenanceRecord.from_citation_metadata({}) is None
    assert ProvenanceRecord.from_citation_metadata({"unrelated": "stuff"}) is None


def test_from_citation_metadata_requires_at_minimum_content_hash_and_accessed_at() -> None:
    """`content_hash` and `accessed_at` are the two non-negotiable fields."""

    meta_partial: dict[str, Any] = {"accessed_at": "2026-05-31T10:00:00Z"}
    assert ProvenanceRecord.from_citation_metadata(meta_partial) is None
    meta_partial2: dict[str, Any] = {"content_hash": "deadbeef"}
    assert ProvenanceRecord.from_citation_metadata(meta_partial2) is None


def test_from_citation_metadata_roundtrip_full() -> None:
    meta: dict[str, Any] = {
        "published_date": "2023-01-15",
        "accessed_at": "2026-05-31T10:00:00Z",
        "content_hash": "abc123def456",
        "revision": "rev. 2023",
        "other_unrelated": "ignored",
    }
    record = ProvenanceRecord.from_citation_metadata(meta)
    assert record is not None
    assert record.published_date == "2023-01-15"
    assert record.accessed_at == "2026-05-31T10:00:00Z"
    assert record.content_hash == "abc123def456"
    assert record.revision == "rev. 2023"


def test_from_citation_metadata_optionals_null_safe() -> None:
    """published_date and revision are optional; only the two anchors must be present."""

    meta: dict[str, Any] = {
        "accessed_at": "2026-05-31T10:00:00Z",
        "content_hash": "deadbeef",
    }
    record = ProvenanceRecord.from_citation_metadata(meta)
    assert record is not None
    assert record.published_date is None
    assert record.revision is None


def test_to_dict_emits_only_present_keys() -> None:
    """The serializer is used by stamp_citation when re-projecting back."""

    record = ProvenanceRecord(
        accessed_at="2026-05-31T10:00:00Z",
        content_hash="abc",
        published_date=None,
        revision=None,
    )
    out = record.model_dump(exclude_none=True)
    assert "published_date" not in out
    assert "revision" not in out
    assert out["accessed_at"] == "2026-05-31T10:00:00Z"
    assert out["content_hash"] == "abc"


def test_record_is_immutable_view_not_a_mutator() -> None:
    """Construction does not mutate the source dict (pure projection)."""

    meta = {
        "accessed_at": "2026-05-31T10:00:00Z",
        "content_hash": "abc",
    }
    snapshot = dict(meta)
    ProvenanceRecord.from_citation_metadata(meta)
    assert meta == snapshot


def test_construction_rejects_unknown_field() -> None:
    """Pydantic strict-ish: unknown keyword raises."""

    with pytest.raises(Exception):
        ProvenanceRecord(  # type: ignore[call-arg]
            accessed_at="x",
            content_hash="y",
            nonsense="oops",
        )


def test_verdict_match_minimal() -> None:
    """The simplest happy-path verdict only needs the two hashes and the recheck time."""

    from jw_core.provenance.models import ProvenanceVerdict

    v = ProvenanceVerdict(
        url="https://wol.jw.org/x",
        status="match",
        original_hash="abc",
        current_hash="abc",
        delta_chars=0,
        accessed_at_original="2026-05-30T10:00:00Z",
        accessed_at_recheck="2026-05-31T10:00:00Z",
    )
    assert v.status == "match"
    assert v.original_hash == v.current_hash
    assert v.nli_rerun is None
    assert v.notes == []


def test_verdict_changed_with_nli_rerun() -> None:
    """When NLI is available and content changed, we attach the new verdict."""

    from jw_core.provenance.models import ProvenanceVerdict

    v = ProvenanceVerdict(
        url="https://wol.jw.org/x",
        status="changed",
        original_hash="abc",
        current_hash="xyz",
        delta_chars=42,
        accessed_at_original="2026-05-30T10:00:00Z",
        accessed_at_recheck="2026-05-31T10:00:00Z",
        nli_rerun={"changed": True, "from": "entails", "to": "neutral", "score": 0.42},
        notes=["sha256 mismatch"],
    )
    assert v.status == "changed"
    assert v.nli_rerun is not None
    assert v.nli_rerun["from"] == "entails"


def test_verdict_unreachable_no_current_hash() -> None:
    """Network failure → status='unreachable', current_hash is None."""

    from jw_core.provenance.models import ProvenanceVerdict

    v = ProvenanceVerdict(
        url="https://wol.jw.org/x",
        status="unreachable",
        original_hash="abc",
        current_hash=None,
        delta_chars=None,
        accessed_at_original="2026-05-30T10:00:00Z",
        accessed_at_recheck="2026-05-31T10:00:00Z",
    )
    assert v.current_hash is None
    assert v.delta_chars is None


def test_verdict_no_record() -> None:
    """Citation lacked provenance keys altogether."""

    from jw_core.provenance.models import ProvenanceVerdict

    v = ProvenanceVerdict(
        url="https://wol.jw.org/x",
        status="no_record",
        original_hash=None,
        current_hash=None,
        delta_chars=None,
        accessed_at_original=None,
        accessed_at_recheck="2026-05-31T10:00:00Z",
    )
    assert v.status == "no_record"
    assert v.original_hash is None


def test_verdict_skipped_explanation() -> None:
    """`skipped` is what `check_since` emits when a citation is too recent."""

    from jw_core.provenance.models import ProvenanceVerdict

    v = ProvenanceVerdict(
        url="https://wol.jw.org/x",
        status="skipped",
        original_hash="abc",
        current_hash=None,
        delta_chars=None,
        accessed_at_original="2026-05-30T10:00:00Z",
        accessed_at_recheck="2026-05-31T10:00:00Z",
        notes=["accessed_at >= since threshold"],
    )
    assert v.status == "skipped"


def test_verdict_rejects_unknown_status() -> None:
    from jw_core.provenance.models import ProvenanceVerdict

    with pytest.raises(Exception):
        ProvenanceVerdict(
            url="https://wol.jw.org/x",
            status="bogus",  # type: ignore[arg-type]
            original_hash=None,
            current_hash=None,
            delta_chars=None,
            accessed_at_original=None,
            accessed_at_recheck="2026-05-31T10:00:00Z",
        )


def test_report_summarize_counts_statuses() -> None:
    from datetime import datetime

    from jw_core.provenance.models import ProvenanceReport, ProvenanceVerdict

    started = datetime(2026, 5, 31, 10, 0, 0)
    finished = datetime(2026, 5, 31, 10, 0, 5)
    verdicts = [
        ProvenanceVerdict(
            url=f"https://wol.jw.org/{i}",
            status=status,
            original_hash="abc",
            current_hash=None,
            delta_chars=None,
            accessed_at_original=None,
            accessed_at_recheck="2026-05-31T10:00:00Z",
        )
        for i, status in enumerate(["match", "match", "changed", "unreachable", "no_record"])
    ]
    report = ProvenanceReport(
        started_at=started,
        finished_at=finished,
        verdicts=verdicts,
        summary=ProvenanceReport.summarize(verdicts),
    )
    assert report.summary["match"] == 2
    assert report.summary["changed"] == 1
    assert report.summary["unreachable"] == 1
    assert report.summary["no_record"] == 1
    assert report.summary.get("skipped", 0) == 0


def test_report_round_trip_json() -> None:
    """Reports serialize cleanly — used by CLI --report json."""

    from datetime import datetime

    from jw_core.provenance.models import ProvenanceReport, ProvenanceVerdict

    started = datetime(2026, 5, 31, 10, 0, 0)
    finished = datetime(2026, 5, 31, 10, 0, 5)
    verdicts = [
        ProvenanceVerdict(
            url="https://wol.jw.org/x",
            status="match",
            original_hash="abc",
            current_hash="abc",
            delta_chars=0,
            accessed_at_original="2026-05-30T10:00:00Z",
            accessed_at_recheck="2026-05-31T10:00:00Z",
        )
    ]
    report = ProvenanceReport(
        started_at=started,
        finished_at=finished,
        verdicts=verdicts,
        summary=ProvenanceReport.summarize(verdicts),
    )
    raw = report.model_dump_json()
    rehydrated = ProvenanceReport.model_validate_json(raw)
    assert rehydrated.verdicts[0].status == "match"
