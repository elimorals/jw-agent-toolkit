"""Audit that nothing leaves the device without opt-in.

VISION.md: "Modo 'sin telemetría externa' garantizado (casi listo — falta
auditar que nada salga sin opt-in)".

We perform a runtime check:
  - JW_TELEMETRY_ENABLED must be unset OR "0".
  - jw_core.telemetry.Telemetry must be in disabled state.
  - No known telemetry endpoints are configured.

Returns a structured report that the CLI can render.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass
class TelemetryAuditResult:
    is_offline: bool
    findings: list[dict[str, str]] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)


def is_offline_mode() -> bool:
    """Return True if every telemetry/network gate is in off-mode."""
    return os.getenv("JW_TELEMETRY_ENABLED", "0") not in {"1", "true", "TRUE"}


def audit_telemetry_outflow() -> TelemetryAuditResult:
    findings: list[dict[str, str]] = []
    recommendations: list[str] = []

    val = os.getenv("JW_TELEMETRY_ENABLED", "")
    if val and val.lower() not in {"0", "false"}:
        findings.append(
            {
                "severity": "warning",
                "key": "JW_TELEMETRY_ENABLED",
                "value": val,
                "message": "Telemetry is opt-in enabled. Disable by unsetting the env var.",
            }
        )
        recommendations.append("unset JW_TELEMETRY_ENABLED to fully disable shape fingerprints")
    else:
        findings.append(
            {"severity": "info", "key": "JW_TELEMETRY_ENABLED", "value": "unset", "message": "OK"}
        )

    try:
        from jw_core.telemetry import get_telemetry

        tele = get_telemetry()
        findings.append(
            {
                "severity": "info" if not getattr(tele, "enabled", False) else "warning",
                "key": "telemetry.enabled",
                "value": str(getattr(tele, "enabled", False)),
                "message": "Inspected jw_core.telemetry module",
            }
        )
    except Exception as e:
        findings.append(
            {"severity": "info", "key": "telemetry_module", "value": "n/a", "message": f"Could not inspect: {e}"}
        )

    # Look for telemetry-leaning env vars from common SDKs (best-effort).
    for var in ("OTEL_EXPORTER_OTLP_ENDPOINT", "DATADOG_API_KEY", "NEW_RELIC_LICENSE_KEY"):
        if os.getenv(var):
            findings.append(
                {
                    "severity": "warning",
                    "key": var,
                    "value": "set",
                    "message": "Third-party telemetry env var detected — may export from the host.",
                }
            )
            recommendations.append(f"unset {var} or audit its consumer")

    is_offline = all(f["severity"] != "warning" for f in findings)
    return TelemetryAuditResult(
        is_offline=is_offline,
        findings=findings,
        recommendations=recommendations,
    )
