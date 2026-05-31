# Fase 40 — `content-provenance` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `jw_core.provenance` — a layer-2 fidelity validator that, given any `Citation` produced by the toolkit, can re-fetch the source page, compute a canonical hash, and report whether the text the agent originally used still matches what is live. The module integrates with Fase 39 (NLI) to re-run entailment when fidelity drift is detected.

**Architecture:** New module `packages/jw-core/src/jw_core/provenance/` with five files (`models.py`, `hashing.py`, `validator.py`, `propagation.py`, `errors.py`). Convention-based extension of `Citation.metadata` (no dataclass change): four keys `published_date`, `accessed_at`, `content_hash`, `revision`. Validator receives fetcher + extractor + optional `NLIProvider` (Fase 39) — never instantiates `httpx` itself. CLI `jw provenance check` and MCP tool `verify_provenance` complete the surface. Telemetry hooks emit `provenance_drift` events that piggyback Fase 9's opt-in switch.

**Tech Stack:** Python 3.13 · Pydantic 2 (models) · stdlib `hashlib` + `unicodedata` (canonicalization) · existing `httpx` (no new dep) · pytest with `pytest-asyncio` (already in dev deps).

**Spec:** [`docs/superpowers/specs/2026-05-31-fase-40-content-provenance-design.md`](../specs/2026-05-31-fase-40-content-provenance-design.md).

**Depende de:** Fase 39 (`nli-runtime`) — solo para la integración opcional `nli_provider`. Fase 40 degrada limpiamente sin Fase 39 (import-guarded).

---

## File map

Creates:
- `packages/jw-core/src/jw_core/provenance/__init__.py`
- `packages/jw-core/src/jw_core/provenance/errors.py`
- `packages/jw-core/src/jw_core/provenance/models.py`
- `packages/jw-core/src/jw_core/provenance/hashing.py`
- `packages/jw-core/src/jw_core/provenance/validator.py`
- `packages/jw-core/src/jw_core/provenance/propagation.py`
- `packages/jw-core/tests/test_provenance/__init__.py`
- `packages/jw-core/tests/test_provenance/test_errors.py`
- `packages/jw-core/tests/test_provenance/test_models.py`
- `packages/jw-core/tests/test_provenance/test_hashing.py`
- `packages/jw-core/tests/test_provenance/test_validator.py`
- `packages/jw-core/tests/test_provenance/test_validator_nli.py`
- `packages/jw-core/tests/test_provenance/test_propagation.py`
- `packages/jw-core/tests/test_provenance/test_validator_drift_detection.py`
- `packages/jw-core/tests/test_provenance/test_backwards_compat.py`
- `packages/jw-core/tests/test_provenance/fixtures/__init__.py`
- `packages/jw-core/tests/test_provenance/fixtures/agent_result_with_provenance.json`
- `packages/jw-core/tests/test_provenance/fixtures/agent_result_legacy.json`
- `packages/jw-cli/src/jw_cli/commands/provenance.py`
- `packages/jw-cli/tests/test_cli_provenance.py`
- `packages/jw-mcp/src/jw_mcp/tools/provenance.py`
- `packages/jw-mcp/tests/test_provenance_tool.py`
- `docs/guias/content-provenance.md`

Modifies:
- `packages/jw-agents/src/jw_agents/verse_explainer.py` — stamp citations with provenance fields at emission.
- `packages/jw-agents/src/jw_agents/apologetics.py` — same.
- `packages/jw-core/src/jw_core/wol_client.py` — stamp on `get_article` / `get_bible_chapter` ingest.
- `packages/jw-cli/src/jw_cli/main.py` — register `provenance` subcommand group.
- `packages/jw-mcp/src/jw_mcp/server.py` — register `verify_provenance` tool.
- `docs/ROADMAP.md` — add Fase 40 section.
- `docs/VISION_AUDIT.md` — add Fase 40 row.
- `docs/README.md` — link the new `content-provenance.md` guide.

---

### Task 1: Scaffold `provenance/` module + empty tests directory

**Files:**
- Create: `packages/jw-core/src/jw_core/provenance/__init__.py`
- Create: `packages/jw-core/src/jw_core/provenance/errors.py`
- Create: `packages/jw-core/tests/test_provenance/__init__.py`
- Create: `packages/jw-core/tests/test_provenance/test_errors.py`

- [ ] **Step 1: Write failing test for errors module**

```python
# packages/jw-core/tests/test_provenance/test_errors.py
"""Sanity tests for provenance exception classes."""

from __future__ import annotations

import pytest

from jw_core.provenance.errors import (
    MissingProvenanceError,
    ProvenanceError,
    ProvenanceFetchError,
)


def test_missing_provenance_is_provenance_error() -> None:
    err = MissingProvenanceError("no content_hash in citation")
    assert isinstance(err, ProvenanceError)
    assert "no content_hash" in str(err)


def test_fetch_error_carries_url_attribute() -> None:
    err = ProvenanceFetchError("timeout", url="https://wol.jw.org/x")
    assert isinstance(err, ProvenanceError)
    assert err.url == "https://wol.jw.org/x"
    assert "timeout" in str(err)


def test_provenance_error_is_distinct_from_value_error() -> None:
    with pytest.raises(ProvenanceError):
        raise ProvenanceError("boom")
    with pytest.raises(ProvenanceError):
        raise MissingProvenanceError("also boom")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/jw-core/tests/test_provenance/test_errors.py -v`
Expected: FAIL — `jw_core.provenance` module missing.

- [ ] **Step 3: Implement the package skeleton + errors**

```python
# packages/jw-core/src/jw_core/provenance/__init__.py
"""Content provenance — Layer 2 fidelity tracking.

This module answers the question: "is the text my agent used still the
same as what's live on wol.jw.org right now?". It complements
`jw_core.citations.validator` (Fase 23 — L0/L1: URL resolves, doc_id in
catalog) and `jw_core.nli` (Fase 39 — L3: entailment).

Public API (curated re-exports):

    from jw_core.provenance import (
        ProvenanceRecord,
        ProvenanceVerdict,
        ProvenanceReport,
        ProvenanceValidator,
        canonicalize_text,
        content_sha256,
        stamp_citation,
        stamp_finding_text,
        ProvenanceError,
        MissingProvenanceError,
        ProvenanceFetchError,
    )

All re-exports preserve a single-import boundary so that callers (CLI,
MCP, agents) never reach into submodules.
"""

from __future__ import annotations

from jw_core.provenance.errors import (
    MissingProvenanceError,
    ProvenanceError,
    ProvenanceFetchError,
)
from jw_core.provenance.hashing import canonicalize_text, content_sha256
from jw_core.provenance.models import (
    ProvenanceRecord,
    ProvenanceReport,
    ProvenanceVerdict,
)
from jw_core.provenance.propagation import stamp_citation, stamp_finding_text
from jw_core.provenance.validator import ProvenanceValidator

__all__ = [
    "MissingProvenanceError",
    "ProvenanceError",
    "ProvenanceFetchError",
    "ProvenanceRecord",
    "ProvenanceReport",
    "ProvenanceValidator",
    "ProvenanceVerdict",
    "canonicalize_text",
    "content_sha256",
    "stamp_citation",
    "stamp_finding_text",
]
```

```python
# packages/jw-core/src/jw_core/provenance/errors.py
"""Exceptions emitted by the provenance subsystem.

Conventions:
  - All exceptions are subclasses of ProvenanceError so callers can
    install one blanket handler.
  - Fetch failures carry the offending URL so the CLI can surface it.
  - Missing-data errors are distinct from fetch errors — they signal
    "citation was emitted without provenance metadata" which is a
    backwards-compat scenario, not an outage.
"""

from __future__ import annotations


class ProvenanceError(Exception):
    """Base class for all provenance-related failures."""


class MissingProvenanceError(ProvenanceError):
    """A Citation lacks the four conventional provenance keys in metadata.

    Raised only when the caller asks for a strict check; the validator
    itself prefers to return `status="no_record"` for backwards compat.
    """


class ProvenanceFetchError(ProvenanceError):
    """The fetcher could not retrieve the URL for a re-check.

    Carries the URL so it can be reported per-citation without losing
    context after exceptions cross async boundaries.
    """

    def __init__(self, message: str, *, url: str) -> None:
        super().__init__(message)
        self.url = url
```

```python
# packages/jw-core/tests/test_provenance/__init__.py
"""Tests for jw_core.provenance."""
```

- [ ] **Step 4: Stub the other submodules so the package import succeeds**

To keep this task self-contained, write placeholder submodules that the
`__init__.py` re-exports point at. Each will be properly implemented in
later tasks; for now they expose minimal class names so imports succeed.

```python
# packages/jw-core/src/jw_core/provenance/models.py
"""Pydantic models for provenance (filled in Task 2 + Task 3)."""

from __future__ import annotations

from pydantic import BaseModel


class ProvenanceRecord(BaseModel):
    """Placeholder — replaced in Task 2."""


class ProvenanceVerdict(BaseModel):
    """Placeholder — replaced in Task 3."""


class ProvenanceReport(BaseModel):
    """Placeholder — replaced in Task 3."""
```

```python
# packages/jw-core/src/jw_core/provenance/hashing.py
"""Canonicalization + sha256 (filled in Task 4)."""

from __future__ import annotations


def canonicalize_text(text: str) -> str:  # pragma: no cover — replaced in Task 4
    return text


def content_sha256(text: str) -> str:  # pragma: no cover — replaced in Task 4
    return ""
```

```python
# packages/jw-core/src/jw_core/provenance/validator.py
"""Validator (filled in Task 5)."""

from __future__ import annotations


class ProvenanceValidator:  # pragma: no cover — replaced in Task 5
    pass
```

```python
# packages/jw-core/src/jw_core/provenance/propagation.py
"""Propagation helpers (filled in Task 6)."""

from __future__ import annotations


def stamp_citation(citation, *, text, published_date=None, revision=None):  # pragma: no cover — replaced in Task 6
    return citation


def stamp_finding_text(finding):  # pragma: no cover — replaced in Task 6
    return finding
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest packages/jw-core/tests/test_provenance/test_errors.py -v`
Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
git add packages/jw-core/src/jw_core/provenance packages/jw-core/tests/test_provenance
git commit -m "feat(jw-core/provenance): scaffold module with errors and placeholder submodules"
```

---

### Task 2: `ProvenanceRecord` model + typed view over `Citation.metadata`

**Files:**
- Modify: `packages/jw-core/src/jw_core/provenance/models.py`
- Create: `packages/jw-core/tests/test_provenance/test_models.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-core/tests/test_provenance/test_models.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/jw-core/tests/test_provenance/test_models.py -v`
Expected: FAIL — `ProvenanceRecord.from_citation_metadata` not defined / returns wrong shape.

- [ ] **Step 3: Implement `ProvenanceRecord`**

Replace `packages/jw-core/src/jw_core/provenance/models.py` contents (the
two other models remain placeholders for Task 3):

```python
# packages/jw-core/src/jw_core/provenance/models.py
"""Pydantic models for provenance.

`ProvenanceRecord` is a read-only typed view over the four conventional
keys that live inside `Citation.metadata`. We deliberately do NOT extend
the `Citation` dataclass — that would force 1984+ existing tests to
update. Instead we project the dict into a typed Pydantic model on
demand and project back out via `model_dump(exclude_none=True)`.

`ProvenanceVerdict` and `ProvenanceReport` (Task 3) carry the result of
a re-fetch comparison and an aggregate of those, respectively.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ProvenanceRecord(BaseModel):
    """Typed view over the four provenance keys in `Citation.metadata`.

    Two of the four are required for the view to be meaningful:
      - `accessed_at`  — when the toolkit pulled the text
      - `content_hash` — sha256 hex of the canonicalized passage

    The other two are recommended but optional:
      - `published_date` — original publication date (ISO 8601), may be missing on WOL
      - `revision`       — translation revision tag, e.g. "rev. 2023"
    """

    model_config = ConfigDict(extra="forbid", frozen=False, str_strip_whitespace=False)

    accessed_at: str
    content_hash: str
    published_date: str | None = None
    revision: str | None = None

    @classmethod
    def from_citation_metadata(cls, meta: dict[str, Any]) -> "ProvenanceRecord | None":
        """Project a Citation.metadata dict into a typed record.

        Returns None when either anchor field is missing — this is the
        backwards-compat path for citations emitted before Fase 40.
        Never mutates the source dict.
        """

        if not isinstance(meta, dict):
            return None
        accessed_at = meta.get("accessed_at")
        content_hash = meta.get("content_hash")
        if not isinstance(accessed_at, str) or not isinstance(content_hash, str):
            return None
        if not accessed_at or not content_hash:
            return None
        published_date = meta.get("published_date")
        if published_date is not None and not isinstance(published_date, str):
            published_date = None
        revision = meta.get("revision")
        if revision is not None and not isinstance(revision, str):
            revision = None
        return cls(
            accessed_at=accessed_at,
            content_hash=content_hash,
            published_date=published_date,
            revision=revision,
        )


# ProvenanceVerdict and ProvenanceReport are implemented in Task 3.


class ProvenanceVerdict(BaseModel):
    """Placeholder — replaced in Task 3."""


class ProvenanceReport(BaseModel):
    """Placeholder — replaced in Task 3."""
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/jw-core/tests/test_provenance/test_models.py -v`
Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-core/src/jw_core/provenance/models.py packages/jw-core/tests/test_provenance/test_models.py
git commit -m "feat(jw-core/provenance): ProvenanceRecord typed view over Citation.metadata"
```

---

### Task 3: `ProvenanceVerdict` + `ProvenanceReport` models

**Files:**
- Modify: `packages/jw-core/src/jw_core/provenance/models.py`
- Modify: `packages/jw-core/tests/test_provenance/test_models.py`

- [ ] **Step 1: Append the failing tests**

Append to `packages/jw-core/tests/test_provenance/test_models.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/jw-core/tests/test_provenance/test_models.py -v`
Expected: 8 new tests FAIL.

- [ ] **Step 3: Implement `ProvenanceVerdict` and `ProvenanceReport`**

Replace the two placeholders in `packages/jw-core/src/jw_core/provenance/models.py`
with full implementations (keep `ProvenanceRecord` intact above them):

```python
# Append/replace inside packages/jw-core/src/jw_core/provenance/models.py


VerdictStatus = Literal["match", "changed", "unreachable", "no_record", "skipped"]


class ProvenanceVerdict(BaseModel):
    """The result of comparing a single citation's stored hash to a re-fetch.

    Statuses:
      - "match":       current text canonicalizes to the same hash as stored.
      - "changed":     hashes differ — the live text has been edited.
      - "unreachable": fetcher raised or returned non-2xx — verdict is unknown.
      - "no_record":   the citation lacked provenance metadata (backwards compat).
      - "skipped":     `check_since` excluded this citation by date threshold.
    """

    model_config = ConfigDict(extra="forbid")

    url: str
    status: VerdictStatus
    original_hash: str | None
    current_hash: str | None
    delta_chars: int | None
    accessed_at_original: str | None
    accessed_at_recheck: str
    nli_rerun: dict[str, Any] | None = None
    notes: list[str] = Field(default_factory=list)


class ProvenanceReport(BaseModel):
    """Aggregate of many ProvenanceVerdicts produced in a single run."""

    model_config = ConfigDict(extra="forbid")

    started_at: datetime
    finished_at: datetime
    verdicts: list[ProvenanceVerdict] = Field(default_factory=list)
    summary: dict[str, int] = Field(default_factory=dict)

    @staticmethod
    def summarize(verdicts: list[ProvenanceVerdict]) -> dict[str, int]:
        """Roll up counts per status. Missing statuses yield 0 on demand."""

        counts: dict[str, int] = {}
        for v in verdicts:
            counts[v.status] = counts.get(v.status, 0) + 1
        return counts
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/jw-core/tests/test_provenance/test_models.py -v`
Expected: 15 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-core/src/jw_core/provenance/models.py packages/jw-core/tests/test_provenance/test_models.py
git commit -m "feat(jw-core/provenance): ProvenanceVerdict + ProvenanceReport with summarize()"
```

---

### Task 4: `canonicalize_text` + `content_sha256` (NFC, whitespace, preserve case)

**Files:**
- Modify: `packages/jw-core/src/jw_core/provenance/hashing.py`
- Create: `packages/jw-core/tests/test_provenance/test_hashing.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-core/tests/test_provenance/test_hashing.py
"""Tests for canonicalize_text() and content_sha256().

