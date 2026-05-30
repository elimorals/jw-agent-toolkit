"""Pydantic models for citation integrity validation.

A `CitationCheck` is a per-URL diagnostic produced by `CitationValidator`.
A `CitationReport` aggregates all checks for one batch.

Verdict philosophy: `is_ok` is *lenient* — a redirect that ultimately lands
on 200 is "ok" structurally even if it generates a warning at the report
level. This keeps individual diagnostics binary while letting the summary
distinguish clean / warning / failed.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

ResolveStatus = Literal[
    "ok",
    "ok_redirect",
    "not_found",
    "gone",
    "server_error",
    "redirect_loop",
    "network_error",
    "skipped",
]

CatalogStatus = Literal[
    "ok",
    "mismatch",
    "missing",
    "unknown",
    "skipped",
]

DriftStatus = Literal[
    "ok",
    "drift",
    "no_snapshot",
    "skipped",
]


class CitationCheck(BaseModel):
    """Diagnostic for one URL."""

    url: str
    resolved_url: str | None = None
    redirect_chain: list[str] = Field(default_factory=list)
    http_status: int | None = None
    resolve: ResolveStatus = "skipped"

    # MEPS catalog cross-check (only meaningful when URL contains a docId)
    doc_id: int | None = None
    pub_code: str | None = None
    catalog: CatalogStatus = "unknown"

    # Snapshot drift (only meaningful in live+drift mode)
    drift: DriftStatus = "skipped"
    snapshot_path: str | None = None

    notes: list[str] = Field(default_factory=list)

    @property
    def is_ok(self) -> bool:
        return (
            self.resolve in {"ok", "ok_redirect", "skipped"}
            and self.catalog in {"ok", "unknown", "skipped"}
            and self.drift in {"ok", "no_snapshot", "skipped"}
        )


class CitationReport(BaseModel):
    """Aggregate report for a batch of CitationChecks."""

    mode: Literal["structural", "live", "live+drift"]
    checks: list[CitationCheck]
    summary: dict[str, int] = Field(default_factory=dict)

    @staticmethod
    def summarize(checks: list[CitationCheck]) -> dict[str, int]:
        agg = {"total": len(checks), "ok": 0, "warning": 0, "failed": 0}
        for c in checks:
            if not c.is_ok:
                agg["failed"] += 1
            elif c.resolve == "ok_redirect" or c.drift == "no_snapshot" or c.catalog == "missing":
                agg["warning"] += 1
            else:
                agg["ok"] += 1
        return agg
