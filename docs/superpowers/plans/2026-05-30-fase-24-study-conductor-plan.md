# Fase 24 — `study_conductor` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `study_conductor` (agent that prepares lessons from the current study book `lff`) and `StudentProgress` (local encryptable SQLite store of student lifecycle: status, notes, goals, baptism target). Expose via CLI `jw study …` and MCP. Protect with 2 golden cases in `jw-eval`.

**Architecture:** New modules in `jw-core/study/` + `jw-core/data/`, new agent + store in `jw-agents/`, new CLI command group, +4 MCP tools. Privacy model mirrors `RevisitStore` (Fernet field encryption, ON DEVICE only) but enforces a passphrase-derived key with persistent salt at `~/.jw-agent-toolkit/study_progress.salt`. First-run is bounded by a blocking consent prompt.

**Tech Stack:** Python 3.13 · Pydantic v2 (store rows + enums) · dataclasses (agent payloads) · cryptography.Fernet (existing `FieldEncryptor`) · SQLite stdlib · Typer (CLI) · FastMCP (MCP tools) · PyYAML (golden cases). Reuse existing `jw_core.parsers.jwpub`, `jw_core.clients.wol`, `jw_core.clients.topic_index`, `jw_core.integrations.meps_catalog`.

**Spec:** [`docs/superpowers/specs/2026-05-30-fase-24-study-conductor-design.md`](../specs/2026-05-30-fase-24-study-conductor-design.md).

---

## File map

Creates:
- `packages/jw-core/src/jw_core/data/study_books.py`
- `packages/jw-core/src/jw_core/data/study_prompts.py`
- `packages/jw-core/src/jw_core/study/lesson_extractor.py`
- `packages/jw-core/tests/test_study_books.py`
- `packages/jw-core/tests/test_study_prompts.py`
- `packages/jw-core/tests/test_lesson_extractor.py`
- `packages/jw-agents/src/jw_agents/study_conductor.py`
- `packages/jw-agents/src/jw_agents/study_progress.py`
- `packages/jw-agents/tests/test_study_conductor.py`
- `packages/jw-agents/tests/test_study_progress.py`
- `packages/jw-cli/src/jw_cli/commands/study.py`
- `packages/jw-cli/tests/test_cli_study.py`
- `packages/jw-eval/fixtures/golden_qa/l1/study_conductor_lff_ch1_es.yaml`
- `packages/jw-eval/fixtures/golden_qa/l3/study_conductor_lff_ch1_es.yaml`
- `docs/guias/conductor-de-estudio.md`

Modifies:
- `packages/jw-cli/src/jw_cli/main.py` — register `study` group
- `packages/jw-mcp/src/jw_mcp/server.py` — register 4 tools
- `docs/ROADMAP.md` — add Fase 24 section
- `docs/VISION_AUDIT.md` — add audit row Fase 24 → VISION #1

---

### Task 1: Registry `study_books`

**Files:**
- Create: `packages/jw-core/src/jw_core/data/study_books.py`
- Create: `packages/jw-core/tests/test_study_books.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-core/tests/test_study_books.py
"""Tests for the study-book registry."""

from __future__ import annotations

import pytest

from jw_core.data.study_books import (
    CURRENT_STUDY_BOOK,
    REGISTRY,
    StudyBook,
    get_book,
    list_supported_languages,
)


def test_current_study_book_is_lff() -> None:
    assert CURRENT_STUDY_BOOK == "lff"
    assert "lff" in REGISTRY


def test_lff_metadata_complete() -> None:
    book = get_book("lff")
    assert book.pub_code == "lff"
    assert book.title_by_lang["es"].startswith("Disfruta")
    assert book.title_by_lang["en"].startswith("Enjoy")
    assert book.total_chapters == 60
    assert "es" in book.languages
    assert "en" in book.languages
    assert "pt" in book.languages


def test_get_book_unknown_raises() -> None:
    with pytest.raises(KeyError):
        get_book("does_not_exist")


def test_list_supported_languages_returns_union() -> None:
    langs = list_supported_languages()
    assert "es" in langs
    assert "en" in langs
    assert "pt" in langs


def test_registry_entries_are_frozen() -> None:
    book = get_book("lff")
    with pytest.raises(Exception):  # FrozenInstanceError
        book.pub_code = "x"  # type: ignore[misc]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/jw-core/tests/test_study_books.py -v`
Expected: FAIL — ModuleNotFoundError on `jw_core.data.study_books`.

- [ ] **Step 3: Implement the registry**

```python
# packages/jw-core/src/jw_core/data/study_books.py
"""Registry of study-book publications used by `study_conductor`.

Each entry is the minimum needed by the agent to load chapters from
JWPUB (local) or WOL (fallback) and render titles in the user's
language. New publications are added by appending entries; the agent
code never changes.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StudyBook:
    pub_code: str
    title_by_lang: dict[str, str]
    languages: tuple[str, ...]
    total_chapters: int
    jwpub_symbol: str


CURRENT_STUDY_BOOK = "lff"

REGISTRY: dict[str, StudyBook] = {
    "lff": StudyBook(
        pub_code="lff",
        title_by_lang={
            "es": "Disfruta de la vida para siempre",
            "en": "Enjoy Life Forever!",
            "pt": "Desfrute a vida para sempre",
            "fr": "Profitez de la vie pour toujours",
            "de": "Genieße das Leben für immer",
            "it": "Goditi la vita per sempre",
            "ja": "永遠の命を楽しもう",
            "ko": "영원한 생명을 즐기십시오",
        },
        languages=("en", "es", "pt", "fr", "de", "it", "ja", "ko"),
        total_chapters=60,
        jwpub_symbol="lff",
    ),
}


def get_book(pub_code: str) -> StudyBook:
    try:
        return REGISTRY[pub_code]
    except KeyError as e:
        raise KeyError(f"Unknown study book pub_code={pub_code!r}") from e


def list_supported_languages() -> set[str]:
    langs: set[str] = set()
    for book in REGISTRY.values():
        langs.update(book.languages)
    return langs
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/jw-core/tests/test_study_books.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-core/src/jw_core/data/study_books.py packages/jw-core/tests/test_study_books.py
git commit -m "feat(jw-core): study_books registry with lff entry (Fase 24)"
```

---

### Task 2: Anticipation templates and crisis keywords

**Files:**
- Create: `packages/jw-core/src/jw_core/data/study_prompts.py`
- Create: `packages/jw-core/tests/test_study_prompts.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-core/tests/test_study_prompts.py
from __future__ import annotations

import pytest

from jw_core.data.study_prompts import (
    ANTICIPATION_TEMPLATES,
    CRISIS_KEYWORDS,
    render_template,
    scan_for_crisis,
)


def test_templates_cover_minimum_languages() -> None:
    for lang in ("es", "en", "pt"):
        assert lang in ANTICIPATION_TEMPLATES
        assert "fact" in ANTICIPATION_TEMPLATES[lang]
        assert "application" in ANTICIPATION_TEMPLATES[lang]
        assert "scripture" in ANTICIPATION_TEMPLATES[lang]


def test_render_fact_template_es() -> None:
    out = render_template("es", "fact", n=3)
    assert "3" in out
    assert "?" in out


def test_render_scripture_requires_ref() -> None:
    out = render_template("en", "scripture", n=2, ref="John 3:16")
    assert "John 3:16" in out
    assert "2" in out


def test_render_unknown_template_raises() -> None:
    with pytest.raises(KeyError):
        render_template("es", "does_not_exist", n=1)


def test_render_falls_back_to_english_for_unknown_lang() -> None:
    out = render_template("xx", "fact", n=1)
    assert "?" in out  # at least it rendered something usable


def test_scan_for_crisis_es_match() -> None:
    hits = scan_for_crisis("La hermana mencionó suicidio.", language="es")
    assert hits == ["suicidio"]


def test_scan_for_crisis_no_match() -> None:
    assert scan_for_crisis("Hablamos sobre el reino", language="es") == []


def test_scan_for_crisis_unknown_lang_falls_back_to_en() -> None:
    hits = scan_for_crisis("He felt abuse", language="xx")
    assert "abuse" in hits
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/jw-core/tests/test_study_prompts.py -v`
Expected: FAIL — `study_prompts` not importable.

- [ ] **Step 3: Implement templates + crisis scanner**

```python
# packages/jw-core/src/jw_core/data/study_prompts.py
"""Procedural templates for `study_conductor` anticipation questions.

Templates are intentionally simple: the agent picks a template per
paragraph and substitutes `n` (paragraph number) and optionally `ref`
(a scripture reference). NO LLM is involved.

CRISIS_KEYWORDS scans user notes locally and surfaces a warning if a
match is found — the agent never blocks the save; it just adds a hint
in the AgentResult.warnings.
"""

from __future__ import annotations

from typing import Any

ANTICIPATION_TEMPLATES: dict[str, dict[str, str]] = {
    "es": {
        "fact":        "¿Qué punto principal enseña el párrafo {n}?",
        "application": "¿Cómo aplicaría usted personalmente lo del párrafo {n}?",
        "scripture":   "Lea {ref}. ¿Cómo apoya esto la idea del párrafo {n}?",
        "feeling":     "¿Cómo se siente respecto a lo que dice el párrafo {n}?",
    },
    "en": {
        "fact":        "What main point does paragraph {n} teach?",
        "application": "How would you personally apply paragraph {n}?",
        "scripture":   "Read {ref}. How does it support the idea in paragraph {n}?",
        "feeling":     "How do you feel about what paragraph {n} says?",
    },
    "pt": {
        "fact":        "Qual é o ponto principal do parágrafo {n}?",
        "application": "Como você aplicaria pessoalmente o parágrafo {n}?",
        "scripture":   "Leia {ref}. Como isso apoia a ideia do parágrafo {n}?",
        "feeling":     "Como você se sente sobre o que o parágrafo {n} diz?",
    },
}

CRISIS_KEYWORDS: dict[str, list[str]] = {
    "es": ["suicidio", "abuso", "violencia", "me quiero morir", "autolesión"],
    "en": ["suicide", "abuse", "violence", "want to die", "self-harm"],
    "pt": ["suicídio", "abuso", "violência", "quero morrer", "automutilação"],
}


def render_template(language: str, kind: str, **kwargs: Any) -> str:
    """Render an anticipation template; fall back to English if `language` unknown."""

    lang_templates = ANTICIPATION_TEMPLATES.get(language) or ANTICIPATION_TEMPLATES["en"]
    template = lang_templates[kind]  # raises KeyError if `kind` unknown — by design
    return template.format(**kwargs)


def scan_for_crisis(text: str, *, language: str) -> list[str]:
    """Return crisis keywords found in `text`. Empty list when none."""

    if not text:
        return []
    haystack = text.lower()
    needles = CRISIS_KEYWORDS.get(language) or CRISIS_KEYWORDS["en"]
    return [kw for kw in needles if kw in haystack]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/jw-core/tests/test_study_prompts.py -v`
