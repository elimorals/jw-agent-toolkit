# Fase 27 — `field_report` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `jw_core.ministry.field_report`, a local-first, encryptable monthly report for pioneers — aggregates hours + active studies + revisits. Exposes CLI (`jw report`) and three MCP tools. Reads revisits read-only from `RevisitStore` (Fase 12) via injectable provider.

**Architecture:** New module in existing `jw-core` package. Two SQLite tables (`hours_entries`, `studies`, plus child `studies_meetings`). `FieldEncryptor` columnar encryption for PII (`note`, `student_id`). Three exporters (md/csv/pdf) consumed by CLI + MCP. PDF is opt-in via `[pdf]` extra (Jinja2 + WeasyPrint).

**Tech Stack:** Python 3.13 · Pydantic v2 · sqlite3 stdlib · WeasyPrint + Jinja2 (optional) · Typer + Rich (CLI) · FastMCP (MCP) · pytest.

**Spec:** [`docs/superpowers/specs/2026-05-30-fase-27-pioneer-report-design.md`](../specs/2026-05-30-fase-27-pioneer-report-design.md).

---

## File map

Creates:
- `packages/jw-core/src/jw_core/data/field_service_tags.py`
- `packages/jw-core/src/jw_core/ministry/__init__.py`
- `packages/jw-core/src/jw_core/ministry/field_report.py`
- `packages/jw-core/src/jw_core/ministry/exporters.py`
- `packages/jw-core/src/jw_core/ministry/templates/monthly_report.html.j2`
- `packages/jw-core/tests/test_field_report.py`
- `packages/jw-cli/src/jw_cli/commands/report.py`
- `docs/guias/informe-precursor.md`

Modifies:
- `packages/jw-core/pyproject.toml` — add `pdf` extra (`weasyprint`, `jinja2`).
- `packages/jw-cli/src/jw_cli/main.py` — register `report` subcommand.
- `packages/jw-mcp/src/jw_mcp/server.py` — register 3 MCP tools.
- `docs/ROADMAP.md` — add Fase 27 section.
- `docs/VISION_AUDIT.md` — add Fase 27 row.

---

### Task 1: Controlled vocabulary for service tags