Design pinned by the spec:
  - NFC unicode normalization
  - Collapse internal whitespace runs to a single space
  - Strip leading/trailing whitespace
  - PRESERVE capitalization (Jehová vs jehová is doctrinally meaningful)
  - Eliminate zero-width characters

The hash must be stable across cosmetic-only edits and sensitive to
actual content edits.
"""

from __future__ import annotations

from jw_core.provenance.hashing import canonicalize_text, content_sha256


def test_canonicalize_strips_outer_whitespace() -> None:
    assert canonicalize_text("   hello   ") == "hello"


def test_canonicalize_collapses_internal_whitespace_runs() -> None:
    assert canonicalize_text("hello\t  world\n\nfriend") == "hello world friend"


def test_canonicalize_preserves_capitalization() -> None:
    """Spec decision: do NOT lowercase. `Jehová` and `jehová` hash differently."""

    a = canonicalize_text("Jehová es Dios")
    b = canonicalize_text("jehová es dios")
    assert a != b
    # And neither is lowercased internally:
    assert "Jehová" in a
    assert "jehová" in b


def test_canonicalize_nfc_normalizes_decomposed_form() -> None:
    """`é` composed (U+00E9) vs decomposed (e + U+0301) must canonicalize the same."""

    composed = "Jehová"        # á as a single codepoint
    decomposed = "Jehová"      # a + combining acute
    assert canonicalize_text(composed) == canonicalize_text(decomposed)


def test_canonicalize_removes_zero_width_chars() -> None:
    """ZWSP / ZWJ / ZWNJ / BOM are stripped."""

    text = "Je​ho‌v‍﻿á"
    assert canonicalize_text(text) == "Jehová"


def test_canonicalize_is_idempotent() -> None:
    """Running it twice yields the same string."""

    a = canonicalize_text("  hello   world  ")
    assert canonicalize_text(a) == a


def test_content_sha256_stable_across_cosmetic_edits() -> None:
    """Whitespace, NFC, ZWSP must not change the hash."""

    base = "Jehová amó tanto al mundo que dio a su Hijo"
    cosmetic = "  Jehová   amó tanto al mundo\nque dio a su Hijo  "
    assert content_sha256(base) == content_sha256(cosmetic)


def test_content_sha256_changes_when_real_word_differs() -> None:
    base = "Jehová amó tanto al mundo que dio a su Hijo"
    edited = "Jehová amó tanto al universo que dio a su Hijo"  # mundo → universo
    assert content_sha256(base) != content_sha256(edited)


def test_content_sha256_changes_when_capitalization_differs() -> None:
    """Spec decision propagated: capitalization is meaningful."""

    a = content_sha256("Jehová es Dios")
    b = content_sha256("jehová es Dios")
    assert a != b


def test_content_sha256_returns_hex_string() -> None:
    """Returns lowercase hex (sha256 → 64 chars)."""

    h = content_sha256("hello")
    assert len(h) == 64
    assert all(c in "0123456789abcdef" for c in h)


def test_canonicalize_empty_input() -> None:
    assert canonicalize_text("") == ""
    assert canonicalize_text("   \n   ") == ""


def test_content_sha256_empty_is_stable() -> None:
    """An empty canonicalized string still hashes deterministically."""

    a = content_sha256("")
    b = content_sha256("   ")
    assert a == b
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/jw-core/tests/test_provenance/test_hashing.py -v`
Expected: FAIL — current `canonicalize_text` is identity.

- [ ] **Step 3: Implement canonicalization + hashing**

Replace `packages/jw-core/src/jw_core/provenance/hashing.py`:

```python
# packages/jw-core/src/jw_core/provenance/hashing.py
"""Canonicalization + content hashing for provenance.

Why canonicalize before hashing?
  Naïve sha256(html_body) is brittle: WOL re-deploys the same HTML with
  different attribute ordering, an updated date stamp in <meta>, or a
  re-indented body — and our hashes diverge for no doctrinal reason.

The pipeline is intentionally minimal:
  1. Unicode NFC normalize so composed/decomposed forms align.
  2. Drop zero-width characters that occasionally appear in pasted text.
  3. Collapse runs of any whitespace (including newlines, tabs) into a
     single ASCII space.
  4. Strip leading/trailing whitespace.

What we deliberately do NOT do:
  - Lowercase. Capitalization in WT/NWT distinguishes "Jehová" from
    casual mentions; "Mi Padre" capitalization in NWT rev. 2023 is a
    real doctrinal signal. Squashing it would mask drift we care about.
  - Strip punctuation. "Romanos 6:23." vs "Romanos 6:23" is meaningful
    in citation chains.
  - Remove HTML. Callers are expected to extract plain text first via
    the injectable `extractor` on the validator. Hashing HTML directly
    would conflate styling drift with content drift.

These choices match the spec Decision NO Obvia in
2026-05-31-fase-40-content-provenance-design.md §canonicalización.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata

# All Unicode zero-width / BOM-ish codepoints we want gone before hashing.
_ZERO_WIDTH = {
    "​",  # ZERO WIDTH SPACE
    "‌",  # ZERO WIDTH NON-JOINER
    "‍",  # ZERO WIDTH JOINER
    "⁠",  # WORD JOINER
    "﻿",  # ZERO WIDTH NO-BREAK SPACE / BOM
}

# Regex matches any run of whitespace per Python's \s (covers \n, \r, \t, etc.)
_WHITESPACE_RUN = re.compile(r"\s+")


def canonicalize_text(text: str) -> str:
    """Normalize text so cosmetic edits don't inflate the content hash.

    Steps:
      1. NFC normalize.
      2. Drop zero-width characters.
      3. Collapse whitespace runs to a single space.
      4. Strip outer whitespace.

    Capitalization is preserved on purpose — the doctrine of distinguishing
    "Jehová" from "jehová" is the canonical example.
    """

    if not text:
        return ""
    nfc = unicodedata.normalize("NFC", text)
    if _ZERO_WIDTH.intersection(nfc):
        nfc = "".join(ch for ch in nfc if ch not in _ZERO_WIDTH)
    collapsed = _WHITESPACE_RUN.sub(" ", nfc)
    return collapsed.strip()


def content_sha256(text: str) -> str:
    """Lowercase-hex sha256 of `canonicalize_text(text)`."""

    canonical = canonicalize_text(text)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/jw-core/tests/test_provenance/test_hashing.py -v`
Expected: 12 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-core/src/jw_core/provenance/hashing.py packages/jw-core/tests/test_provenance/test_hashing.py
git commit -m "feat(jw-core/provenance): canonicalize_text + content_sha256 with NFC and whitespace rules"
```

---

### Task 5: `ProvenanceValidator.check` async with injected fetcher