Expected: 8 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-core/src/jw_core/data/study_prompts.py packages/jw-core/tests/test_study_prompts.py
git commit -m "feat(jw-core): study_prompts templates (es/en/pt) + crisis keyword scanner"
```

---

### Task 3: `LessonContent` model and `lesson_extractor` skeleton with WOL fallback

**Files:**
- Create: `packages/jw-core/src/jw_core/study/lesson_extractor.py`
- Create: `packages/jw-core/tests/test_lesson_extractor.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-core/tests/test_lesson_extractor.py
from __future__ import annotations

from dataclasses import dataclass

import pytest

from jw_core.study.lesson_extractor import (
    LessonContent,
    LessonExtractionError,
    extract_lesson,
)


def test_lesson_content_shape() -> None:
    lc = LessonContent(
        pub_code="lff",
        chapter=1,
        language="es",
        title="¿Existe alguien que se preocupe por usted?",
        paragraphs=["P1...", "P2..."],
        scripture_refs={1: ["1 Pedro 5:6, 7"], 2: []},
        source="jwpub_local",
        citation_url="https://wol.jw.org/es/wol/publication/r4/lp-s/lff/1",
    )
    assert lc.pub_code == "lff"
    assert lc.source == "jwpub_local"
    assert len(lc.paragraphs) == 2


def test_extract_lesson_unknown_pub_raises() -> None:
    with pytest.raises(LessonExtractionError):
        extract_lesson("nope", chapter=1, language="es")


def test_extract_lesson_chapter_out_of_range() -> None:
    with pytest.raises(LessonExtractionError):
        extract_lesson("lff", chapter=999, language="es")


def test_extract_lesson_wol_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    # Force JWPUB lookup to return None → must fall back to WOL.

    def fake_find_jwpub(*args: object, **kwargs: object) -> None:
        return None

    @dataclass
    class _FakeHTMLPage:
        title: str = "Capítulo 1"
        paragraphs: tuple[str, ...] = ("Texto del párrafo 1.", "Texto del párrafo 2.")

    def fake_wol_get(*args: object, **kwargs: object) -> _FakeHTMLPage:
        return _FakeHTMLPage()

    monkeypatch.setattr(
        "jw_core.study.lesson_extractor._find_jwpub_path",
        fake_find_jwpub,
    )
    monkeypatch.setattr(
        "jw_core.study.lesson_extractor._fetch_chapter_from_wol",
        fake_wol_get,
    )

    lc = extract_lesson("lff", chapter=1, language="es")
    assert lc.source == "wol_fallback"
    assert len(lc.paragraphs) == 2
    assert lc.citation_url.startswith("https://wol.jw.org/")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/jw-core/tests/test_lesson_extractor.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement extractor**

```python
# packages/jw-core/src/jw_core/study/lesson_extractor.py
"""Extract one chapter of a study book.

Two paths:
  1) JWPUB local: looks up the publication via `meps_catalog`, decrypts
     with `parsers.jwpub.parse_jwpub`, picks the document by chapter
     number (1-based, matches the JW Library TOC).
  2) WOL fallback: when no local JWPUB is registered, fetches the
     publication page from wol.jw.org via `WOLClient`.

Returns a plain `LessonContent` dataclass — the agent layer wraps this
in `Finding`/`AgentResult` shape.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from jw_core.data.study_books import get_book


class LessonExtractionError(RuntimeError):
    pass


SourceKind = Literal["jwpub_local", "wol_fallback"]


@dataclass(frozen=True)
class LessonContent:
    pub_code: str
    chapter: int
    language: str
    title: str
    paragraphs: list[str]
    scripture_refs: dict[int, list[str]] = field(default_factory=dict)  # paragraph_idx → refs
    source: SourceKind = "wol_fallback"
    citation_url: str = ""


def extract_lesson(pub_code: str, chapter: int, language: str = "es") -> LessonContent:
    """Load one lesson. Raise `LessonExtractionError` on validation errors."""

    try:
        book = get_book(pub_code)
    except KeyError as e:
        raise LessonExtractionError(str(e)) from e

    if not (1 <= chapter <= book.total_chapters):
        raise LessonExtractionError(
            f"chapter={chapter} out of range for {pub_code} (1..{book.total_chapters})"
        )
    if language not in book.languages:
        raise LessonExtractionError(
            f"language={language!r} not supported for {pub_code} (supported: {book.languages})"
        )

    jwpub_path = _find_jwpub_path(symbol=book.jwpub_symbol, language=language)
    if jwpub_path is not None:
        return _extract_from_jwpub(book, chapter, language, jwpub_path)

    return _extract_from_wol(book, chapter, language)


def _find_jwpub_path(*, symbol: str, language: str):
    """Stub: lazy-imports MEPS catalog. Returns Path | None."""

    try:
        from jw_core.integrations.meps_catalog import find_publication_path
    except ImportError:
        return None
    return find_publication_path(symbol=symbol, language=language)


def _extract_from_jwpub(book, chapter, language, path) -> LessonContent:
    """Decrypt JWPUB and pick the requested chapter's document."""

    from jw_core.parsers.jwpub import parse_jwpub

    pub = parse_jwpub(path)
    documents = list(pub.documents)
    if not (1 <= chapter <= len(documents)):
        raise LessonExtractionError(
            f"jwpub for {book.pub_code}/{language} only has {len(documents)} documents"
        )
    doc = documents[chapter - 1]
    title = doc.title or book.title_by_lang.get(language, book.pub_code)
    paragraphs = list(doc.paragraphs)
    refs = _collect_scripture_refs(paragraphs)
    return LessonContent(
        pub_code=book.pub_code,
        chapter=chapter,
        language=language,
        title=title,
        paragraphs=paragraphs,
        scripture_refs=refs,
        source="jwpub_local",
        citation_url=_canonical_url(book.pub_code, chapter, language),
    )


def _extract_from_wol(book, chapter, language) -> LessonContent:
    """Fetch the chapter page from WOL and normalize to LessonContent."""

    page = _fetch_chapter_from_wol(book.pub_code, chapter, language)
    return LessonContent(
        pub_code=book.pub_code,
        chapter=chapter,
        language=language,
        title=getattr(page, "title", "") or book.title_by_lang.get(language, book.pub_code),
        paragraphs=list(getattr(page, "paragraphs", []) or []),
        scripture_refs=_collect_scripture_refs(list(getattr(page, "paragraphs", []) or [])),
        source="wol_fallback",
        citation_url=_canonical_url(book.pub_code, chapter, language),
    )


def _fetch_chapter_from_wol(pub_code: str, chapter: int, language: str):
    """Lazy import — never touch network at import time."""

    from jw_core.clients.factory import build_clients

    suite = build_clients()
    return suite.wol.get_publication_page(pub_code, n=chapter, language=language)


def _collect_scripture_refs(paragraphs: list[str]) -> dict[int, list[str]]:
    from jw_core.parsers.reference import find_references

    refs: dict[int, list[str]] = {}
    for i, p in enumerate(paragraphs, start=1):
        try:
            hits = find_references(p)
            refs[i] = [str(h) for h in hits] if hits else []
        except Exception:
            refs[i] = []
    return refs


def _canonical_url(pub_code: str, chapter: int, language: str) -> str:
    iso = {"es": "es", "en": "en", "pt": "pt"}.get(language, language)
    return f"https://wol.jw.org/{iso}/wol/publication/r4/lp-{iso[:1]}/{pub_code}/{chapter}"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/jw-core/tests/test_lesson_extractor.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-core/src/jw_core/study/lesson_extractor.py packages/jw-core/tests/test_lesson_extractor.py
git commit -m "feat(jw-core): lesson_extractor with JWPUB-local + WOL fallback paths"
```

---

### Task 4: `LessonStatus`, `GoalKind`, `StudentGoal`, `LessonRow` Pydantic models

**Files:**
- Create: `packages/jw-agents/src/jw_agents/study_progress.py` (partial — just models)
- Create: `packages/jw-agents/tests/test_study_progress.py` (partial — model tests)

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-agents/tests/test_study_progress.py
from __future__ import annotations

import pytest
from pydantic import ValidationError

from jw_agents.study_progress import (
    GoalKind,
    LessonRow,
    LessonStatus,
    StudentGoal,
)


def test_lesson_status_enum_values() -> None:
    assert LessonStatus.NOT_STARTED.value == "not_started"
    assert LessonStatus.IN_PROGRESS.value == "in_progress"
    assert LessonStatus.COMPLETED.value == "completed"
    assert LessonStatus.SKIPPED.value == "skipped"


def test_goal_kind_enum_includes_taxonomy() -> None:
    assert GoalKind.ATTEND_MEETINGS in GoalKind
    assert GoalKind.DROP_ADDICTION_SMOKING in GoalKind
    assert GoalKind.DROP_ADDICTION_ALCOHOL in GoalKind
    assert GoalKind.PRAY_DAILY in GoalKind
    assert GoalKind.FAMILY_WORSHIP in GoalKind
    assert GoalKind.BAPTISM in GoalKind


def test_lesson_row_validates_student_id() -> None:
    LessonRow(
        student_id="amelia2024",
        book_pub="lff",
        lesson=1,
        updated_at_iso="2026-05-30T00:00:00",
    )


def test_lesson_row_rejects_invalid_student_id() -> None:
    with pytest.raises(ValidationError):
        LessonRow(
            student_id="Amelia García",
            book_pub="lff",
            lesson=1,
            updated_at_iso="2026-05-30T00:00:00",
        )


def test_lesson_row_default_status_not_started() -> None:
    row = LessonRow(
        student_id="x_y_z",
        book_pub="lff",
        lesson=1,
        updated_at_iso="2026-05-30T00:00:00",
    )
    assert row.status == LessonStatus.NOT_STARTED


