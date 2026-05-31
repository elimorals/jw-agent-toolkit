"""Offline tests for scripts/live_smoke.py.

The script's PURPOSE is to hit jw.org for real, but its CODE must still
be testable offline so it lands in CI without flakiness. We do that by
injecting fake checks into the runner: the runner is provider-agnostic
(takes a dict of `name -> async callable(suite)`), so tests pass their
own checks that DON'T touch the network.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any

import pytest

# `scripts/` isn't a package — add it to sys.path so we can import.
_SCRIPTS = Path(__file__).resolve().parent.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import live_smoke  # noqa: E402


# ─── Fake suite — never touches jw.org ──────────────────────────────────


class _FakeSuite:
    """Stand-in for ClientSuite. Tests don't actually call its methods —
    they provide their own check functions that ignore the suite."""


@pytest.fixture
def fake_suite() -> _FakeSuite:
    return _FakeSuite()


# ─── run_smoke contract ─────────────────────────────────────────────────


async def _ok_check(_suite: Any) -> str:
    return "fake ok"


async def _failing_check(_suite: Any) -> str:
    raise RuntimeError("simulated failure")


async def _slow_check(_suite: Any) -> str:
    await asyncio.sleep(10)
    return "never"


@pytest.fixture
def patched_checks(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Replace live_smoke.CHECKS with deterministic fakes."""
    fakes: dict[str, Any] = {
        "ok_one": _ok_check,
        "ok_two": _ok_check,
    }
    monkeypatch.setattr(live_smoke, "CHECKS", fakes)
    # Also short-circuit build_clients so it can't accidentally do I/O.
    monkeypatch.setattr(live_smoke, "build_clients", lambda: _FakeSuite())
    return fakes


def test_run_smoke_all_green(patched_checks: dict[str, Any]) -> None:
    report = asyncio.run(live_smoke.run_smoke())
    assert report.overall_ok is True
    assert len(report.checks) == 2
    assert all(c.ok for c in report.checks)
    assert {c.name for c in report.checks} == {"ok_one", "ok_two"}


def test_run_smoke_mixed_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        live_smoke,
        "CHECKS",
        {"good": _ok_check, "bad": _failing_check},
    )
    monkeypatch.setattr(live_smoke, "build_clients", lambda: _FakeSuite())
    report = asyncio.run(live_smoke.run_smoke())
    assert report.overall_ok is False
    by_name = {c.name: c for c in report.checks}
    assert by_name["good"].ok is True
    assert by_name["bad"].ok is False
    assert "simulated failure" in (by_name["bad"].error or "")
    assert by_name["bad"].error is not None
    assert by_name["bad"].error.startswith("RuntimeError")


def test_run_smoke_respects_filter(patched_checks: dict[str, Any]) -> None:
    report = asyncio.run(live_smoke.run_smoke(only=["ok_one"]))
    assert len(report.checks) == 1
    assert report.checks[0].name == "ok_one"


def test_run_smoke_unknown_filter_returns_empty(
    patched_checks: dict[str, Any],
) -> None:
    report = asyncio.run(live_smoke.run_smoke(only=["nonexistent"]))
    assert report.overall_ok is False
    assert report.checks == []


def test_run_smoke_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(live_smoke, "CHECKS", {"slow": _slow_check})
    monkeypatch.setattr(live_smoke, "build_clients", lambda: _FakeSuite())
    report = asyncio.run(live_smoke.run_smoke(timeout=0.05))
    assert report.overall_ok is False
    assert report.checks[0].error is not None
    assert "Timeout" in report.checks[0].error


# ─── Report serialization ───────────────────────────────────────────────


def test_to_json_round_trip() -> None:
    rep = live_smoke.SmokeReport(
        timestamp_utc="2026-05-30T12:00:00+00:00",
        overall_ok=True,
        checks=[
            live_smoke.CheckResult(
                name="cdn.search", ok=True, duration_ms=123, detail="3 hits"
            ),
            live_smoke.CheckResult(
                name="pub_media",
                ok=False,
                duration_ms=42,
                detail="",
                error="HTTPError: 503",
            ),
        ],
    )
    data = json.loads(rep.to_json())
    assert data["overall_ok"] is True
    assert data["timestamp_utc"].startswith("2026-")
    assert len(data["checks"]) == 2
    failed = next(c for c in data["checks"] if c["name"] == "pub_media")
    assert failed["ok"] is False
    assert failed["error"] == "HTTPError: 503"


# ─── Built-in CHECKS contract ───────────────────────────────────────────


def test_builtin_checks_have_six_entries() -> None:
    """If someone adds a 7th client, this test reminds them to register
    it in the live smoke and in the CI workflow."""
    expected = {
        "cdn.search",
        "wol.homepage",
        "mediator.languages",
        "pub_media",
        "topic_index.search",
        "weblang",
    }
    assert set(live_smoke.CHECKS.keys()) == expected


def test_builtin_checks_are_coroutines() -> None:
    import inspect

    for name, fn in live_smoke.CHECKS.items():
        assert inspect.iscoroutinefunction(fn), f"{name} is not async"
