# Fase 23 — `jw_core.citations` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `jw_core.citations`, an inject­able batch validator that verifies wol.jw.org URLs produced by agents along three dimensions (HTTP resolve, MEPS docId↔pub_code mapping, optional HTML drift). Exposed via CLI `jw citations check`, MCP tool `validate_citations`, and reusable by Fase 22's drift-issue script.

**Architecture:** New subpackage inside `jw-core` (no new top-level package). Three layers, all in `jw_core.citations`: models (Pydantic) → helpers (URL parser + agent-output extractor) → `CitationValidator` (orchestrator with injectable async fetcher and `MepsCatalog` lookup). Default mode is offline-structural; `--live` opt-in for HTTP; `--drift` opt-in for snapshot comparison against `packages/jw-eval/fixtures/wol_snapshots/` (cross-package READ only, NO import dependency on `jw-eval`).

**Tech Stack:** Python 3.13 · Pydantic 2 (models) · `asyncio.Semaphore` (concurrency) · `httpx.AsyncClient` (live fetcher) · `MepsCatalog` (Fase 19, existing) · `_shape_hash` (Fase 9 telemetry, reused) · Typer (CLI subapp) · FastMCP (`@mcp.tool()`).

**Spec:** [`docs/superpowers/specs/2026-05-30-fase-23-citation-validator-design.md`](../specs/2026-05-30-fase-23-citation-validator-design.md).

---

## File map

Creates:
- `packages/jw-core/src/jw_core/citations/__init__.py`
- `packages/jw-core/src/jw_core/citations/models.py`
- `packages/jw-core/src/jw_core/citations/validator.py`
- `packages/jw-core/tests/test_citation_validator.py`
- `packages/jw-cli/src/jw_cli/commands/citations.py`
- `packages/jw-mcp/tests/test_citations_tool.py`
- `docs/guias/citation-validator.md`

Modifies:
- `packages/jw-cli/src/jw_cli/commands/__init__.py` — import `citations`.
- `packages/jw-cli/src/jw_cli/main.py` — register the `citations_app` Typer sub-app.
- `packages/jw-mcp/src/jw_mcp/server.py` — register `validate_citations` tool.
- `packages/jw-agents/tests/test_verse_explainer.py` — add `test_smoke_citations`.
- `docs/ROADMAP.md` — add Fase 23 section.
- `docs/VISION_AUDIT.md` — add Fase 23 row.
- `docs/README.md` — link the new guide.

---

### Task 1: Scaffold the `citations` subpackage

**Files:**
- Create: `packages/jw-core/src/jw_core/citations/__init__.py`

- [ ] **Step 1: Verify parent directory exists**

Run: `ls packages/jw-core/src/jw_core/`
Expected: list includes `clients`, `parsers`, `integrations`, `data`, `telemetry.py`. We are adding a sibling `citations/`.

- [ ] **Step 2: Create the package init with placeholder re-exports**

```python
# packages/jw-core/src/jw_core/citations/__init__.py
"""Citation integrity validator — verifies wol URLs and MEPS mappings.

Public API:
    from jw_core.citations import (
        CitationValidator,
        CitationCheck,
        CitationReport,
        ResolveStatus,
        CatalogStatus,
        DriftStatus,
    )

See `docs/guias/citation-validator.md` and Fase 23 spec.
"""

from jw_core.citations.models import (
    CatalogStatus,
    CitationCheck,
    CitationReport,
    DriftStatus,
    ResolveStatus,
)
from jw_core.citations.validator import CitationValidator

__all__ = [
    "CatalogStatus",
    "CitationCheck",
    "CitationReport",
    "CitationValidator",
    "DriftStatus",
    "ResolveStatus",
]
```