def test_student_goal_minimal() -> None:
    g = StudentGoal(kind=GoalKind.BAPTISM, set_at_iso="2026-05-30T00:00:00")
    assert g.kind == GoalKind.BAPTISM
    assert g.achieved_at_iso is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/jw-agents/tests/test_study_progress.py -v`
Expected: FAIL — `study_progress` missing.

- [ ] **Step 3: Implement the models**

```python
# packages/jw-agents/src/jw_agents/study_progress.py
"""StudentProgress — local-only encryptable store for the study-book lifecycle.

VISION rule: "No tracker de hermanos sin opt-in". This IS a tracker, so:
  - First-run requires an explicit y/N consent + passphrase.
  - student_id is an alias (regex `^[a-z0-9_-]{3,32}$`), never a real name.
  - Free-text `notes` are Fernet-encrypted at rest with a key derived
    from the user's passphrase (PBKDF2-HMAC-SHA256, persistent salt).
  - Storage is ON DEVICE only. No sync. No telemetry.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class LessonStatus(str, Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED   = "completed"
    SKIPPED     = "skipped"


class GoalKind(str, Enum):
    ATTEND_MEETINGS         = "attend_meetings"
    DROP_ADDICTION_SMOKING  = "drop_addiction_smoking"
    DROP_ADDICTION_ALCOHOL  = "drop_addiction_alcohol"
    DROP_ADDICTION_OTHER    = "drop_addiction_other"
    PRAY_DAILY              = "pray_daily"
    FAMILY_WORSHIP          = "family_worship"
    BAPTISM                 = "baptism"
    OTHER                   = "other"


class StudentGoal(BaseModel):
    kind: GoalKind
    note: str = ""
    set_at_iso: str
    achieved_at_iso: str | None = None
    target_iso: str | None = None


class LessonRow(BaseModel):
    student_id: str = Field(pattern=r"^[a-z0-9_-]{3,32}$")
    book_pub: str
    lesson: int = Field(ge=1)
    status: LessonStatus = LessonStatus.NOT_STARTED
    notes: str = ""
    goals: list[StudentGoal] = []
    started_at_iso: str | None = None
    completed_at_iso: str | None = None
    attended_meetings_count: int = 0
    baptism_target_iso: str | None = None
    updated_at_iso: str
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/jw-agents/tests/test_study_progress.py -v`
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-agents/src/jw_agents/study_progress.py packages/jw-agents/tests/test_study_progress.py
git commit -m "feat(jw-agents): LessonStatus/GoalKind/StudentGoal/LessonRow models for study progress"
```

---

### Task 5: First-run passphrase + salt persistence

**Files:**
- Modify: `packages/jw-agents/src/jw_agents/study_progress.py`
- Modify: `packages/jw-agents/tests/test_study_progress.py`

- [ ] **Step 1: Append failing tests**

```python
# Append to packages/jw-agents/tests/test_study_progress.py
from pathlib import Path

from jw_agents.study_progress import (
    PrivacyState,
    derive_encryptor_for_passphrase,
    load_or_create_salt,
)


def test_load_or_create_salt_creates_when_missing(tmp_path: Path) -> None:
    target = tmp_path / "salt.bin"
    state = load_or_create_salt(target)
    assert state == PrivacyState.CREATED
    assert target.exists()
    assert len(target.read_bytes()) == 16


def test_load_or_create_salt_returns_existing(tmp_path: Path) -> None:
    target = tmp_path / "salt.bin"
    load_or_create_salt(target)
    state2 = load_or_create_salt(target)
    assert state2 == PrivacyState.LOADED


def test_derive_encryptor_round_trip(tmp_path: Path) -> None:
    salt_path = tmp_path / "salt.bin"
    load_or_create_salt(salt_path)
    enc = derive_encryptor_for_passphrase("hunter2", salt_path=salt_path)
    assert enc.enabled
    token = enc.encrypt("nota sensible")
    assert enc.decrypt(token) == "nota sensible"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/jw-agents/tests/test_study_progress.py -v`
Expected: 3 new tests FAIL — symbols missing.

- [ ] **Step 3: Implement privacy bootstrap**

Append to `packages/jw-agents/src/jw_agents/study_progress.py`:

```python
import os
import secrets
from enum import Enum as _PyEnum
from pathlib import Path

from jw_core.privacy.encryption import FieldEncryptor, derive_key_from_password


class PrivacyState(str, _PyEnum):
    CREATED = "created"
    LOADED  = "loaded"


def default_salt_path() -> Path:
    raw = os.getenv("JW_STUDY_SALT", "~/.jw-agent-toolkit/study_progress.salt")
    return Path(raw).expanduser()


def default_db_path() -> Path:
    raw = os.getenv("JW_STUDY_DB", "~/.jw-agent-toolkit/study_progress.db")
    return Path(raw).expanduser()


def load_or_create_salt(path: Path) -> PrivacyState:
    """Persistent 16-byte salt. Created with `os.urandom` on first call."""

    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        return PrivacyState.LOADED
    path.write_bytes(secrets.token_bytes(16))
    return PrivacyState.CREATED


def derive_encryptor_for_passphrase(
    passphrase: str, *, salt_path: Path | None = None
) -> FieldEncryptor:
    """Derive a FieldEncryptor from passphrase + persistent salt."""

    salt_path = salt_path or default_salt_path()
    load_or_create_salt(salt_path)
    salt = salt_path.read_bytes()
    key = derive_key_from_password(passphrase, salt=salt)
    return FieldEncryptor(key=key)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/jw-agents/tests/test_study_progress.py -v`
Expected: 9 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-agents/src/jw_agents/study_progress.py packages/jw-agents/tests/test_study_progress.py
git commit -m "feat(jw-agents): study_progress passphrase-derived FieldEncryptor + persistent salt"
```

---

### Task 6: `StudentProgressStore` (SQLite, encrypt notes)

**Files:**
- Modify: `packages/jw-agents/src/jw_agents/study_progress.py`
- Modify: `packages/jw-agents/tests/test_study_progress.py`

- [ ] **Step 1: Append failing tests**

```python
# Append to packages/jw-agents/tests/test_study_progress.py
from pathlib import Path

from jw_agents.study_progress import StudentProgressStore


def test_store_round_trip_without_encryption(tmp_path: Path) -> None:
    store = StudentProgressStore(db_path=tmp_path / "p.db")
    row = LessonRow(
        student_id="demo_user",
        book_pub="lff",
        lesson=1,
        status=LessonStatus.IN_PROGRESS,
        notes="alpha",
        updated_at_iso="2026-05-30T00:00:00",
    )
    store.upsert(row)
    got = store.get("demo_user", "lff", 1)
    assert got is not None
    assert got.status == LessonStatus.IN_PROGRESS
    assert got.notes == "alpha"


def test_store_encrypted_notes_round_trip(tmp_path: Path) -> None:
    salt_path = tmp_path / "salt.bin"
    load_or_create_salt(salt_path)
    enc = derive_encryptor_for_passphrase("hunter2", salt_path=salt_path)
    store = StudentProgressStore(db_path=tmp_path / "p.db", encryptor=enc)
    row = LessonRow(
        student_id="demo_user",
        book_pub="lff",
        lesson=2,
        notes="nota privada con áéíóú",
        updated_at_iso="2026-05-30T00:00:00",
    )
    store.upsert(row)
    got = store.get("demo_user", "lff", 2)
    assert got is not None
    assert got.notes == "nota privada con áéíóú"

    # Sanity: opening DB without key returns ciphertext for notes.
    plain_store = StudentProgressStore(db_path=tmp_path / "p.db")
    raw = plain_store.get("demo_user", "lff", 2)
    assert raw is not None
    assert raw.notes != "nota privada con áéíóú"


def test_store_list_for_student(tmp_path: Path) -> None:
    store = StudentProgressStore(db_path=tmp_path / "p.db")
    for n in (1, 2, 3):
        store.upsert(LessonRow(
            student_id="demo_user", book_pub="lff", lesson=n,
            updated_at_iso="2026-05-30T00:00:00",
        ))
    rows = store.list_for_student("demo_user")
    assert [r.lesson for r in rows] == [1, 2, 3]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/jw-agents/tests/test_study_progress.py -v`
Expected: 3 new tests FAIL — `StudentProgressStore` missing.

- [ ] **Step 3: Implement the store**

Append to `packages/jw-agents/src/jw_agents/study_progress.py`:

```python
import json
import sqlite3
from datetime import datetime, timezone


class StudentProgressStore:
    SCHEMA = """
    CREATE TABLE IF NOT EXISTS lessons (
        student_id TEXT NOT NULL,
        book_pub TEXT NOT NULL,
        lesson INTEGER NOT NULL,
        status TEXT NOT NULL DEFAULT 'not_started',
        notes TEXT NOT NULL DEFAULT '',
        goals_json TEXT NOT NULL DEFAULT '[]',
        started_at_iso TEXT,
        completed_at_iso TEXT,
        attended_meetings_count INTEGER NOT NULL DEFAULT 0,
        baptism_target_iso TEXT,
        updated_at_iso TEXT NOT NULL,
        PRIMARY KEY (student_id, book_pub, lesson)
    );
    CREATE INDEX IF NOT EXISTS idx_student ON lessons (student_id);
    CREATE INDEX IF NOT EXISTS idx_book ON lessons (book_pub);
    """

    def __init__(
        self,
        db_path: Path | str | None = None,
        *,
        encryptor: FieldEncryptor | None = None,
    ) -> None:
        self.path = Path(db_path).expanduser() if db_path else default_db_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.path)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(self.SCHEMA)
        self._conn.commit()
        self._enc = encryptor if encryptor is not None else FieldEncryptor()

    def _encrypt_notes(self, value: str) -> str:
        if self._enc.enabled and value:
            return self._enc.encrypt(value)
        return value

    def _decrypt_notes(self, value: str) -> str:
        if self._enc.enabled and value:
            try:
                return self._enc.decrypt(value)
            except Exception:
                return value
        return value

    def upsert(self, row: LessonRow) -> LessonRow:
        if not row.updated_at_iso:
            row.updated_at_iso = datetime.now(timezone.utc).isoformat()
        encrypted_notes = self._encrypt_notes(row.notes)
        goals_json = json.dumps([g.model_dump() for g in row.goals])
        self._conn.execute(
            """
            INSERT INTO lessons (student_id, book_pub, lesson, status, notes, goals_json,
                                 started_at_iso, completed_at_iso, attended_meetings_count,
                                 baptism_target_iso, updated_at_iso)
            VALUES (:sid, :pub, :lesson, :status, :notes, :goals,
                    :started, :completed, :attended, :baptism, :updated)
            ON CONFLICT(student_id, book_pub, lesson) DO UPDATE SET
                status=excluded.status,
                notes=excluded.notes,
                goals_json=excluded.goals_json,
                started_at_iso=excluded.started_at_iso,
                completed_at_iso=excluded.completed_at_iso,
                attended_meetings_count=excluded.attended_meetings_count,
                baptism_target_iso=excluded.baptism_target_iso,
                updated_at_iso=excluded.updated_at_iso
            """,
            {
                "sid": row.student_id, "pub": row.book_pub, "lesson": row.lesson,
                "status": row.status.value, "notes": encrypted_notes, "goals": goals_json,
                "started": row.started_at_iso, "completed": row.completed_at_iso,
                "attended": row.attended_meetings_count,
                "baptism": row.baptism_target_iso,
                "updated": row.updated_at_iso,
            },
        )
        self._conn.commit()
        return row

    def get(self, student_id: str, book_pub: str, lesson: int) -> LessonRow | None:
        cur = self._conn.execute(
            "SELECT * FROM lessons WHERE student_id=? AND book_pub=? AND lesson=?",
            (student_id, book_pub, lesson),
        )
        row = cur.fetchone()
        return self._row_to_model(row) if row else None

    def list_for_student(self, student_id: str, book_pub: str | None = None) -> list[LessonRow]:
        if book_pub:
            cur = self._conn.execute(
                "SELECT * FROM lessons WHERE student_id=? AND book_pub=? ORDER BY lesson",
                (student_id, book_pub),
            )
        else:
            cur = self._conn.execute(
                "SELECT * FROM lessons WHERE student_id=? ORDER BY book_pub, lesson",
                (student_id,),
            )
        return [self._row_to_model(r) for r in cur.fetchall()]

    def _row_to_model(self, row: sqlite3.Row) -> LessonRow:
        goals_raw = json.loads(row["goals_json"] or "[]")
        return LessonRow(
            student_id=row["student_id"],
            book_pub=row["book_pub"],
            lesson=row["lesson"],
            status=LessonStatus(row["status"]),
            notes=self._decrypt_notes(row["notes"]),
            goals=[StudentGoal(**g) for g in goals_raw],
            started_at_iso=row["started_at_iso"],
            completed_at_iso=row["completed_at_iso"],
            attended_meetings_count=row["attended_meetings_count"],
            baptism_target_iso=row["baptism_target_iso"],
            updated_at_iso=row["updated_at_iso"],
        )

    def close(self) -> None:
        self._conn.close()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/jw-agents/tests/test_study_progress.py -v`
Expected: 12 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-agents/src/jw_agents/study_progress.py packages/jw-agents/tests/test_study_progress.py
git commit -m "feat(jw-agents): StudentProgressStore SQLite + Fernet-encrypted notes"
```

---

### Task 7: Crisis warning integration in store + `set_goal` helper

**Files:**
- Modify: `packages/jw-agents/src/jw_agents/study_progress.py`
- Modify: `packages/jw-agents/tests/test_study_progress.py`

- [ ] **Step 1: Append failing tests**

```python
# Append to packages/jw-agents/tests/test_study_progress.py
from jw_agents.study_progress import set_goal_for_student, scan_lesson_for_crisis


def test_scan_lesson_for_crisis_hits() -> None:
    row = LessonRow(
        student_id="demo_user", book_pub="lff", lesson=1,
        notes="Mencionó suicidio en la última visita",
        updated_at_iso="2026-05-30T00:00:00",
    )
    hits = scan_lesson_for_crisis(row, language="es")
    assert "suicidio" in hits


def test_set_goal_for_student_appends(tmp_path: Path) -> None:
    store = StudentProgressStore(db_path=tmp_path / "p.db")
    row = LessonRow(
        student_id="demo_user", book_pub="lff", lesson=1,
        updated_at_iso="2026-05-30T00:00:00",
    )
    store.upsert(row)
    updated = set_goal_for_student(
        store, "demo_user", "lff", 1,
        kind=GoalKind.BAPTISM, target_iso="2026-12-31T00:00:00",
    )
    assert any(g.kind == GoalKind.BAPTISM for g in updated.goals)
    assert updated.baptism_target_iso == "2026-12-31T00:00:00"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/jw-agents/tests/test_study_progress.py -v`
Expected: 2 new tests FAIL.

- [ ] **Step 3: Implement helpers**

Append to `packages/jw-agents/src/jw_agents/study_progress.py`:

```python
from jw_core.data.study_prompts import scan_for_crisis


def scan_lesson_for_crisis(row: LessonRow, *, language: str) -> list[str]:
    return scan_for_crisis(row.notes, language=language)


def set_goal_for_student(
    store: "StudentProgressStore",
    student_id: str,
    book_pub: str,
    lesson: int,
    *,
    kind: GoalKind,
    target_iso: str | None = None,
    note: str = "",
) -> LessonRow:
    """Append (or upsert) a goal on a student's lesson row."""

    row = store.get(student_id, book_pub, lesson)
    if row is None:
        row = LessonRow(
            student_id=student_id, book_pub=book_pub, lesson=lesson,
            updated_at_iso=datetime.now(timezone.utc).isoformat(),
        )
    now = datetime.now(timezone.utc).isoformat()
    # Replace existing goal of same kind; otherwise append.
    goals = [g for g in row.goals if g.kind != kind]
    goals.append(StudentGoal(kind=kind, set_at_iso=now, target_iso=target_iso, note=note))
    row.goals = goals
    if kind == GoalKind.BAPTISM and target_iso:
        row.baptism_target_iso = target_iso
    row.updated_at_iso = now
    store.upsert(row)
    return row
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/jw-agents/tests/test_study_progress.py -v`
Expected: 14 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-agents/src/jw_agents/study_progress.py packages/jw-agents/tests/test_study_progress.py
git commit -m "feat(jw-agents): scan_lesson_for_crisis + set_goal_for_student helpers"
```