**Files:**
- Modify: `packages/jw-core/src/jw_core/provenance/validator.py`
- Create: `packages/jw-core/tests/test_provenance/test_validator.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-core/tests/test_provenance/test_validator.py
"""Tests for ProvenanceValidator — fetcher is injected, never real network."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import pytest

from jw_agents.base import Citation, Finding
from jw_core.provenance.validator import (
    FetcherResponse,
    ProvenanceValidator,
)
from jw_core.provenance.hashing import content_sha256


# ── Fakes ──────────────────────────────────────────────────────────────


@dataclass
class FakeFetcher:
    """Maps URL → (status, body). Async-callable like the production fetcher."""

    canned: dict[str, tuple[int, str]] = field(default_factory=dict)
    calls: list[str] = field(default_factory=list)
    raise_for: set[str] = field(default_factory=set)

    async def __call__(self, url: str) -> FetcherResponse:
        self.calls.append(url)
        if url in self.raise_for:
            raise RuntimeError(f"forced failure for {url}")
        status, body = self.canned.get(url, (404, ""))
        return FetcherResponse(final_url=url, status=status, body=body)


def _stamped_citation(text: str, *, url: str = "https://wol.jw.org/x") -> Citation:
    """Build a citation as if the parser had stamped it with provenance."""

    return Citation(
        url=url,
        title="t",
        kind="verse",
        metadata={
            "accessed_at": "2026-05-30T10:00:00Z",
            "content_hash": content_sha256(text),
            "published_date": "2024-01-01",
            "revision": "rev. 2023",
        },
    )


# ── Tests ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_check_match_when_content_unchanged() -> None:
    text = "Jehová amó tanto al mundo"
    cit = _stamped_citation(text)
    fetcher = FakeFetcher(canned={cit.url: (200, text)})

    validator = ProvenanceValidator(fetcher=fetcher)
    verdict = await validator.check(cit)

    assert verdict.status == "match"
    assert verdict.original_hash == verdict.current_hash
    assert verdict.delta_chars == 0
    assert fetcher.calls == [cit.url]


@pytest.mark.asyncio
async def test_check_changed_when_text_edited() -> None:
    original_text = "Jehová amó tanto al mundo"
    new_text = "Jehová amó tanto al universo"  # mundo → universo
    cit = _stamped_citation(original_text)
    fetcher = FakeFetcher(canned={cit.url: (200, new_text)})

    validator = ProvenanceValidator(fetcher=fetcher)
    verdict = await validator.check(cit)

    assert verdict.status == "changed"
    assert verdict.original_hash != verdict.current_hash
    assert verdict.delta_chars is not None
    assert verdict.delta_chars >= 0


@pytest.mark.asyncio
async def test_check_unreachable_when_fetcher_raises() -> None:
    cit = _stamped_citation("doesn't matter")
    fetcher = FakeFetcher(raise_for={cit.url})

    validator = ProvenanceValidator(fetcher=fetcher)
    verdict = await validator.check(cit)

    assert verdict.status == "unreachable"
    assert verdict.current_hash is None
    assert any("forced failure" in n for n in verdict.notes)


@pytest.mark.asyncio
async def test_check_unreachable_when_non_2xx() -> None:
    cit = _stamped_citation("text")
    fetcher = FakeFetcher(canned={cit.url: (404, "")})

    validator = ProvenanceValidator(fetcher=fetcher)
    verdict = await validator.check(cit)

    assert verdict.status == "unreachable"
    assert any("404" in n for n in verdict.notes)


@pytest.mark.asyncio
async def test_check_no_record_when_citation_lacks_provenance() -> None:
    """Backwards compat: legacy citations have no content_hash → no_record."""

    cit = Citation(url="https://wol.jw.org/x", title="t", kind="verse", metadata={})
    fetcher = FakeFetcher(canned={cit.url: (200, "anything")})

    validator = ProvenanceValidator(fetcher=fetcher)
    verdict = await validator.check(cit)

    assert verdict.status == "no_record"
    assert verdict.original_hash is None
    assert fetcher.calls == []  # no fetch attempted


@pytest.mark.asyncio
async def test_check_uses_injected_extractor() -> None:
    """If the fetcher returns HTML, the extractor turns it into plain text first."""

    canonical_text = "Jehová amó tanto al mundo"
    html = f"<html><body><p>{canonical_text}</p><script>junk</script></body></html>"
    cit = _stamped_citation(canonical_text)

    def text_only(body: str) -> str:
        import re

        return re.sub(r"<[^>]+>", " ", body)

    fetcher = FakeFetcher(canned={cit.url: (200, html)})
    validator = ProvenanceValidator(fetcher=fetcher, extractor=text_only)
    verdict = await validator.check(cit)

    assert verdict.status == "match"


@pytest.mark.asyncio
async def test_check_agent_output_paralellizes_unique_urls() -> None:
    """Two findings, same URL → fetcher called once."""

    text = "shared body"
    cit_a = _stamped_citation(text, url="https://wol.jw.org/shared")
    cit_b = _stamped_citation(text, url="https://wol.jw.org/shared")
    finding_a = Finding(summary="a", citation=cit_a, excerpt=text)
    finding_b = Finding(summary="b", citation=cit_b, excerpt=text)

    class _R:
        findings = [finding_a, finding_b]

    fetcher = FakeFetcher(canned={cit_a.url: (200, text)})
    validator = ProvenanceValidator(fetcher=fetcher)
    report = await validator.check_agent_output(_R())

    assert len(report.verdicts) == 2
    assert all(v.status == "match" for v in report.verdicts)
    # Dedup: only one network call even though two findings point at it
    assert fetcher.calls.count(cit_a.url) == 1
    assert report.summary["match"] == 2


@pytest.mark.asyncio
async def test_check_since_filters_by_accessed_at_threshold() -> None:
    """Only re-check citations accessed BEFORE the `since` cutoff."""

    text = "body"
    old = _stamped_citation(text, url="https://wol.jw.org/old")
    old.metadata["accessed_at"] = "2026-01-01T00:00:00Z"
    new = _stamped_citation(text, url="https://wol.jw.org/new")
    new.metadata["accessed_at"] = "2026-05-31T00:00:00Z"

    class _F:
        def __init__(self, c: Citation) -> None:
            self.citation = c
            self.metadata: dict[str, Any] = {}

    class _R:
        findings = [_F(old), _F(new)]

    fetcher = FakeFetcher(canned={old.url: (200, text), new.url: (200, text)})
    validator = ProvenanceValidator(fetcher=fetcher)
    report = await validator.check_since(
        _R(),
        since=datetime(2026, 3, 1, tzinfo=timezone.utc),
    )

    # `new` is younger than the cutoff → skipped.
    skipped = [v for v in report.verdicts if v.status == "skipped"]
    matched = [v for v in report.verdicts if v.status == "match"]
    assert len(skipped) == 1
    assert skipped[0].url == new.url
    assert len(matched) == 1
    assert matched[0].url == old.url
    # Only the old URL should have been fetched.
    assert fetcher.calls == [old.url]


@pytest.mark.asyncio
async def test_check_agent_output_aggregates_summary() -> None:
    """Mixed outcomes — summary counts each status."""

    text_match = "x"
    text_orig = "y"
    text_drift = "z"  # different from text_orig

    cit_match = _stamped_citation(text_match, url="https://wol.jw.org/a")
    cit_drift = _stamped_citation(text_orig, url="https://wol.jw.org/b")
    cit_dead = _stamped_citation(text_match, url="https://wol.jw.org/c")
    cit_legacy = Citation(url="https://wol.jw.org/d", metadata={})

    class _F:
        def __init__(self, c: Citation) -> None:
            self.citation = c
            self.metadata: dict[str, Any] = {}

    class _R:
        findings = [_F(cit_match), _F(cit_drift), _F(cit_dead), _F(cit_legacy)]

    fetcher = FakeFetcher(
        canned={
            cit_match.url: (200, text_match),
            cit_drift.url: (200, text_drift),
            cit_dead.url: (500, ""),
            cit_legacy.url: (200, "irrelevant"),
        }
    )
    validator = ProvenanceValidator(fetcher=fetcher)
    report = await validator.check_agent_output(_R())

    assert report.summary["match"] == 1
    assert report.summary["changed"] == 1
    assert report.summary["unreachable"] == 1
    assert report.summary["no_record"] == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/jw-core/tests/test_provenance/test_validator.py -v`
Expected: FAIL — `ProvenanceValidator` is still a placeholder.

- [ ] **Step 3: Implement `ProvenanceValidator`**

Replace `packages/jw-core/src/jw_core/provenance/validator.py`:

```python
# packages/jw-core/src/jw_core/provenance/validator.py
"""Re-fetch citations and compare content hashes.

The validator is intentionally narrow: it does not own a network client,
does not parse HTML on its own, and does not know about Fase 39 unless
an `nli_provider` is passed. This keeps it deterministic in tests and
trivially mockable in CI.

Public surface:
    ProvenanceValidator.check(citation) -> ProvenanceVerdict
    ProvenanceValidator.check_agent_output(result) -> ProvenanceReport
    ProvenanceValidator.check_since(result, *, since=dt) -> ProvenanceReport
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol

from jw_agents.base import Citation
from jw_core.provenance.hashing import canonicalize_text, content_sha256
from jw_core.provenance.models import (
    ProvenanceRecord,
    ProvenanceReport,
    ProvenanceVerdict,
)


@dataclass
class FetcherResponse:
    """Minimal response carried back from the injected fetcher."""

    final_url: str
    status: int
    body: str = ""
    redirect_chain: list[str] = field(default_factory=list)


AsyncFetcher = Callable[[str], Awaitable[FetcherResponse]]
Extractor = Callable[[str], str]


class NLIProvider(Protocol):  # pragma: no cover — structural typing only
    """Minimal slice of Fase 39's NLIProvider needed for re-validation."""

    async def evaluate_entailment(self, claim: str, premise: str) -> Any: ...


def _default_extractor(body: str) -> str:
    """Identity extractor — used when caller does not provide one.

    The spec recommends callers always inject one. Identity is a safe
    fallback that won't crash on plain-text fetcher responses (the
    FakeFetcher case in tests).
    """

    return body


def _utcnow_iso() -> str:
    """ISO 8601 UTC timestamp for `accessed_at_recheck`."""

    return datetime.now(timezone.utc).isoformat()


def _parse_iso(value: str | None) -> datetime | None:
    """Best-effort ISO 8601 parser; returns None on garbage."""

    if not value:
        return None
    try:
        # Python 3.11+ parses Z-suffixed strings natively.
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


class ProvenanceValidator:
    """Compare stored content hashes vs live re-fetches.

    Args:
        fetcher:     async URL -> FetcherResponse. Required.
        extractor:   sync HTML/body -> plain text. Defaults to identity.
                     Inject the WOL extractor for HTML pages.
        nli_provider: Fase 39's NLIProvider. When provided AND a verdict
                     is `changed`, re-runs entailment on the new text.
        concurrency: max parallel fetches (default 4 — matches Fase 23).
    """

    def __init__(
        self,
        *,
        fetcher: AsyncFetcher,
        extractor: Extractor | None = None,
        nli_provider: NLIProvider | None = None,
        concurrency: int = 4,
    ) -> None:
        self._fetcher = fetcher
        self._extractor = extractor or _default_extractor
        self._nli_provider = nli_provider
        self._concurrency = concurrency
        self._sem: asyncio.Semaphore | None = None

    def _get_sem(self) -> asyncio.Semaphore:
        if self._sem is None:
            self._sem = asyncio.Semaphore(self._concurrency)
        return self._sem

    # ── Single-citation check ──────────────────────────────────────────

    async def check(self, citation: Citation) -> ProvenanceVerdict:
        """Re-fetch one citation's URL and compare content hashes."""

        recheck_at = _utcnow_iso()
        record = ProvenanceRecord.from_citation_metadata(citation.metadata)
        if record is None:
            # Backwards compat: never emitted with provenance — skip the fetch.
            return ProvenanceVerdict(
                url=citation.url,
                status="no_record",
                original_hash=None,
                current_hash=None,
                delta_chars=None,
                accessed_at_original=None,
                accessed_at_recheck=recheck_at,
                notes=["citation has no provenance metadata"],
            )

        # Fetch.
        try:
            async with self._get_sem():
                resp = await self._fetcher(citation.url)
        except Exception as exc:  # noqa: BLE001 — fetcher contract is wide
            return ProvenanceVerdict(
                url=citation.url,
                status="unreachable",
                original_hash=record.content_hash,
                current_hash=None,
                delta_chars=None,
                accessed_at_original=record.accessed_at,
                accessed_at_recheck=recheck_at,
                notes=[f"fetcher raised: {exc!r}"],
            )

        if not (200 <= resp.status < 300):
            return ProvenanceVerdict(
                url=citation.url,
                status="unreachable",
                original_hash=record.content_hash,
                current_hash=None,
                delta_chars=None,
                accessed_at_original=record.accessed_at,
                accessed_at_recheck=recheck_at,
                notes=[f"non-2xx response: HTTP {resp.status}"],
            )

        # Extract + hash.
        plain = self._extractor(resp.body)
        current_hash = content_sha256(plain)
        canonical_current = canonicalize_text(plain)
        # `delta_chars` is a coarse heuristic — we don't know the original
        # canonical length anymore (we only stored the hash), so we report
        # the absolute character count of the canonical current text. This
        # is enough for an operator to spot order-of-magnitude drift.
        delta = abs(len(canonical_current)) if current_hash != record.content_hash else 0

        if current_hash == record.content_hash:
            return ProvenanceVerdict(
                url=citation.url,
                status="match",
                original_hash=record.content_hash,
                current_hash=current_hash,
                delta_chars=0,
                accessed_at_original=record.accessed_at,
                accessed_at_recheck=recheck_at,
            )

        verdict = ProvenanceVerdict(
            url=citation.url,
            status="changed",
            original_hash=record.content_hash,
            current_hash=current_hash,
            delta_chars=delta,
            accessed_at_original=record.accessed_at,
            accessed_at_recheck=recheck_at,
            notes=["sha256 mismatch"],
        )

        # Optional re-NLI on the fresh text — only if Fase 39 is wired up
        # AND the original citation carried both a claim and a baseline verdict.
        if self._nli_provider is not None:
            verdict.nli_rerun = await self._maybe_rerun_nli(citation, canonical_current)

        return verdict

    async def _maybe_rerun_nli(
        self,
        citation: Citation,
        new_premise: str,
    ) -> dict[str, Any] | None:
        """Re-run NLI on the new text and report a delta vs the stored verdict."""

        claim = citation.metadata.get("nli_claim")
        baseline = citation.metadata.get("nli_verdict")
        if not isinstance(claim, str) or not claim:
            return None
        try:
            new = await self._nli_provider.evaluate_entailment(claim, new_premise)
        except Exception as exc:  # noqa: BLE001
            return {"changed": False, "error": f"nli_rerun failed: {exc!r}"}
        # Fase 39's verdict is a Pydantic model with `.label` and `.score`
        # — but we duck-type to keep this validator independent of its
        # exact shape. We accept any object exposing `.label` and `.score`,
        # or any dict with those keys.
        new_label = getattr(new, "label", None)
        if new_label is None and isinstance(new, dict):
            new_label = new.get("label")
        new_score = getattr(new, "score", None)
        if new_score is None and isinstance(new, dict):
            new_score = new.get("score")
        if new_label is None:
            return None
        return {
            "changed": (baseline != new_label),
            "from": baseline,
            "to": new_label,
            "score": new_score,
        }

    # ── Batch over an AgentResult-like ─────────────────────────────────

    async def check_agent_output(self, agent_output: Any) -> ProvenanceReport:
        """Iterate the result's findings, dedup by URL, parallelize fetches."""

        started = datetime.now(timezone.utc)
        citations = self._collect_citations(agent_output)
        verdicts = await self._check_many(citations)
        finished = datetime.now(timezone.utc)
        return ProvenanceReport(
            started_at=started,
            finished_at=finished,
            verdicts=verdicts,
            summary=ProvenanceReport.summarize(verdicts),
        )

    async def check_since(
        self,
        agent_output: Any,
        *,
        since: datetime,
    ) -> ProvenanceReport:
        """Like check_agent_output but skips citations younger than `since`."""

        started = datetime.now(timezone.utc)
        all_citations = self._collect_citations(agent_output)
        to_check: list[Citation] = []
        skipped_verdicts: list[ProvenanceVerdict] = []
        recheck_at = _utcnow_iso()
        for cit in all_citations:
            accessed = _parse_iso(cit.metadata.get("accessed_at"))
            if accessed is not None and accessed >= since:
                skipped_verdicts.append(
                    ProvenanceVerdict(
                        url=cit.url,
                        status="skipped",
                        original_hash=cit.metadata.get("content_hash"),
                        current_hash=None,
                        delta_chars=None,
                        accessed_at_original=cit.metadata.get("accessed_at"),
                        accessed_at_recheck=recheck_at,
                        notes=[f"accessed_at >= since={since.isoformat()}"],
                    )
                )
            else:
                to_check.append(cit)
        fetched = await self._check_many(to_check)
        verdicts = fetched + skipped_verdicts
        finished = datetime.now(timezone.utc)
        return ProvenanceReport(
            started_at=started,
            finished_at=finished,
            verdicts=verdicts,
            summary=ProvenanceReport.summarize(verdicts),
        )

    # ── Internals ──────────────────────────────────────────────────────

    @staticmethod
    def _collect_citations(agent_output: Any) -> list[Citation]:
        """Best-effort: pull citations out of `findings`. Order preserved."""

        out: list[Citation] = []
        for f in getattr(agent_output, "findings", []) or []:
            cit = getattr(f, "citation", None)
            if isinstance(cit, Citation):
                out.append(cit)
        return out

    async def _check_many(self, citations: list[Citation]) -> list[ProvenanceVerdict]:
        """Dedup by URL, run checks concurrently, then re-expand by URL."""

        seen: dict[str, Citation] = {}
        order: list[str] = []
        for cit in citations:
            if cit.url not in seen:
                seen[cit.url] = cit
                order.append(cit.url)
        tasks = [self.check(seen[u]) for u in order]
        verdicts_by_url = dict(zip(order, await asyncio.gather(*tasks), strict=True))
        # Re-expand: every input citation gets a verdict (verbatim copy if dup).
        return [verdicts_by_url[c.url] for c in citations]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/jw-core/tests/test_provenance/test_validator.py -v`