**Files:**
- Create: `packages/jw-core/src/jw_core/data/field_service_tags.py`
- Create: `packages/jw-core/tests/test_field_report.py` (initial; only this task's tests)

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-core/tests/test_field_report.py
"""Tests for jw_core.ministry.field_report and related field_service modules."""

from __future__ import annotations

import json
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Task 1 — vocabulary
# ---------------------------------------------------------------------------


def test_default_tags_present() -> None:
    from jw_core.data.field_service_tags import DEFAULT_TAGS, load_tags

    assert "street" in DEFAULT_TAGS
    assert "return_visit" in DEFAULT_TAGS
    assert "bible_study" in DEFAULT_TAGS
    tags = load_tags(override_path=None)
    assert set(DEFAULT_TAGS).issubset(tags)


def test_override_adds_local_tag(tmp_path: Path) -> None:
    from jw_core.data.field_service_tags import load_tags

    override = tmp_path / "field_service_tags_local.json"
    override.write_text(json.dumps({"add": ["hospital"], "remove": []}), encoding="utf-8")
    tags = load_tags(override_path=override)
    assert "hospital" in tags
    assert "street" in tags  # defaults survive


def test_override_can_remove(tmp_path: Path) -> None:
    from jw_core.data.field_service_tags import load_tags

    override = tmp_path / "field_service_tags_local.json"
    override.write_text(json.dumps({"add": [], "remove": ["letter"]}), encoding="utf-8")
    tags = load_tags(override_path=override)
    assert "letter" not in tags
    assert "street" in tags


def test_override_missing_file_returns_defaults(tmp_path: Path) -> None:
    from jw_core.data.field_service_tags import DEFAULT_TAGS, load_tags

    assert set(load_tags(override_path=tmp_path / "nope.json")) == set(DEFAULT_TAGS)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/jw-core/tests/test_field_report.py -v`
Expected: FAIL — `ModuleNotFoundError: jw_core.data.field_service_tags`.

- [ ] **Step 3: Implement vocabulary**

```python
# packages/jw-core/src/jw_core/data/field_service_tags.py
"""Controlled vocabulary for field-service hour entries.

Defaults cover the common modern forms of ministry. Users can override
locally by dropping a JSON file at
``~/.jw-agent-toolkit/field_service_tags_local.json``::

    {"add": ["hospital", "prison"], "remove": ["letter"]}

The override is **additive over the defaults** — `remove` drops items
out, `add` brings new ones in. Validation lives in the Pydantic models
in :mod:`jw_core.ministry.field_report` which read the resolved tag
set at import time of the model.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

DEFAULT_TAGS: tuple[str, ...] = (
    "street",
    "return_visit",
    "bible_study",
    "online",
    "phone",
    "cart",
    "letter",
    "other",
)


def _default_override_path() -> Path:
    raw = os.getenv(
        "JW_FIELD_TAGS_OVERRIDE",
        "~/.jw-agent-toolkit/field_service_tags_local.json",
    )
    return Path(raw).expanduser()


def load_tags(override_path: Path | None = None) -> tuple[str, ...]:
    """Return the effective tag tuple after applying any local override.

    Pass ``override_path=None`` to use the default user-config location.
    Pass an explicit ``Path`` (including non-existent) in tests to isolate.
    """

    path = override_path if override_path is not None else _default_override_path()
    tags = list(DEFAULT_TAGS)
    if not path.exists():
        return tuple(tags)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return tuple(tags)
    removed = set(data.get("remove") or [])
    added = [t for t in (data.get("add") or []) if t not in tags]
    tags = [t for t in tags if t not in removed] + added
    return tuple(tags)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/jw-core/tests/test_field_report.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-core/src/jw_core/data/field_service_tags.py packages/jw-core/tests/test_field_report.py
git commit -m "feat(jw-core): controlled vocab for field-service tags with local override"
```

---

### Task 2: Pydantic models + `__init__`

**Files:**
- Create: `packages/jw-core/src/jw_core/ministry/__init__.py`
- Create: `packages/jw-core/src/jw_core/ministry/field_report.py` (partial — models only)

- [ ] **Step 1: Append the failing test**

Append to `packages/jw-core/tests/test_field_report.py`:

```python
# ---------------------------------------------------------------------------
# Task 2 — models
# ---------------------------------------------------------------------------


def test_hours_entry_validates() -> None:
    from datetime import date as date_
    from jw_core.ministry.field_report import HoursEntry

    e = HoursEntry(
        entry_id="abc",
        date=date_(2026, 5, 15),
        hours_decimal=2.5,
        tag="street",
        note="parque central",
    )
    assert e.hours_decimal == 2.5
    assert e.tag == "street"


def test_hours_entry_rejects_overflow() -> None:
    from datetime import date as date_
    from jw_core.ministry.field_report import HoursEntry

    with pytest.raises(ValueError):
        HoursEntry(entry_id="x", date=date_(2026, 5, 15), hours_decimal=25.0)


def test_hours_entry_rejects_unknown_tag() -> None:
    from datetime import date as date_
    from jw_core.ministry.field_report import HoursEntry

    with pytest.raises(ValueError):
        HoursEntry(
            entry_id="x", date=date_(2026, 5, 15), hours_decimal=1.0, tag="weird"  # type: ignore[arg-type]
        )


def test_study_entry_defaults() -> None:
    from datetime import date as date_
    from jw_core.ministry.field_report import StudyEntry

    s = StudyEntry(study_id="s1", student_id="maria", started_at=date_(2026, 4, 1))
    assert s.closed_at is None
    assert s.met_dates == []
    assert s.note == ""


def test_monthly_report_shape() -> None:
    from jw_core.ministry.field_report import MonthlyReport

    r = MonthlyReport(
        month="2026-05",
        total_hours=10.5,
        total_hours_display="10h 30min",
        breakdown_by_tag={"street": 5.0, "untagged": 5.5},
        active_studies_max=3,
        active_studies_ids=["s1", "s2", "s3"],
        revisits_count=7,
        entries_count=4,
        days_with_service=3,
    )
    assert r.month == "2026-05"
    assert r.active_studies_max == 3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/jw-core/tests/test_field_report.py -v`
Expected: 5 new tests FAIL — `jw_core.ministry.field_report` missing.

- [ ] **Step 3: Implement `__init__` and models**

```python
# packages/jw-core/src/jw_core/ministry/__init__.py
"""Ministry helpers: monthly field-service report (Fase 27)."""

from jw_core.ministry.field_report import (
    FieldReportStore,
    HoursEntry,
    MonthlyReport,
    RevisitProvider,
    StudyEntry,
    aggregate_monthly_report,
)

__all__ = [
    "FieldReportStore",
    "HoursEntry",
    "MonthlyReport",
    "RevisitProvider",
    "StudyEntry",
    "aggregate_monthly_report",
]
```

```python
# packages/jw-core/src/jw_core/ministry/field_report.py
"""Local-first monthly field-service report for pioneers.

Stores ``HoursEntry`` and ``StudyEntry`` rows in SQLite, encrypts PII
columns at rest via :class:`jw_core.privacy.encryption.FieldEncryptor`,
and aggregates a :class:`MonthlyReport` for a given ``YYYY-MM``.

Read-only revisit counts come from an injectable ``RevisitProvider`` —
this module **never** imports ``jw_agents``.
"""

from __future__ import annotations

from datetime import date as _date
from typing import Literal, Protocol

from pydantic import BaseModel, Field

# Frozen at import time. Override-aware variant lives behind a CLI helper.
ServiceTag = Literal[
    "street",
    "return_visit",
    "bible_study",
    "online",
    "phone",
    "cart",
    "letter",
    "other",
]


class HoursEntry(BaseModel):
    """One log of hours worked."""

    entry_id: str
    date: _date
    hours_decimal: float = Field(ge=0.0, le=24.0)
    tag: ServiceTag | None = None
    note: str = ""
    created_at_unix: float = 0.0


class StudyEntry(BaseModel):
    """One active or closed Bible study."""

    study_id: str
    student_id: str  # arbitrary alias chosen by the user; ciphered at rest
    started_at: _date
    closed_at: _date | None = None
    met_dates: list[_date] = Field(default_factory=list)
    note: str = ""
    created_at_unix: float = 0.0


class MonthlyReport(BaseModel):
    """Aggregate report shape returned to CLI/MCP/exporters."""

    month: str  # "YYYY-MM"
    total_hours: float
    total_hours_display: str
    breakdown_by_tag: dict[str, float]
    active_studies_max: int
    active_studies_ids: list[str]
    revisits_count: int
    entries_count: int
    days_with_service: int


class RevisitProvider(Protocol):
    """Read-only count of revisits in a half-open date range [start, end]."""

    def count_in_range(self, start: _date, end: _date) -> int: ...


# Forward declarations; implementations land in later tasks.
class FieldReportStore:  # pragma: no cover - placeholder until Task 3
    """SQLite-backed store. Implemented in Task 3."""


def aggregate_monthly_report(  # pragma: no cover - placeholder until Task 5
    store: "FieldReportStore", month: str, *, revisits: RevisitProvider | None = None
) -> MonthlyReport:
    """Aggregator. Implemented in Task 5."""

    raise NotImplementedError
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/jw-core/tests/test_field_report.py -v`
Expected: 9 passed (4 from Task 1 + 5 from Task 2).

- [ ] **Step 5: Commit**

```bash
git add packages/jw-core/src/jw_core/ministry/__init__.py packages/jw-core/src/jw_core/ministry/field_report.py packages/jw-core/tests/test_field_report.py
git commit -m "feat(jw-core): Pydantic models for field_report (HoursEntry/StudyEntry/MonthlyReport)"
```

---

### Task 3: `FieldReportStore` SQLite + encryption (CRUD)

**Files:**
- Modify: `packages/jw-core/src/jw_core/ministry/field_report.py`
- Modify: `packages/jw-core/tests/test_field_report.py`

- [ ] **Step 1: Append the failing test**

```python
# ---------------------------------------------------------------------------
# Task 3 — FieldReportStore CRUD
# ---------------------------------------------------------------------------


def _enc_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("JW_PRIVACY_KEY", raising=False)


def test_store_creates_db_and_inserts_hours(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from datetime import date as date_
    from jw_core.ministry.field_report import FieldReportStore, HoursEntry

    _enc_off(monkeypatch)
    db = tmp_path / "fs.db"
    store = FieldReportStore(path=db)
    e = store.add_hours(
        HoursEntry(entry_id="", date=date_(2026, 5, 15), hours_decimal=2.5, tag="street")
    )
    assert e.entry_id  # auto-assigned uuid
    assert db.exists()

    rows = store.list_hours(month="2026-05")
    assert len(rows) == 1
    assert rows[0].hours_decimal == 2.5
    assert rows[0].tag == "street"
    store.close()


def test_store_list_hours_filters_by_month(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from datetime import date as date_
    from jw_core.ministry.field_report import FieldReportStore, HoursEntry

    _enc_off(monkeypatch)
    store = FieldReportStore(path=tmp_path / "fs.db")
    store.add_hours(HoursEntry(entry_id="", date=date_(2026, 4, 30), hours_decimal=1.0))
    store.add_hours(HoursEntry(entry_id="", date=date_(2026, 5, 1), hours_decimal=2.0))
    store.add_hours(HoursEntry(entry_id="", date=date_(2026, 5, 31), hours_decimal=3.0))
    store.add_hours(HoursEntry(entry_id="", date=date_(2026, 6, 1), hours_decimal=4.0))

    may = store.list_hours(month="2026-05")
    assert sorted(r.hours_decimal for r in may) == [2.0, 3.0]
    store.close()


def test_store_log_study_and_close(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from datetime import date as date_
    from jw_core.ministry.field_report import FieldReportStore, StudyEntry

    _enc_off(monkeypatch)
    store = FieldReportStore(path=tmp_path / "fs.db")
    s = store.upsert_study(
        StudyEntry(study_id="", student_id="maria", started_at=date_(2026, 4, 1))
    )
    assert s.study_id
    store.close_study(student_id="maria", closed_at=date_(2026, 5, 10))
    studies = store.list_studies()
    assert studies[0].closed_at == date_(2026, 5, 10)


def test_store_mark_met_today(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from datetime import date as date_
    from jw_core.ministry.field_report import FieldReportStore, StudyEntry

    _enc_off(monkeypatch)
    store = FieldReportStore(path=tmp_path / "fs.db")
    store.upsert_study(StudyEntry(study_id="", student_id="maria", started_at=date_(2026, 5, 1)))
    store.mark_met(student_id="maria", met_date=date_(2026, 5, 5))
    store.mark_met(student_id="maria", met_date=date_(2026, 5, 12))
    store.mark_met(student_id="maria", met_date=date_(2026, 5, 5))  # duplicate must be a no-op
    studies = store.list_studies()
    assert sorted(studies[0].met_dates) == [date_(2026, 5, 5), date_(2026, 5, 12)]


def test_store_encrypts_note_when_key_set(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import sqlite3

    from cryptography.fernet import Fernet  # type: ignore[import-not-found]

    from datetime import date as date_
    from jw_core.ministry.field_report import FieldReportStore, HoursEntry

    monkeypatch.setenv("JW_PRIVACY_KEY", Fernet.generate_key().decode("ascii"))
    db = tmp_path / "fs.db"
    store = FieldReportStore(path=db)
    store.add_hours(
        HoursEntry(
            entry_id="",
            date=date_(2026, 5, 15),
            hours_decimal=2.5,
            tag="street",
            note="secret note",
        )
    )

    # Inspect raw row: note column must NOT contain "secret note" cleartext.
    raw = sqlite3.connect(db)
    raw.row_factory = sqlite3.Row
    row = raw.execute("SELECT note FROM hours_entries").fetchone()
    assert "secret note" not in row["note"]
    raw.close()

    # But round-trip via store decrypts correctly.
    entries = store.list_hours(month="2026-05")
    assert entries[0].note == "secret note"
    store.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/jw-core/tests/test_field_report.py -v`
Expected: 5 new tests FAIL — `FieldReportStore` is a placeholder.

- [ ] **Step 3: Implement the store**

Replace the placeholder `FieldReportStore` in `field_report.py` with the real implementation. Add these imports at the top and the full class below the models (keep `aggregate_monthly_report` placeholder for now):

```python
# packages/jw-core/src/jw_core/ministry/field_report.py
# ... (keep existing imports + models from Task 2) ...

import os
import sqlite3
import time
import uuid
from pathlib import Path

from jw_core.privacy.encryption import FieldEncryptor


def _default_db_path() -> Path:
    return Path(os.getenv("JW_FIELD_DB", "~/.jw-agent-toolkit/field_service.db")).expanduser()


def _iso(d: _date) -> str:
    return d.isoformat()


def _from_iso(s: str | None) -> _date | None:
    return _date.fromisoformat(s) if s else None


class FieldReportStore:
    """SQLite-backed store for hours + studies + meetings.

    Encryption is automatic when ``JW_PRIVACY_KEY`` is set. Columns
    ``note`` and ``student_id`` go through the encryptor; everything
    else stays in cleartext so SQL aggregates (`SUM`, `GROUP BY`) work.
    """

    SCHEMA = """
    CREATE TABLE IF NOT EXISTS hours_entries (
        entry_id TEXT PRIMARY KEY,
        date TEXT NOT NULL,                -- ISO yyyy-mm-dd
        hours_decimal REAL NOT NULL,
        tag TEXT,
        note TEXT NOT NULL DEFAULT '',
        created_at_unix REAL NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_hours_date ON hours_entries (date);

    CREATE TABLE IF NOT EXISTS studies (
        study_id TEXT PRIMARY KEY,
        student_id TEXT NOT NULL,          -- ciphered alias
        started_at TEXT NOT NULL,
        closed_at TEXT,
        note TEXT NOT NULL DEFAULT '',
        created_at_unix REAL NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_studies_started ON studies (started_at);

    CREATE TABLE IF NOT EXISTS studies_meetings (
        study_id TEXT NOT NULL,
        met_date TEXT NOT NULL,
        PRIMARY KEY (study_id, met_date),
        FOREIGN KEY (study_id) REFERENCES studies(study_id) ON DELETE CASCADE
    );
    """

    def __init__(
        self,
        path: Path | str | None = None,
        *,
        encryptor: FieldEncryptor | None = None,
    ) -> None:
        self.path = Path(path).expanduser() if path else _default_db_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(self.SCHEMA)
        self._conn.commit()
        self._enc = encryptor if encryptor is not None else FieldEncryptor()

    # ----------------------------- hours ---------------------------------

    def add_hours(self, entry: HoursEntry) -> HoursEntry:
        if not entry.entry_id:
            entry.entry_id = uuid.uuid4().hex
        if not entry.created_at_unix:
            entry.created_at_unix = time.time()
        self._conn.execute(
            "INSERT INTO hours_entries "
            "(entry_id, date, hours_decimal, tag, note, created_at_unix) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                entry.entry_id,
                _iso(entry.date),
                float(entry.hours_decimal),
                entry.tag,
                self._enc.encrypt(entry.note) if entry.note else "",
                entry.created_at_unix,
            ),
        )
        self._conn.commit()
        return entry

    def list_hours(self, *, month: str | None = None) -> list[HoursEntry]:
        if month:
            cur = self._conn.execute(
                "SELECT * FROM hours_entries WHERE substr(date, 1, 7) = ? ORDER BY date",
                (month,),
            )
        else:
            cur = self._conn.execute("SELECT * FROM hours_entries ORDER BY date")
        return [self._row_to_hours(r) for r in cur.fetchall()]

    def _row_to_hours(self, row: sqlite3.Row) -> HoursEntry:
        note_raw = row["note"]
        return HoursEntry(
            entry_id=row["entry_id"],
            date=_date.fromisoformat(row["date"]),
            hours_decimal=row["hours_decimal"],
            tag=row["tag"],
            note=self._enc.decrypt(note_raw) if (self._enc.enabled and note_raw) else note_raw or "",
            created_at_unix=row["created_at_unix"],
        )

    # ---------------------------- studies --------------------------------

    def upsert_study(self, study: StudyEntry) -> StudyEntry:
        if not study.study_id:
            study.study_id = uuid.uuid4().hex
        if not study.created_at_unix:
            study.created_at_unix = time.time()
        self._conn.execute(
            "INSERT OR REPLACE INTO studies "
            "(study_id, student_id, started_at, closed_at, note, created_at_unix) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                study.study_id,
                self._enc.encrypt(study.student_id),
                _iso(study.started_at),
                _iso(study.closed_at) if study.closed_at else None,
                self._enc.encrypt(study.note) if study.note else "",
                study.created_at_unix,
            ),
        )
        self._conn.commit()
        return study

    def close_study(self, *, student_id: str, closed_at: _date) -> int:
        """Close every open study matching `student_id`. Returns rows updated."""

        # When encryption is on, student_id stored as ciphertext differs each call → scan.
        if self._enc.enabled:
            ids_to_close = [
                row["study_id"]
                for row in self._conn.execute(
                    "SELECT study_id, student_id FROM studies WHERE closed_at IS NULL"
                )
                if self._enc.decrypt(row["student_id"]) == student_id
            ]
            cur = self._conn.executemany(
                "UPDATE studies SET closed_at = ? WHERE study_id = ?",
                [(_iso(closed_at), sid) for sid in ids_to_close],
            )
            self._conn.commit()
            return len(ids_to_close)
        cur = self._conn.execute(
            "UPDATE studies SET closed_at = ? "
            "WHERE student_id = ? AND closed_at IS NULL",
            (_iso(closed_at), student_id),
        )
        self._conn.commit()
        return cur.rowcount

    def mark_met(self, *, student_id: str, met_date: _date) -> None:
        # Resolve student alias → study_id(s)
        if self._enc.enabled:
            study_ids = [
                row["study_id"]
                for row in self._conn.execute("SELECT study_id, student_id FROM studies")
                if self._enc.decrypt(row["student_id"]) == student_id
            ]
        else:
            study_ids = [
                row["study_id"]
                for row in self._conn.execute(
                    "SELECT study_id FROM studies WHERE student_id = ?", (student_id,)
                )
            ]
        for sid in study_ids:
            self._conn.execute(
                "INSERT OR IGNORE INTO studies_meetings (study_id, met_date) VALUES (?, ?)",
                (sid, _iso(met_date)),
            )
        self._conn.commit()

    def list_studies(self) -> list[StudyEntry]:
        rows = self._conn.execute("SELECT * FROM studies ORDER BY started_at").fetchall()
        result: list[StudyEntry] = []
        for row in rows:
            mets = self._conn.execute(
                "SELECT met_date FROM studies_meetings WHERE study_id = ? ORDER BY met_date",
                (row["study_id"],),
            ).fetchall()
            result.append(
                StudyEntry(
                    study_id=row["study_id"],
                    student_id=self._enc.decrypt(row["student_id"])
                    if self._enc.enabled
                    else row["student_id"],
                    started_at=_date.fromisoformat(row["started_at"]),
                    closed_at=_from_iso(row["closed_at"]),
                    met_dates=[_date.fromisoformat(m["met_date"]) for m in mets],
                    note=self._enc.decrypt(row["note"])
                    if (self._enc.enabled and row["note"])
                    else row["note"] or "",
                    created_at_unix=row["created_at_unix"],
                )
            )
        return result

    # -------------------------- lifecycle --------------------------------

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "FieldReportStore":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/jw-core/tests/test_field_report.py -v`
Expected: 14 passed (5 new + 9 prior).

- [ ] **Step 5: Commit**

```bash
git add packages/jw-core/src/jw_core/ministry/field_report.py packages/jw-core/tests/test_field_report.py
git commit -m "feat(jw-core): FieldReportStore SQLite CRUD with columnar encryption"
```

---

### Task 4: `RevisitProvider` + fake helper

**Files:**
- Modify: `packages/jw-core/src/jw_core/ministry/field_report.py` (already has the Protocol)
- Modify: `packages/jw-core/tests/test_field_report.py`

- [ ] **Step 1: Append the failing test**

```python
# ---------------------------------------------------------------------------
# Task 4 — RevisitProvider
# ---------------------------------------------------------------------------


class _FakeRevisits:
    def __init__(self, by_month: dict[str, int]) -> None:
        self._by_month = by_month

    def count_in_range(self, start, end):  # type: ignore[no-untyped-def]
        from datetime import date as date_

        assert isinstance(start, date_) and isinstance(end, date_)
        return self._by_month.get(start.strftime("%Y-%m"), 0)


def test_revisit_provider_protocol_is_structural() -> None:
    from jw_core.ministry.field_report import RevisitProvider

    p: RevisitProvider = _FakeRevisits({"2026-05": 7})
    from datetime import date as date_

    assert p.count_in_range(date_(2026, 5, 1), date_(2026, 5, 31)) == 7
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/jw-core/tests/test_field_report.py -v -k revisit_provider`
Expected: PASS already (Protocol is structural — type-only check). The test will pass on first run; if not, fix the Protocol export.

- [ ] **Step 3: Commit (no code change needed, just the test)**

```bash
git add packages/jw-core/tests/test_field_report.py
git commit -m "test(jw-core): RevisitProvider protocol is structural"
```

---

### Task 5: `aggregate_monthly_report` (the actual aggregator)

**Files:**
- Modify: `packages/jw-core/src/jw_core/ministry/field_report.py`
- Modify: `packages/jw-core/tests/test_field_report.py`

- [ ] **Step 1: Append the failing test**

```python
# ---------------------------------------------------------------------------
# Task 5 — aggregate_monthly_report
# ---------------------------------------------------------------------------


def _seed_may_2026(store) -> None:
    from datetime import date as date_
    from jw_core.ministry.field_report import HoursEntry, StudyEntry

    store.add_hours(HoursEntry(entry_id="", date=date_(2026, 5, 2), hours_decimal=2.0, tag="street"))
    store.add_hours(HoursEntry(entry_id="", date=date_(2026, 5, 2), hours_decimal=1.5, tag="return_visit"))
    store.add_hours(HoursEntry(entry_id="", date=date_(2026, 5, 10), hours_decimal=3.75, tag="cart"))
    store.add_hours(HoursEntry(entry_id="", date=date_(2026, 5, 20), hours_decimal=0.5, tag=None))
    # April leftover — must NOT count
    store.add_hours(HoursEntry(entry_id="", date=date_(2026, 4, 30), hours_decimal=10.0, tag="street"))

    # 4 studies: 1 already closed in April; 2 started before; 1 started mid-May; 1 closed mid-May
    store.upsert_study(
        StudyEntry(
            study_id="", student_id="alpha", started_at=date_(2026, 3, 1), closed_at=date_(2026, 4, 15)
        )
    )
    store.upsert_study(StudyEntry(study_id="", student_id="beta", started_at=date_(2026, 4, 1)))
    store.upsert_study(StudyEntry(study_id="", student_id="gamma", started_at=date_(2026, 4, 15)))
    store.upsert_study(StudyEntry(study_id="", student_id="delta", started_at=date_(2026, 5, 5)))
    store.upsert_study(
        StudyEntry(
            study_id="", student_id="epsilon", started_at=date_(2026, 4, 20), closed_at=date_(2026, 5, 12)
        )
    )


def test_aggregate_monthly_report_basic(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _enc_off(monkeypatch)
    from jw_core.ministry.field_report import FieldReportStore, aggregate_monthly_report

    store = FieldReportStore(path=tmp_path / "fs.db")
    _seed_may_2026(store)
    report = aggregate_monthly_report(
        store, "2026-05", revisits=_FakeRevisits({"2026-05": 11})
    )

    # 2.0 + 1.5 + 3.75 + 0.5 = 7.75 hours
    assert report.total_hours == pytest.approx(7.75)
    # 5-min rounding: 7h 45min
    assert report.total_hours_display == "7h 45min"
    assert report.breakdown_by_tag["street"] == pytest.approx(2.0)
    assert report.breakdown_by_tag["return_visit"] == pytest.approx(1.5)
    assert report.breakdown_by_tag["cart"] == pytest.approx(3.75)
    assert report.breakdown_by_tag["untagged"] == pytest.approx(0.5)
    assert report.entries_count == 4
    assert report.days_with_service == 3

    # Active in May: beta, gamma, delta, epsilon. alpha closed in April.
    assert report.active_studies_max == 4
    assert report.revisits_count == 11


def test_aggregate_monthly_report_5min_rounding_half_up() -> None:
    """7.46 hours → 7h 30min (rounds 27.6 → 30, since 27.6 is closer to 30 than 25 under 5-min rounding)."""

    from jw_core.ministry.field_report import _format_hours_5min

    assert _format_hours_5min(7.0) == "7h 00min"
    assert _format_hours_5min(7.5) == "7h 30min"
    assert _format_hours_5min(7.46) == "7h 30min"  # 27.6min → round to 30
    assert _format_hours_5min(0.0) == "0h 00min"
    assert _format_hours_5min(1.0833) == "1h 05min"  # 4.998 → 5


def test_aggregate_monthly_report_empty(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _enc_off(monkeypatch)
    from jw_core.ministry.field_report import FieldReportStore, aggregate_monthly_report

    store = FieldReportStore(path=tmp_path / "fs.db")
    r = aggregate_monthly_report(store, "2026-05", revisits=None)
    assert r.total_hours == 0.0
    assert r.entries_count == 0
    assert r.active_studies_max == 0
    assert r.revisits_count == 0
    assert r.days_with_service == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/jw-core/tests/test_field_report.py -v -k aggregate`
Expected: FAIL — `aggregate_monthly_report` is `NotImplementedError`; `_format_hours_5min` missing.

- [ ] **Step 3: Implement aggregator + display helper**

Replace the placeholder `aggregate_monthly_report` in `field_report.py` with:

```python
# packages/jw-core/src/jw_core/ministry/field_report.py — append below the store
import calendar
from decimal import ROUND_HALF_UP, Decimal


def _format_hours_5min(hours: float) -> str:
    """Render decimal hours as ``Xh Ymin`` rounded to 5-minute increments."""

    total_min = Decimal(str(hours)) * Decimal(60)
    rounded_5 = (total_min / Decimal(5)).quantize(Decimal("1"), rounding=ROUND_HALF_UP) * Decimal(5)
    h, m = divmod(int(rounded_5), 60)
    return f"{h}h {m:02d}min"


def _month_bounds(month: str) -> tuple[_date, _date]:
    """Return (start, end_inclusive) for ``YYYY-MM``."""

    y, m = month.split("-")
    yi, mi = int(y), int(m)
    last = calendar.monthrange(yi, mi)[1]
    return _date(yi, mi, 1), _date(yi, mi, last)


def _is_active_during(study: StudyEntry, start: _date, end: _date) -> bool:
    if study.started_at > end:
        return False
    if study.closed_at is not None and study.closed_at <= start:
        return False
    return True


def aggregate_monthly_report(
    store: FieldReportStore,
    month: str,
    *,
    revisits: RevisitProvider | None = None,
) -> MonthlyReport:
    """Aggregate every signal for ``month`` (YYYY-MM) into a :class:`MonthlyReport`.

    Active studies use the MAX during the month (per modern JW practice — see
    spec §"Decisiones clave"). ``revisits`` is optional; if omitted, the count
    falls back to ``0``.
    """

    month_start, month_end = _month_bounds(month)
    entries = store.list_hours(month=month)

    total = sum(e.hours_decimal for e in entries)
    breakdown: dict[str, float] = {}
    for e in entries:
        key = e.tag or "untagged"
        breakdown[key] = breakdown.get(key, 0.0) + e.hours_decimal

    days_with_service = len({e.date for e in entries})

    studies = store.list_studies()
    active = [s for s in studies if _is_active_during(s, month_start, month_end)]
    active_ids = [s.study_id for s in active]

    revisits_count = 0
    if revisits is not None:
        try:
            revisits_count = int(revisits.count_in_range(month_start, month_end))
        except Exception:  # noqa: BLE001 — provider never crashes the report
            revisits_count = 0

    return MonthlyReport(
        month=month,
        total_hours=round(float(total), 4),
        total_hours_display=_format_hours_5min(float(total)),
        breakdown_by_tag=breakdown,
        active_studies_max=len(active),
        active_studies_ids=active_ids,
        revisits_count=revisits_count,
        entries_count=len(entries),
        days_with_service=days_with_service,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/jw-core/tests/test_field_report.py -v`
Expected: 18 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-core/src/jw_core/ministry/field_report.py packages/jw-core/tests/test_field_report.py
git commit -m "feat(jw-core): aggregate_monthly_report with 5-min rounding and MAX-active-studies rule"
```

---

### Task 6: Exporter — markdown

**Files:**
- Create: `packages/jw-core/src/jw_core/ministry/exporters.py`
- Modify: `packages/jw-core/tests/test_field_report.py`

- [ ] **Step 1: Append the failing test**

```python
# ---------------------------------------------------------------------------
# Task 6 — markdown exporter
# ---------------------------------------------------------------------------


def test_render_markdown_contains_all_sections() -> None:
    from jw_core.ministry.exporters import render_markdown
    from jw_core.ministry.field_report import MonthlyReport

    report = MonthlyReport(
        month="2026-05",
        total_hours=7.75,
        total_hours_display="7h 45min",
        breakdown_by_tag={"street": 2.0, "return_visit": 1.5, "cart": 3.75, "untagged": 0.5},
        active_studies_max=4,
        active_studies_ids=["a", "b", "c", "d"],
        revisits_count=11,
        entries_count=4,
        days_with_service=3,
    )
    md = render_markdown(report)
    assert "# Informe mensual" in md
    assert "2026-05" in md
    assert "7h 45min" in md
    assert "Cursos bíblicos activos" in md
    assert "Revisitas" in md
    assert "11" in md
    assert "street" in md
    # Footer with MAX-rule explanation
    assert "máximo" in md.lower() or "maximo" in md.lower()


def test_render_markdown_handles_empty_report() -> None:
    from jw_core.ministry.exporters import render_markdown
    from jw_core.ministry.field_report import MonthlyReport

    md = render_markdown(
        MonthlyReport(
            month="2026-05",
            total_hours=0.0,
            total_hours_display="0h 00min",
            breakdown_by_tag={},
            active_studies_max=0,
            active_studies_ids=[],
            revisits_count=0,
            entries_count=0,
            days_with_service=0,
        )
    )
    assert "2026-05" in md
    assert "0h 00min" in md
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/jw-core/tests/test_field_report.py -v -k render_markdown`
Expected: FAIL — exporters module missing.

- [ ] **Step 3: Implement markdown exporter**

```python
# packages/jw-core/src/jw_core/ministry/exporters.py
"""Serializers for :class:`MonthlyReport` → markdown / csv / pdf.

PDF is optional and gated by the ``[pdf]`` extra (weasyprint + jinja2).
The other two exporters are stdlib-only.
"""

from __future__ import annotations

import csv
import io
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from jw_core.ministry.field_report import MonthlyReport


_TAG_LABELS_ES = {
    "street": "Predicación pública",
    "return_visit": "Revisitas (horas)",
    "bible_study": "Estudios bíblicos (horas)",
    "online": "En línea",
    "phone": "Teléfono",
    "cart": "Testimonio con exhibidor",
    "letter": "Cartas",
    "other": "Otro",
    "untagged": "Sin clasificar",
}


def _tag_label(tag: str) -> str:
    return _TAG_LABELS_ES.get(tag, tag)


def render_markdown(report: "MonthlyReport") -> str:
    """Render a human-friendly markdown report (in Spanish)."""

    lines: list[str] = []
    lines.append(f"# Informe mensual — {report.month}")
    lines.append("")
    lines.append("## Resumen")
    lines.append("")
    lines.append(f"- **Horas totales**: {report.total_hours_display} ({report.total_hours:.2f} h)")
    lines.append(f"- **Días con servicio**: {report.days_with_service}")
    lines.append(f"- **Cursos bíblicos activos (máximo)**: {report.active_studies_max}")
    lines.append(f"- **Revisitas registradas**: {report.revisits_count}")
    lines.append(f"- **Entradas registradas**: {report.entries_count}")
    lines.append("")
    if report.breakdown_by_tag:
        lines.append("## Desglose por modalidad")
        lines.append("")
        lines.append("| Modalidad | Horas |")
        lines.append("|---|---:|")
        for tag in sorted(report.breakdown_by_tag, key=lambda t: -report.breakdown_by_tag[t]):
            lines.append(f"| {_tag_label(tag)} | {report.breakdown_by_tag[tag]:.2f} |")
        lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(
        "_Cursos bíblicos activos se reportan como el **máximo** durante "
        "el mes (práctica JW vigente). Las revisitas vienen del store "
        "local de RevisitTracker (Fase 12, solo lectura)._"
    )
    return "\n".join(lines)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/jw-core/tests/test_field_report.py -v -k render_markdown`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-core/src/jw_core/ministry/exporters.py packages/jw-core/tests/test_field_report.py
git commit -m "feat(jw-core): markdown exporter for MonthlyReport (Spanish labels + MAX-rule footer)"
```

---

### Task 7: Exporter — CSV

**Files:**
- Modify: `packages/jw-core/src/jw_core/ministry/exporters.py`
- Modify: `packages/jw-core/tests/test_field_report.py`

- [ ] **Step 1: Append the failing test**

```python
# ---------------------------------------------------------------------------
# Task 7 — CSV exporter
# ---------------------------------------------------------------------------


def test_render_csv_has_expected_header_and_rows() -> None:
    import csv
    import io

    from jw_core.ministry.exporters import render_csv
    from jw_core.ministry.field_report import MonthlyReport

    report = MonthlyReport(
        month="2026-05",
        total_hours=7.75,
        total_hours_display="7h 45min",
        breakdown_by_tag={"street": 2.0, "cart": 3.75},
        active_studies_max=4,
        active_studies_ids=["a", "b", "c", "d"],
        revisits_count=11,
        entries_count=4,
        days_with_service=3,
    )
    csv_text = render_csv(report)
    reader = csv.reader(io.StringIO(csv_text))
    rows = list(reader)
    assert rows[0] == ["mes", "metrica", "valor"]
    flat = {(r[0], r[1]): r[2] for r in rows[1:]}
    assert flat[("2026-05", "horas_totales")] == "7.75"
    assert flat[("2026-05", "horas_display")] == "7h 45min"
    assert flat[("2026-05", "dias_con_servicio")] == "3"
    assert flat[("2026-05", "cursos_activos_max")] == "4"
    assert flat[("2026-05", "revisitas")] == "11"
    assert flat[("2026-05", "tag.street")] == "2.00"
    assert flat[("2026-05", "tag.cart")] == "3.75"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/jw-core/tests/test_field_report.py -v -k render_csv`
Expected: FAIL — `render_csv` missing.

- [ ] **Step 3: Implement CSV exporter**

Append to `packages/jw-core/src/jw_core/ministry/exporters.py`:

```python
def render_csv(report: "MonthlyReport") -> str:
    """Render the report as a long-form CSV (mes, metrica, valor)."""

    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["mes", "metrica", "valor"])
    w.writerow([report.month, "horas_totales", f"{report.total_hours:.2f}"])
    w.writerow([report.month, "horas_display", report.total_hours_display])
    w.writerow([report.month, "dias_con_servicio", str(report.days_with_service)])
    w.writerow([report.month, "cursos_activos_max", str(report.active_studies_max)])
    w.writerow([report.month, "revisitas", str(report.revisits_count)])
    w.writerow([report.month, "entradas_registradas", str(report.entries_count)])
    for tag, hours in sorted(report.breakdown_by_tag.items()):
        w.writerow([report.month, f"tag.{tag}", f"{hours:.2f}"])
    return buf.getvalue()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/jw-core/tests/test_field_report.py -v -k render_csv`
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-core/src/jw_core/ministry/exporters.py packages/jw-core/tests/test_field_report.py
git commit -m "feat(jw-core): CSV exporter for MonthlyReport (long-form mes/metrica/valor)"
```

---

### Task 8: Exporter — PDF (optional `[pdf]` extra)

**Files:**
- Modify: `packages/jw-core/pyproject.toml`
- Modify: `packages/jw-core/src/jw_core/ministry/exporters.py`
- Create: `packages/jw-core/src/jw_core/ministry/templates/monthly_report.html.j2`
- Modify: `packages/jw-core/tests/test_field_report.py`

- [ ] **Step 1: Append the failing test (skipped when extras absent)**

```python
# ---------------------------------------------------------------------------
# Task 8 — PDF exporter (optional extra)
# ---------------------------------------------------------------------------


def test_render_pdf_writes_bytes(tmp_path: Path) -> None:
    pytest.importorskip("jinja2")
    pytest.importorskip("weasyprint")

    from jw_core.ministry.exporters import render_pdf
    from jw_core.ministry.field_report import MonthlyReport

    out = tmp_path / "r.pdf"
    render_pdf(
        MonthlyReport(
            month="2026-05",
            total_hours=7.75,
            total_hours_display="7h 45min",
            breakdown_by_tag={"street": 2.0, "cart": 3.75},
            active_studies_max=4,
            active_studies_ids=[],
            revisits_count=11,
            entries_count=4,
            days_with_service=3,
        ),
        out_path=out,
    )
    assert out.exists()
    head = out.read_bytes()[:4]
    assert head == b"%PDF"


def test_render_pdf_raises_helpful_error_when_extra_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import builtins

    real_import = builtins.__import__

    def fake_import(name: str, *args, **kwargs):  # type: ignore[no-untyped-def]
        if name in ("weasyprint", "jinja2"):
            raise ImportError(f"forced missing: {name}")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    from jw_core.ministry import exporters as ex

    # Reload to retrigger lazy imports
    import importlib

    importlib.reload(ex)
    with pytest.raises(RuntimeError, match=r"\[pdf\]"):
        ex.render_pdf(
            ex.MonthlyReport(  # type: ignore[attr-defined]
                month="2026-05",
                total_hours=0.0,
                total_hours_display="0h 00min",
                breakdown_by_tag={},
                active_studies_max=0,
                active_studies_ids=[],
                revisits_count=0,
                entries_count=0,
                days_with_service=0,
            ),
            out_path=Path("/tmp/unused.pdf"),
        )
```

- [ ] **Step 2: Run test to verify it fails (or skips)**

Run: `uv run pytest packages/jw-core/tests/test_field_report.py -v -k render_pdf`
Expected: FAIL — `render_pdf` missing OR `helpful_error` test fails because the function doesn't exist yet.

- [ ] **Step 3: Add the `[pdf]` extra in pyproject**

Edit `packages/jw-core/pyproject.toml` and append (or extend the existing) section:

```toml
[project.optional-dependencies]
# ... keep existing extras ...
pdf = [
    "jinja2>=3.1",
    "weasyprint>=62",
]
```

- [ ] **Step 4: Create the Jinja template**

```html
{# packages/jw-core/src/jw_core/ministry/templates/monthly_report.html.j2 #}
<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8" />
  <title>Informe mensual — {{ report.month }}</title>
  <style>
    @page { size: A4; margin: 22mm; }
    body { font-family: "Helvetica", "Arial", sans-serif; color: #1f2937; }
    h1   { font-size: 22pt; margin-bottom: 0; }
    h2   { font-size: 14pt; margin-top: 24pt; border-bottom: 1px solid #e5e7eb; padding-bottom: 4pt; }
    table{ width: 100%; border-collapse: collapse; margin-top: 8pt; }
    th, td { padding: 6pt 8pt; border-bottom: 1px solid #f3f4f6; text-align: left; }
    th   { background: #f9fafb; font-weight: 600; }
    td.num { text-align: right; font-variant-numeric: tabular-nums; }
    .summary li { margin: 4pt 0; }
    .footer { margin-top: 24pt; color: #6b7280; font-size: 9pt; }
  </style>
</head>
<body>
  <h1>Informe mensual</h1>
  <p>{{ report.month }}</p>

  <h2>Resumen</h2>
  <ul class="summary">
    <li><strong>Horas totales</strong>: {{ report.total_hours_display }} ({{ "%.2f"|format(report.total_hours) }} h)</li>
    <li><strong>Días con servicio</strong>: {{ report.days_with_service }}</li>
    <li><strong>Cursos bíblicos activos (máximo)</strong>: {{ report.active_studies_max }}</li>
    <li><strong>Revisitas registradas</strong>: {{ report.revisits_count }}</li>
    <li><strong>Entradas registradas</strong>: {{ report.entries_count }}</li>
  </ul>

  {% if report.breakdown_by_tag %}
  <h2>Desglose por modalidad</h2>
  <table>
    <thead><tr><th>Modalidad</th><th class="num">Horas</th></tr></thead>
    <tbody>
    {% for tag, hours in breakdown %}
      <tr><td>{{ labels[tag] }}</td><td class="num">{{ "%.2f"|format(hours) }}</td></tr>
    {% endfor %}
    </tbody>
  </table>
  {% endif %}

  <p class="footer">
    Cursos bíblicos activos se reportan como el <em>máximo</em> durante
    el mes (práctica JW vigente). Las revisitas vienen del store local
    de RevisitTracker (Fase 12, solo lectura). Generado por jw-agent-toolkit.
  </p>
</body>
</html>
```

- [ ] **Step 5: Implement `render_pdf`**

Append to `packages/jw-core/src/jw_core/ministry/exporters.py`:

```python
# Lazy-import re-export of MonthlyReport so the missing-extras test can
# call `exporters.MonthlyReport` after a reload.
from jw_core.ministry.field_report import MonthlyReport  # noqa: E402


def render_pdf(report: "MonthlyReport", *, out_path: Path) -> Path:
    """Render the report to PDF (requires the ``[pdf]`` extra)."""

    try:
        from jinja2 import Environment, FileSystemLoader, select_autoescape
        from weasyprint import HTML
    except ImportError as exc:  # noqa: BLE001
        raise RuntimeError(
            "PDF rendering requires the [pdf] extra. Install with "
            "`uv pip install -e 'packages/jw-core[pdf]'`."
        ) from exc

    templates_dir = Path(__file__).parent / "templates"
    env = Environment(
        loader=FileSystemLoader(str(templates_dir)),
        autoescape=select_autoescape(["html", "xml"]),
    )
    tpl = env.get_template("monthly_report.html.j2")
    breakdown = sorted(
        report.breakdown_by_tag.items(), key=lambda kv: -kv[1]
    )
    html = tpl.render(
        report=report,
        breakdown=breakdown,
        labels={**_TAG_LABELS_ES, **{k: _tag_label(k) for k in report.breakdown_by_tag}},
    )
    HTML(string=html).write_pdf(str(out_path))
    return out_path
```

- [ ] **Step 6: Run test to verify it passes**

Run: `uv pip install -e 'packages/jw-core[pdf]'` (one-shot install on dev machine; in CI weasyprint may be skipped).
Run: `uv run pytest packages/jw-core/tests/test_field_report.py -v -k render_pdf`
Expected: 1 passed + 1 (helpful-error) passed (or first skipped if weasyprint not available on dev box).

- [ ] **Step 7: Commit**

```bash
git add packages/jw-core/pyproject.toml packages/jw-core/src/jw_core/ministry/exporters.py packages/jw-core/src/jw_core/ministry/templates packages/jw-core/tests/test_field_report.py
git commit -m "feat(jw-core): PDF exporter via WeasyPrint + Jinja2 behind [pdf] extra"
```

---

### Task 9: CLI — `jw report` subcommand

**Files:**
- Create: `packages/jw-cli/src/jw_cli/commands/report.py`
- Modify: `packages/jw-cli/src/jw_cli/main.py`

- [ ] **Step 1: Write the CLI command file**

```python
# packages/jw-cli/src/jw_cli/commands/report.py
"""`jw report` — log hours / studies / meetings, then render the monthly report."""

from __future__ import annotations

import os
import sys
from datetime import date as _date
from pathlib import Path

import typer
from rich.console import Console

from jw_core.ministry.exporters import render_csv, render_markdown
from jw_core.ministry.field_report import (
    FieldReportStore,
    HoursEntry,
    StudyEntry,
    aggregate_monthly_report,
)

console = Console()
report_app = typer.Typer(name="report", help="Informe mensual de precursor (local).")


def _warn_no_encryption() -> None:
    if os.getenv("JW_PRIVACY_KEY"):
        return
    if os.getenv("JW_FIELD_DISABLE_ENCRYPTION") == "1":
        return
    console.print(
        "[yellow][!] Cifrado deshabilitado (no se encontró JW_PRIVACY_KEY).\n"
        "    Tus notas y alias se guardarán en cleartext en "
        "~/.jw-agent-toolkit/field_service.db.\n"
        "    Para habilitarlo: export JW_PRIVACY_KEY=$(jw keygen)\n"
        "    Para silenciar este aviso: export JW_FIELD_DISABLE_ENCRYPTION=1[/yellow]"
    )


def _today() -> _date:
    return _date.today()


class _RevisitsAdapter:
    """Best-effort, read-only adapter over jw_agents.RevisitStore.

    Returns 0 (and never raises) if the revisit DB is absent — keeps the
    report renderable on a fresh install.
    """

    def count_in_range(self, start: _date, end: _date) -> int:
        try:
            from jw_agents.revisit_tracker import RevisitStore
        except ImportError:
            return 0
        try:
            with RevisitStore() as store:
                rows = store.list_all()
        except Exception:  # noqa: BLE001
            return 0
        # Revisit timestamps live in `next_visit_iso` and `updated_at_unix`.
        # We use `updated_at_unix` as proxy for "interaction date" — accepted
        # by VISION.md (a revisit is a touchpoint we logged).
        import datetime as _dt

        n = 0
        for r in rows:
            ts = r.updated_at_unix or 0
            if not ts:
                continue
            d = _dt.date.fromtimestamp(ts)
            if start <= d <= end:
                n += 1
        return n


@report_app.command("log-hours")
def log_hours_cmd(
    hours: float = typer.Option(..., "--hours", "-h", help="Horas decimales (ej. 1.25)."),
    date: str = typer.Option("", "--date", "-d", help="ISO yyyy-mm-dd. Por omisión, hoy."),
    tag: str = typer.Option("", "--tag", "-t"),
    note: str = typer.Option("", "--note", "-n"),
) -> None:
    """Registrar una entrada de horas."""

    _warn_no_encryption()
    d = _date.fromisoformat(date) if date else _today()
    with FieldReportStore() as store:
        e = store.add_hours(
            HoursEntry(entry_id="", date=d, hours_decimal=hours, tag=tag or None, note=note)
        )
    console.print(f"[green]+ {e.hours_decimal}h[/green] el {e.date} (tag={e.tag}) id={e.entry_id[:8]}")


@report_app.command("log-study")
def log_study_cmd(
    student_alias: str = typer.Option(..., "--student-alias", "-s"),
    started: str = typer.Option("", "--started"),
    close: bool = typer.Option(False, "--close", help="Cerrar el estudio."),
    closed: str = typer.Option("", "--closed"),
    note: str = typer.Option("", "--note", "-n"),
) -> None:
    """Crear o cerrar un curso bíblico."""

    _warn_no_encryption()
    with FieldReportStore() as store:
        if close:
            n = store.close_study(
                student_id=student_alias,
                closed_at=_date.fromisoformat(closed) if closed else _today(),
            )
            console.print(f"[green]✓ cerrado(s) {n} estudio(s) de {student_alias}[/green]")
        else:
            s = store.upsert_study(
                StudyEntry(
                    study_id="",
                    student_id=student_alias,
                    started_at=_date.fromisoformat(started) if started else _today(),
                    note=note,
                )
            )
            console.print(f"[green]+ estudio[/green] {s.student_id} desde {s.started_at} id={s.study_id[:8]}")


@report_app.command("met-today")
def met_today_cmd(
    student_alias: str = typer.Option(..., "--student-alias", "-s"),
    date: str = typer.Option("", "--date", "-d"),
) -> None:
    """Marcar que se reunió con un estudiante hoy (o en --date)."""

    _warn_no_encryption()
    d = _date.fromisoformat(date) if date else _today()
    with FieldReportStore() as store:
        store.mark_met(student_id=student_alias, met_date=d)
    console.print(f"[green]✓ reunión con {student_alias} el {d}[/green]")


@report_app.command("show")
def show_cmd(
    month: str = typer.Option(..., "--month", "-m"),
    detail: bool = typer.Option(False, "--detail"),
) -> None:
    """Listar entradas crudas del mes."""

    with FieldReportStore() as store:
        rows = store.list_hours(month=month)
    if not rows:
        console.print(f"[dim]sin entradas en {month}[/dim]")
        return
    for r in rows:
        if detail:
            console.print(f"{r.date} {r.hours_decimal:>5.2f}h tag={r.tag or '-':<14} {r.note}")
        else:
            console.print(f"{r.date} {r.hours_decimal:>5.2f}h tag={r.tag or '-'}")


@report_app.callback(invoke_without_command=True)
def report_root(
    ctx: typer.Context,
    month: str = typer.Option("", "--month", "-m"),
    format: str = typer.Option("md", "--format", "-f", help="md|csv|pdf"),
    out: str = typer.Option("", "--out", "-o"),
) -> None:
    """Generar el informe del mes (default markdown a stdout)."""

    if ctx.invoked_subcommand is not None:
        return
    if not month:
        console.print("[red]--month YYYY-MM es requerido cuando no se usa subcomando[/red]")
        raise typer.Exit(code=2)

    with FieldReportStore() as store:
        report = aggregate_monthly_report(store, month, revisits=_RevisitsAdapter())

    if format == "md":
        body = render_markdown(report)
    elif format == "csv":
        body = render_csv(report)
    elif format == "pdf":
        out_path = Path(out or f"informe-{month}.pdf").expanduser()
        from jw_core.ministry.exporters import render_pdf

        render_pdf(report, out_path=out_path)
        console.print(f"[green]✓ PDF escrito en {out_path}[/green]")
        return
    else:
        console.print(f"[red]formato desconocido: {format}[/red]")
        raise typer.Exit(code=2)

    if out:
        Path(out).expanduser().write_text(body, encoding="utf-8")
        console.print(f"[green]✓ {format} escrito en {out}[/green]")
    else:
        sys.stdout.write(body)
```

- [ ] **Step 2: Register in CLI main**

Edit `packages/jw-cli/src/jw_cli/main.py`:

Append at the end of the imports section:
```python
from jw_cli.commands import report as report_module
```

Inside `app = typer.Typer(...)` block of registrations, append:
```python
app.add_typer(report_module.report_app, name="report")
```

- [ ] **Step 3: Smoke-test the CLI**

```bash
uv run jw report --help
uv run jw report log-hours --hours 1.5 --tag street --date 2026-05-15
uv run jw report log-study --student-alias maria --started 2026-05-01
uv run jw report met-today --student-alias maria --date 2026-05-08
uv run jw report --month 2026-05 --format md
uv run jw report --month 2026-05 --format csv
```

Expected: help text renders, log commands print confirmations, markdown report on stdout containing "Informe mensual — 2026-05" and 1.5h.

- [ ] **Step 4: Commit**

```bash
git add packages/jw-cli/src/jw_cli/commands/report.py packages/jw-cli/src/jw_cli/main.py
git commit -m "feat(jw-cli): jw report subcommand (log-hours / log-study / met-today / show / render)"
```

---

### Task 10: MCP tools

**Files:**
- Modify: `packages/jw-mcp/src/jw_mcp/server.py`

- [ ] **Step 1: Add MCP tool definitions**

In `packages/jw-mcp/src/jw_mcp/server.py`, in the imports block, add:

```python
from datetime import date as _date
from jw_core.ministry.field_report import (
    FieldReportStore,
    HoursEntry,
    StudyEntry,
    aggregate_monthly_report,
)
from jw_core.ministry.exporters import render_csv, render_markdown
```

Then near the end (before the `if __name__ == "__main__":` block, alongside the existing tool registrations), add:

```python
# ---------------------------------------------------------------------------
# Phase 27 — Pioneer monthly report
# ---------------------------------------------------------------------------


@mcp.tool()
def field_log_hours(
    hours_decimal: float,
    date: str = "",
    tag: str | None = None,
    note: str = "",
) -> dict[str, Any]:
    """Registrar horas de servicio (local, cifrable). `date` ISO o vacío = hoy."""

    d = _date.fromisoformat(date) if date else _date.today()
    with FieldReportStore() as store:
        e = store.add_hours(
            HoursEntry(entry_id="", date=d, hours_decimal=hours_decimal, tag=tag, note=note)
        )
    return {"entry_id": e.entry_id, "date": e.date.isoformat(), "hours_decimal": e.hours_decimal, "tag": e.tag}


@mcp.tool()
def field_log_study(
    student_alias: str,
    started: str = "",
    closed: str = "",
    met_today: bool = False,
    note: str = "",
) -> dict[str, Any]:
    """Registrar, cerrar o marcar reunión de un curso bíblico (local, cifrable)."""

    with FieldReportStore() as store:
        if closed:
            n = store.close_study(student_id=student_alias, closed_at=_date.fromisoformat(closed))
            return {"closed_count": n, "student_alias": student_alias}
        s = store.upsert_study(
            StudyEntry(
                study_id="",
                student_id=student_alias,
                started_at=_date.fromisoformat(started) if started else _date.today(),
                note=note,
            )
        )
        if met_today:
            store.mark_met(student_id=student_alias, met_date=_date.today())
        return {
            "study_id": s.study_id,
            "student_alias": student_alias,
            "started_at": s.started_at.isoformat(),
            "met_today": met_today,
        }


@mcp.tool()
def field_monthly_report(
    month: str,
    include_revisits: bool = True,
    format: str = "json",
) -> dict[str, Any]:
    """Generar el informe mensual. ``format`` ∈ {json, markdown, csv}."""

    revisits = None
    if include_revisits:
        # Inline adapter — mirrors the CLI's _RevisitsAdapter.
        try:
            from jw_agents.revisit_tracker import RevisitStore
        except ImportError:
            RevisitStore = None  # type: ignore[assignment]
        if RevisitStore is not None:
            import datetime as _dt

            class _Adapter:
                def count_in_range(self, start: _date, end: _date) -> int:
                    try:
                        with RevisitStore() as s:
                            rows = s.list_all()
                    except Exception:
                        return 0
                    n = 0
                    for r in rows:
                        ts = r.updated_at_unix or 0
                        if ts and start <= _dt.date.fromtimestamp(ts) <= end:
                            n += 1
                    return n

            revisits = _Adapter()

    with FieldReportStore() as store:
        report = aggregate_monthly_report(store, month, revisits=revisits)
    if format == "markdown":
        return {"format": "markdown", "body": render_markdown(report)}
    if format == "csv":
        return {"format": "csv", "body": render_csv(report)}
    return {"format": "json", **report.model_dump()}
```

- [ ] **Step 2: Smoke-test the MCP tools**

```bash
uv run python - <<'PY'
import asyncio, json
from jw_mcp.server import field_log_hours, field_monthly_report

print(field_log_hours(hours_decimal=2.0, date="2026-05-12", tag="cart"))
print(json.dumps(field_monthly_report(month="2026-05", include_revisits=False), indent=2, default=str))
PY
```

Expected: hours added; monthly report dict contains `total_hours >= 2.0` and `entries_count >= 1`.

- [ ] **Step 3: Commit**

```bash
git add packages/jw-mcp/src/jw_mcp/server.py
git commit -m "feat(jw-mcp): field_log_hours / field_log_study / field_monthly_report tools"
```

---

### Task 11: Guide `docs/guias/informe-precursor.md`

**Files:**
- Create: `docs/guias/informe-precursor.md`

- [ ] **Step 1: Write the guide**

```markdown
# Informe mensual de precursor

> Guía de uso de `jw report`. Audiencia: precursores regulares,
> auxiliares y especiales que quieran llevar sus cifras del mes en local.

## En 30 segundos

```bash
# 1. (recomendado) genera tu clave y guárdala en tu gestor de contraseñas
export JW_PRIVACY_KEY=$(jw keygen)

# 2. registra horas y estudios cuando te ocurren
jw report log-hours --hours 2.5 --tag street --note "parque central"
jw report log-study --student-alias maria --started 2026-05-01
jw report met-today --student-alias maria

# 3. al cierre del mes, genera el informe
jw report --month 2026-05                   # markdown a stdout
jw report --month 2026-05 --format csv --out informe.csv
jw report --month 2026-05 --format pdf --out informe.pdf
```

## ¿Qué almacena y dónde?

- DB local: `~/.jw-agent-toolkit/field_service.db` (override con `JW_FIELD_DB`).
- Notas y alias de estudiantes están cifrados si `JW_PRIVACY_KEY` está set.
- Horas, fechas y modalidad (`street`, `cart`...) se guardan planas — sin ellas no se podría sumar.
- Las revisitas no se duplican: se leen del store de `jw ministry revisit` (Fase 12) solo en lectura.

## Cifrado

- **Activado**: define `JW_PRIVACY_KEY` (Fernet base64 — usa `jw keygen` para generar una).
- **Desactivado**: no definas la variable. Verás un warning al primer uso.
- **Silenciar el warning** sin activarlo: `export JW_FIELD_DISABLE_ENCRYPTION=1`. No recomendado.
- **Si pierdes la clave**: los datos cifrados son irrecuperables. Guarda la clave en tu gestor de contraseñas.

## Modalidades (tags)

Vocabulario por defecto: `street, return_visit, bible_study, online, phone, cart, letter, other`.

Para añadir locales propios (ej. `hospital`, `prison`) crea
`~/.jw-agent-toolkit/field_service_tags_local.json`:

```json
{"add": ["hospital", "prison"], "remove": []}
```

## Reglas de agregación importantes

- **Horas**: suma directa de las entries del mes. Display redondeado a múltiplos de 5 min según práctica vigente.
- **Cursos bíblicos activos**: se reporta el **máximo** durante el mes. Un curso empezado el 4 y cerrado el 25 cuenta, así como uno empezado el 25 y aún abierto al cierre. Esta convención evita penalizar cierres mediados del mes.
- **Revisitas**: cuenta de entradas en `revisit_tracker` cuya fecha de actualización cae dentro del mes. Se muestra aparte de `tag.return_visit` (que son horas, no contactos).

## Una semana en la vida de un precursor

```bash
# lunes
jw report log-hours --hours 3.0 --tag street --note "centro"
jw report log-study --student-alias luis --started 2026-05-01

# martes
jw report log-hours --hours 2.0 --tag cart
jw report met-today --student-alias luis

# miércoles
jw report log-hours --hours 1.5 --tag return_visit

# jueves
jw report log-hours --hours 4.0 --tag online --note "Zoom con tres revisitas"

# viernes
jw report log-hours --hours 2.0 --tag letter

# sábado
jw report log-hours --hours 5.0 --tag street
jw report met-today --student-alias luis

# domingo
jw report log-hours --hours 1.5 --tag phone

# fin de semana del mes
jw report --month 2026-05
```

## MCP

Tres herramientas equivalentes para Claude Desktop / cualquier cliente MCP:

- `field_log_hours(hours_decimal, date, tag, note)`
- `field_log_study(student_alias, started, closed, met_today, note)`
- `field_monthly_report(month, include_revisits, format)`

## Lo que no hace (por diseño)

- No exporta a S-21 oficial — esto es uso personal.
- No sincroniza entre dispositivos.
- No envía nada a la nube ni a la congregación.
- No reemplaza el informe que entrega el precursor: lo asiste.
```

- [ ] **Step 2: Commit**

```bash
git add docs/guias/informe-precursor.md
git commit -m "docs: informe-precursor guide for Fase 27"
```

---

### Task 12: ROADMAP + VISION_AUDIT update

**Files:**
- Modify: `docs/ROADMAP.md`
- Modify: `docs/VISION_AUDIT.md`

- [ ] **Step 1: Append Fase 27 section to ROADMAP**

Append at the end of `docs/ROADMAP.md`:

```markdown
## Fase 27 — Informe mensual de precursor

- ✅ `jw_core.data.field_service_tags` con vocabulario controlado + override JSON.
- ✅ `jw_core.ministry.field_report.FieldReportStore` SQLite con cifrado columnar (`note`, `student_id`).
- ✅ `HoursEntry` + `StudyEntry` + `MonthlyReport` Pydantic models.
- ✅ `aggregate_monthly_report` con regla MAX para estudios activos y redondeo de display a 5 min.
- ✅ `RevisitProvider` Protocol inyectable; CLI/MCP usan adapter read-only sobre `RevisitStore` (Fase 12).
- ✅ Exporters: `render_markdown`, `render_csv`, `render_pdf` (PDF detrás de `[pdf]` extra).
- ✅ CLI `jw report` con sub-sub `log-hours`, `log-study`, `met-today`, `show`.
- ✅ MCP tools: `field_log_hours`, `field_log_study`, `field_monthly_report`.
- ✅ Tests: 100% paths, `test_field_report.py` con fakes para revisitas y test de encriptación raw-row.
- ✅ Guía `docs/guias/informe-precursor.md`.
```

- [ ] **Step 2: Add row to VISION_AUDIT**

Find the section/table in `docs/VISION_AUDIT.md` que lista las fases, y añade la fila para Fase 27. Si VISION_AUDIT lleva subsecciones por agente, crea una sección `### Fase 27 — Informe mensual de precursor` con:

```markdown
### Fase 27 — Informe mensual de precursor (VISION #3)

- ✅ Aggregator `jw_core.ministry.field_report` (horas + estudios + revisitas) cifrable.
- ✅ CLI `jw report --month YYYY-MM` (md/csv/pdf).
- ✅ MCP tools: `field_log_hours`, `field_log_study`, `field_monthly_report`.
- ✅ Privacidad: cifrado columnar opt-in via `JW_PRIVACY_KEY`; warning amistoso si desactivado.
- ✅ Cross-package: `RevisitProvider` Protocol inyectable; no acopla `jw-core` a `jw-agents`.
- ✅ Tests CPU-only; PDF opcional via `[pdf]` extra.
```

- [ ] **Step 3: Commit**

```bash
git add docs/ROADMAP.md docs/VISION_AUDIT.md
git commit -m "docs: ROADMAP + VISION_AUDIT update for Fase 27"
```

---

### Task 13: Full suite green + smoke

**Files:**
- None (verification step only)

- [ ] **Step 1: Run the entire test suite**

Run: `.venv/bin/python -m pytest`
Expected: prior 551 + new tests all green. No skipped beyond the expected `weasyprint` skip on CI public runners.

- [ ] **Step 2: End-to-end smoke**

```bash
export JW_PRIVACY_KEY=$(uv run jw keygen)
rm -f ~/.jw-agent-toolkit/field_service.db
uv run jw report log-hours --hours 2.5 --tag street --note "parque" --date 2026-05-15
uv run jw report log-study --student-alias maria --started 2026-05-01
uv run jw report met-today --student-alias maria --date 2026-05-08
uv run jw report --month 2026-05 --format md
uv run jw report --month 2026-05 --format csv --out /tmp/r.csv
test -s /tmp/r.csv && echo "OK csv"
uv pip install -e 'packages/jw-core[pdf]' 2>/dev/null || true
uv run jw report --month 2026-05 --format pdf --out /tmp/r.pdf 2>/dev/null && file /tmp/r.pdf || echo "(PDF extra not installed)"
```

Expected:
- markdown contains `# Informe mensual — 2026-05`, `2.5` and `street`.
- CSV non-empty.
- PDF file is a PDF if the extra is installed.

- [ ] **Step 3: Audit checklist**

- [ ] No `jw_agents` import inside `jw_core/ministry/`.
- [ ] No network call (`grep -RInE 'http(s)?://' packages/jw-core/src/jw_core/ministry/` returns nothing other than docstring comments referencing wol).
- [ ] No LLM dependency (`grep -RIn 'ollama\|anthropic\|openai' packages/jw-core/src/jw_core/ministry/` empty).
- [ ] Encryption test passes: raw SQLite row does not contain cleartext note when `JW_PRIVACY_KEY` is set.
- [ ] CLI help text in Spanish (matches existing pattern of `jw ministry`).

- [ ] **Step 4: Final commit on this branch**

```bash
git status
# If anything stray, add + commit; otherwise just tag the work:
git log --oneline -n 15
```

---

## Self-review

Cosas que esta plan **no** rompe:

- 551 tests existentes (no toca módulos previos salvo `jw-mcp/server.py` y `jw-cli/main.py`, ambos por addition).
- Reglas duras de dependencia: `jw-core` sigue sin depender del resto del workspace.
- Política local-first + sin red en tests.
- Compatibilidad de cifrado con `FieldEncryptor` existente (Fase 11).
- Patrón store-con-`__enter__/__exit__` ya usado por `RevisitStore` y `PersonalNoteStore`.

Cosas que sí cambian deliberadamente:

- Añade un extra `[pdf]` al `pyproject.toml` de `jw-core`. Las dependencias `weasyprint`/`jinja2` quedan opcionales y los tests las saltan si no están.
- Crea `~/.jw-agent-toolkit/field_service.db` la primera vez que se usa, distinto de los archivos previos.

Decisiones que el implementador puede revisar conmigo antes de tocar código:

1. ¿Quiero que la regla de revisitas use `updated_at_unix` del `RevisitStore`, o un campo dedicado (lo cual implicaría escribir en el store y rompe la propiedad de read-only)? El plan asume `updated_at_unix`, conservador.
2. ¿Etiquetas en español por defecto en la prosa exportada (sí) o quedarse en inglés (no)? El plan elige español porque el resto del toolkit ya lo hace.
3. ¿`render_pdf` recibe `out_path` obligatorio (sí) o devuelve `bytes` cuando no se pasa? El plan elige obligatorio para no inflar la memoria.

## Execution choice

Dado que cada tarea es independiente excepto Task 3 ← Task 5 (aggregator depende del store) y Task 9 ← Tasks 6/7/8 (CLI depende de exporters), la ejecución natural es **secuencial**:

1. Task 1 → 2 → 3 → 4 → 5: núcleo del módulo (puede pararse aquí si fuera ultra-mínimo).
2. Task 6 → 7 → 8: exporters (PDF opcional).
3. Task 9 → 10: surfaces (CLI + MCP).
4. Task 11 → 12 → 13: docs + final audit.

Total: ~12-15 commits. Estimado: 2-3 días con verificación.