---

### Task 8: `study_conductor` agent — `prepare_lesson`

**Files:**
- Create: `packages/jw-agents/src/jw_agents/study_conductor.py`
- Create: `packages/jw-agents/tests/test_study_conductor.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-agents/tests/test_study_conductor.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from jw_agents.study_conductor import (
    AnticipationQuestion,
    LessonPrep,
    prepare_lesson,
)


@dataclass
class _FakeLesson:
    pub_code: str = "lff"
    chapter: int = 1
    language: str = "es"
    title: str = "¿Existe alguien que se preocupe por usted?"
    paragraphs: list[str] = None
    scripture_refs: dict[int, list[str]] = None
    source: str = "jwpub_local"
    citation_url: str = "https://wol.jw.org/es/wol/publication/r4/lp-s/lff/1"

    def __post_init__(self) -> None:
        if self.paragraphs is None:
            self.paragraphs = [
                "Jehová es un Padre amoroso (1 Pedro 5:7).",
                "Él se preocupa por usted más de lo que imagina.",
            ]
        if self.scripture_refs is None:
            self.scripture_refs = {1: ["1 Pedro 5:7"], 2: []}


def test_prepare_lesson_returns_findings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "jw_agents.study_conductor.extract_lesson",
        lambda *a, **k: _FakeLesson(),
    )
    monkeypatch.setattr(
        "jw_agents.study_conductor._topic_hits",
        lambda *a, **k: ["Jehová", "Padre amoroso"],
    )
    result = prepare_lesson("lff", chapter=1, language="es")
    assert result.agent_name == "study_conductor"
    assert len(result.findings) >= 1

    lesson_finding = result.findings[0]
    assert lesson_finding.citation.url.startswith("https://wol.jw.org/")
    assert lesson_finding.metadata["source"] == "jwpub_chapter"
    prep = lesson_finding.metadata["payload"]
    assert isinstance(prep, LessonPrep)
    assert prep.pub_code == "lff"
    assert len(prep.questions) >= 2
    assert any("1 Pedro 5:7" in q.text for q in prep.questions)


def test_prepare_lesson_unknown_pub_warns(monkeypatch: pytest.MonkeyPatch) -> None:
    from jw_core.study.lesson_extractor import LessonExtractionError

    def boom(*a: Any, **k: Any) -> Any:
        raise LessonExtractionError("nope")

    monkeypatch.setattr("jw_agents.study_conductor.extract_lesson", boom)
    result = prepare_lesson("nope", chapter=1, language="es")
    assert result.findings == []
    assert any("nope" in w for w in result.warnings)


def test_anticipation_question_dataclass() -> None:
    q = AnticipationQuestion(
        paragraph_index=1, text="hi", template_id="es.fact", related_verses=[],
    )
    assert q.paragraph_index == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/jw-agents/tests/test_study_conductor.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement the agent**

```python
# packages/jw-agents/src/jw_agents/study_conductor.py
"""study_conductor — procedural agent for preparing study-book lessons.

VISION rule: "No sustituir la palabra de los ancianos". This agent
generates **preparation material for the conductor** (the brother doing
the personal study), NOT a script to read aloud.

Pipeline:
    1. extract_lesson(pub, chapter, lang)  — load content (JWPUB or WOL).
    2. generate_anticipation_questions(...) — templated questions.
    3. topic_index hits for the chapter title — supporting subjects.
    4. wrap as AgentResult with stable source ordering (Fase 22 L1).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from jw_agents.base import AgentResult, Citation, Finding
from jw_core.data.study_prompts import render_template
from jw_core.study.lesson_extractor import (
    LessonContent,
    LessonExtractionError,
    extract_lesson,
)

AGENT_NAME = "study_conductor"


@dataclass(frozen=True)
class AnticipationQuestion:
    paragraph_index: int
    text: str
    template_id: str
    related_verses: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class LessonPrep:
    pub_code: str
    chapter: int
    language: str
    title: str
    summary: str
    questions: list[AnticipationQuestion]
    key_verses: list[str]
    supporting_topics: list[str]
    source: Literal["jwpub_local", "wol_fallback"]


def prepare_lesson(pub_code: str, chapter: int, language: str = "es") -> AgentResult:
    query = f"prepare_lesson({pub_code!r}, ch={chapter}, lang={language!r})"
    warnings: list[str] = []
    findings: list[Finding] = []

    try:
        content = extract_lesson(pub_code, chapter, language)
    except LessonExtractionError as e:
        return AgentResult(
            query=query,
            agent_name=AGENT_NAME,
            findings=[],
            warnings=[str(e)],
        )

    if content.source == "wol_fallback":
        warnings.append("JWPUB local no encontrado: usando WOL como fallback.")

    questions = _generate_anticipation_questions(content)
    key_verses = sorted({r for refs in content.scripture_refs.values() for r in refs})
    topics = _topic_hits(content.title, language)

    prep = LessonPrep(
        pub_code=content.pub_code,
        chapter=content.chapter,
        language=content.language,
        title=content.title,
        summary=_make_summary(content),
        questions=questions,
        key_verses=key_verses,
        supporting_topics=topics,
        source=content.source,
    )

    # Primary finding: the lesson itself (highest-priority source).
    findings.append(
        Finding(
            summary=f"Lección {content.chapter} — {content.title}",
            excerpt=prep.summary,
            citation=Citation(
                url=content.citation_url,
                title=content.title,
                kind="chapter",
            ),
            metadata={
                "source": "jwpub_chapter" if content.source == "jwpub_local" else "wol_chapter",
                "payload": prep,
            },
        )
    )

    # Secondary findings: topic_index subjects (lower priority).
    for subject in topics:
        findings.append(
            Finding(
                summary=f"Tema relacionado: {subject}",
                excerpt="",
                citation=Citation(url=content.citation_url, title=subject, kind="topic"),
                metadata={"source": "topic_index"},
            )
        )

    return AgentResult(
        query=query,
        agent_name=AGENT_NAME,
        findings=findings,
        warnings=warnings,
        metadata={"pub_code": pub_code, "chapter": chapter, "language": language},
    )


def _generate_anticipation_questions(content: LessonContent) -> list[AnticipationQuestion]:
    """Two questions per paragraph (fact + application); +scripture when refs exist."""

    out: list[AnticipationQuestion] = []
    for idx, _para in enumerate(content.paragraphs, start=1):
        out.append(AnticipationQuestion(
            paragraph_index=idx,
            text=render_template(content.language, "fact", n=idx),
            template_id=f"{content.language}.fact",
            related_verses=[],
        ))
        out.append(AnticipationQuestion(
            paragraph_index=idx,
            text=render_template(content.language, "application", n=idx),
            template_id=f"{content.language}.application",
            related_verses=[],
        ))
        refs = content.scripture_refs.get(idx, [])
        for ref in refs:
            out.append(AnticipationQuestion(
                paragraph_index=idx,
                text=render_template(content.language, "scripture", n=idx, ref=ref),
                template_id=f"{content.language}.scripture",
                related_verses=[ref],
            ))
    return out


def _make_summary(content: LessonContent) -> str:
    # First paragraph clipped; deterministic, no LLM.
    if not content.paragraphs:
        return content.title
    first = content.paragraphs[0]
    return (first[:320] + "…") if len(first) > 320 else first


def _topic_hits(title: str, language: str) -> list[str]:
    """Up to 3 supporting subjects from topic_index. Best-effort, no raise."""

    try:
        from jw_core.clients.factory import build_clients

        suite = build_clients()
        results = suite.topic_index.search(title, language=language)
        return [r.title for r in (results or [])[:3]]
    except Exception:
        return []
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/jw-agents/tests/test_study_conductor.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-agents/src/jw_agents/study_conductor.py packages/jw-agents/tests/test_study_conductor.py
git commit -m "feat(jw-agents): study_conductor.prepare_lesson agent (templated, no LLM)"
```

---

### Task 9: Disclosure / consent flow (CLI helper)

**Files:**
- Modify: `packages/jw-agents/src/jw_agents/study_progress.py`
- Modify: `packages/jw-agents/tests/test_study_progress.py`

- [ ] **Step 1: Append failing tests**

```python
# Append to packages/jw-agents/tests/test_study_progress.py
from jw_agents.study_progress import build_disclosure_text, looks_like_first_run


def test_disclosure_text_in_spanish_mentions_local_only() -> None:
    text = build_disclosure_text(language="es")
    assert "local" in text.lower()
    assert "passphrase" in text.lower() or "frase" in text.lower()
    assert "ancianos" in text.lower() or "consejero" in text.lower()


def test_disclosure_text_english() -> None:
    text = build_disclosure_text(language="en")
    assert "local" in text.lower()


def test_first_run_detection(tmp_path: Path) -> None:
    salt = tmp_path / "salt.bin"
    assert looks_like_first_run(salt) is True
    salt.write_bytes(b"x" * 16)
    assert looks_like_first_run(salt) is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/jw-agents/tests/test_study_progress.py -v`
Expected: 3 new tests FAIL.

- [ ] **Step 3: Implement**

Append to `packages/jw-agents/src/jw_agents/study_progress.py`:

```python
DISCLOSURE = {
    "es": (
        "Este comando registra datos personales de personas reales (estudiantes).\n"
        "• Todo se guarda LOCAL en este disco. No se sube a ningún servidor.\n"
        "• Necesita elegir una passphrase. Si la olvida, los datos se pierden\n"
        "  por diseño (no hay recuperación).\n"
        "• Esto NO sustituye a los ancianos ni a un consejero profesional. Si la\n"
        "  nota refleja una crisis, contacte a los ancianos o a un profesional.\n"
        "\n¿Continuar? [y/N]: "
    ),
    "en": (
        "This command stores personal data about real people (students).\n"
        "• Everything stays LOCAL on this disk. Nothing is uploaded.\n"
        "• Pick a passphrase. If you lose it the data is irrecoverable by design.\n"
        "• This does NOT replace elders or a professional counselor. If a note\n"
        "  reflects a crisis, contact elders or a professional.\n"
        "\nContinue? [y/N]: "
    ),
    "pt": (
        "Este comando guarda dados pessoais de pessoas reais (estudantes).\n"
        "• Tudo fica LOCAL neste disco. Nada é enviado para a internet.\n"
        "• Escolha uma passphrase. Se perdê-la, os dados são irrecuperáveis.\n"
        "• Isto NÃO substitui os anciãos nem um conselheiro profissional.\n"
        "\nContinuar? [y/N]: "
    ),
}


def build_disclosure_text(*, language: str) -> str:
    return DISCLOSURE.get(language) or DISCLOSURE["en"]


def looks_like_first_run(salt_path: Path | None = None) -> bool:
    return not (salt_path or default_salt_path()).exists()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/jw-agents/tests/test_study_progress.py -v`
Expected: 17 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-agents/src/jw_agents/study_progress.py packages/jw-agents/tests/test_study_progress.py
git commit -m "feat(jw-agents): disclosure text (es/en/pt) and first-run detector"
```

---

### Task 10: CLI command group `jw study` — scaffolding

**Files:**
- Create: `packages/jw-cli/src/jw_cli/commands/study.py`
- Create: `packages/jw-cli/tests/test_cli_study.py`
- Modify: `packages/jw-cli/src/jw_cli/main.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-cli/tests/test_cli_study.py
from __future__ import annotations

from typer.testing import CliRunner

from jw_cli.main import app


runner = CliRunner()


def test_study_help_runs() -> None:
    result = runner.invoke(app, ["study", "--help"])
    assert result.exit_code == 0
    assert "study" in result.stdout.lower()


def test_study_goals_lists_taxonomy() -> None:
    result = runner.invoke(app, ["study", "goals"])
    assert result.exit_code == 0
    out = result.stdout
    assert "attend_meetings" in out
    assert "baptism" in out
    assert "drop_addiction_smoking" in out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/jw-cli/tests/test_cli_study.py -v`
Expected: FAIL — `study` command missing.

- [ ] **Step 3: Implement CLI skeleton + `goals` subcommand**

```python
# packages/jw-cli/src/jw_cli/commands/study.py
"""`jw study …` — preparation + lifecycle for the current study book.