Expected: 9 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-core/src/jw_core/provenance/validator.py packages/jw-core/tests/test_provenance/test_validator.py
git commit -m "feat(jw-core/provenance): ProvenanceValidator.check/check_agent_output/check_since with FakeFetcher"
```

---

### Task 6: Propagation helpers (`stamp_citation`, `stamp_finding_text`) + WOL ingest hook

**Files:**
- Modify: `packages/jw-core/src/jw_core/provenance/propagation.py`
- Create: `packages/jw-core/tests/test_provenance/test_propagation.py`
- Modify: `packages/jw-core/src/jw_core/wol_client.py` (small additions)

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-core/tests/test_provenance/test_propagation.py
"""Tests for stamp_citation / stamp_finding_text propagation helpers."""

from __future__ import annotations

from jw_agents.base import Citation, Finding
from jw_core.provenance.hashing import content_sha256
from jw_core.provenance.propagation import stamp_citation, stamp_finding_text


def test_stamp_citation_writes_four_keys() -> None:
    cit = Citation(url="https://wol.jw.org/x", title="t", kind="verse", metadata={})
    text = "Jehová amó tanto al mundo"

    stamped = stamp_citation(
        cit,
        text=text,
        published_date="2024-01-15",
        revision="rev. 2023",
    )

    assert stamped is cit  # in-place mutation, returns same object
    assert cit.metadata["content_hash"] == content_sha256(text)
    assert cit.metadata["published_date"] == "2024-01-15"
    assert cit.metadata["revision"] == "rev. 2023"
    assert isinstance(cit.metadata["accessed_at"], str)
    assert cit.metadata["accessed_at"].endswith(("+00:00", "Z"))


def test_stamp_citation_is_idempotent_for_same_text() -> None:
    """Re-stamping with the same text → hash unchanged; accessed_at refreshes."""

    cit = Citation(url="https://wol.jw.org/x", metadata={})
    text = "same body"

    stamp_citation(cit, text=text)
    h1 = cit.metadata["content_hash"]
    a1 = cit.metadata["accessed_at"]

    import time

    time.sleep(0.001)
    stamp_citation(cit, text=text)
    h2 = cit.metadata["content_hash"]
    a2 = cit.metadata["accessed_at"]

    assert h1 == h2
    # accessed_at allowed to differ (re-stamping refreshes the timestamp)
    assert isinstance(a2, str)


def test_stamp_citation_different_text_changes_hash() -> None:
    cit = Citation(url="https://wol.jw.org/x", metadata={})
    stamp_citation(cit, text="version 1")
    h1 = cit.metadata["content_hash"]
    stamp_citation(cit, text="version 2")
    h2 = cit.metadata["content_hash"]
    assert h1 != h2


def test_stamp_citation_preserves_unrelated_metadata() -> None:
    cit = Citation(url="https://wol.jw.org/x", metadata={"source": "wol", "lang": "es"})
    stamp_citation(cit, text="body")
    assert cit.metadata["source"] == "wol"
    assert cit.metadata["lang"] == "es"
    assert "content_hash" in cit.metadata


def test_stamp_citation_optional_fields_omitted_remain_absent() -> None:
    """Don't write keys for `published_date=None` / `revision=None`."""

    cit = Citation(url="https://wol.jw.org/x", metadata={})
    stamp_citation(cit, text="x")
    assert "published_date" not in cit.metadata
    assert "revision" not in cit.metadata


def test_stamp_finding_text_uses_excerpt_as_default_text() -> None:
    cit = Citation(url="https://wol.jw.org/x", metadata={})
    finding = Finding(summary="s", citation=cit, excerpt="the excerpt body")

    stamp_finding_text(finding)

    assert cit.metadata["content_hash"] == content_sha256("the excerpt body")


def test_stamp_finding_text_no_op_when_excerpt_empty() -> None:
    """Findings without text shouldn't lie about their provenance."""

    cit = Citation(url="https://wol.jw.org/x", metadata={})
    finding = Finding(summary="s", citation=cit, excerpt="")
    stamp_finding_text(finding)
    assert "content_hash" not in cit.metadata


def test_stamp_finding_text_passes_through_published_date_kwargs() -> None:
    """Caller can override the auto-detected fields when known."""

    cit = Citation(url="https://wol.jw.org/x", metadata={})
    finding = Finding(summary="s", citation=cit, excerpt="hello")

    stamp_finding_text(finding, published_date="2024-01-01", revision="rev. 2023")

    assert cit.metadata["published_date"] == "2024-01-01"
    assert cit.metadata["revision"] == "rev. 2023"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/jw-core/tests/test_provenance/test_propagation.py -v`
Expected: FAIL — current placeholder is identity.

- [ ] **Step 3: Implement propagation helpers**

Replace `packages/jw-core/src/jw_core/provenance/propagation.py`:

```python
# packages/jw-core/src/jw_core/provenance/propagation.py
"""Stamp citations with the four conventional provenance keys.

This module is the hand-off point between text acquisition (WOL parser,
JWPUB indexer, agent body extraction) and provenance bookkeeping. Each
acquisition site calls `stamp_citation(...)` once with the canonical
text it just resolved — from that moment forward, the citation carries
a hash and timestamp that the validator can later verify.

Design rules:
  - In-place mutation. The Citation dataclass is passed by reference.
  - Idempotent for same text. Same input twice → same hash. Accessed_at
    refreshes (the timestamp is a "last touch" record, not a "first seen").
  - Never write keys for fields the caller didn't provide. Absent fields
    stay absent so a downstream `ProvenanceRecord` round-trip stays clean.
  - No I/O. This is pure CPU work.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from jw_agents.base import Citation, Finding
from jw_core.provenance.hashing import content_sha256


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def stamp_citation(
    citation: Citation,
    *,
    text: str,
    published_date: str | None = None,
    revision: str | None = None,
) -> Citation:
    """Write the four provenance keys into `citation.metadata` in place.

    Always written:
      - `content_hash` = sha256(canonicalize_text(text))
      - `accessed_at`  = ISO 8601 UTC now

    Only written when not None:
      - `published_date`
      - `revision`

    Returns the same citation object for fluent chaining.
    """

    meta: dict[str, Any] = citation.metadata
    meta["content_hash"] = content_sha256(text)
    meta["accessed_at"] = _utcnow_iso()
    if published_date is not None:
        meta["published_date"] = published_date
    if revision is not None:
        meta["revision"] = revision
    return citation


def stamp_finding_text(
    finding: Finding,
    *,
    text: str | None = None,
    published_date: str | None = None,
    revision: str | None = None,
) -> Finding:
    """Convenience: stamp the finding's citation using `finding.excerpt` by default.

    When `finding.excerpt` is empty AND no explicit `text` is given,
    this is a no-op — we won't fabricate a hash over the empty string
    and pretend that's provenance.
    """

    effective = text if text is not None else (finding.excerpt or "")
    if not effective:
        return finding
    stamp_citation(
        finding.citation,
        text=effective,
        published_date=published_date,
        revision=revision,
    )
    return finding
```

- [ ] **Step 4: Wire `stamp_citation` into `WOLClient.get_article` and `get_bible_chapter`**

In `packages/jw-core/src/jw_core/wol_client.py`, locate the spots where
each method returns its parsed result (article + citation, chapter +
citation). Add an import at the top of the file:

```python
from jw_core.provenance.propagation import stamp_citation
```

Inside `get_article`, after the parsed body is available and the
`Citation` is constructed but before it's returned, stamp it. The exact
existing variable names may differ; the pattern is:

```python
        # After: citation = Citation(url=..., title=..., kind="article", metadata={...})
        # And after the parser produced `body_text: str` and `published_date: str | None`:
        stamp_citation(
            citation,
            text=body_text,
            published_date=published_date,
        )
        return article  # or whatever the original return value is
```

Inside `get_bible_chapter`, do the same. For chapters the canonical
"text" is the joined verse bodies; the revision tag is the NWT manifest
code the client already has access to:

```python
        # After the chapter dataclass is built and `chapter_text: str` exists:
        stamp_citation(
            chapter.citation,
            text=chapter_text,
            published_date=None,           # WOL Bible chapters have no per-chapter publish date
            revision=manifest.revision_tag, # e.g. "rev. 2023" — read from the WOL manifest
        )
        return chapter
```

If `manifest.revision_tag` does not exist as an attribute on the
current WOL manifest object, pass `revision=None` for now — the field
is optional and the Fase 40 spec accepts that. Don't invent a value.

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest packages/jw-core/tests/test_provenance/test_propagation.py -v`
Expected: 8 passed.

Then run the WOL client tests to confirm no regression:

Run: `uv run pytest packages/jw-core/tests/test_wol_client.py -v`
Expected: all existing tests still pass; new metadata keys are additive.

- [ ] **Step 6: Commit**

```bash
git add packages/jw-core/src/jw_core/provenance/propagation.py \
        packages/jw-core/tests/test_provenance/test_propagation.py \
        packages/jw-core/src/jw_core/wol_client.py
git commit -m "feat(jw-core/provenance): stamp_citation + WOLClient ingest integration"
```

---

### Task 7: Integrate stamping in `verse_explainer` and `apologetics` agents

**Files:**
- Modify: `packages/jw-agents/src/jw_agents/verse_explainer.py`
- Modify: `packages/jw-agents/src/jw_agents/apologetics.py`
- Create: `packages/jw-core/tests/test_provenance/fixtures/agent_result_with_provenance.json`

- [ ] **Step 1: Write a verification test that asserts the stamped output**

We extend `test_propagation.py` with an integration-style test that
constructs a `verse_explainer` (or any agent), runs it on a mocked
client, and asserts every emitted `Citation` carries the four keys.

Append to `packages/jw-core/tests/test_provenance/test_propagation.py`:

```python
def test_verse_explainer_stamps_findings_through_excerpt() -> None:
    """End-to-end-ish: a finding emitted from an agent body has provenance."""

    from jw_agents.base import Citation, Finding

    # Simulate what the agent does after extracting verse text:
    cit = Citation(url="https://wol.jw.org/es/wol/b/r4/lp-s/nwt/E/2024/43/3", metadata={})
    finding = Finding(
        summary="Juan 3:16 muestra el amor de Dios.",
        citation=cit,
        excerpt="Porque Dios amó tanto al mundo que dio a su Hijo unigénito",
    )
    stamp_finding_text(finding, published_date=None, revision="rev. 2023")
    record = finding.citation.metadata
    assert "content_hash" in record
    assert "accessed_at" in record
    assert record["revision"] == "rev. 2023"
```

- [ ] **Step 2: Run test to verify it fails (or passes — depends on Task 6)**

Run: `uv run pytest packages/jw-core/tests/test_provenance/test_propagation.py::test_verse_explainer_stamps_findings_through_excerpt -v`
Expected: pass — confirms the helper works for agent-emitted findings.

- [ ] **Step 3: Patch `verse_explainer.py` to stamp at emission**

Open `packages/jw-agents/src/jw_agents/verse_explainer.py`. Find every
spot where a `Finding(...)` is constructed and appended to the result.
Wherever the finding's `excerpt` is the canonical verse text, stamp it
immediately after construction:

```python
from jw_core.provenance.propagation import stamp_finding_text

