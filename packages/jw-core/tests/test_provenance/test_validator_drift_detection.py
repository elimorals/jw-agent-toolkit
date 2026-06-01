"""When a citation drifts, validator emits a `provenance_drift` telemetry event.

Mirrors the Fase 9 opt-in pattern: nothing is written unless
JW_TELEMETRY_ENABLED is set.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from jw_agents.base import Citation
from jw_core.provenance.hashing import content_sha256
from jw_core.provenance.validator import FetcherResponse, ProvenanceValidator


class _Fake:
    def __init__(self, body: str) -> None:
        self._body = body

    async def __call__(self, url: str) -> FetcherResponse:
        return FetcherResponse(final_url=url, status=200, body=self._body)


async def test_drift_writes_provenance_drift_event_when_telemetry_on(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    telemetry_path = tmp_path / "telemetry.json"
    monkeypatch.setenv("JW_TELEMETRY_ENABLED", "1")
    monkeypatch.setenv("JW_TELEMETRY_PATH", str(telemetry_path))

    import jw_core.telemetry as tel

    tel._singleton = None  # noqa: SLF001

    body_orig = "Original Jehová body"
    body_new = "Edited Jehová body"
    cit = Citation(
        url="https://wol.jw.org/x",
        metadata={
            "accessed_at": "2026-05-30T10:00:00Z",
            "content_hash": content_sha256(body_orig),
        },
    )

    validator = ProvenanceValidator(fetcher=_Fake(body_new))
    verdict = await validator.check(cit)
    assert verdict.status == "changed"

    assert telemetry_path.exists()
    data = json.loads(telemetry_path.read_text(encoding="utf-8"))
    events = data.get("provenance_events", []) + data.get("drift_events", [])
    assert any(
        e.get("kind") == "provenance_drift" or e.get("endpoint") == "provenance_drift"
        for e in events
    )


async def test_no_telemetry_when_disabled(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    telemetry_path = tmp_path / "telemetry.json"
    monkeypatch.delenv("JW_TELEMETRY_ENABLED", raising=False)
    monkeypatch.setenv("JW_TELEMETRY_PATH", str(telemetry_path))

    import jw_core.telemetry as tel

    tel._singleton = None  # noqa: SLF001

    cit = Citation(
        url="https://wol.jw.org/x",
        metadata={
            "accessed_at": "2026-05-30T10:00:00Z",
            "content_hash": content_sha256("x"),
        },
    )
    validator = ProvenanceValidator(fetcher=_Fake("y"))
    await validator.check(cit)

    assert not telemetry_path.exists()