Subcommands:
  lesson    Prepare a chapter (anticipation questions + key verses).
  log       Record progress (status/note/goals) for a (student, book, lesson).
  progress  Show the student's lifecycle across the book.
  goals     Print the controlled goal taxonomy.
  directory Manage the optional alias→display-name map.
"""

from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from jw_agents.study_progress import GoalKind

study_app = typer.Typer(
    name="study",
    help="Preparación de lecciones y registro de progreso del estudiante.",
    no_args_is_help=True,
)
console = Console()


@study_app.command("goals")
def goals_cmd() -> None:
    """Lista la taxonomía controlada de metas."""

    table = Table(title="Metas del estudiante (vocabulario controlado)")
    table.add_column("kind")
    table.add_column("ejemplo de uso")
    examples = {
        "attend_meetings": "Asistir a una reunión cada semana",
        "drop_addiction_smoking": "Dejar de fumar",
        "drop_addiction_alcohol": "Reducir consumo de alcohol",
        "drop_addiction_other": "Otra adicción (en nota cifrada)",
        "pray_daily": "Orar todos los días",
        "family_worship": "Iniciar adoración en familia semanal",
        "baptism": "Calificar para el bautismo",
        "other": "Cualquier otra meta (en nota cifrada)",
    }
    for k in GoalKind:
        table.add_row(k.value, examples.get(k.value, ""))
    console.print(table)
```

Edit `packages/jw-cli/src/jw_cli/main.py`:
- Import: `from jw_cli.commands import study`
- Add: `app.add_typer(study.study_app, name="study")`

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/jw-cli/tests/test_cli_study.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-cli/src/jw_cli/commands/study.py packages/jw-cli/src/jw_cli/main.py packages/jw-cli/tests/test_cli_study.py
git commit -m "feat(jw-cli): jw study command group + goals subcommand"
```

---

### Task 11: CLI `jw study lesson <pub> <ch>`

**Files:**
- Modify: `packages/jw-cli/src/jw_cli/commands/study.py`
- Modify: `packages/jw-cli/tests/test_cli_study.py`

- [ ] **Step 1: Append failing test**

```python
# Append to packages/jw-cli/tests/test_cli_study.py
def test_study_lesson_renders_prep(monkeypatch) -> None:
    from jw_agents.base import AgentResult, Citation, Finding
    from jw_agents.study_conductor import AnticipationQuestion, LessonPrep

    prep = LessonPrep(
        pub_code="lff", chapter=1, language="es",
        title="¿Existe alguien que se preocupe por usted?",
        summary="Jehová es un Padre amoroso.",
        questions=[
            AnticipationQuestion(1, "¿Qué punto principal enseña el párrafo 1?",
                                 "es.fact", []),
        ],
        key_verses=["1 Pedro 5:7"], supporting_topics=["Jehová"], source="jwpub_local",
    )
    fake_result = AgentResult(
        query="prepare_lesson",
        agent_name="study_conductor",
        findings=[Finding(
            summary="L1", excerpt="Jehová...",
            citation=Citation(url="https://wol.jw.org/x", title="L1", kind="chapter"),
            metadata={"source": "jwpub_chapter", "payload": prep},
        )],
    )
    monkeypatch.setattr(
        "jw_cli.commands.study.prepare_lesson",
        lambda *a, **k: fake_result,
    )
    result = runner.invoke(app, ["study", "lesson", "lff", "1", "--lang", "es"])
    assert result.exit_code == 0
    assert "1 Pedro 5:7" in result.stdout
    assert "párrafo 1" in result.stdout
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/jw-cli/tests/test_cli_study.py::test_study_lesson_renders_prep -v`
Expected: FAIL — `lesson` command not defined.

- [ ] **Step 3: Implement**

Append to `packages/jw-cli/src/jw_cli/commands/study.py`:

```python
from jw_agents.study_conductor import prepare_lesson


@study_app.command("lesson")
def lesson_cmd(
    pub_code: str = typer.Argument(..., help="Código de publicación (p.ej. lff)"),
    chapter: int = typer.Argument(..., help="Número de capítulo (1-based)"),
    lang: str = typer.Option("es", "--lang", "-l", help="Idioma (es/en/pt/…)"),
) -> None:
    """Prepara una lección: preguntas de anticipación y versículos clave."""

    result = prepare_lesson(pub_code, chapter=chapter, language=lang)
    if not result.findings:
        for w in result.warnings:
            console.print(f"[yellow]⚠[/yellow] {w}")
        raise typer.Exit(code=1)

    for w in result.warnings:
        console.print(f"[yellow]⚠[/yellow] {w}")

    primary = result.findings[0]
    prep = primary.metadata.get("payload")
    if prep is None:
        console.print("[red]Salida inesperada del agente.[/red]")
        raise typer.Exit(code=2)

    console.rule(f"[bold]{prep.title}[/bold]  ({prep.pub_code} ch. {prep.chapter}, {prep.language})")
    console.print(prep.summary)
    console.print(f"\n[bold]Versículos clave:[/bold] {', '.join(prep.key_verses) or '(none)'}")
    if prep.supporting_topics:
        console.print(f"[bold]Temas relacionados:[/bold] {', '.join(prep.supporting_topics)}")

    console.print("\n[bold]Preguntas de anticipación:[/bold]")
    for q in prep.questions:
        console.print(f"  · (¶{q.paragraph_index}) {q.text}")

    console.print(f"\n[dim]Fuente: {prep.source} — {primary.citation.url}[/dim]")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/jw-cli/tests/test_cli_study.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-cli/src/jw_cli/commands/study.py packages/jw-cli/tests/test_cli_study.py
git commit -m "feat(jw-cli): jw study lesson <pub> <ch> command"
```

---

### Task 12: CLI `jw study log` (with first-run disclosure + passphrase)

**Files:**
- Modify: `packages/jw-cli/src/jw_cli/commands/study.py`
- Modify: `packages/jw-cli/tests/test_cli_study.py`

- [ ] **Step 1: Append failing test**

```python
# Append to packages/jw-cli/tests/test_cli_study.py
def test_study_log_writes_and_reads(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("JW_STUDY_DB", str(tmp_path / "p.db"))
    monkeypatch.setenv("JW_STUDY_SALT", str(tmp_path / "salt.bin"))
    monkeypatch.setenv("JW_STUDY_PASSPHRASE", "hunter2")

    result = runner.invoke(app, [
        "study", "log", "demo_user", "lff", "1",
        "--status", "in_progress",
        "--note", "buena receptividad",
        "--goal", "attend_meetings",
    ])
    assert result.exit_code == 0, result.stdout
    assert "demo_user" in result.stdout
    assert "in_progress" in result.stdout


def test_study_log_rejects_bad_student_id(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("JW_STUDY_DB", str(tmp_path / "p.db"))
    monkeypatch.setenv("JW_STUDY_SALT", str(tmp_path / "salt.bin"))
    monkeypatch.setenv("JW_STUDY_PASSPHRASE", "hunter2")
    result = runner.invoke(app, ["study", "log", "Amelia García", "lff", "1"])
    assert result.exit_code != 0


def test_study_log_warns_on_crisis_keyword(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("JW_STUDY_DB", str(tmp_path / "p.db"))
    monkeypatch.setenv("JW_STUDY_SALT", str(tmp_path / "salt.bin"))
    monkeypatch.setenv("JW_STUDY_PASSPHRASE", "hunter2")
    result = runner.invoke(app, [
        "study", "log", "demo_user", "lff", "1",
        "--note", "Mencionó suicidio en la visita",
    ])
    assert result.exit_code == 0
    assert "crisis" in result.stdout.lower() or "anciano" in result.stdout.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/jw-cli/tests/test_cli_study.py -v`
Expected: 3 new tests FAIL.

- [ ] **Step 3: Implement**

Append to `packages/jw-cli/src/jw_cli/commands/study.py`:

```python
import os
from datetime import datetime, timezone

from jw_agents.study_progress import (
    GoalKind,
    LessonRow,
    LessonStatus,
    StudentGoal,
    StudentProgressStore,
    build_disclosure_text,
    default_salt_path,
    derive_encryptor_for_passphrase,
    looks_like_first_run,
    scan_lesson_for_crisis,
)
from pydantic import ValidationError


def _get_store(language: str = "es") -> StudentProgressStore:
    passphrase = os.getenv("JW_STUDY_PASSPHRASE")
    if not passphrase:
        console.print(
            "[red]Falta passphrase.[/red] "
            "Set JW_STUDY_PASSPHRASE en el entorno y vuelva a intentarlo."
        )
        raise typer.Exit(code=2)

    salt = default_salt_path()
    if looks_like_first_run(salt):
        console.print(build_disclosure_text(language=language))
        confirm = typer.confirm("¿Continuar?", default=False)
        if not confirm:
            raise typer.Exit(code=3)

    enc = derive_encryptor_for_passphrase(passphrase, salt_path=salt)
    return StudentProgressStore(encryptor=enc)


@study_app.command("log")
def log_cmd(
    student_id: str = typer.Argument(..., help="Alias del estudiante (regex [a-z0-9_-]{3,32})"),
    pub_code: str = typer.Argument(..., help="Código de publicación (lff, …)"),
    lesson: int = typer.Argument(..., help="Número de lección"),
    status: str = typer.Option("in_progress", "--status",
                                help="not_started|in_progress|completed|skipped"),
    note: str = typer.Option("", "--note", help="Nota libre (se cifra al guardar)"),
    goal: list[str] = typer.Option(None, "--goal",
                                    help="Meta de la taxonomía (repetible)"),
    target_iso: str = typer.Option(None, "--target-iso",
                                    help="ISO date (solo para --goal baptism)"),
    lang: str = typer.Option("es", "--lang", "-l"),
) -> None:
    """Registra el progreso de una lección para un estudiante."""

    try:
        row = LessonRow(
            student_id=student_id,
            book_pub=pub_code,
            lesson=lesson,
            status=LessonStatus(status),
            notes=note,
            updated_at_iso=datetime.now(timezone.utc).isoformat(),
        )
    except (ValidationError, ValueError) as e:
        console.print(f"[red]Entrada inválida:[/red] {e}")
        raise typer.Exit(code=4) from e

    if row.status == LessonStatus.IN_PROGRESS and not row.started_at_iso:
        row.started_at_iso = row.updated_at_iso
    if row.status == LessonStatus.COMPLETED and not row.completed_at_iso:
        row.completed_at_iso = row.updated_at_iso

    if goal:
        now = row.updated_at_iso
        row.goals = [
            StudentGoal(kind=GoalKind(g), set_at_iso=now,
                        target_iso=(target_iso if GoalKind(g) == GoalKind.BAPTISM else None))
            for g in goal
        ]
        if any(g.kind == GoalKind.BAPTISM for g in row.goals):
            row.baptism_target_iso = target_iso

    crisis_hits = scan_lesson_for_crisis(row, language=lang)
    if crisis_hits:
        console.print(
            "[yellow]⚠ Detectados términos de crisis "
            f"({', '.join(crisis_hits)}). Se recomienda contactar a los ancianos o un consejero.[/yellow]"
        )

    store = _get_store(language=lang)
    saved = store.upsert(row)
    console.print(f"[green]✓[/green] {saved.student_id} · {saved.book_pub} ch.{saved.lesson} → {saved.status.value}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/jw-cli/tests/test_cli_study.py -v`
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-cli/src/jw_cli/commands/study.py packages/jw-cli/tests/test_cli_study.py
git commit -m "feat(jw-cli): jw study log with passphrase + first-run consent + crisis warning"
```

---

### Task 13: CLI `jw study progress <student>` + `jw study lessons`

**Files:**
- Modify: `packages/jw-cli/src/jw_cli/commands/study.py`
- Modify: `packages/jw-cli/tests/test_cli_study.py`

- [ ] **Step 1: Append failing test**

```python
# Append to packages/jw-cli/tests/test_cli_study.py
def test_study_progress_shows_lifecycle(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("JW_STUDY_DB", str(tmp_path / "p.db"))
    monkeypatch.setenv("JW_STUDY_SALT", str(tmp_path / "salt.bin"))
    monkeypatch.setenv("JW_STUDY_PASSPHRASE", "hunter2")

    # Seed two lessons
    runner.invoke(app, ["study", "log", "demo_user", "lff", "1", "--status", "completed"])
    runner.invoke(app, ["study", "log", "demo_user", "lff", "2", "--status", "in_progress"])

    result = runner.invoke(app, ["study", "progress", "demo_user"])
    assert result.exit_code == 0
    assert "1" in result.stdout and "2" in result.stdout
    assert "completed" in result.stdout
    assert "in_progress" in result.stdout


def test_study_lessons_lists_chapter_titles() -> None:
    result = runner.invoke(app, ["study", "lessons", "lff", "--lang", "es"])
    assert result.exit_code == 0
    assert "Disfruta" in result.stdout
    assert "60" in result.stdout  # total chapters
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/jw-cli/tests/test_cli_study.py -v`
Expected: 2 new tests FAIL.

- [ ] **Step 3: Implement**

Append to `packages/jw-cli/src/jw_cli/commands/study.py`:

```python
from jw_core.data.study_books import get_book


@study_app.command("lessons")
def lessons_cmd(
    pub_code: str = typer.Argument(...),
    lang: str = typer.Option("es", "--lang", "-l"),
) -> None:
    """Muestra el inventario de capítulos de un libro de estudio."""

    try:
        book = get_book(pub_code)
    except KeyError:
        console.print(f"[red]Libro desconocido:[/red] {pub_code}")
        raise typer.Exit(code=2)
    console.print(f"[bold]{book.title_by_lang.get(lang, book.pub_code)}[/bold] — {book.total_chapters} capítulos")
    console.print(f"Idiomas soportados: {', '.join(book.languages)}")


@study_app.command("progress")
def progress_cmd(
    student_id: str = typer.Argument(...),
    pub_code: str = typer.Option(None, "--pub", help="Filtrar por publicación"),
    lang: str = typer.Option("es", "--lang", "-l"),
) -> None:
    """Muestra el ciclo de vida de un estudiante (todas sus lecciones)."""

    store = _get_store(language=lang)
    rows = store.list_for_student(student_id, book_pub=pub_code)
    if not rows:
        console.print(f"[yellow]Sin registros para {student_id}.[/yellow]")
        raise typer.Exit(code=0)

    table = Table(title=f"Progreso de {student_id}")
    table.add_column("pub")
    table.add_column("ch")
    table.add_column("status")
    table.add_column("metas")
    table.add_column("actualizado")
    for r in rows:
        table.add_row(
            r.book_pub, str(r.lesson), r.status.value,
            ", ".join(g.kind.value for g in r.goals) or "—",
            r.updated_at_iso[:10],
        )
    console.print(table)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/jw-cli/tests/test_cli_study.py -v`
Expected: 8 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-cli/src/jw_cli/commands/study.py packages/jw-cli/tests/test_cli_study.py
git commit -m "feat(jw-cli): jw study progress + jw study lessons commands"
```

---

### Task 14: CLI `jw study directory` (opt-in alias→display name)

**Files:**
- Modify: `packages/jw-cli/src/jw_cli/commands/study.py`
- Modify: `packages/jw-cli/tests/test_cli_study.py`

- [ ] **Step 1: Append failing test**

```python
# Append to packages/jw-cli/tests/test_cli_study.py
def test_study_directory_set_and_clear(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("JW_STUDY_DIRECTORY", str(tmp_path / "directory.json"))

    r1 = runner.invoke(app, ["study", "directory", "set", "demo_user", "Demo García"])
    assert r1.exit_code == 0

    r2 = runner.invoke(app, ["study", "directory", "show"])
    assert r2.exit_code == 0
    assert "Demo García" in r2.stdout

    r3 = runner.invoke(app, ["study", "directory", "clear", "--yes"])
    assert r3.exit_code == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/jw-cli/tests/test_cli_study.py -v`
Expected: 1 new test FAIL.

- [ ] **Step 3: Implement**

Append to `packages/jw-cli/src/jw_cli/commands/study.py`:

```python
import json
from pathlib import Path


def _directory_path() -> Path:
    raw = os.getenv("JW_STUDY_DIRECTORY", "~/.jw-agent-toolkit/study_directory.json")
    return Path(raw).expanduser()


directory_app = typer.Typer(name="directory", help="Alias→nombre opcional (opt-in).")
study_app.add_typer(directory_app, name="directory")


@directory_app.command("set")
def directory_set(alias: str, display_name: str) -> None:
    path = _directory_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    data: dict[str, str] = {}
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
    data[alias] = display_name
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    console.print(f"[green]✓[/green] {alias} → {display_name}")


@directory_app.command("show")
def directory_show() -> None:
    path = _directory_path()
    if not path.exists():
        console.print("[yellow]Sin directorio.[/yellow]")
        return
    data = json.loads(path.read_text(encoding="utf-8"))
    table = Table(title="Directorio (alias → nombre)")
    table.add_column("alias")
    table.add_column("nombre")
    for k, v in sorted(data.items()):
        table.add_row(k, v)
    console.print(table)


@directory_app.command("clear")
def directory_clear(yes: bool = typer.Option(False, "--yes")) -> None:
    if not yes:
        console.print("[yellow]Use --yes para confirmar.[/yellow]")
        raise typer.Exit(code=1)
    path = _directory_path()
    if path.exists():
        path.unlink()
    console.print("[green]✓[/green] Directorio eliminado.")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/jw-cli/tests/test_cli_study.py -v`
Expected: 9 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-cli/src/jw_cli/commands/study.py packages/jw-cli/tests/test_cli_study.py
git commit -m "feat(jw-cli): jw study directory (opt-in alias→display name JSON)"
```

---

### Task 15: MCP tool `prepare_lesson`

**Files:**
- Modify: `packages/jw-mcp/src/jw_mcp/server.py`
- Create: `packages/jw-mcp/tests/test_mcp_study.py` (or extend an existing test file)

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-mcp/tests/test_mcp_study.py
from __future__ import annotations

import pytest


def test_prepare_lesson_tool_returns_dict(monkeypatch) -> None:
    from jw_mcp import server as srv
    from jw_agents.base import AgentResult, Citation, Finding

    def fake_prepare(*a, **k):
        return AgentResult(
            query="x", agent_name="study_conductor",
            findings=[Finding(
                summary="Lección 1", excerpt="…",
                citation=Citation(url="https://wol.jw.org/x", title="t", kind="chapter"),
                metadata={"source": "wol_chapter"},
            )],
        )

    monkeypatch.setattr(srv, "prepare_lesson_agent", fake_prepare)
    out = srv.prepare_lesson("lff", 1, "es")
    assert "findings" in out
    assert len(out["findings"]) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/jw-mcp/tests/test_mcp_study.py -v`
Expected: FAIL — symbol missing.

- [ ] **Step 3: Implement tool**

Edit `packages/jw-mcp/src/jw_mcp/server.py`:

```python
# Imports (top of file, alongside existing agent imports)
from jw_agents.study_conductor import prepare_lesson as prepare_lesson_agent

# Tool registration (under the section where other agent tools are registered)
@mcp.tool()
def prepare_lesson(
    pub_code: str,
    chapter: int,
    language: str = "es",
) -> dict[str, Any]:
    """Prepare a study-book lesson: anticipation questions + key verses + topics.

    Args:
        pub_code: Publication code (e.g. "lff" for Enjoy Life Forever!).
        chapter: 1-based chapter number.
        language: ISO code (es/en/pt/…). Falls back to English for unknown.
    """

    try:
        result = prepare_lesson_agent(pub_code, chapter=chapter, language=language)
    except Exception as e:  # noqa: BLE001
        return {"error": str(e)}
    return result.to_dict()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/jw-mcp/tests/test_mcp_study.py -v`
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-mcp/src/jw_mcp/server.py packages/jw-mcp/tests/test_mcp_study.py
git commit -m "feat(jw-mcp): expose prepare_lesson tool"
```

---

### Task 16: MCP tools `log_student_progress`, `list_student_lessons`, `set_student_goal`

**Files:**
- Modify: `packages/jw-mcp/src/jw_mcp/server.py`
- Modify: `packages/jw-mcp/tests/test_mcp_study.py`

- [ ] **Step 1: Append failing tests**

```python
# Append to packages/jw-mcp/tests/test_mcp_study.py
def test_log_student_progress_requires_passphrase(monkeypatch) -> None:
    monkeypatch.delenv("JW_STUDY_PASSPHRASE", raising=False)
    from jw_mcp import server as srv
    out = srv.log_student_progress("demo_user", "lff", 1)
    assert "error" in out
    assert "passphrase" in out["error"].lower() or "JW_STUDY_PASSPHRASE" in out["error"]


def test_log_student_progress_round_trip(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("JW_STUDY_PASSPHRASE", "hunter2")
    monkeypatch.setenv("JW_STUDY_DB", str(tmp_path / "p.db"))
    monkeypatch.setenv("JW_STUDY_SALT", str(tmp_path / "salt.bin"))
    from jw_agents.study_progress import load_or_create_salt
    load_or_create_salt(tmp_path / "salt.bin")

    from jw_mcp import server as srv
    out = srv.log_student_progress(
        "demo_user", "lff", 1, status="completed", note="ok", goals=["attend_meetings"],
    )
    assert "error" not in out, out
    listing = srv.list_student_lessons("demo_user", book_pub="lff")
    assert listing["count"] == 1
    set_out = srv.set_student_goal(
        "demo_user", kind="baptism", target_iso="2026-12-31T00:00:00",
    )
    assert "error" not in set_out, set_out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/jw-mcp/tests/test_mcp_study.py -v`
Expected: 2 new tests FAIL.

- [ ] **Step 3: Implement tools**

Append to `packages/jw-mcp/src/jw_mcp/server.py`:

```python
import os as _os
from datetime import datetime as _dt, timezone as _tz

from jw_agents.study_progress import (
    GoalKind as _GoalKind,
    LessonRow as _LessonRow,
    LessonStatus as _LessonStatus,
    StudentGoal as _StudentGoal,
    StudentProgressStore as _StudentProgressStore,
    default_salt_path as _default_salt_path,
    derive_encryptor_for_passphrase as _derive_enc,
    set_goal_for_student as _set_goal_for_student,
)


def _study_store() -> _StudentProgressStore | dict[str, str]:
    passphrase = _os.getenv("JW_STUDY_PASSPHRASE")
    if not passphrase:
        return {"error": "JW_STUDY_PASSPHRASE not set"}
    enc = _derive_enc(passphrase, salt_path=_default_salt_path())
    return _StudentProgressStore(encryptor=enc)


@mcp.tool()
def log_student_progress(
    student_id: str,
    book_pub: str,
    lesson: int,
    status: str = "in_progress",
    note: str = "",
    goals: list[str] | None = None,
    target_iso: str | None = None,
) -> dict[str, Any]:
    """Record progress for (student, book, lesson). Notes encrypted at rest."""

    store_or_err = _study_store()
    if isinstance(store_or_err, dict):
        return store_or_err
    store = store_or_err

    try:
        now = _dt.now(_tz.utc).isoformat()
        row = _LessonRow(
            student_id=student_id, book_pub=book_pub, lesson=lesson,
            status=_LessonStatus(status), notes=note,
            updated_at_iso=now,
            started_at_iso=now if status == "in_progress" else None,
            completed_at_iso=now if status == "completed" else None,
            goals=[
                _StudentGoal(kind=_GoalKind(g), set_at_iso=now,
                              target_iso=(target_iso if g == "baptism" else None))
                for g in (goals or [])
            ],
            baptism_target_iso=(target_iso if goals and "baptism" in goals else None),
        )
        saved = store.upsert(row)
        return {"row": saved.model_dump(mode="json")}
    except Exception as e:  # noqa: BLE001
        return {"error": str(e)}


@mcp.tool()
def list_student_lessons(
    student_id: str, book_pub: str | None = None,
) -> dict[str, Any]:
    """List a student's lessons (decrypted notes in-memory)."""

    store_or_err = _study_store()
    if isinstance(store_or_err, dict):
        return store_or_err
    store = store_or_err
    rows = store.list_for_student(student_id, book_pub=book_pub)
    return {"count": len(rows), "rows": [r.model_dump(mode="json") for r in rows]}