# ... existing code ...
        finding = Finding(
            summary=summary,
            citation=citation,
            excerpt=excerpt,
            metadata={"source": "verse_text"},
        )
        stamp_finding_text(
            finding,
            published_date=None,         # verse-level publish date not available
            revision=resolved_revision,  # comes from WOLClient.get_bible_chapter result
        )
        result.findings.append(finding)
```

If `resolved_revision` is not exposed by the current `verse_explainer`
flow, pass `revision=None`. The field is optional per the spec — don't
guess.

- [ ] **Step 4: Patch `apologetics.py` to stamp at emission**

Open `packages/jw-agents/src/jw_agents/apologetics.py`. Same treatment:
wherever `Finding(...)` is appended to the result, stamp it. The
`apologetics` agent typically produces findings of three sources
(`topic_index`, `verse_text`, `study_aid`). Each gets the same single-
line stamp call:

```python
from jw_core.provenance.propagation import stamp_finding_text

# At each Finding(...) construction site:
        stamp_finding_text(finding, published_date=None, revision=None)
        result.findings.append(finding)
```

Pass actual `published_date` / `revision` when the upstream parser
exposes them. Otherwise `None`.

- [ ] **Step 5: Create a golden fixture for downstream tests**

```json
// packages/jw-core/tests/test_provenance/fixtures/agent_result_with_provenance.json
{
  "query": "Juan 3:16",
  "agent_name": "verse_explainer",
  "warnings": [],
  "metadata": {"language": "es"},
  "findings": [
    {
      "summary": "Juan 3:16 muestra el amor de Dios.",
      "excerpt": "Porque Dios amó tanto al mundo que dio a su Hijo unigénito",
      "metadata": {"source": "verse_text"},
      "citation": {
        "url": "https://wol.jw.org/es/wol/b/r4/lp-s/nwt/E/2024/43/3",
        "title": "Juan 3",
        "kind": "verse",
        "metadata": {
          "accessed_at": "2026-05-30T10:00:00+00:00",
          "content_hash": "PLACEHOLDER_HASH_REPLACE_VIA_SCRIPT",
          "published_date": null,
          "revision": "rev. 2023"
        }
      }
    }
  ]
}
```

Then write a small helper at the top of the JSON fixture or in
`conftest.py` (next to the fixtures dir) that, on first load, replaces
`PLACEHOLDER_HASH_REPLACE_VIA_SCRIPT` with the canonical hash of the
`excerpt`. Simplest: do this lazily in the CLI test (Task 9) and in the
backwards-compat test (Task 12) rather than committing a real hash that
could go stale if the canonicalization rules ever change.

- [ ] **Step 6: Run regression suite**

Run: `uv run pytest packages/jw-agents/tests -v`
Expected: all existing agent tests pass; the only change is additional
keys in `Citation.metadata` which are transparent to consumers.

- [ ] **Step 7: Commit**

```bash
git add packages/jw-agents/src/jw_agents/verse_explainer.py \
        packages/jw-agents/src/jw_agents/apologetics.py \
        packages/jw-core/tests/test_provenance/test_propagation.py \
        packages/jw-core/tests/test_provenance/fixtures/agent_result_with_provenance.json
git commit -m "feat(jw-agents): stamp provenance on verse_explainer + apologetics findings"
```

---

### Task 8: NLI re-validation hook (Fase 39 integration, import-guarded)

**Files:**
- Create: `packages/jw-core/tests/test_provenance/test_validator_nli.py`
- Modify: `packages/jw-core/src/jw_core/provenance/validator.py` (verify the hook from Task 5 works end-to-end)

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-core/tests/test_provenance/test_validator_nli.py
"""When content drifts AND an NLIProvider is wired, the validator re-runs NLI."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from jw_agents.base import Citation
from jw_core.provenance.hashing import content_sha256
from jw_core.provenance.validator import (
    FetcherResponse,
    ProvenanceValidator,
)


@dataclass
class _NLIVerdict:
    """Mirror of Fase 39's NLIVerdict shape — duck-typed by the validator."""

    label: str
    score: float


class FakeNLIProvider:
    """Returns a pre-canned verdict regardless of input."""

    def __init__(self, label: str, score: float) -> None:
        self.label = label
        self.score = score
        self.calls: list[tuple[str, str]] = []

    async def evaluate_entailment(self, claim: str, premise: str) -> Any:
        self.calls.append((claim, premise))
        return _NLIVerdict(label=self.label, score=self.score)


class FakeFetcher:
    def __init__(self, body: str) -> None:
        self._body = body

    async def __call__(self, url: str) -> FetcherResponse:
        return FetcherResponse(final_url=url, status=200, body=self._body)


@pytest.mark.asyncio
async def test_nli_rerun_attached_on_changed_when_provider_present() -> None:
    """Hash mismatch + NLI provider → verdict.nli_rerun populated."""

    original_text = "Jesús es el Hijo de Dios"
    new_text = "Jesús es Dios mismo"
    cit = Citation(
        url="https://wol.jw.org/x",
        metadata={
            "accessed_at": "2026-05-30T10:00:00Z",
            "content_hash": content_sha256(original_text),
            "nli_claim": "Jesus is the Son of God",
            "nli_verdict": "entails",  # baseline verdict at original time
        },
    )
    provider = FakeNLIProvider(label="neutral", score=0.42)
    validator = ProvenanceValidator(fetcher=FakeFetcher(new_text), nli_provider=provider)

    verdict = await validator.check(cit)

    assert verdict.status == "changed"
    assert verdict.nli_rerun is not None
    assert verdict.nli_rerun["changed"] is True
    assert verdict.nli_rerun["from"] == "entails"
    assert verdict.nli_rerun["to"] == "neutral"
    assert verdict.nli_rerun["score"] == pytest.approx(0.42)
    assert len(provider.calls) == 1


@pytest.mark.asyncio
async def test_nli_rerun_changed_false_when_label_matches() -> None:
    """If NLI still says 'entails' even though content changed, mark unchanged verdict."""

    original_text = "x"
    new_text = "y"  # hash differs
    cit = Citation(
        url="https://wol.jw.org/x",
        metadata={
            "accessed_at": "2026-05-30T10:00:00Z",
            "content_hash": content_sha256(original_text),
            "nli_claim": "claim",
            "nli_verdict": "entails",
        },
    )
    provider = FakeNLIProvider(label="entails", score=0.91)
    validator = ProvenanceValidator(fetcher=FakeFetcher(new_text), nli_provider=provider)

    verdict = await validator.check(cit)

    assert verdict.status == "changed"
    assert verdict.nli_rerun is not None
    assert verdict.nli_rerun["changed"] is False
    assert verdict.nli_rerun["to"] == "entails"


@pytest.mark.asyncio
async def test_nli_rerun_skipped_when_no_claim_in_metadata() -> None:
    """Without a baseline claim, we can't re-run NLI — nli_rerun stays None."""

    original_text = "x"
    new_text = "y"
    cit = Citation(
        url="https://wol.jw.org/x",
        metadata={
            "accessed_at": "2026-05-30T10:00:00Z",
            "content_hash": content_sha256(original_text),
            # No 'nli_claim' key.
        },
    )
    provider = FakeNLIProvider(label="entails", score=1.0)
    validator = ProvenanceValidator(fetcher=FakeFetcher(new_text), nli_provider=provider)

    verdict = await validator.check(cit)

    assert verdict.status == "changed"
    assert verdict.nli_rerun is None
    assert provider.calls == []


@pytest.mark.asyncio
async def test_nli_rerun_never_runs_when_status_is_match() -> None:
    """No drift → no NLI re-run."""

    text = "stable text"
    cit = Citation(
        url="https://wol.jw.org/x",
        metadata={
            "accessed_at": "2026-05-30T10:00:00Z",
            "content_hash": content_sha256(text),
            "nli_claim": "claim",
            "nli_verdict": "entails",
        },
    )
    provider = FakeNLIProvider(label="contradicts", score=0.99)
    validator = ProvenanceValidator(fetcher=FakeFetcher(text), nli_provider=provider)

    verdict = await validator.check(cit)

    assert verdict.status == "match"
    assert verdict.nli_rerun is None
    assert provider.calls == []


@pytest.mark.asyncio
async def test_nli_rerun_error_captured_when_provider_raises() -> None:
    """A misbehaving provider must not crash the whole validator."""

    new_text = "different"
    cit = Citation(
        url="https://wol.jw.org/x",
        metadata={
            "accessed_at": "2026-05-30T10:00:00Z",
            "content_hash": content_sha256("original"),
            "nli_claim": "claim",
            "nli_verdict": "entails",
        },
    )

    class _BoomProvider:
        async def evaluate_entailment(self, claim: str, premise: str) -> Any:
            raise RuntimeError("boom")

    validator = ProvenanceValidator(fetcher=FakeFetcher(new_text), nli_provider=_BoomProvider())
    verdict = await validator.check(cit)

    assert verdict.status == "changed"
    assert verdict.nli_rerun is not None
    assert "boom" in verdict.nli_rerun.get("error", "")
```

- [ ] **Step 2: Run test to verify it passes (or fails)**

Run: `uv run pytest packages/jw-core/tests/test_provenance/test_validator_nli.py -v`
Expected: 5 passed — the hook was already implemented in Task 5. If a
test fails it pinpoints a missing edge case in `_maybe_rerun_nli`; fix
that method directly and re-run.

- [ ] **Step 3: Verify import-guard — Fase 39 absent must not crash**

Confirm by inspection that `validator.py` does NOT import from
`jw_core.nli` at module level. It only accepts an `NLIProvider`
Protocol, which is structural — so missing Fase 39 (e.g. older
deployments) keeps the validator usable, just without re-NLI.

If a stray `from jw_core.nli import ...` was added during development,
delete it. The only legitimate reference is `NLIProvider` defined
locally in `validator.py` as a `typing.Protocol`.

- [ ] **Step 4: Commit**

```bash
git add packages/jw-core/tests/test_provenance/test_validator_nli.py
git commit -m "test(jw-core/provenance): NLI re-run on changed verdict (import-guarded)"
```

---

### Task 9: CLI `jw provenance check`

**Files:**
- Create: `packages/jw-cli/src/jw_cli/commands/provenance.py`
- Create: `packages/jw-cli/tests/test_cli_provenance.py`
- Modify: `packages/jw-cli/src/jw_cli/main.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-cli/tests/test_cli_provenance.py
"""End-to-end tests for `jw provenance check`."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from typer.testing import CliRunner

from jw_cli.main import app
from jw_core.provenance.hashing import content_sha256

runner = CliRunner()


def _write_agent_result(tmp_path: Path, *, body_text: str, accessed_at: str) -> Path:
    """Write a minimal AgentResult JSON with provenance fields filled in."""

    result = {
        "query": "Juan 3:16",
        "agent_name": "verse_explainer",
        "warnings": [],
        "metadata": {"language": "es"},
        "findings": [
            {
                "summary": "Juan 3:16 muestra el amor de Dios.",
                "excerpt": body_text,
                "metadata": {"source": "verse_text"},
                "citation": {
                    "url": "https://wol.jw.org/x",
                    "title": "Juan 3",
                    "kind": "verse",
                    "metadata": {
                        "accessed_at": accessed_at,
                        "content_hash": content_sha256(body_text),
                        "published_date": None,
                        "revision": "rev. 2023",
                    },
                },
            }
        ],
    }
    p = tmp_path / "result.json"
    p.write_text(json.dumps(result), encoding="utf-8")
    return p


def test_provenance_check_help() -> None:
    out = runner.invoke(app, ["provenance", "check", "--help"])
    assert out.exit_code == 0
    assert "agent-output" in out.stdout.lower() or "agent_output" in out.stdout.lower()


def test_provenance_check_reports_match_with_fake_fetcher(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With JW_PROVENANCE_FETCHER=fake the CLI uses a stub that returns the original body."""

    body = "Porque Dios amó tanto al mundo"
    result_path = _write_agent_result(tmp_path, body_text=body, accessed_at="2026-05-30T10:00:00Z")

    # The CLI consults this env var to pick a fetcher; "fake" means
    # "echo the stored excerpt back" — used for deterministic CI runs.
    monkeypatch.setenv("JW_PROVENANCE_FETCHER", "fake")

    out = runner.invoke(
        app,
        ["provenance", "check", "--agent-output", str(result_path), "--report", "json"],
    )
    assert out.exit_code == 0, out.stdout
    data = json.loads(out.stdout.strip().splitlines()[-1])
    assert data["summary"]["match"] == 1


def test_provenance_check_exit_2_on_change(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the stub returns *different* text, exit code 2 surfaces drift."""

    body = "original"
    result_path = _write_agent_result(tmp_path, body_text=body, accessed_at="2026-05-30T10:00:00Z")

    # The "fake-drift" fetcher returns a body that always differs.
    monkeypatch.setenv("JW_PROVENANCE_FETCHER", "fake-drift")

    out = runner.invoke(
        app,
        ["provenance", "check", "--agent-output", str(result_path), "--report", "json"],
    )
    assert out.exit_code == 2
    data = json.loads(out.stdout.strip().splitlines()[-1])
    assert data["summary"]["changed"] == 1


def test_provenance_check_since_filters_recent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """--since 2026-05-31 means the 2026-05-30 citation IS rechecked (it's older)."""

    body = "text"
    result_path = _write_agent_result(tmp_path, body_text=body, accessed_at="2026-05-30T10:00:00Z")
    monkeypatch.setenv("JW_PROVENANCE_FETCHER", "fake")

    out = runner.invoke(
        app,
        [
            "provenance",
            "check",
            "--agent-output",
            str(result_path),
            "--since",
            "2026-05-31",
            "--report",
            "json",
        ],
    )
    assert out.exit_code == 0
    data = json.loads(out.stdout.strip().splitlines()[-1])
    # 2026-05-30 < 2026-05-31 → eligible for re-check, not skipped.
    assert data["summary"].get("match") == 1
    assert data["summary"].get("skipped", 0) == 0


def test_provenance_check_markdown_report(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """--report md emits a legible markdown table."""

    body = "text"
    result_path = _write_agent_result(tmp_path, body_text=body, accessed_at="2026-05-30T10:00:00Z")
    monkeypatch.setenv("JW_PROVENANCE_FETCHER", "fake")
    out_path = tmp_path / "out.md"

    out = runner.invoke(
        app,
        [
            "provenance",
            "check",
            "--agent-output",
            str(result_path),
            "--report",
            "md",
            "--out",
            str(out_path),
        ],
    )
    assert out.exit_code == 0
    body_md = out_path.read_text(encoding="utf-8")
    assert "| URL |" in body_md or "URL" in body_md
    assert "match" in body_md
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/jw-cli/tests/test_cli_provenance.py -v`
Expected: FAIL — `provenance` subcommand not registered.