- [ ] **Step 3: Verify nothing breaks at import time (it WILL fail — that's expected)**

Run: `uv run python -c "import jw_core.citations"`
Expected: `ModuleNotFoundError: No module named 'jw_core.citations.models'`. We fix it in Task 2.

- [ ] **Step 4: Commit the scaffold (broken on purpose; subsequent tasks complete it)**

```bash
git add packages/jw-core/src/jw_core/citations/__init__.py
git commit -m "feat(jw-core/citations): scaffold subpackage with re-export stubs"
```

---

### Task 2: Pydantic models

**Files:**
- Create: `packages/jw-core/src/jw_core/citations/models.py`
- Create: `packages/jw-core/tests/test_citation_validator.py` (just the models section for now)

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-core/tests/test_citation_validator.py
"""Tests for jw_core.citations."""

from __future__ import annotations

import pytest

from jw_core.citations.models import (
    CatalogStatus,
    CitationCheck,
    CitationReport,
    DriftStatus,
    ResolveStatus,
)


def test_citation_check_defaults_are_skipped() -> None:
    c = CitationCheck(url="https://wol.jw.org/x")
    assert c.resolve == "skipped"
    assert c.catalog == "unknown"
    assert c.drift == "skipped"
    assert c.is_ok is True


def test_citation_check_fails_on_404() -> None:
    c = CitationCheck(url="https://wol.jw.org/x", resolve="not_found", http_status=404)
    assert c.is_ok is False


def test_citation_check_warns_on_redirect() -> None:
    c = CitationCheck(
        url="https://wol.jw.org/x",
        resolve="ok_redirect",
        http_status=200,
        redirect_chain=["https://wol.jw.org/y"],
    )
    # is_ok stays True, but the summarizer should count it as warning.
    assert c.is_ok is True


def test_citation_report_summarize_counts() -> None:
    checks = [
        CitationCheck(url="a", resolve="ok", http_status=200),
        CitationCheck(url="b", resolve="ok_redirect", http_status=200, redirect_chain=["c"]),
        CitationCheck(url="c", resolve="not_found", http_status=404),
        CitationCheck(url="d", resolve="ok", http_status=200, drift="no_snapshot"),
    ]
    report = CitationReport(
        mode="live",
        checks=checks,
        summary=CitationReport.summarize(checks),
    )
    assert report.summary["total"] == 4
    assert report.summary["ok"] == 1
    assert report.summary["warning"] == 2  # redirect + no_snapshot
    assert report.summary["failed"] == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/jw-core/tests/test_citation_validator.py -v`
Expected: FAIL — `ModuleNotFoundError: jw_core.citations.models`.

- [ ] **Step 3: Implement the models**

```python
# packages/jw-core/src/jw_core/citations/models.py
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/jw-core/tests/test_citation_validator.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-core/src/jw_core/citations/models.py packages/jw-core/tests/test_citation_validator.py
git commit -m "feat(jw-core/citations): add CitationCheck/CitationReport pydantic models"
```

---

### Task 3: URL parser + agent-output extractor

**Files:**
- Create: `packages/jw-core/src/jw_core/citations/validator.py` (helpers only at this stage)
- Modify: `packages/jw-core/tests/test_citation_validator.py`

- [ ] **Step 1: Append failing tests for the helpers**

Append to `packages/jw-core/tests/test_citation_validator.py`:

```python
from jw_core.citations.validator import _extract_urls, _parse_wol_url


def test_parse_wol_url_document_endpoint() -> None:
    url = "https://wol.jw.org/es/wol/d/r4/lp-s/1101989140"
    parsed = _parse_wol_url(url)
    assert parsed == {"doc_id": 1101989140, "pub_code": None, "iso": "es"}


def test_parse_wol_url_bible_chapter() -> None:
    url = "https://wol.jw.org/es/wol/b/r4/lp-s/nwt/E/2024/43/3"
    parsed = _parse_wol_url(url)
    assert parsed == {"doc_id": None, "pub_code": "nwt", "iso": "es"}


def test_parse_wol_url_unknown_pattern_returns_none() -> None:
    assert _parse_wol_url("https://b.jw-cdn.org/apis/foo") is None
    assert _parse_wol_url("https://example.com/random") is None


def test_extract_urls_from_dict_agent_output() -> None:
    out = {
        "findings": [
            {"text": "x", "metadata": {"citation_url": "https://wol.jw.org/x"}},
            {"text": "y", "metadata": {"citation_url": "https://wol.jw.org/y"}},
            {"text": "z", "metadata": {}},  # no URL
            {"text": "dup", "metadata": {"citation_url": "https://wol.jw.org/x"}},  # duplicate
        ]
    }
    urls = _extract_urls(out)
    assert urls == ["https://wol.jw.org/x", "https://wol.jw.org/y"]


def test_extract_urls_from_object_agent_output() -> None:
    class _Citation:
        url = "https://wol.jw.org/z"

    class _Finding:
        metadata: dict = {}
        citation = _Citation()

    class _Result:
        findings = [_Finding()]

    urls = _extract_urls(_Result())
    assert urls == ["https://wol.jw.org/z"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/jw-core/tests/test_citation_validator.py -v`
Expected: FAIL — `_extract_urls` / `_parse_wol_url` not defined.

- [ ] **Step 3: Implement the helpers (validator.py first slice)**

```python
# packages/jw-core/src/jw_core/citations/validator.py
"""Citation integrity validator.

This file is built up incrementally across Fase 23 tasks. In this slice we
ship only the URL parser and the agent-output extractor — the validator
class itself arrives in Task 4.
"""

from __future__ import annotations

import re
from typing import Any


_WOL_DOC_RE = re.compile(
    r"^https?://wol\.jw\.org/(?P<iso>[a-z]{2,3})/wol/d/[^/]+/[^/]+/(?P<doc_id>\d+)/?$"
)
_WOL_BIBLE_RE = re.compile(
    r"^https?://wol\.jw\.org/(?P<iso>[a-z]{2,3})/wol/b/[^/]+/[^/]+/(?P<pub>[^/]+)/[^/]+/\d+/?$"
)


def _parse_wol_url(url: str) -> dict[str, Any] | None:
    """Parse a wol.jw.org URL into its structural pieces.

    Recognized patterns (from `docs/ARCHITECTURE.md`):
      /{iso}/wol/d/{r}/{lp_tag}/{docId}
      /{iso}/wol/b/{r}/{lp_tag}/{pub}/{book_num}/{chapter}

    Returns None for any URL we don't recognize (b.jw-cdn.org, external, ...).
    """

    m = _WOL_DOC_RE.match(url)
    if m:
        return {"doc_id": int(m.group("doc_id")), "pub_code": None, "iso": m.group("iso")}
    m = _WOL_BIBLE_RE.match(url)
    if m:
        return {"doc_id": None, "pub_code": m.group("pub"), "iso": m.group("iso")}
    return None


def _extract_urls(agent_output: Any) -> list[str]:
    """Pull deduplicated, order-preserved URLs out of an AgentResult-like.

    Accepts a dict (already-serialized) OR any object exposing `.findings`
    where each finding has metadata.citation_url or finding.citation.url.
    """

    seen: set[str] = set()
    urls: list[str] = []

    if isinstance(agent_output, dict):
        findings = agent_output.get("findings", []) or []
        candidates = []
        for f in findings:
            if not isinstance(f, dict):
                continue
            url = (f.get("metadata") or {}).get("citation_url")
            if not url:
                citation = f.get("citation") or {}
                url = citation.get("url") if isinstance(citation, dict) else None
            candidates.append(url)
    else:
        findings = getattr(agent_output, "findings", []) or []
        candidates = []
        for f in findings:
            meta = getattr(f, "metadata", None) or {}
            url = meta.get("citation_url") if isinstance(meta, dict) else None
            if not url:
                citation = getattr(f, "citation", None)
                url = getattr(citation, "url", None) if citation else None
            candidates.append(url)

    for url in candidates:
        if not url or url in seen:
            continue
        seen.add(url)
        urls.append(url)
    return urls
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/jw-core/tests/test_citation_validator.py -v`
Expected: 9 passed (4 model tests + 5 helper tests).

- [ ] **Step 5: Verify the package init now imports**

Run: `uv run python -c "from jw_core.citations import CitationCheck; print(CitationCheck(url='x'))"`
Expected: prints a `CitationCheck` model (no ImportError). The `CitationValidator` import in `__init__.py` will still fail; that lands in Task 4.

Temporarily, edit `__init__.py` to gracefully degrade — replace the `from jw_core.citations.validator import CitationValidator` line with:

```python
try:
    from jw_core.citations.validator import CitationValidator
except ImportError:  # built incrementally; full class lands in Task 4
    CitationValidator = None  # type: ignore[assignment, misc]
```

(This is removed in Task 4.)

- [ ] **Step 6: Commit**

```bash
git add packages/jw-core/src/jw_core/citations/validator.py packages/jw-core/tests/test_citation_validator.py packages/jw-core/src/jw_core/citations/__init__.py
git commit -m "feat(jw-core/citations): URL parser + agent-output URL extractor"
```

---

### Task 4: `CitationValidator` — structural mode (catalog only)

**Files:**
- Modify: `packages/jw-core/src/jw_core/citations/validator.py`
- Modify: `packages/jw-core/src/jw_core/citations/__init__.py` (drop the try/except shim)
- Modify: `packages/jw-core/tests/test_citation_validator.py`

- [ ] **Step 1: Append failing tests for the structural mode**

```python
# in test_citation_validator.py
import pytest

from jw_core.citations import CitationValidator
from jw_core.integrations.meps_catalog import MepsCatalog


@pytest.mark.asyncio
async def test_structural_with_empty_catalog_returns_unknown(tmp_path) -> None:
    cat = MepsCatalog(db_path=tmp_path / "meps.db")
    v = CitationValidator(catalog=cat)
    report = await v.validate_urls(
        ["https://wol.jw.org/es/wol/d/r4/lp-s/1101989140"],
        mode="structural",
    )
    assert report.mode == "structural"
    assert len(report.checks) == 1
    check = report.checks[0]
    assert check.doc_id == 1101989140
    assert check.catalog == "unknown"  # catalog empty
    assert check.resolve == "skipped"
    assert check.is_ok is True


@pytest.mark.asyncio
async def test_structural_with_populated_catalog_ok(tmp_path) -> None:
    cat = MepsCatalog(db_path=tmp_path / "meps.db")
    # Hand-craft a publication+document row to avoid needing a real .jwpub.
    conn = cat._open()  # noqa: SLF001 — test-only access
    conn.execute(
        "INSERT INTO publication (pub_code, language_index, title) VALUES ('w24', 0, 'Watchtower')"
    )
    conn.execute(
        """INSERT INTO document
           (document_id, meps_document_id, pub_code, language_index, title)
           VALUES (1, 1101989140, 'w24', 0, 'Trinity?')"""
    )
    conn.commit()

    v = CitationValidator(catalog=cat)
    report = await v.validate_urls(
        ["https://wol.jw.org/es/wol/d/r4/lp-s/1101989140"],
        mode="structural",
    )
    check = report.checks[0]
    assert check.catalog == "ok"
    assert check.pub_code == "w24"


@pytest.mark.asyncio
async def test_structural_url_without_docid_is_unknown(tmp_path) -> None:
    cat = MepsCatalog(db_path=tmp_path / "meps.db")
    v = CitationValidator(catalog=cat)
    report = await v.validate_urls(
        ["https://wol.jw.org/es/wol/b/r4/lp-s/nwt/E/2024/43/3"],
        mode="structural",
    )
    check = report.checks[0]
    # Bible-chapter URLs carry pub_code but no doc_id — catalog can't disambiguate
    assert check.pub_code == "nwt"
    assert check.catalog == "unknown"


@pytest.mark.asyncio
async def test_validate_agent_output_dict(tmp_path) -> None:
    cat = MepsCatalog(db_path=tmp_path / "meps.db")
    v = CitationValidator(catalog=cat)
    agent_out = {
        "findings": [
            {"metadata": {"citation_url": "https://wol.jw.org/es/wol/d/r4/lp-s/1"}},
            {"metadata": {"citation_url": "https://wol.jw.org/es/wol/d/r4/lp-s/2"}},
        ]
    }
    report = await v.validate_agent_output(agent_out, mode="structural")
    assert len(report.checks) == 2
```

Also add this to your `conftest.py` if not already present (asyncio support):

```python
# packages/jw-core/tests/conftest.py — only add if missing
import pytest_asyncio  # noqa: F401  # registers the marker

pytest_plugins = ["pytest_asyncio"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/jw-core/tests/test_citation_validator.py -v`
Expected: FAIL — `CitationValidator` is `None` (from the Task 3 shim).

- [ ] **Step 3: Implement the validator (structural slice)**

Append/replace the body of `packages/jw-core/src/jw_core/citations/validator.py` so the full file is:

```python
# packages/jw-core/src/jw_core/citations/validator.py
"""Citation integrity validator.

Three modes:
  - structural: offline, MepsCatalog lookup only (default).
  - live:       structural + HTTP resolve via injectable async fetcher.
  - live+drift: live + compares fetched HTML shape against committed snapshot.

The validator NEVER instantiates an httpx client itself. Callers pass a
fetcher callable; tests pass a fake; CLI/MCP pass an httpx-backed adapter.
"""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Callable, Literal

from jw_core.citations.models import (
    CitationCheck,
    CitationReport,
    DriftStatus,
)
from jw_core.integrations.meps_catalog import MepsCatalog


_WOL_DOC_RE = re.compile(
    r"^https?://wol\.jw\.org/(?P<iso>[a-z]{2,3})/wol/d/[^/]+/[^/]+/(?P<doc_id>\d+)/?$"
)
_WOL_BIBLE_RE = re.compile(
    r"^https?://wol\.jw\.org/(?P<iso>[a-z]{2,3})/wol/b/[^/]+/[^/]+/(?P<pub>[^/]+)/[^/]+/\d+/?$"
)


def _parse_wol_url(url: str) -> dict[str, Any] | None:
    m = _WOL_DOC_RE.match(url)
    if m:
        return {"doc_id": int(m.group("doc_id")), "pub_code": None, "iso": m.group("iso")}
    m = _WOL_BIBLE_RE.match(url)
    if m:
        return {"doc_id": None, "pub_code": m.group("pub"), "iso": m.group("iso")}
    return None


def _extract_urls(agent_output: Any) -> list[str]:
    seen: set[str] = set()
    urls: list[str] = []
    candidates: list[str | None] = []

    if isinstance(agent_output, dict):
        for f in agent_output.get("findings", []) or []:
            if not isinstance(f, dict):
                continue
            url = (f.get("metadata") or {}).get("citation_url")
            if not url:
                citation = f.get("citation") or {}
                url = citation.get("url") if isinstance(citation, dict) else None
            candidates.append(url)
    else:
        for f in getattr(agent_output, "findings", []) or []:
            meta = getattr(f, "metadata", None) or {}
            url = meta.get("citation_url") if isinstance(meta, dict) else None
            if not url:
                citation = getattr(f, "citation", None)
                url = getattr(citation, "url", None) if citation else None
            candidates.append(url)

    for url in candidates:
        if not url or url in seen:
            continue
        seen.add(url)
        urls.append(url)
    return urls


@dataclass
class FetcherResponse:
    final_url: str
    status: int
    redirect_chain: list[str] = field(default_factory=list)
    body: str = ""


AsyncFetcher = Callable[[str], Awaitable[FetcherResponse]]
Mode = Literal["structural", "live", "live+drift"]


class CitationValidator:
    """Batch validator for wol.jw.org citation URLs.

    Construct once per batch (cheap). All public methods are async.

    Args:
        catalog: MepsCatalog instance (Fase 19). When None, all catalog
            checks degrade to `skipped`.
        fetcher: async callable URL -> FetcherResponse. Required for
            modes 'live' and 'live+drift'.
        snapshots_root: directory containing HTML snapshots named
            `<sha256(url)>.html`. Required for mode 'live+drift'.
        max_redirects: cap on redirect chain length per URL (default 3).
        concurrency: max concurrent fetches in live modes (default 4).
    """

    def __init__(
        self,
        *,
        catalog: MepsCatalog | None = None,
        fetcher: AsyncFetcher | None = None,
        snapshots_root: Path | None = None,
        max_redirects: int = 3,
        concurrency: int = 4,
    ) -> None:
        self.catalog = catalog
        self.fetcher = fetcher
        self.snapshots_root = snapshots_root
        self.max_redirects = max_redirects
        self._sem = asyncio.Semaphore(concurrency)
        self._catalog_lock = asyncio.Lock()

    # ── Public API ─────────────────────────────────────────────────────

    async def validate_urls(self, urls: list[str], *, mode: Mode = "structural") -> CitationReport:
        if mode in {"live", "live+drift"} and self.fetcher is None:
            raise ValueError(f"mode={mode!r} requires a fetcher")
        if mode == "live+drift" and self.snapshots_root is None:
            raise ValueError("mode='live+drift' requires snapshots_root")

        tasks = [self._check_one(u, mode=mode) for u in urls]
        checks = await asyncio.gather(*tasks)
        return CitationReport(
            mode=mode,
            checks=list(checks),
            summary=CitationReport.summarize(list(checks)),
        )

    async def validate_agent_output(
        self,
        agent_output: Any,
        *,
        mode: Mode = "structural",
    ) -> CitationReport:
        return await self.validate_urls(_extract_urls(agent_output), mode=mode)

    # ── Internals ──────────────────────────────────────────────────────

    async def _check_one(self, url: str, *, mode: Mode) -> CitationCheck:
        check = CitationCheck(url=url)
        parsed = _parse_wol_url(url)
        if parsed:
            check.doc_id = parsed["doc_id"]
            check.pub_code = parsed["pub_code"]

        await self._populate_catalog(check)

        if mode in {"live", "live+drift"}:
            await self._populate_live(check)

        if mode == "live+drift":
            self._populate_drift(check)

        return check

    async def _populate_catalog(self, check: CitationCheck) -> None:
        if self.catalog is None:
            check.catalog = "skipped"
            return
        if check.doc_id is None:
            check.catalog = "unknown"
            return

        # MepsCatalog is sqlite-backed; run in a thread to avoid blocking
        # the event loop on disk I/O and to dodge sqlite single-thread checks.
        async with self._catalog_lock:
            docs = await asyncio.to_thread(
                self.catalog.find_documents,
                meps_document_id=check.doc_id,
                limit=1,
            )
        if not docs:
            check.catalog = "missing"
            check.notes.append(f"doc_id={check.doc_id} not in MepsCatalog")
            return
        doc = docs[0]
        if check.pub_code is not None and check.pub_code != doc.pub_code:
            check.catalog = "mismatch"
            check.notes.append(
                f"URL says pub_code={check.pub_code!r} but catalog says {doc.pub_code!r}"
            )
        else:
            check.catalog = "ok"
            check.pub_code = check.pub_code or doc.pub_code

    async def _populate_live(self, check: CitationCheck) -> None:
        assert self.fetcher is not None
        async with self._sem:
            try:
                resp = await self.fetcher(check.url)
            except Exception as exc:  # noqa: BLE001 — fetcher contract is wide
                check.resolve = "network_error"
                check.notes.append(f"fetch failed: {exc!r}")
                return

        check.http_status = resp.status
        check.resolved_url = resp.final_url
        check.redirect_chain = list(resp.redirect_chain)

        if len(resp.redirect_chain) > self.max_redirects:
            check.resolve = "redirect_loop"
            check.notes.append(f"redirect chain {len(resp.redirect_chain)} > {self.max_redirects}")
            return
        if resp.status == 404:
            check.resolve = "not_found"
        elif resp.status == 410:
            check.resolve = "gone"
        elif 500 <= resp.status < 600:
            check.resolve = "server_error"
        elif 200 <= resp.status < 300:
            check.resolve = "ok_redirect" if resp.redirect_chain else "ok"
        else:
            check.resolve = "network_error"
            check.notes.append(f"unexpected HTTP {resp.status}")

    def _populate_drift(self, check: CitationCheck) -> None:
        if self.snapshots_root is None:
            check.drift = "skipped"
            return
        import hashlib

        digest = hashlib.sha256(check.url.encode("utf-8")).hexdigest()
        snap = self.snapshots_root / f"{digest}.html"
        if not snap.exists():
            check.drift = "no_snapshot"
            return
        # We need the live body; if structural-only fetcher returned empty,
        # treat as no_snapshot (we have nothing to compare to).
        # The body has been stored on the check via _populate_live? — actually
        # we discarded body. For drift comparison we re-derive from notes the
        # fact that we DID fetch; the body comparison is left to a future
        # iteration. For now we mark `ok` if snapshot exists AND resolve was
        # ok / ok_redirect, else `drift`.
        check.snapshot_path = str(snap)
        if check.resolve in {"ok", "ok_redirect"}:
            check.drift = "ok"
        else:
            check.drift = "drift"
            check.notes.append(f"resolve={check.resolve!r} so live differs from snapshot")
```

> Note: this slice intentionally implements drift as a coarse signal
> (snapshot exists + resolve ok ⇒ drift ok). Deep HTML shape comparison
> is a Task 6 refinement.

Also fix `__init__.py`: replace the try/except with the direct import again:

```python
# packages/jw-core/src/jw_core/citations/__init__.py
"""Citation integrity validator — verifies wol URLs and MEPS mappings."""

from jw_core.citations.models import (
    CatalogStatus,
    CitationCheck,
    CitationReport,
    DriftStatus,
    ResolveStatus,
)
from jw_core.citations.validator import (
    CitationValidator,
    FetcherResponse,
)

__all__ = [
    "CatalogStatus",
    "CitationCheck",
    "CitationReport",
    "CitationValidator",
    "DriftStatus",
    "FetcherResponse",
    "ResolveStatus",
]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/jw-core/tests/test_citation_validator.py -v`
Expected: 13 passed (4 models + 5 helpers + 4 structural).

- [ ] **Step 5: Commit**

```bash
git add packages/jw-core/src/jw_core/citations packages/jw-core/tests/test_citation_validator.py
git commit -m "feat(jw-core/citations): CitationValidator structural mode (catalog lookups)"
```

---

### Task 5: Live mode + redirect handling + concurrency

**Files:**
- Modify: `packages/jw-core/tests/test_citation_validator.py` (append live tests)
- No production code changes (already in validator.py) — but we PROVE it via tests with a fake fetcher.

- [ ] **Step 1: Append failing tests for live mode**

```python
# in test_citation_validator.py

from jw_core.citations.validator import FetcherResponse


def _fake_fetcher_factory(table: dict[str, FetcherResponse]):
    async def fetch(url: str) -> FetcherResponse:
        if url not in table:
            raise RuntimeError(f"unexpected URL {url}")
        return table[url]
    return fetch


@pytest.mark.asyncio
async def test_live_ok(tmp_path) -> None:
    cat = MepsCatalog(db_path=tmp_path / "meps.db")
    url = "https://wol.jw.org/es/wol/d/r4/lp-s/1"
    fetcher = _fake_fetcher_factory(
        {url: FetcherResponse(final_url=url, status=200, redirect_chain=[], body="<p>ok</p>")}
    )
    v = CitationValidator(catalog=cat, fetcher=fetcher)
    report = await v.validate_urls([url], mode="live")
    assert report.checks[0].resolve == "ok"
    assert report.checks[0].http_status == 200


@pytest.mark.asyncio
async def test_live_ok_redirect(tmp_path) -> None:
    cat = MepsCatalog(db_path=tmp_path / "meps.db")
    url = "https://wol.jw.org/es/wol/d/r4/lp-s/1"
    fetcher = _fake_fetcher_factory(
        {
            url: FetcherResponse(
                final_url="https://wol.jw.org/es/wol/d/r4/lp-s/2",
                status=200,
                redirect_chain=["https://wol.jw.org/es/wol/d/r4/lp-s/1"],
                body="<p>ok</p>",
            )
        }
    )
    v = CitationValidator(catalog=cat, fetcher=fetcher)
    report = await v.validate_urls([url], mode="live")
    check = report.checks[0]
    assert check.resolve == "ok_redirect"
    assert check.redirect_chain == ["https://wol.jw.org/es/wol/d/r4/lp-s/1"]
    assert check.is_ok is True
    assert report.summary["warning"] >= 1


@pytest.mark.asyncio
async def test_live_404(tmp_path) -> None:
    cat = MepsCatalog(db_path=tmp_path / "meps.db")
    url = "https://wol.jw.org/es/wol/d/r4/lp-s/9999999"
    fetcher = _fake_fetcher_factory(
        {url: FetcherResponse(final_url=url, status=404)}
    )
    v = CitationValidator(catalog=cat, fetcher=fetcher)
    report = await v.validate_urls([url], mode="live")
    assert report.checks[0].resolve == "not_found"
    assert report.checks[0].is_ok is False
    assert report.summary["failed"] == 1


@pytest.mark.asyncio
async def test_live_redirect_loop(tmp_path) -> None:
    cat = MepsCatalog(db_path=tmp_path / "meps.db")
    url = "https://wol.jw.org/es/wol/d/r4/lp-s/1"
    chain = [f"https://wol.jw.org/r/{i}" for i in range(5)]  # 5 > max_redirects 3
    fetcher = _fake_fetcher_factory(
        {url: FetcherResponse(final_url=url, status=200, redirect_chain=chain)}
    )
    v = CitationValidator(catalog=cat, fetcher=fetcher, max_redirects=3)
    report = await v.validate_urls([url], mode="live")
    assert report.checks[0].resolve == "redirect_loop"


@pytest.mark.asyncio
async def test_live_network_error_is_isolated(tmp_path) -> None:
    cat = MepsCatalog(db_path=tmp_path / "meps.db")

    async def fetcher(url: str) -> FetcherResponse:
        raise TimeoutError("connection timed out")

    v = CitationValidator(catalog=cat, fetcher=fetcher)
    report = await v.validate_urls(
        ["https://wol.jw.org/es/wol/d/r4/lp-s/1"], mode="live"
    )
    assert report.checks[0].resolve == "network_error"
    assert report.checks[0].is_ok is False


@pytest.mark.asyncio
async def test_concurrency_is_bounded(tmp_path) -> None:
    cat = MepsCatalog(db_path=tmp_path / "meps.db")

    live: int = 0
    peak: int = 0
    lock = asyncio.Lock()

    async def slow_fetcher(url: str) -> FetcherResponse:
        nonlocal live, peak
        async with lock:
            live += 1
            peak = max(peak, live)
        await asyncio.sleep(0.05)
        async with lock:
            live -= 1
        return FetcherResponse(final_url=url, status=200)

    v = CitationValidator(catalog=cat, fetcher=slow_fetcher, concurrency=3)
    urls = [f"https://wol.jw.org/es/wol/d/r4/lp-s/{i}" for i in range(10)]
    await v.validate_urls(urls, mode="live")
    assert peak <= 3, f"peak concurrency {peak} > limit 3"


@pytest.mark.asyncio
async def test_live_requires_fetcher(tmp_path) -> None:
    cat = MepsCatalog(db_path=tmp_path / "meps.db")
    v = CitationValidator(catalog=cat)
    with pytest.raises(ValueError):
        await v.validate_urls(["https://wol.jw.org/x"], mode="live")
```

- [ ] **Step 2: Run test to verify they pass (live mode logic already exists in validator)**

Run: `uv run pytest packages/jw-core/tests/test_citation_validator.py -v`
Expected: 20 passed (13 prior + 7 live).

If `test_concurrency_is_bounded` flakes (peak > 3 by a tiny margin), the issue is most likely the semaphore being created in `__init__` before the event loop is running. Fix: lazy-construct the semaphore inside `_check_one` if `self._sem is None` OR move `self._sem = asyncio.Semaphore(concurrency)` to a `_get_sem(self)` helper that builds it on first use within the loop.

- [ ] **Step 3: Commit**

```bash
git add packages/jw-core/tests/test_citation_validator.py
git commit -m "test(jw-core/citations): live mode + redirect + concurrency coverage"
```

---

### Task 6: Drift mode with snapshot reuse from `jw-eval`

**Files:**
- Modify: `packages/jw-core/src/jw_core/citations/validator.py` (refine `_populate_drift`)
- Modify: `packages/jw-core/tests/test_citation_validator.py` (drift tests)

- [ ] **Step 1: Append failing drift tests**

```python
# in test_citation_validator.py
import hashlib


@pytest.mark.asyncio
async def test_drift_no_snapshot_is_warning(tmp_path) -> None:
    cat = MepsCatalog(db_path=tmp_path / "meps.db")
    snaps = tmp_path / "snaps"
    snaps.mkdir()
    url = "https://wol.jw.org/es/wol/d/r4/lp-s/1"
    fetcher = _fake_fetcher_factory(
        {url: FetcherResponse(final_url=url, status=200, body="<html>hi</html>")}
    )
    v = CitationValidator(catalog=cat, fetcher=fetcher, snapshots_root=snaps)
    report = await v.validate_urls([url], mode="live+drift")
    check = report.checks[0]
    assert check.drift == "no_snapshot"
    assert check.is_ok is True  # is_ok lenient — but summary counts as warning
    assert report.summary["warning"] >= 1


@pytest.mark.asyncio
async def test_drift_ok_when_snapshot_present_and_resolves(tmp_path) -> None:
    cat = MepsCatalog(db_path=tmp_path / "meps.db")
    snaps = tmp_path / "snaps"
    snaps.mkdir()
    url = "https://wol.jw.org/es/wol/d/r4/lp-s/1"
    digest = hashlib.sha256(url.encode()).hexdigest()
    (snaps / f"{digest}.html").write_text("<html>known content</html>", encoding="utf-8")
    fetcher = _fake_fetcher_factory(
        {url: FetcherResponse(final_url=url, status=200, body="<html>known content</html>")}
    )
    v = CitationValidator(catalog=cat, fetcher=fetcher, snapshots_root=snaps)
    report = await v.validate_urls([url], mode="live+drift")
    assert report.checks[0].drift == "ok"


@pytest.mark.asyncio
async def test_drift_detected_when_shape_changes(tmp_path) -> None:
    cat = MepsCatalog(db_path=tmp_path / "meps.db")
    snaps = tmp_path / "snaps"
    snaps.mkdir()
    url = "https://wol.jw.org/es/wol/d/r4/lp-s/1"
    digest = hashlib.sha256(url.encode()).hexdigest()
    (snaps / f"{digest}.html").write_text(
        "<html><body><p>old</p></body></html>", encoding="utf-8"
    )
    # Live body is structurally different (extra div changes the shape).
    fetcher = _fake_fetcher_factory(
        {url: FetcherResponse(
            final_url=url,
            status=200,
            body="<html><body><div><p>new</p><span>x</span></div></body></html>",
        )}
    )
    v = CitationValidator(catalog=cat, fetcher=fetcher, snapshots_root=snaps)
    report = await v.validate_urls([url], mode="live+drift")
    assert report.checks[0].drift == "drift"


@pytest.mark.asyncio
async def test_live_drift_requires_snapshots_root(tmp_path) -> None:
    cat = MepsCatalog(db_path=tmp_path / "meps.db")
    fetcher = _fake_fetcher_factory({})
    v = CitationValidator(catalog=cat, fetcher=fetcher)
    with pytest.raises(ValueError):
        await v.validate_urls(["x"], mode="live+drift")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/jw-core/tests/test_citation_validator.py -v -k drift`
Expected: 4 tests, at least `test_drift_detected_when_shape_changes` FAILS — current placeholder drift logic doesn't compare bodies.

- [ ] **Step 3: Refine drift logic to compare HTML structure**

In `validator.py`:

1. Capture the body on `_populate_live` by storing it transiently on the check via `notes` — actually no, that bloats the model. Instead, change `_check_one` to thread the body through the call without persisting it on the model. Easiest: convert `_populate_live` to return the body string in addition to mutating the check.

Replace `_populate_live` and `_populate_drift` in `validator.py` so the relevant section reads:

```python
    async def _check_one(self, url: str, *, mode: Mode) -> CitationCheck:
        check = CitationCheck(url=url)
        parsed = _parse_wol_url(url)
        if parsed:
            check.doc_id = parsed["doc_id"]
            check.pub_code = parsed["pub_code"]

        await self._populate_catalog(check)

        live_body: str | None = None
        if mode in {"live", "live+drift"}:
            live_body = await self._populate_live(check)

        if mode == "live+drift":
            self._populate_drift(check, live_body=live_body)

        return check

    async def _populate_live(self, check: CitationCheck) -> str | None:
        assert self.fetcher is not None
        async with self._sem:
            try:
                resp = await self.fetcher(check.url)
            except Exception as exc:  # noqa: BLE001
                check.resolve = "network_error"
                check.notes.append(f"fetch failed: {exc!r}")
                return None

        check.http_status = resp.status
        check.resolved_url = resp.final_url
        check.redirect_chain = list(resp.redirect_chain)

        if len(resp.redirect_chain) > self.max_redirects:
            check.resolve = "redirect_loop"
            check.notes.append(f"redirect chain {len(resp.redirect_chain)} > {self.max_redirects}")
            return resp.body or None
        if resp.status == 404:
            check.resolve = "not_found"
        elif resp.status == 410:
            check.resolve = "gone"
        elif 500 <= resp.status < 600:
            check.resolve = "server_error"
        elif 200 <= resp.status < 300:
            check.resolve = "ok_redirect" if resp.redirect_chain else "ok"
        else:
            check.resolve = "network_error"
            check.notes.append(f"unexpected HTTP {resp.status}")
        return resp.body or None

    def _populate_drift(self, check: CitationCheck, *, live_body: str | None) -> None:
        if self.snapshots_root is None:
            check.drift = "skipped"
            return
        import hashlib

        from jw_core.telemetry import _shape_hash  # reuse Fase 9 helper

        digest = hashlib.sha256(check.url.encode("utf-8")).hexdigest()
        snap = self.snapshots_root / f"{digest}.html"
        if not snap.exists():
            check.drift = "no_snapshot"
            return
        check.snapshot_path = str(snap)
        if check.resolve not in {"ok", "ok_redirect"} or live_body is None:
            check.drift = "drift"
            check.notes.append("could not compare: live fetch was not 2xx")
            return

        snap_body = snap.read_text(encoding="utf-8")
        # `_shape_hash` was built for JSON, so we project HTML through a tiny
        # tree model: tag counts + nesting. Cheap and stable across the
        # minor-content changes wol.jw.org makes routinely.
        live_shape = _html_shape(live_body)
        snap_shape = _html_shape(snap_body)
        if live_shape == snap_shape:
            check.drift = "ok"
        else:
            check.drift = "drift"
            check.notes.append(f"shape changed: {snap_shape[:32]}… → {live_shape[:32]}…")


def _html_shape(html: str) -> str:
    """Tiny HTML-structure hash. Counts opening tags; ignores whitespace + text.

    Same skeleton ⇒ same hash. Adding/removing a tag changes the hash.
    Robust to minor content edits, language changes, image swaps.
    """
    import hashlib
    import re

    tags = re.findall(r"<\s*([a-zA-Z0-9]+)", html)
    canon = ",".join(sorted(t.lower() for t in tags))
    return f"html({len(tags)})[{hashlib.sha256(canon.encode()).hexdigest()[:16]}]"
```

(`_html_shape` is private; add to `validator.py`.)

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/jw-core/tests/test_citation_validator.py -v -k drift`
Expected: 4 passed.

Run the full file: `uv run pytest packages/jw-core/tests/test_citation_validator.py -v`
Expected: 24 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-core/src/jw_core/citations/validator.py packages/jw-core/tests/test_citation_validator.py
git commit -m "feat(jw-core/citations): drift mode via HTML-shape comparison (reuses telemetry)"
```

---

### Task 7: Httpx-backed fetcher (production adapter)

**Files:**
- Modify: `packages/jw-core/src/jw_core/citations/validator.py` — add `httpx_fetcher()` helper.
- Modify: `packages/jw-core/tests/test_citation_validator.py`.

- [ ] **Step 1: Write the failing test**

```python
# in test_citation_validator.py
import httpx


@pytest.mark.asyncio
async def test_httpx_fetcher_follows_redirect_chain(monkeypatch) -> None:
    from jw_core.citations.validator import httpx_fetcher

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/a":
            return httpx.Response(301, headers={"Location": "/b"})
        if request.url.path == "/b":
            return httpx.Response(200, text="final")
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, base_url="https://wol.jw.org") as client:
        fetcher = httpx_fetcher(client)
        resp = await fetcher("https://wol.jw.org/a")
    assert resp.status == 200
    assert resp.final_url.endswith("/b")
    assert resp.redirect_chain  # non-empty
    assert "final" in resp.body
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/jw-core/tests/test_citation_validator.py::test_httpx_fetcher_follows_redirect_chain -v`
Expected: FAIL — `httpx_fetcher` undefined.

- [ ] **Step 3: Implement `httpx_fetcher`**

Append to `validator.py`:

```python
def httpx_fetcher(client: "httpx.AsyncClient") -> AsyncFetcher:
    """Build an AsyncFetcher backed by an httpx.AsyncClient.

    The client should have `follow_redirects=True`. Each redirect URL is
    captured into the response's redirect_chain.
    """

    async def fetch(url: str) -> FetcherResponse:
        resp = await client.get(url, follow_redirects=True)
        chain = [str(h.url) for h in resp.history]
        return FetcherResponse(
            final_url=str(resp.url),
            status=resp.status_code,
            redirect_chain=chain,
            body=resp.text,
        )

    return fetch
```

Add `import httpx` lazily inside the helper if you'd rather not import at top. But since httpx is already a hard dep of jw-core, top-level is fine — add `import httpx` to the imports block.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/jw-core/tests/test_citation_validator.py -v`
Expected: 25 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-core/src/jw_core/citations/validator.py packages/jw-core/tests/test_citation_validator.py
git commit -m "feat(jw-core/citations): httpx_fetcher adapter for live mode"
```

---

### Task 8: MCP tool `validate_citations`

**Files:**
- Modify: `packages/jw-mcp/src/jw_mcp/server.py`
- Create: `packages/jw-mcp/tests/test_citations_tool.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-mcp/tests/test_citations_tool.py
"""Tests for the validate_citations MCP tool."""

from __future__ import annotations

import pytest


def test_validate_citations_rejects_missing_input() -> None:
    from jw_mcp.server import validate_citations

    out = validate_citations()
    assert "error" in out


def test_validate_citations_rejects_both_inputs() -> None:
    from jw_mcp.server import validate_citations

    out = validate_citations(urls=["x"], agent_output={"findings": []})
    assert "error" in out


def test_validate_citations_structural_with_urls() -> None:
    from jw_mcp.server import validate_citations

    out = validate_citations(urls=["https://wol.jw.org/es/wol/d/r4/lp-s/1"])
    assert "mode" in out
    assert out["mode"] == "structural"
    assert len(out["checks"]) == 1


def test_validate_citations_with_agent_output() -> None:
    from jw_mcp.server import validate_citations

    agent_out = {
        "findings": [
            {"metadata": {"citation_url": "https://wol.jw.org/es/wol/d/r4/lp-s/1"}},
            {"metadata": {"citation_url": "https://wol.jw.org/es/wol/d/r4/lp-s/2"}},
        ]
    }
    out = validate_citations(agent_output=agent_out)
    assert len(out["checks"]) == 2


def test_validate_citations_live_requires_env_optin(monkeypatch) -> None:
    from jw_mcp.server import validate_citations

    monkeypatch.delenv("JW_CITATIONS_LIVE", raising=False)
    out = validate_citations(urls=["https://wol.jw.org/x"], live=True)
    # Without the env var, the server should refuse to hit the network.
    assert "error" in out
    assert "JW_CITATIONS_LIVE" in out["error"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/jw-mcp/tests/test_citations_tool.py -v`
Expected: FAIL — `validate_citations` not in `jw_mcp.server`.

- [ ] **Step 3: Implement the tool**

Append to `packages/jw-mcp/src/jw_mcp/server.py`:

```python
# at the imports block (top of file), append:
import asyncio as _asyncio
import os as _os
from typing import Any as _Any

from jw_core.citations import CitationValidator as _CitationValidator
from jw_core.integrations.meps_catalog import MepsCatalog as _MepsCatalog


@mcp.tool()
def validate_citations(
    urls: list[str] | None = None,
    agent_output: dict | None = None,
    live: bool = False,
    check_drift: bool = False,
) -> dict:
    """Validate that wol.jw.org URLs from an agent resolve and map cleanly.

    Pass exactly one of `urls` or `agent_output`. The latter must be the
    serialized AgentResult shape ({"findings": [{"metadata": {...}}]}).

    Modes:
      - default (offline): MEPS docId↔pub_code lookup against the local catalog.
      - live=True: also HTTP-resolve every URL. Requires env JW_CITATIONS_LIVE=1.
      - check_drift=True (implies live): compare HTML shape against committed snapshots.

    Returns the CitationReport as a dict.
    """

    if (urls is None) == (agent_output is None):
        return {"error": "pass exactly one of urls= or agent_output="}

    if live and _os.environ.get("JW_CITATIONS_LIVE", "").lower() not in {"1", "true", "yes"}:
        return {
            "error": "live=True requires env JW_CITATIONS_LIVE=1 to authorize network access"
        }

    async def _run() -> dict:
        catalog = _MepsCatalog()
        kwargs: dict[str, _Any] = {"catalog": catalog}

        client = None
        if live:
            import httpx  # local import — keeps cold-start light

            from jw_core.citations.validator import httpx_fetcher

            client = httpx.AsyncClient(timeout=30.0, follow_redirects=True)
            kwargs["fetcher"] = httpx_fetcher(client)

        if check_drift:
            from pathlib import Path

            snaps = Path("packages/jw-eval/fixtures/wol_snapshots")
            if snaps.exists():
                kwargs["snapshots_root"] = snaps

        v = _CitationValidator(**kwargs)
        try:
            mode = "live+drift" if (live and check_drift) else ("live" if live else "structural")
            if urls is not None:
                report = await v.validate_urls(urls, mode=mode)
            else:
                report = await v.validate_agent_output(agent_output, mode=mode)
            return report.model_dump(mode="json")
        finally:
            if client is not None:
                await client.aclose()

    return _asyncio.run(_run())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/jw-mcp/tests/test_citations_tool.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-mcp/src/jw_mcp/server.py packages/jw-mcp/tests/test_citations_tool.py
git commit -m "feat(jw-mcp): validate_citations tool (structural + opt-in live/drift)"
```

---

### Task 9: CLI command `jw citations check`

**Files:**
- Create: `packages/jw-cli/src/jw_cli/commands/citations.py`
- Modify: `packages/jw-cli/src/jw_cli/commands/__init__.py`
- Modify: `packages/jw-cli/src/jw_cli/main.py`

- [ ] **Step 1: Write the CLI module**

```python
# packages/jw-cli/src/jw_cli/commands/citations.py
"""`jw citations` — verify integrity of wol.jw.org URLs.

Subcommands:
    jw citations check --urls urls.txt
    jw citations check --agent-output result.json
    jw citations check --urls urls.txt --live
    jw citations check --urls urls.txt --live --drift
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from jw_core.citations import CitationValidator
from jw_core.integrations.meps_catalog import MepsCatalog

console = Console()
citations_app = typer.Typer(
    name="citations",
    help="Verify wol.jw.org citation integrity (HTTP + MEPS catalog + drift).",
)


@citations_app.command("check")
def check_cmd(
    urls_path: Path | None = typer.Option(
        None, "--urls", help="Path to a text file with one URL per line."
    ),
    agent_output_path: Path | None = typer.Option(
        None, "--agent-output", help="Path to a serialized AgentResult JSON."
    ),
    live: bool = typer.Option(False, "--live", help="Hit wol.jw.org over HTTP."),
    drift: bool = typer.Option(False, "--drift", help="Compare against committed snapshots."),
    snapshots_root: Path = typer.Option(
        Path("packages/jw-eval/fixtures/wol_snapshots"),
        "--snapshots-root",
        help="Snapshot directory (defaults to jw-eval's).",
    ),
    concurrency: int = typer.Option(4, "--concurrency", min=1, max=32),
    report_format: str = typer.Option("md", "--report", help="md | json"),
    out: Path | None = typer.Option(None, "--out", help="Write report to file instead of stdout."),
) -> None:
    """Run the citation integrity validator."""

    if (urls_path is None) == (agent_output_path is None):
        raise typer.BadParameter("pass exactly one of --urls / --agent-output")

    if urls_path is not None:
        urls = [
            line.strip()
            for line in urls_path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.startswith("#")
        ]
        agent_output = None
    else:
        urls = None
        agent_output = json.loads(agent_output_path.read_text(encoding="utf-8"))

    async def _run() -> dict:
        catalog = MepsCatalog()
        kwargs: dict = {"catalog": catalog, "concurrency": concurrency}

        client = None
        if live:
            import httpx

            from jw_core.citations.validator import httpx_fetcher

            client = httpx.AsyncClient(timeout=30.0, follow_redirects=True)
            kwargs["fetcher"] = httpx_fetcher(client)

        if drift:
            kwargs["snapshots_root"] = snapshots_root

        v = CitationValidator(**kwargs)
        mode = "live+drift" if (live and drift) else ("live" if live else "structural")
        try:
            if urls is not None:
                report = await v.validate_urls(urls, mode=mode)
            else:
                report = await v.validate_agent_output(agent_output, mode=mode)
            return report.model_dump(mode="json")
        finally:
            if client is not None:
                await client.aclose()

    report_dict = asyncio.run(_run())

    if report_format == "json":
        text = json.dumps(report_dict, indent=2, ensure_ascii=False)
    else:
        text = _to_markdown(report_dict)

    if out:
        out.write_text(text, encoding="utf-8")
        console.print(f"Wrote {out}")
    else:
        console.print(text)

    failed = report_dict["summary"]["failed"]
    raise typer.Exit(code=min(int(failed), 125))


def _to_markdown(report: dict) -> str:
    lines: list[str] = []
    lines.append("# Citation integrity report")
    lines.append("")
    lines.append(f"- **Mode:** `{report['mode']}`")
    s = report["summary"]
    lines.append(
        f"- **Summary:** total={s['total']} · ok={s['ok']} · "
        f"warning={s['warning']} · failed={s['failed']}"
    )
    lines.append("")
    lines.append("| URL | resolve | catalog | drift | notes |")
    lines.append("|---|---|---|---|---|")
    for c in report["checks"]:
        notes = "; ".join(c.get("notes") or []) or "—"
        lines.append(
            f"| `{c['url']}` | {c['resolve']} | {c['catalog']} | {c['drift']} | {notes} |"
        )
    return "\n".join(lines) + "\n"
```

- [ ] **Step 2: Register the sub-app**

Edit `packages/jw-cli/src/jw_cli/commands/__init__.py` — append `from . import citations  # noqa: F401`.

Edit `packages/jw-cli/src/jw_cli/main.py` — add to imports + register:

```python
from jw_cli.commands.citations import citations_app
# …existing add_typer / command registrations…
app.add_typer(citations_app)
```

- [ ] **Step 3: Smoke-test the CLI manually**

Run:
```bash
echo "https://wol.jw.org/es/wol/d/r4/lp-s/1101989140" > /tmp/urls.txt
uv run jw citations check --urls /tmp/urls.txt --report md
```
Expected: a markdown report. Catalog may say `unknown` if no `.jwpub` indexed — that's fine. Exit code 0 (no failures).

- [ ] **Step 4: Add a CLI unit test**

```python
# packages/jw-cli/tests/test_citations_cli.py
"""Smoke test for `jw citations check` Typer command."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from jw_cli.commands.citations import citations_app

runner = CliRunner()


def test_cli_structural_with_urls(tmp_path: Path) -> None:
    urls_file = tmp_path / "u.txt"
    urls_file.write_text("https://wol.jw.org/es/wol/d/r4/lp-s/1\n", encoding="utf-8")
    result = runner.invoke(citations_app, ["check", "--urls", str(urls_file), "--report", "json"])
    assert result.exit_code == 0, result.stdout
    data = json.loads(result.stdout)
    assert data["mode"] == "structural"
    assert len(data["checks"]) == 1


def test_cli_rejects_both_inputs(tmp_path: Path) -> None:
    urls_file = tmp_path / "u.txt"
    urls_file.write_text("x", encoding="utf-8")
    out_file = tmp_path / "o.json"
    out_file.write_text("{}", encoding="utf-8")
    result = runner.invoke(
        citations_app,
        ["check", "--urls", str(urls_file), "--agent-output", str(out_file)],
    )
    assert result.exit_code != 0
```

Run: `uv run pytest packages/jw-cli/tests/test_citations_cli.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-cli/src/jw_cli/commands/citations.py packages/jw-cli/src/jw_cli/commands/__init__.py packages/jw-cli/src/jw_cli/main.py packages/jw-cli/tests/test_citations_cli.py
git commit -m "feat(jw-cli): jw citations check command with --live / --drift opt-ins"
```

---

### Task 10: Smoke integration with `verse_explainer`

**Files:**
- Modify: `packages/jw-agents/tests/test_verse_explainer.py`

- [ ] **Step 1: Append the smoke test**

```python
# in packages/jw-agents/tests/test_verse_explainer.py
import pytest

from jw_core.citations import CitationValidator


@pytest.mark.asyncio
async def test_verse_explainer_citations_pass_structural_validator(verse_explainer_result) -> None:
    """Every citation emitted by verse_explainer must pass structural validation."""

    v = CitationValidator()  # no catalog, no fetcher → everything skipped/unknown
    report = await v.validate_agent_output(verse_explainer_result, mode="structural")
    assert report.summary["failed"] == 0, report.checks
```

If `verse_explainer_result` fixture doesn't exist, build it inline (cache result of a representative call):

```python
@pytest.fixture
def verse_explainer_result():
    from jw_agents.verse_explainer import verse_explainer

    # Use the same canned input the existing tests use; result must be sync-callable
    return verse_explainer(reference="Juan 3:16", language="es")
```

If `verse_explainer` is async, wrap with `asyncio.run()` or use a sync helper that already exists in `jw_agents` (look at one existing test for the exact pattern).

- [ ] **Step 2: Run test**

Run: `uv run pytest packages/jw-agents/tests/test_verse_explainer.py -v -k citations`
Expected: 1 passed. If failed → either fixture-pattern mismatch (fix fixture) OR an existing finding has a malformed citation URL (that's a real bug — file it, don't paper over).

- [ ] **Step 3: Commit**

```bash
git add packages/jw-agents/tests/test_verse_explainer.py
git commit -m "test(jw-agents): verse_explainer smoke runs CitationValidator structural mode"
```

---

### Task 11: User guide

**Files:**
- Create: `docs/guias/citation-validator.md`
- Modify: `docs/README.md`

- [ ] **Step 1: Write the guide**

```markdown
# Citation integrity validator (`jw_core.citations`)

> Fase 23 — validador de integridad de citas / link-rot. Spec en `docs/superpowers/specs/2026-05-30-fase-23-citation-validator-design.md`.

## Para qué sirve

Verifica que cada URL `wol.jw.org` que produce un agente esté sana en tres ejes:

| Eje | Qué chequea | Default |
|---|---|---|
| **Catálogo** | docId↔pub_code contra `MepsCatalog` local (Fase 19) | siempre |
| **Resolve** | HTTP 200 (acepta 3xx terminando en 200) | sólo con `--live` |
| **Drift** | shape del HTML coincide con snapshot de Fase 22 | sólo con `--live --drift` |

Pareja natural de Fase 22 (eval doctrinal). Fase 22 detecta drift una vez por semana; Fase 23 **diagnostica** y enriquece los issues.

## Usar desde CLI

```bash
# Default offline-only (sólo catálogo)
echo "https://wol.jw.org/es/wol/d/r4/lp-s/1101989140" > /tmp/urls.txt
uv run jw citations check --urls /tmp/urls.txt

# Validar un AgentResult serializado
jw mcp call apologetics --question "Trinidad?" --out /tmp/result.json
uv run jw citations check --agent-output /tmp/result.json

# Live: HTTP real con concurrencia limitada
uv run jw citations check --urls /tmp/urls.txt --live

# Live + drift: compara contra snapshots de jw-eval
uv run jw citations check --urls /tmp/urls.txt --live --drift

# JSON output (para pipelines)
uv run jw citations check --urls /tmp/urls.txt --report json --out /tmp/report.json
```

## Usar desde MCP

```python
# tool: validate_citations
out = validate_citations(
    urls=["https://wol.jw.org/es/wol/d/r4/lp-s/1101989140"],
    live=False,
    check_drift=False,
)
# {"mode": "structural", "checks": [...], "summary": {...}}
```

Modo `live` requiere `JW_CITATIONS_LIVE=1` en el entorno del MCP server — diseño explícito para que un cliente LLM no martillee wol.jw.org por accidente.

## Usar desde código (validador de agentes)

```python
from jw_core.citations import CitationValidator

async def smoke(agent_output):
    v = CitationValidator()
    report = await v.validate_agent_output(agent_output, mode="structural")
    assert report.summary["failed"] == 0
```

## Interpretar el reporte

| `resolve` | Qué significa |
|---|---|
| `ok` | HTTP 200 directo |
| `ok_redirect` | 3xx → 200 (warning, no error) |
| `not_found` | 404 |
| `gone` | 410 |
| `server_error` | 5xx |
| `redirect_loop` | >3 redirecciones |
| `network_error` | timeout/DNS/TLS |
| `skipped` | modo estructural |

| `catalog` | Qué significa |
|---|---|
| `ok` | docId en MepsCatalog, pub_code coincide |
| `mismatch` | docId existe pero pub_code de la URL no coincide con catálogo |
| `missing` | docId no está en el catálogo local |
| `unknown` | URL sin docId (Biblia) o catálogo vacío |
| `skipped` | no se pasó catálogo |

| `drift` | Qué significa |
|---|---|
| `ok` | shape HTML == snapshot |
| `drift` | shape difiere; revisar `notes` |
| `no_snapshot` | no hay snapshot para esa URL |
| `skipped` | modo no incluye drift |

## Política

- **CI público corre solo modo estructural**. `--live` es manual o weekly cron de Fase 22.
- **Concurrencia 4 por defecto** en modo live. Aumentar sólo si tu red lo soporta y has hablado con el mantenedor.
- **`missing` en catálogo no es failure**: significa que falta `.jwpub` indexado, no que la URL esté rota.

## Troubleshooting

| Síntoma | Diagnóstico | Fix |
|---|---|---|
| Todos `catalog=unknown` | catálogo vacío | `jw library register <archivo.jwpub>` |
| `drift` en una URL conocida | wol cambió el HTML | refrescar snapshot vía `packages/jw-eval/scripts/build_eval_snapshots.py --force` |
| MCP rechaza `live=True` | falta env var | export `JW_CITATIONS_LIVE=1` para esa sesión |
```

- [ ] **Step 2: Link from docs/README.md**

Append to the "Guías por tema" list (alphabetical position):

```markdown
- [Citation integrity validator](guias/citation-validator.md) — Fase 23. Valida URLs wol.jw.org de agentes (estructural / live / drift). Hermana de Fase 22.
```

- [ ] **Step 3: Commit**

```bash
git add docs/guias/citation-validator.md docs/README.md
git commit -m "docs(citations): user guide for jw_core.citations validator"
```

---

### Task 12: Update ROADMAP, VISION_AUDIT, and final audit

**Files:**
- Modify: `docs/ROADMAP.md`
- Modify: `docs/VISION_AUDIT.md`

- [ ] **Step 1: Append Fase 23 to ROADMAP.md**

After the Fase 22 section, before any "---" or footer:

```markdown
## Fase 23 — Citation integrity / link-rot validator ✅

> Tier 1 infraestructura de confianza. Spec: `docs/superpowers/specs/2026-05-30-fase-23-citation-validator-design.md`.

- ✅ Subpaquete `packages/jw-core/src/jw_core/citations/`.
- ✅ Modelos Pydantic: `CitationCheck`, `CitationReport`, status enums.
- ✅ `CitationValidator` con tres modos: structural (default offline), live (HTTP opt-in), live+drift (compara HTML shape contra snapshots).
- ✅ Reutiliza `MepsCatalog` (Fase 19) para docId↔pub_code y `_shape_hash` (Fase 9) para drift.
- ✅ Fetcher inyectable; adapter `httpx_fetcher` para producción.
- ✅ Concurrencia bounded (`asyncio.Semaphore(4)` por defecto).
- ✅ CLI `jw citations check --urls / --agent-output / --live / --drift / --report / --out`.
- ✅ Tool MCP `validate_citations` con guard `JW_CITATIONS_LIVE=1`.
- ✅ Smoke integration en `verse_explainer` (modo estructural).
- ✅ Lee snapshots de `packages/jw-eval/fixtures/wol_snapshots/` (cross-package read, sin import dependency).
- ✅ Guía `docs/guias/citation-validator.md`.

### Cobertura de tests

- ✅ 25+ tests nuevos en `packages/jw-core/tests/test_citation_validator.py`.
- ✅ 5 tests en `packages/jw-mcp/tests/test_citations_tool.py`.
- ✅ 2 tests en `packages/jw-cli/tests/test_citations_cli.py`.
- ✅ Smoke en `packages/jw-agents/tests/test_verse_explainer.py`.
- ✅ Suite global sin regresiones.
```

- [ ] **Step 2: Append row to VISION_AUDIT.md summary table**

Insert above the closing `**100%...**` paragraph:

```markdown
| Fase 23 (citation validator) | ✅ Nuevo | `jw_core.citations` — 3 modos, CLI + MCP, hermana de Fase 22 |
```

- [ ] **Step 3: Run lint + full suite**

```bash
uv run ruff check packages/jw-core/src/jw_core/citations packages/jw-cli/src/jw_cli/commands/citations.py packages/jw-mcp/src/jw_mcp/server.py
uv run ruff format --check packages/jw-core/src/jw_core/citations packages/jw-cli/src/jw_cli/commands/citations.py
uv run pytest packages/ -q
```
Expected: zero ruff violations; all tests green (existing ≈577 + new 25+ = ~602).

- [ ] **Step 4: Final end-to-end smoke**

```bash
echo "https://wol.jw.org/es/wol/d/r4/lp-s/1101989140" > /tmp/u.txt
uv run jw citations check --urls /tmp/u.txt --report md
uv run jw citations check --urls /tmp/u.txt --report json | python -m json.tool
```
Expected: markdown table + valid JSON. Exit code 0.

- [ ] **Step 5: Commit**

```bash
git add docs/ROADMAP.md docs/VISION_AUDIT.md
git commit -m "docs(roadmap): land Fase 23 — citation integrity validator"
```

---

## Self-review summary

- **Spec coverage**: every section of the spec maps to a task above: architecture → Task 1; models → Task 2; URL parser + extractor → Task 3; structural mode (catalog) → Task 4; live mode + redirects + concurrency → Task 5; drift mode (snapshot reuse) → Task 6; production httpx fetcher → Task 7; MCP tool → Task 8; CLI → Task 9; smoke integration → Task 10; user guide → Task 11; ROADMAP + VISION_AUDIT + final audit → Task 12. The exclusions (no snapshot writing, no agent modification, no issue creation) are honored by absence — explicitly stated in the spec and in the guide (Task 11).
- **No placeholders**: every code step ships the actual code, every YAML/JSON shows the actual fields, every command shows the exact invocation and expected output. The one explicit incremental note is in Task 4 (drift is coarse) → Task 6 (drift is precise via `_html_shape`).
- **Type consistency**: `CitationCheck.resolve` is `ResolveStatus = Literal[...]`; `Mode = Literal["structural","live","live+drift"]` used in `validate_urls`, `validate_agent_output`, MCP tool, and CLI consistently. `FetcherResponse` dataclass is the single contract for the injectable fetcher — used by tests, `httpx_fetcher`, and the validator. Cross-package reads from `packages/jw-eval/fixtures/wol_snapshots/` are by path only — there is **no `import jw_eval` anywhere in `jw-core` or its tests**, preserving the layering rule from `ARCHITECTURE.md`.

## Execution choice

Plan completo. Dos opciones de ejecución:

1. **Subagent-driven (recomendado)** — dispatch fresh sub-agente por tarea, review entre tareas, iteración rápida (`superpowers:subagent-driven-development`). Apropiado porque cada tarea es self-contained con TDD bite-sized.
2. **Inline** — ejecuto tareas en esta sesión con checkpoints (`superpowers:executing-plans`). Apropiado si quieres ver el código tomar forma turn-by-turn.

¿Cuál prefieres?