@mcp.tool()
def set_student_goal(
    student_id: str,
    kind: str,
    book_pub: str = "lff",
    lesson: int = 1,
    target_iso: str | None = None,
    note: str = "",
) -> dict[str, Any]:
    """Append or replace a goal on a (student, book, lesson) row."""

    store_or_err = _study_store()
    if isinstance(store_or_err, dict):
        return store_or_err
    try:
        row = _set_goal_for_student(
            store_or_err, student_id, book_pub, lesson,
            kind=_GoalKind(kind), target_iso=target_iso, note=note,
        )
        return {"row": row.model_dump(mode="json")}
    except Exception as e:  # noqa: BLE001
        return {"error": str(e)}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/jw-mcp/tests/test_mcp_study.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-mcp/src/jw_mcp/server.py packages/jw-mcp/tests/test_mcp_study.py
git commit -m "feat(jw-mcp): log_student_progress, list_student_lessons, set_student_goal tools"
```

---

### Task 17: Golden case L1 — `study_conductor_lff_ch1_es`

**Files:**
- Create: `packages/jw-eval/fixtures/golden_qa/l1/study_conductor_lff_ch1_es.yaml`

- [ ] **Step 1: Write the YAML**

```yaml
# packages/jw-eval/fixtures/golden_qa/l1/study_conductor_lff_ch1_es.yaml
id: l1_study_conductor_lff_ch1_es
agent: study_conductor
layer: l1
input:
  pub_code: lff
  chapter: 1
  language: es
