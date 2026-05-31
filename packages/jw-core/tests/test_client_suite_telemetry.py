"""Tests that ClientSuite exposes the shared Telemetry instance.

Regression for bug found by eval (Fase 22+) calibration:
`news_monitor` reads `clients.telemetry` to wire a side-channel client
(JWBroadcastingClient) — but `ClientSuite` only exposed `throttler` and
`cache`, raising `AttributeError`. This test pins the contract.
"""

from __future__ import annotations

from jw_core.clients.factory import build_clients
from jw_core.telemetry import Telemetry


def test_client_suite_exposes_telemetry() -> None:
    """The factory bundle must expose .telemetry alongside .throttler/.cache."""

    suite = build_clients(enable_throttling=False, enable_cache=False)
    try:
        assert hasattr(suite, "telemetry"), (
            "ClientSuite must expose `.telemetry` so downstream callers "
            "(e.g. news_monitor wiring JWBroadcastingClient) can pass the "
            "shared Telemetry instance to ad-hoc clients."
        )
        # When enable_telemetry is None (default), telemetry is None unless
        # JW_TELEMETRY_ENABLED=1 — but the attribute must exist regardless.
        assert suite.telemetry is None or isinstance(suite.telemetry, Telemetry)
    finally:
        # ClientSuite.aclose is async; we built without cache so no DB file
        # was opened. Closing throttler/clients here would need an event
        # loop; the dataclass holds nothing that leaks file descriptors
        # under enable_cache=False, so we just drop the reference.
        del suite