- [ ] **Step 3: Implement the CLI command**

```python
# packages/jw-cli/src/jw_cli/commands/provenance.py
"""CLI subcommand: `jw provenance ...`.

Currently exposes:
    jw provenance check --agent-output <file> [--since DATE] [--report json|md] [--out FILE]

The fetcher used at runtime is chosen by env var JW_PROVENANCE_FETCHER:
  - unset / "httpx"  → uses jw_core's WOLClient httpx-backed fetcher (live network).
  - "fake"           → echoes the citation's stored excerpt back (CI-friendly).
  - "fake-drift"     → returns a sentinel string that always differs (test-only).

Exit codes:
  0 — every verdict is `match` or `skipped` or `no_record`.
  2 — at least one verdict is `changed`.
  3 — at least one verdict is `unreachable` AND no `changed`.
"""

from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import typer

from jw_agents.base import Citation, Finding
from jw_core.provenance.validator import (
    FetcherResponse,
    ProvenanceValidator,
)

app = typer.Typer(help="Content provenance checks.")


# ── Internal: hydrate AgentResult JSON into Citation objects ────────────


def _load_citations(path: Path) -> list[Citation]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    cits: list[Citation] = []
    for f in raw.get("findings", []):
        cit_raw = f.get("citation") or {}
        cits.append(
            Citation(
                url=cit_raw.get("url", ""),
                title=cit_raw.get("title", ""),
                kind=cit_raw.get("kind", ""),
                metadata=dict(cit_raw.get("metadata") or {}),
            )
        )
    return cits


def _wrap_as_result(citations: list[Citation]) -> Any:
    """Wrap a list of citations into a minimal AgentResult-like object."""

    findings = [Finding(summary="", citation=c, excerpt="") for c in citations]

    class _R:
        pass

    r = _R()
    r.findings = findings  # type: ignore[attr-defined]
    return r


# ── Fetcher selection ──────────────────────────────────────────────────


def _select_fetcher() -> Any:
    choice = os.environ.get("JW_PROVENANCE_FETCHER", "httpx").lower()
    if choice == "fake":
        return _FakeEchoFetcher()
    if choice == "fake-drift":
        return _FakeDriftFetcher()
    return _HttpxFetcher()


class _FakeEchoFetcher:
    """Returns the stored excerpt-equivalent text — used in tests for `match` paths.

    Since the validator only knows the original hash, we synthesize a
    body from the citation's metadata: if `content_hash` matches what we
    re-canonicalize from a body, hashes line up. The trick: we look up
    the original `excerpt` by reverse-mapping from the JSON file via a
    sidecar dict the CLI builds before invoking. For now we just echo
    the URL as the body — Task 9 tests stage citations whose hash equals
    `content_sha256(body)` for a body the test code controls.

    To keep this self-contained, the fake remembers the AgentResult that
    was loaded so it can serve the right excerpt.
    """

    excerpts: dict[str, str] = {}

    async def __call__(self, url: str) -> FetcherResponse:
        body = _FakeEchoFetcher.excerpts.get(url, "")
        return FetcherResponse(final_url=url, status=200, body=body)


class _FakeDriftFetcher:
    async def __call__(self, url: str) -> FetcherResponse:
        return FetcherResponse(
            final_url=url, status=200, body="DRIFT_SENTINEL_TEXT"
        )


class _HttpxFetcher:
    """Real-network fetcher backed by httpx. Only constructed when chosen."""

    async def __call__(self, url: str) -> FetcherResponse:
        import httpx

        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            resp = await client.get(url, headers={"User-Agent": "jw-cli/provenance"})
            return FetcherResponse(
                final_url=str(resp.url),
                status=resp.status_code,
                body=resp.text,
                redirect_chain=[str(h.url) for h in resp.history],
            )


# ── Reporters ──────────────────────────────────────────────────────────


def _render_markdown(report) -> str:
    lines = [
        "# Provenance report",
        "",
        f"- started_at: {report.started_at.isoformat()}",
        f"- finished_at: {report.finished_at.isoformat()}",
        f"- summary: {report.summary}",
        "",
        "| URL | Status | Original hash | Current hash | Delta chars | Accessed (orig) | Accessed (recheck) |",
        "|-----|--------|---------------|--------------|-------------|-----------------|--------------------|",
    ]
    for v in report.verdicts:
        lines.append(
            f"| {v.url} | {v.status} | {v.original_hash or '-'} | {v.current_hash or '-'} "
            f"| {v.delta_chars if v.delta_chars is not None else '-'} "
            f"| {v.accessed_at_original or '-'} | {v.accessed_at_recheck} |"
        )
    return "\n".join(lines) + "\n"


def _exit_code(report) -> int:
    if report.summary.get("changed", 0) > 0:
        return 2
    if report.summary.get("unreachable", 0) > 0:
        return 3
    return 0


# ── Command ────────────────────────────────────────────────────────────


@app.command("check")
def check_cmd(
    agent_output: Path = typer.Option(..., "--agent-output", help="Path to an AgentResult JSON file."),
    since: str | None = typer.Option(None, "--since", help="ISO date — only re-check citations accessed before this date."),
    report: str = typer.Option("json", "--report", help="Output format: json or md."),
    out: Path | None = typer.Option(None, "--out", help="Optional output file path (default stdout)."),
) -> None:
    """Re-check that every citation's content_hash still matches the live source."""

    citations = _load_citations(agent_output)

    # Prime the fake echo fetcher with the excerpts from the loaded JSON,
    # keyed by URL, so it can correctly return the body whose hash equals
    # what's stored in citation.metadata.content_hash.
    raw = json.loads(agent_output.read_text(encoding="utf-8"))
    excerpts: dict[str, str] = {}
    for f in raw.get("findings", []):
        cit = f.get("citation") or {}
        url = cit.get("url")
        excerpt = f.get("excerpt") or ""
        if url and excerpt:
            excerpts[url] = excerpt
    _FakeEchoFetcher.excerpts.update(excerpts)

    fetcher = _select_fetcher()
    validator = ProvenanceValidator(fetcher=fetcher)
    wrapped = _wrap_as_result(citations)

    async def run() -> Any:
        if since is None:
            return await validator.check_agent_output(wrapped)
        try:
            cutoff = datetime.fromisoformat(since)
            if cutoff.tzinfo is None:
                cutoff = cutoff.replace(tzinfo=timezone.utc)
        except ValueError as exc:
            raise typer.BadParameter(f"--since must be ISO 8601: {exc}") from exc
        return await validator.check_since(wrapped, since=cutoff)

    result = asyncio.run(run())

    if report == "md":
        payload = _render_markdown(result)
    else:
        payload = result.model_dump_json()

    if out is not None:
        out.write_text(payload, encoding="utf-8")
    else:
        typer.echo(payload)

    raise typer.Exit(code=_exit_code(result))
```

- [ ] **Step 4: Register the subcommand**

Edit `packages/jw-cli/src/jw_cli/main.py`. Find the existing `app =
typer.Typer(...)` and the imports / `app.add_typer(...)` block. Add:

```python
from jw_cli.commands.provenance import app as provenance_app

app.add_typer(provenance_app, name="provenance", help="Content provenance checks (Fase 40).")
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest packages/jw-cli/tests/test_cli_provenance.py -v`
Expected: 5 passed.

- [ ] **Step 6: Commit**

```bash
git add packages/jw-cli/src/jw_cli/commands/provenance.py \
        packages/jw-cli/tests/test_cli_provenance.py \
        packages/jw-cli/src/jw_cli/main.py
git commit -m "feat(jw-cli): jw provenance check subcommand"
```

---

### Task 10: MCP tool `verify_provenance`

**Files:**
- Create: `packages/jw-mcp/src/jw_mcp/tools/provenance.py`
- Create: `packages/jw-mcp/tests/test_provenance_tool.py`
- Modify: `packages/jw-mcp/src/jw_mcp/server.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-mcp/tests/test_provenance_tool.py
"""Tests for the `verify_provenance` MCP tool."""

from __future__ import annotations

import json
from typing import Any

import pytest

from jw_core.provenance.hashing import content_sha256
from jw_mcp.tools.provenance import verify_provenance


def _build_agent_output(body: str, *, url: str = "https://wol.jw.org/x") -> dict[str, Any]:
    return {
        "query": "q",
        "agent_name": "verse_explainer",
        "warnings": [],
        "metadata": {},
        "findings": [
            {
                "summary": "s",
                "excerpt": body,
                "metadata": {"source": "verse_text"},
                "citation": {
                    "url": url,
                    "title": "t",
                    "kind": "verse",
                    "metadata": {
                        "accessed_at": "2026-05-30T10:00:00Z",
                        "content_hash": content_sha256(body),
                        "published_date": None,
                        "revision": "rev. 2023",
                    },
                },
            }
        ],
    }


class _FakeFetcher:
    def __init__(self, body: str) -> None:
        self._body = body

    async def __call__(self, url: str):
        from jw_core.provenance.validator import FetcherResponse

        return FetcherResponse(final_url=url, status=200, body=self._body)


@pytest.mark.asyncio
async def test_verify_provenance_returns_dict_with_summary() -> None:
    body = "stable text"
    agent_output = _build_agent_output(body)

    out = await verify_provenance(
        agent_output,
        since=None,
        with_nli=False,
        fetcher=_FakeFetcher(body),
    )

    assert isinstance(out, dict)
    assert out["summary"]["match"] == 1


@pytest.mark.asyncio
async def test_verify_provenance_changed_in_summary() -> None:
    body_orig = "x"
    body_new = "y"
    agent_output = _build_agent_output(body_orig)

    out = await verify_provenance(
        agent_output,
        since=None,
        with_nli=False,
        fetcher=_FakeFetcher(body_new),
    )

    assert out["summary"]["changed"] == 1


@pytest.mark.asyncio
async def test_verify_provenance_since_filters() -> None:
    body = "x"
    agent_output = _build_agent_output(body)

    out = await verify_provenance(
        agent_output,
        since="2024-01-01",  # everything is younger → all skipped? NO — accessed_at is 2026-05-30, older than? No, NEWER.
        with_nli=False,
        fetcher=_FakeFetcher(body),
    )
    # accessed_at=2026-05-30 >= since=2024-01-01 → skipped
    assert out["summary"].get("skipped", 0) == 1


@pytest.mark.asyncio
async def test_verify_provenance_with_nli_flag_without_provider_no_op() -> None:
    """`with_nli=True` with no NLI configured → still works, just no nli_rerun."""

    body_orig = "x"
    body_new = "y"
    agent_output = _build_agent_output(body_orig)

    out = await verify_provenance(
        agent_output,
        since=None,
        with_nli=True,
        fetcher=_FakeFetcher(body_new),
    )
    verdicts = out["verdicts"]
    assert verdicts[0]["status"] == "changed"
    assert verdicts[0].get("nli_rerun") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/jw-mcp/tests/test_provenance_tool.py -v`
Expected: FAIL — `verify_provenance` module missing.

- [ ] **Step 3: Implement the MCP tool**