expected:
  min_findings: 1
  must_have_source: jwpub_chapter
  must_have_citation: true
  forbidden_keywords_in_findings:
    - "supuestamente"
    - "tal vez"
    - "talvez"
metadata:
  topic: study_book.lff.ch1
  added_by: elias
  added_at: 2026-05-30
  note: |
    Si la suite corre sin JWPUB local, el agente devuelve source=wol_chapter.
    En ese caso este caso L1 puede ajustarse a `must_have_source: wol_chapter`
    en una rama de CI sin red.
```

- [ ] **Step 2: Verify the case loads cleanly**

Run:
```bash
uv run python -c "
from pathlib import Path
from jw_eval.loader import load_case_file
case = load_case_file(Path('packages/jw-eval/fixtures/golden_qa/l1/study_conductor_lff_ch1_es.yaml'))
print(case.id, case.agent, case.layer)
"
```
Expected: `l1_study_conductor_lff_ch1_es study_conductor l1`

- [ ] **Step 3: Commit**

```bash
git add packages/jw-eval/fixtures/golden_qa/l1/study_conductor_lff_ch1_es.yaml
git commit -m "test(jw-eval): add L1 golden case for study_conductor lff ch.1 (es)"
```

---

### Task 18: Golden case L3 — semantic check for the same lesson

**Files:**
- Create: `packages/jw-eval/fixtures/golden_qa/l3/study_conductor_lff_ch1_es.yaml`

- [ ] **Step 1: Write the YAML**

```yaml
# packages/jw-eval/fixtures/golden_qa/l3/study_conductor_lff_ch1_es.yaml
id: l3_study_conductor_lff_ch1_es
agent: study_conductor
layer: l3
input:
  pub_code: lff
  chapter: 1
  language: es
expected_citations:
  - https://wol.jw.org/es/wol/publication/r4/lp-s/lff/1
expected_keywords_any:
  - "Jehová"
  - "Padre amoroso"
  - "se preocupa"
expected_keywords_none:
  - "doctrina inalcanzable"
  - "pasajes oscuros"
golden_answer: |
  La lección 1 enseña que Jehová Dios es un Padre amoroso que se preocupa por
  cada uno de nosotros como personas. La invitación a "echar todas nuestras
  ansiedades sobre él" (1 Pedro 5:7) muestra que él está cerca y disponible, y
  que su carácter se revela en las Escrituras como un Dios accesible, no
  distante. La preparación personal del conductor debería resaltar (a) la
  identidad de Jehová como Padre, (b) la evidencia bíblica de su preocupación
  por cada persona, y (c) preguntas que ayuden al estudiante a anclar este
  punto en su propia experiencia.
judge:
  primary: embeddings
  threshold_pass: 0.78
  threshold_review_min: 0.55
  threshold_review_max: 0.78
metadata:
  topic: study_book.lff.ch1
  added_by: elias
  added_at: 2026-05-30
```

- [ ] **Step 2: Verify the case loads**

Run:
```bash
uv run python -c "
from pathlib import Path
from jw_eval.loader import load_case_file
case = load_case_file(Path('packages/jw-eval/fixtures/golden_qa/l3/study_conductor_lff_ch1_es.yaml'))
print(case.id, case.layer)
"
```
Expected: `l3_study_conductor_lff_ch1_es l3`

- [ ] **Step 3: Commit**

```bash
git add packages/jw-eval/fixtures/golden_qa/l3/study_conductor_lff_ch1_es.yaml
git commit -m "test(jw-eval): add L3 golden case for study_conductor lff ch.1 (es)"
```

---

### Task 19: Guide `docs/guias/conductor-de-estudio.md`

**Files:**
- Create: `docs/guias/conductor-de-estudio.md`

- [ ] **Step 1: Write the guide**

```markdown
# Guía — Conductor de estudio bíblico personal

> Fase 24. Acompaña la preparación de cada lección del libro de estudio
> actual («Disfruta de la vida para siempre», `lff`) y registra el ciclo
> de vida del estudiante: lecciones, metas y notas privadas cifradas.

## Qué hace

- `jw study lesson <pub> <ch> --lang es` — genera preguntas de anticipación
  por párrafo, lista versículos clave y temas del Índice Temático.
- `jw study log <student> <pub> <ch> [--status …] [--note …] [--goal …]`
  — registra progreso. La nota se cifra al guardar.
- `jw study progress <student>` — vista de ciclo de vida.
- `jw study lessons <pub>` — inventario del libro.
- `jw study goals` — taxonomía controlada de metas.
- `jw study directory set <alias> <nombre>` — alias→nombre opt-in.

## Qué NO hace

- No sustituye al conductor humano ni a los ancianos.
- No envía nada a la nube. Todo local, en `~/.jw-agent-toolkit/`.
- No mantiene un directorio de hermanos: `student_id` es un alias.
- No genera texto con LLM. Las preguntas vienen de plantillas
  determinísticas en `jw_core.data.study_prompts`.

## Privacidad

1. **Passphrase**: la primera vez se le pide. Si la pierde, los datos
   guardados **no son recuperables**. Por diseño.
2. **Salt persistente** en `~/.jw-agent-toolkit/study_progress.salt`.
3. **Cifrado**: Fernet con clave derivada por PBKDF2-HMAC-SHA256.
4. **Detector de crisis**: si una nota contiene palabras como
   «suicidio», «abuso», el CLI imprime una advertencia recomendando
   contactar a los ancianos o a un profesional. La nota igualmente se
   guarda — no bloquea.
5. **MCP**: las tools de progreso exigen `JW_STUDY_PASSPHRASE` en el
   entorno. Sin variable, devuelven `{"error": "..."}` y no tocan el
   disco.

## Flujo recomendado

```bash
# 1. Preparar la lección 1 (idioma español)
jw study lesson lff 1 --lang es

# 2. Registrar avance del estudiante "amelia2024"
export JW_STUDY_PASSPHRASE='...'  # solo en esta sesión
jw study log amelia2024 lff 1 --status completed \
    --note "Receptiva al tema del nombre de Dios" \
    --goal attend_meetings

# 3. Ver ciclo de vida
jw study progress amelia2024
```

## Configuración

| Variable | Default | Para qué |
|---|---|---|
| `JW_STUDY_DB`        | `~/.jw-agent-toolkit/study_progress.db`   | Ruta del SQLite. |
| `JW_STUDY_SALT`      | `~/.jw-agent-toolkit/study_progress.salt` | Salt persistente. |
| `JW_STUDY_PASSPHRASE`| (sin default)                              | Required para `log`. |
| `JW_STUDY_DIRECTORY` | `~/.jw-agent-toolkit/study_directory.json` | Alias→nombre opt-in. |

## Recuperación ante errores

- Passphrase olvidada → no hay recuperación. Borre `study_progress.db`
  y `study_progress.salt`, empiece de nuevo. (Considere ese trade-off
  antes de adoptar la herramienta.)
- JWPUB no registrado en `meps_catalog` → fallback automático a WOL.
- Cambio de pub de estudio (2027+): edite `study_books.REGISTRY`.
```

- [ ] **Step 2: Commit**

```bash
git add docs/guias/conductor-de-estudio.md
git commit -m "docs: guide for jw study (conductor-de-estudio.md, Fase 24)"
```

---

### Task 20: Update ROADMAP and VISION_AUDIT

**Files:**
- Modify: `docs/ROADMAP.md`
- Modify: `docs/VISION_AUDIT.md`

- [ ] **Step 1: Update ROADMAP**

Append to `docs/ROADMAP.md` (or insert in the right section):

```markdown
### Fase 24 — `study_conductor` + `StudentProgress` (Tier 2)

**Entregado**: agente procedural `study_conductor.prepare_lesson` (no LLM),
store local cifrable `StudentProgressStore`, comandos `jw study {lesson,
log, progress, lessons, goals, directory}`, 4 tools MCP, golden cases L1+L3
en `jw-eval`, guía `docs/guias/conductor-de-estudio.md`.

**Cubre**: VISION.md item #1 («Conductor de Disfruta de la vida para
siempre»).

**No cubre** (post-fase): recordatorios temporales (Fase 25-adjacent),
gráficas (export JSON ya lo habilita externamente), modo familia.
```

- [ ] **Step 2: Update VISION_AUDIT**

Append a row in `docs/VISION_AUDIT.md`:

```markdown
| Fase 24 | VISION #1 | `study_conductor` + `StudentProgress` | ✅ |
```

- [ ] **Step 3: Run full test suite to ensure no regressions**

Run: `uv run pytest packages/jw-core packages/jw-agents packages/jw-cli packages/jw-mcp packages/jw-eval -q`
Expected: all previously-green tests still green; new tests included.

- [ ] **Step 4: Commit**

```bash
git add docs/ROADMAP.md docs/VISION_AUDIT.md
git commit -m "docs: ROADMAP + VISION_AUDIT entries for Fase 24"
```

---

## Self-review

Before opening the PR, run the checklist:

- [ ] All 20 tasks committed with passing tests at each step.
- [ ] `pytest -q` green across the whole workspace.
- [ ] `uv run jw study --help` exits 0 and shows every subcommand.
- [ ] `uv run jw study lesson lff 1 --lang es` shows preparation output
  with citation URL.
- [ ] `JW_STUDY_PASSPHRASE=demo uv run jw study log demo_user lff 1
  --status in_progress --note "test"` round-trips through the encrypted
  store.
- [ ] `JW_STUDY_PASSPHRASE=demo uv run jw study progress demo_user`
  shows the seeded row.
- [ ] First-run consent flow is bounded: on a fresh box (no salt
  file), the CLI prints the disclosure and aborts unless the user
  confirms.
- [ ] Crisis warning prints when a note contains a keyword from any of
  es/en/pt.
- [ ] Eval golden cases load: `uv run jw eval --layer 1 --filter
  agent=study_conductor` finds and runs them.
- [ ] Guide reachable from `docs/README.md` (link added if not already).
- [ ] No regressions in the 551+ pre-Fase-24 tests.
- [ ] No new networking in import-time code paths.
- [ ] No telemetry or sync added to `study_progress.db`.

## Execution choice

Two ways to execute this plan:

1. **Sequential** (recommended for the first pass): work tasks 1→20 in
   order on the `feature/fase-24-study-conductor` branch. Each task is
   a self-contained commit. Total estimated time: **7-10 days**.

2. **Parallel sub-agents** (faster but riskier): the dependency graph
   allows three tracks once Task 4 (models) is done:
     - Track A: Tasks 5-7 (store + crisis + goals).
     - Track B: Tasks 8 (agent) + 17-18 (eval cases).
     - Track C: Tasks 10-14 (CLI surface).
   - Reunify with Tasks 15-16 (MCP) which depend on A.
   - Final Tasks 19-20 (docs) come last.
   Use `superpowers:subagent-driven-development` to dispatch the tracks
   on separate worktrees. Estimated time: **4-6 days** at the cost of
   merge friction.

Pick **Sequential** unless the team is already comfortable with the
parallel-worktrees workflow.