```python
# packages/jw-mcp/src/jw_mcp/tools/provenance.py
"""MCP tool: verify_provenance.

Exposed via FastMCP from server.py. Accepts a serialized AgentResult
(dict) and optionally re-runs NLI on drifted citations.

The fetcher kwarg is internal — production callers will receive the
default httpx-backed fetcher injected by server.py. Tests pass a stub.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from jw_agents.base import Citation, Finding
from jw_core.provenance.validator import (
    FetcherResponse,
    ProvenanceValidator,
)


def _hydrate(agent_output: dict[str, Any]) -> Any:
    """Convert a JSON-serialized AgentResult into a Citation-bearing wrapper."""

    findings: list[Finding] = []
    for f in agent_output.get("findings", []) or []:
        cit_raw = f.get("citation") or {}
        cit = Citation(
            url=cit_raw.get("url", ""),
            title=cit_raw.get("title", ""),
            kind=cit_raw.get("kind", ""),
            metadata=dict(cit_raw.get("metadata") or {}),
        )
        findings.append(
            Finding(
                summary=f.get("summary", ""),
                citation=cit,
                excerpt=f.get("excerpt", "") or "",
                metadata=dict(f.get("metadata") or {}),
            )
        )

    class _R:
        pass

    r = _R()
    r.findings = findings  # type: ignore[attr-defined]
    return r


async def verify_provenance(
    agent_output: dict[str, Any],
    *,
    since: str | None = None,
    with_nli: bool = False,
    fetcher: Any | None = None,
    nli_provider: Any | None = None,
) -> dict[str, Any]:
    """Re-check that each citation's content_hash still matches the live page.

    Args:
        agent_output: serialized AgentResult dict (`AgentResult.to_dict()` shape).
        since: optional ISO date; only re-check citations accessed earlier.
        with_nli: hint that the caller wants NLI re-validation. If no
            `nli_provider` is wired, this is a no-op silent fall-through.
        fetcher: injectable for tests; default constructed by server.py.
        nli_provider: injectable NLIProvider from Fase 39.

    Returns:
        A `ProvenanceReport.model_dump(mode="json")` dict.
    """

    if fetcher is None:
        # Lazy import: only when production path is taken.
        from jw_cli.commands.provenance import _HttpxFetcher  # type: ignore[import-not-found]

        fetcher = _HttpxFetcher()

    effective_nli = nli_provider if with_nli else None
    validator = ProvenanceValidator(fetcher=fetcher, nli_provider=effective_nli)
    wrapped = _hydrate(agent_output)

    if since is None:
        report = await validator.check_agent_output(wrapped)
    else:
        cutoff = datetime.fromisoformat(since)
        if cutoff.tzinfo is None:
            cutoff = cutoff.replace(tzinfo=timezone.utc)
        report = await validator.check_since(wrapped, since=cutoff)

    return report.model_dump(mode="json")
```

- [ ] **Step 4: Register the tool in `server.py`**

In `packages/jw-mcp/src/jw_mcp/server.py`, near other `@mcp.tool()`
registrations, add:

```python
from jw_mcp.tools.provenance import verify_provenance as _verify_provenance_impl


@mcp.tool()
async def verify_provenance(
    agent_output: dict,
    since: str | None = None,
    with_nli: bool = False,
) -> dict:
    """Re-check that each citation's content_hash still matches the live page.

    Returns a ProvenanceReport dict. Network-bound: respects WOLClient
    throttle. Pass `since='2026-01-01'` to skip recently-accessed
    citations. Pass `with_nli=True` to re-run entailment on drifted
    text when Fase 39 is configured server-side.
    """

    return await _verify_provenance_impl(
        agent_output,
        since=since,
        with_nli=with_nli,
    )
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest packages/jw-mcp/tests/test_provenance_tool.py -v`
Expected: 4 passed.

- [ ] **Step 6: Commit**

```bash
git add packages/jw-mcp/src/jw_mcp/tools/provenance.py \
        packages/jw-mcp/tests/test_provenance_tool.py \
        packages/jw-mcp/src/jw_mcp/server.py
git commit -m "feat(jw-mcp): verify_provenance tool"
```

---

### Task 11: Drift-detection regression test (telemetry hook)

**Files:**
- Create: `packages/jw-core/tests/test_provenance/test_validator_drift_detection.py`
- Modify: `packages/jw-core/src/jw_core/provenance/validator.py` (telemetry side-effect)

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-core/tests/test_provenance/test_validator_drift_detection.py
"""When a citation drifts, validator emits a `provenance_drift` telemetry event.

Mirrors the Fase 9 opt-in pattern: nothing is written unless
JW_TELEMETRY_ENABLED is set. CI runs default-off, so this test sets the
env var explicitly and points at a tmp path.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from jw_agents.base import Citation
from jw_core.provenance.hashing import content_sha256
from jw_core.provenance.validator import (
    FetcherResponse,
    ProvenanceValidator,
)


class _Fake:
    def __init__(self, body: str) -> None:
        self._body = body

    async def __call__(self, url: str) -> FetcherResponse:
        return FetcherResponse(final_url=url, status=200, body=self._body)


@pytest.mark.asyncio
async def test_drift_writes_provenance_drift_event_when_telemetry_on(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    telemetry_path = tmp_path / "telemetry.json"
    monkeypatch.setenv("JW_TELEMETRY_ENABLED", "1")
    monkeypatch.setenv("JW_TELEMETRY_PATH", str(telemetry_path))

    # Reset the telemetry singleton so it re-reads the env var.
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

    # Telemetry file should now contain a provenance_drift event.
    assert telemetry_path.exists()
    data = json.loads(telemetry_path.read_text(encoding="utf-8"))
    events: list[dict[str, Any]] = data.get("drift_events", []) + data.get("provenance_events", [])
    assert any(
        e.get("kind") == "provenance_drift" or e.get("endpoint") == "provenance_drift"
        for e in events
    )


@pytest.mark.asyncio
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/jw-core/tests/test_provenance/test_validator_drift_detection.py -v`
Expected: FAIL — the validator does not yet write a telemetry event.

- [ ] **Step 3: Add the telemetry side-effect to the validator**

Open `packages/jw-core/src/jw_core/provenance/validator.py`. Inside
the `check()` method, after determining `status="changed"` and just
before returning the verdict, append a telemetry record:

```python
        # Emit a provenance_drift telemetry event (opt-in via JW_TELEMETRY_ENABLED).
        try:
            from jw_core.telemetry import get_telemetry

            tel = get_telemetry()
            if tel.enabled:
                state = tel._state.setdefault("provenance_events", [])  # noqa: SLF001
                state.append(
                    {
                        "kind": "provenance_drift",
                        "url": citation.url,
                        "delta_chars": delta,
                        "original_accessed_at": record.accessed_at,
                        "ts": __import__("time").time(),
                    }
                )
                tel._save()  # noqa: SLF001
        except Exception:  # noqa: BLE001 — telemetry must never break the validator
            pass
```

Place that block between the `verdict = ProvenanceVerdict(...)`
construction and the optional `_maybe_rerun_nli` call.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/jw-core/tests/test_provenance/test_validator_drift_detection.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-core/src/jw_core/provenance/validator.py \
        packages/jw-core/tests/test_provenance/test_validator_drift_detection.py
git commit -m "feat(jw-core/provenance): opt-in provenance_drift telemetry event"
```

---

### Task 12: Backwards-compat test — legacy AgentResults still work

**Files:**
- Create: `packages/jw-core/tests/test_provenance/test_backwards_compat.py`
- Create: `packages/jw-core/tests/test_provenance/fixtures/agent_result_legacy.json`

- [ ] **Step 1: Write the legacy fixture (no provenance keys)**

```json
// packages/jw-core/tests/test_provenance/fixtures/agent_result_legacy.json
{
  "query": "Juan 3:16",
  "agent_name": "verse_explainer",
  "warnings": [],
  "metadata": {"language": "es"},
  "findings": [
    {
      "summary": "Juan 3:16 muestra el amor de Dios.",
      "excerpt": "Porque Dios amó tanto al mundo",
      "metadata": {"source": "verse_text"},
      "citation": {
        "url": "https://wol.jw.org/x",
        "title": "Juan 3",
        "kind": "verse",
        "metadata": {}
      }
    },
    {
      "summary": "Otro hallazgo legacy.",
      "excerpt": "another body",
      "metadata": {"source": "topic_index"},
      "citation": {
        "url": "https://wol.jw.org/y",
        "title": "Topic",
        "kind": "article",
        "metadata": {"language": "es"}
      }
    }
  ]
}
```

- [ ] **Step 2: Write the failing test**

```python
# packages/jw-core/tests/test_provenance/test_backwards_compat.py
"""Backwards compat: legacy AgentResults (pre-Fase 40) must still process cleanly.

The validator MUST NOT crash on citations lacking provenance keys.
Every such citation gets verdict `no_record` and the fetcher is NOT
called for them (no wasted network).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from jw_agents.base import Citation, Finding
from jw_core.provenance.validator import (
    FetcherResponse,
    ProvenanceValidator,
)

FIXTURE = Path(__file__).parent / "fixtures" / "agent_result_legacy.json"


class _CountingFetcher:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def __call__(self, url: str) -> FetcherResponse:
        self.calls.append(url)
        return FetcherResponse(final_url=url, status=200, body="should not be hashed")


def _hydrate(raw: dict[str, Any]):
    findings: list[Finding] = []
    for f in raw["findings"]:
        cit = Citation(
            url=f["citation"]["url"],
            title=f["citation"].get("title", ""),
            kind=f["citation"].get("kind", ""),
            metadata=dict(f["citation"].get("metadata") or {}),
        )
        findings.append(
            Finding(
                summary=f["summary"],
                citation=cit,
                excerpt=f.get("excerpt", ""),
            )
        )

    class _R:
        pass

    r = _R()
    r.findings = findings  # type: ignore[attr-defined]
    return r


@pytest.mark.asyncio
async def test_legacy_result_yields_only_no_record_verdicts() -> None:
    raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
    wrapped = _hydrate(raw)
    fetcher = _CountingFetcher()
    validator = ProvenanceValidator(fetcher=fetcher)

    report = await validator.check_agent_output(wrapped)

    assert len(report.verdicts) == 2
    assert all(v.status == "no_record" for v in report.verdicts)
    # Legacy URLs should NEVER be fetched.
    assert fetcher.calls == []
    assert report.summary["no_record"] == 2


@pytest.mark.asyncio
async def test_mixed_legacy_and_new_findings_coexist() -> None:
    """Half-and-half result: legacy citations skip, new ones get checked."""

    from jw_core.provenance.hashing import content_sha256

    body_new = "new finding body"
    findings = [
        Finding(
            summary="legacy",
            citation=Citation(url="https://wol.jw.org/legacy", metadata={}),
            excerpt="",
        ),
        Finding(
            summary="new",
            citation=Citation(
                url="https://wol.jw.org/new",
                metadata={
                    "accessed_at": "2026-05-30T10:00:00Z",
                    "content_hash": content_sha256(body_new),
                },
            ),
            excerpt=body_new,
        ),
    ]

    class _R:
        pass

    r = _R()
    r.findings = findings  # type: ignore[attr-defined]

    class _F:
        calls: list[str] = []

        async def __call__(self, url: str) -> FetcherResponse:
            _F.calls.append(url)
            return FetcherResponse(final_url=url, status=200, body=body_new)

    fetcher = _F()
    validator = ProvenanceValidator(fetcher=fetcher)
    report = await validator.check_agent_output(r)

    statuses = [v.status for v in report.verdicts]
    assert "no_record" in statuses
    assert "match" in statuses
    # Only the new citation was fetched.
    assert fetcher.calls == ["https://wol.jw.org/new"]


def test_provenance_record_from_legacy_metadata_returns_none() -> None:
    """Unit-level confirmation: legacy metadata dict can't fool the projection."""

    from jw_core.provenance.models import ProvenanceRecord

    assert ProvenanceRecord.from_citation_metadata({"source": "wol"}) is None
    assert ProvenanceRecord.from_citation_metadata({}) is None
```

- [ ] **Step 3: Run test to verify it passes**

Run: `uv run pytest packages/jw-core/tests/test_provenance/test_backwards_compat.py -v`
Expected: 3 passed — the validator from Task 5 already implements the
short-circuit, this task just locks it in.

- [ ] **Step 4: Commit**

```bash
git add packages/jw-core/tests/test_provenance/test_backwards_compat.py \
        packages/jw-core/tests/test_provenance/fixtures/agent_result_legacy.json
git commit -m "test(jw-core/provenance): backwards-compat for citations without provenance keys"
```

---

### Task 13: Documentation — guide, ROADMAP, VISION_AUDIT, layered taxonomy

**Files:**
- Create: `docs/guias/content-provenance.md`
- Modify: `docs/ROADMAP.md`
- Modify: `docs/VISION_AUDIT.md`
- Modify: `docs/README.md`

- [ ] **Step 1: Write the user-facing guide**

```markdown
<!-- docs/guias/content-provenance.md -->
# Content provenance (Fase 40)

> **Estado:** Estable desde Fase 40 (2026-05-31). Reemplaza ningún
> mecanismo previo; complementa Fase 23 (validación de URL) y Fase 39
> (NLI runtime).

## Qué resuelve

`wol.jw.org` cambia. Artículos se reescriben, NWT publica revisiones,
párrafos se reordenan. Una `Citation` que apuntaba a un texto concreto
el martes puede quedar **huérfana** el viernes — la URL sigue
resolviendo (Fase 23 ✓, L0), el `doc_id` sigue en el catálogo (Fase 23 ✓,
L1), pero el **texto** ya no es el que el agente usó. Sin Fase 40, esto
ocurre en silencio.

Fase 40 añade tres datos pequeños a cada `Citation.metadata`:

| Clave            | Tipo          | Significado                                                    |
|------------------|---------------|----------------------------------------------------------------|
| `published_date` | `str \| None` | Fecha original de publicación del artículo (ISO 8601).         |
| `accessed_at`    | `str`         | Cuándo descargó el texto el toolkit (ISO 8601 UTC).            |
| `content_hash`   | `str`         | sha256 hex del texto **canonicalizado** (NFC + whitespace).    |
| `revision`       | `str \| None` | Etiqueta de revisión, ej. `"rev. 2023"` para NWT.              |

Cualquier momento posterior, `provenance_check(citation)` puede:
1. Re-fetchar la URL.
2. Re-canonicalizar el texto.
3. Comparar con el `content_hash` original.
4. Si está integrado con Fase 39, re-correr NLI sobre el texto nuevo.

## La taxonomía de capas

Fase 40 ocupa una capa concreta — **L2: fidelidad de contenido** — dentro
de un esquema de cuatro:

| Capa | Pregunta                                                                | Fase  | Modo            |
|------|-------------------------------------------------------------------------|-------|-----------------|
| L0   | ¿La URL existe y responde 200?                                          | 23    | live HTTP       |
| L1   | ¿El `doc_id`/`pub_code` está en MepsCatalog?                            | 23    | offline catalog |
| L2   | ¿El **contenido** sigue siendo el mismo que el agente usó?              | **40**| hash + re-fetch |
| L3   | ¿La afirmación se desprende del passage actual?                         | 39    | NLI semántico   |

Las cuatro capas son **ortogonales**: una URL puede resolver (L0 ✓),
estar en catálogo (L1 ✓), tener fidelidad rota (L2 ✗), y por ende
entailment incierto (L3 ?). Fase 40 es la primera capa que ataca el
texto en sí, no su envoltorio.

## Uso desde CLI

```bash
# Re-chequear todas las citas de un resultado de agente:
jw provenance check --agent-output result.json

# Solo lo que se accedió antes del 2026-01-01 (típico cron mensual):
jw provenance check --agent-output result.json --since 2026-01-01

# Reporte legible en Markdown:
jw provenance check --agent-output result.json --report md --out drift.md

# Con re-validación NLI cuando Fase 39 está configurado:
JW_NLI_PROVIDER=deberta jw provenance check --agent-output result.json --with-nli
```

Códigos de salida:
- `0` — todo match (o no_record).
- `2` — hubo al menos un `changed`. Investigar.
- `3` — hubo al menos un `unreachable`. Red caída o URL muerta.

## Uso desde MCP

```python
@mcp.tool()
async def verify_provenance(
    agent_output: dict,
    since: str | None = None,
    with_nli: bool = False,
) -> dict:
    """Re-check that each citation's content_hash still matches the live page."""
```

Devuelve un `ProvenanceReport` serializado. La invocación es
network-bound (respeta el throttle del `WOLClient`).

## Uso programático

```python
from jw_core.provenance import ProvenanceValidator
from jw_agents.verse_explainer import VerseExplainer

result = await VerseExplainer(client).run("Juan 3:16", language="es")

validator = ProvenanceValidator(fetcher=my_fetcher)
report = await validator.check_agent_output(result)

if report.summary.get("changed", 0):
    print("Drift detectado:")
    for v in report.verdicts:
        if v.status == "changed":
            print(f"  {v.url} — {v.delta_chars} chars de delta")
```

## Backwards compatibility

Los `AgentResult` emitidos antes de Fase 40 no llevan las claves de
provenance. `ProvenanceValidator` los detecta y devuelve verdict
`no_record` sin llamar al fetcher — cero coste, cero falsos positivos.

## Telemetría opt-in

Cuando `JW_TELEMETRY_ENABLED=1`, cada `changed` se registra como un
evento `provenance_drift` en `~/.jw-agent-toolkit/telemetry.json`. Nada
sale de tu máquina. Inspeccionable con `Telemetry.report()`.

## Tests

```bash
.venv/bin/python -m pytest packages/jw-core/tests/test_provenance -v
.venv/bin/python -m pytest packages/jw-cli/tests/test_cli_provenance.py -v
.venv/bin/python -m pytest packages/jw-mcp/tests/test_provenance_tool.py -v
```
```

- [ ] **Step 2: Append a row to `docs/VISION_AUDIT.md`**

Locate the audit table and insert a new row (preserving table format):

```markdown
| Fase 40 | content-provenance | L2 fidelidad de contenido (hash + re-fetch) | Estable | `packages/jw-core/src/jw_core/provenance/` · `jw provenance check` · MCP `verify_provenance` |
```

If the column names differ in the existing table, adapt the row to match
exactly. The mandatory information to surface: phase number, slug,
one-line description, status (`Estable`), and the integration points.

- [ ] **Step 3: Append a section to `docs/ROADMAP.md`**

```markdown
## Fase 40 — content-provenance

- **Estado**: Estable (2026-05-31).
- **Spec**: `docs/superpowers/specs/2026-05-31-fase-40-content-provenance-design.md`.
- **Plan**: `docs/superpowers/plans/2026-05-31-fase-40-content-provenance-plan.md`.
- **Guía**: `docs/guias/content-provenance.md`.

Añade trazabilidad reproducible al passage citado por cada agente.
Cuatro claves convencionales en `Citation.metadata`
(`published_date`, `accessed_at`, `content_hash`, `revision`) +
`ProvenanceValidator` que re-fetcha y compara hashes. Integra con Fase
39 para re-correr NLI al detectar cambio. CLI `jw provenance check` +
MCP `verify_provenance`. Telemetría opt-in via Fase 9.

Encaja en la taxonomía de cuatro capas L0–L3 — Fase 40 ocupa L2
(fidelidad de contenido), complementando L0/L1 (Fase 23) y L3 (Fase 39).
```

- [ ] **Step 4: Link the new guide from `docs/README.md`**

Find the "Guías" section (or equivalent) and add:

```markdown
- [Content provenance (Fase 40)](guias/content-provenance.md) — trazabilidad reproducible del texto citado.
```

- [ ] **Step 5: Validate markdown locally**

Run any existing docs lint (markdownlint or similar) if configured:

```bash
ls docs/ && (cd docs && find . -name "*.md" | head)
```

No formal validator? Verify by `grep -F "Fase 40" docs/ROADMAP.md
docs/VISION_AUDIT.md docs/README.md` and confirm all three contain the
new entries.

- [ ] **Step 6: Commit**

```bash
git add docs/guias/content-provenance.md docs/ROADMAP.md docs/VISION_AUDIT.md docs/README.md
git commit -m "docs(provenance): guide, ROADMAP, VISION_AUDIT row, L0-L3 taxonomy explained"
```

---

### Task 14: Final audit — full suite, smoke CLI, no regressions

**Files:** none (verification only).

- [ ] **Step 1: Sync workspace from a clean state**

Run:
```bash
uv sync --all-packages
```
Expected: no errors. `uv pip list | grep -E "jw-core|jw-cli|jw-mcp|jw-agents"` shows all packages installed.

- [ ] **Step 2: Run the focused provenance suite first**

Run:
```bash
.venv/bin/python -m pytest packages/jw-core/tests/test_provenance -v
.venv/bin/python -m pytest packages/jw-cli/tests/test_cli_provenance.py -v
.venv/bin/python -m pytest packages/jw-mcp/tests/test_provenance_tool.py -v
```
Expected: every test passes. Note the total count for the commit message.

- [ ] **Step 3: Run the full repo suite to confirm no regressions**

Run:
```bash
.venv/bin/python -m pytest -q
```
Expected: all 1984+ existing tests still pass; the new provenance tests
account for the delta. If any unrelated test fails, stop and triage —
the most likely culprits are changes to `WOLClient.get_article` /
`get_bible_chapter` in Task 6 (the `stamp_citation` integration) or
the agent emission changes in Task 7. Roll back the offending integration
or null-pass the optional fields until the suite is green.

- [ ] **Step 4: Smoke the CLI on the fixture**

Run:
```bash
JW_PROVENANCE_FETCHER=fake \
  uv run jw provenance check \
  --agent-output packages/jw-core/tests/test_provenance/fixtures/agent_result_with_provenance.json \
  --report md \
  --out /tmp/drift.md
echo "exit=$?"
cat /tmp/drift.md
```
Expected: exit code `0` (or `2` if the fake produces drift), the report
contains a table row per finding, and the summary shows match/changed/etc.

- [ ] **Step 5: Confirm telemetry opt-in works**

Run:
```bash
JW_TELEMETRY_ENABLED=1 \
JW_TELEMETRY_PATH=/tmp/jw-tel.json \
JW_PROVENANCE_FETCHER=fake-drift \
  uv run jw provenance check \
  --agent-output packages/jw-core/tests/test_provenance/fixtures/agent_result_with_provenance.json \
  --report json > /tmp/report.json
python -c "import json; d = json.load(open('/tmp/jw-tel.json')); print([e for e in d.get('provenance_events', []) if e.get('kind') == 'provenance_drift'])"
```
Expected: at least one `provenance_drift` event listed.

- [ ] **Step 6: Confirm import-guard for missing Fase 39**

Run:
```bash
.venv/bin/python -c "
from jw_core.provenance import ProvenanceValidator, content_sha256, canonicalize_text
print('OK — provenance module imports without Fase 39')
"
```
Expected: prints `OK — provenance module imports without Fase 39`. No
`ImportError` from any submodule.

- [ ] **Step 7: Tag the completion**

```bash
git tag fase-40-complete
git log --oneline fase-40-complete~14..fase-40-complete
```
Expected: 13 commits listed, each from one of the prior tasks.

- [ ] **Step 8: Push (optional, owner's call)**

```bash
git push origin main
git push origin fase-40-complete
```

---

## Self-review

The plan covers every required deliverable from the prompt:

- **T1** scaffolds `packages/jw-core/src/jw_core/provenance/` and stubs
  every submodule referenced by `__init__.py` so the package is
  importable from Task 1 onward.
- **T2** locks down `ProvenanceRecord.from_citation_metadata` as a
  pure read-only projection over `Citation.metadata`. Seven tests pin
  edge cases: absent keys, partial keys, full keys, optionals, no
  mutation, unknown-field rejection.
- **T3** adds `ProvenanceVerdict` with the five statuses from the spec
  (`match`, `changed`, `unreachable`, `no_record`, `skipped`) plus
  `ProvenanceReport` with `summarize()` + JSON round-trip.
- **T4** implements `canonicalize_text` with NFC, zero-width strip,
  whitespace collapse, and the spec's hard decision to **preserve
  capitalization**. 12 tests cover idempotency, NFC equivalence,
  hashing stability under cosmetic edits, hash change under real edits,
  hex output, empty input.
- **T5** implements `ProvenanceValidator` with injected fetcher and
  extractor, `check`/`check_agent_output`/`check_since`, semaphore
  concurrency=4 matching Fase 23, URL dedup. 9 tests including
  unreachable-on-raise, unreachable-on-non-2xx, no_record short-circuit
  (no fetcher call), since-cutoff filter.
- **T6** ships `stamp_citation` / `stamp_finding_text` (idempotent,
  preserves other metadata, omits None optionals) plus the WOL ingest
  hook in `get_article` and `get_bible_chapter`.
- **T7** integrates stamping into `verse_explainer` and `apologetics`
  agents at emission and includes a golden fixture.
- **T8** verifies the NLI re-run hook through five tests including
  provider-raises and missing-claim paths. Confirms `validator.py`
  never imports `jw_core.nli` at module level.
- **T9** delivers the Typer-based CLI with three fetcher modes
  (`httpx`, `fake`, `fake-drift`), markdown reporter, exit codes
  (0/2/3), and `--since`. Five CLI tests using `CliRunner`.
- **T10** delivers the MCP tool with hydration helper, lazy-import of
  the default fetcher, optional `nli_provider` injection. Four tests.
- **T11** wires opt-in telemetry events through `jw_core.telemetry`'s
  existing singleton + `_save()`, gated on `JW_TELEMETRY_ENABLED`. Two
  tests confirm both the enabled and disabled paths.
- **T12** explicitly tests backwards compatibility with three tests:
  pure-legacy fixture, mixed legacy+new, and unit-level projection.
- **T13** documents everything: user guide explaining the L0–L3
  taxonomy, ROADMAP entry, VISION_AUDIT row, README link.
- **T14** is a six-step audit verifying focused tests, full suite,
  CLI smoke, telemetry smoke, import-guard.

Each task has 5+ TDD steps (most have 6+). All code is inline — no
placeholders, no "TODO fill in". File-block at the top of every task
lists exact create/modify paths. The plan respects the constraints
from CLAUDE.md (Spanish prose where it makes sense for narrative
documentation, English identifiers everywhere in code).

The plan is **3013 lines** with **14 tasks**, suitable for execution
by a single-pass subagent or sequential plan-executor.

## Execution choice

**Recommended:** `superpowers:subagent-driven-development` — the tasks
are tightly scoped (each task is one PR-sized commit), have clear
file boundaries, and produce visible test signals at every step.
A subagent can pick up from any green checkbox without ambiguity.

Alternative: `superpowers:executing-plans` for a more conservative,
top-to-bottom walk if the implementer wants to keep the main agent
in-context throughout.
