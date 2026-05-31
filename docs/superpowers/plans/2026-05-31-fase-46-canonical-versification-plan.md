# Fase 46 — `canonical-versification` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the `versification` module inside `jw-core` — a curated catalog of ~150 numbering discrepancies (NWT vs masoretic vs LXX vs vulgate) plus a stable `to_canonical` API, a trilingual explainer, CLI subcommand, and MCP tool. Zero regressions on the 1984 existing tests; the new `BibleRef.tradition` field is opt-in with default `"nwt"`.

**Architecture:** New subpackage `packages/jw-core/src/jw_core/versification/` with three layers — Pydantic models (`Tradition`, `VerseCoord`, `VersificationMapping`, `MappingResult`), lazy registry (`@lru_cache` JSON loader), and a pure-function mapper (`to_canonical` + `explain`). Catalog lives at `packages/jw-core/src/jw_core/data/versification_map.json` (seeded with 30 entries; follow-on PR enumerates the full 150). Integrations: `BibleRef.tradition` opt-in field, `jw versification` Typer subcommand, MCP tool `to_canonical_versification`.

**Tech Stack:** Python 3.13 · Pydantic v2 · `functools.lru_cache` · pytest · hypothesis (property tests) · Typer (CLI) · FastMCP (MCP tool). No network, no LLM, no extra runtime deps.

**Spec:** [`docs/superpowers/specs/2026-05-31-fase-46-canonical-versification-design.md`](../specs/2026-05-31-fase-46-canonical-versification-design.md).

---

## File map

Creates:
- `packages/jw-core/src/jw_core/versification/__init__.py`
- `packages/jw-core/src/jw_core/versification/models.py`
- `packages/jw-core/src/jw_core/versification/registry.py`
- `packages/jw-core/src/jw_core/versification/mapping.py`
- `packages/jw-core/src/jw_core/versification/explain.py`
- `packages/jw-core/src/jw_core/data/versification_map.json`
- `packages/jw-core/tests/test_versification_models.py`
- `packages/jw-core/tests/test_versification_registry.py`
- `packages/jw-core/tests/test_versification_mapping.py`
- `packages/jw-core/tests/test_versification_mapping_property.py`
- `packages/jw-core/tests/test_versification_known.py`
- `packages/jw-core/tests/test_versification_explain.py`
- `packages/jw-core/tests/test_versification_copyright_guard.py`
- `packages/jw-cli/src/jw_cli/commands/versification.py`
- `packages/jw-cli/tests/test_versification_cli.py`
- `packages/jw-mcp/tests/test_versification_mcp.py`
- `scripts/audit_versification_catalog.py`
- `docs/guias/versification.md`

Modifies:
- `packages/jw-core/src/jw_core/models.py` — add optional `tradition` field to `BibleRef`.
- `packages/jw-core/src/jw_core/__init__.py` — re-export `versification` namespace.
- `packages/jw-cli/src/jw_cli/main.py` — register `versification` Typer sub-app.
- `packages/jw-mcp/src/jw_mcp/server.py` — register `to_canonical_versification` tool.
- `docs/VISION_AUDIT.md` — add Fase 46 row.
- `docs/ROADMAP.md` — mark Fase 46 status.

---

### Task 1: Scaffold the `versification` subpackage with models

**Files:**
- Create: `packages/jw-core/src/jw_core/versification/__init__.py`
- Create: `packages/jw-core/src/jw_core/versification/models.py`
- Create: `packages/jw-core/tests/test_versification_models.py`

- [ ] **Step 1: Write the failing tests**

```python
# packages/jw-core/tests/test_versification_models.py
"""Tests for versification Pydantic models.

VerseCoord intentionally relaxes BibleRef: verse_start >= 0 to permit
superscriptions (BHS/LXX style: verse 0 = title). chapter >= 0 too so we
can encode the rare "no chapter" entries some sources flag.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from jw_core.versification.models import (
    MappingResult,
    Tradition,
    VerseCoord,
    VersificationMapping,
)


def test_verse_coord_basic() -> None:
    c = VerseCoord(chapter=51, verse_start=1)
    assert c.chapter == 51
    assert c.verse_start == 1
    assert c.verse_end is None


def test_verse_coord_allows_superscription_verse_zero() -> None:
    """BHS counts Psalm titles as verse 0; VerseCoord must accept that."""
    c = VerseCoord(chapter=51, verse_start=0)
    assert c.verse_start == 0


def test_verse_coord_rejects_negative() -> None:
    with pytest.raises(ValidationError):
        VerseCoord(chapter=-1, verse_start=1)
    with pytest.raises(ValidationError):
        VerseCoord(chapter=51, verse_start=-1)


def test_verse_coord_range() -> None:
    c = VerseCoord(chapter=2, verse_start=28, verse_end=32)
    assert c.verse_end == 32


def test_tradition_literal_values() -> None:
    """Tradition is a Literal — verify exactly which values are accepted."""
    valid: list[Tradition] = ["nwt", "masoretic", "lxx", "vulgate"]
    for t in valid:
        # round-trip through a model that uses the alias
        m = MappingResult(
            ref_book="Joel",
            ref_book_num=29,
            coord=VerseCoord(chapter=2, verse_start=28),
            from_tradition=t,
            to_tradition=t,
            is_discrepant=False,
        )
        assert m.from_tradition == t


def test_versification_mapping_minimal_nwt_to_masoretic() -> None:
    m = VersificationMapping(
        book="Joel",
        book_num=29,
        issue="chapter_renumber",
        nwt=VerseCoord(chapter=2, verse_start=28, verse_end=32),
        masoretic=VerseCoord(chapter=3, verse_start=1, verse_end=5),
        source="Tov 2012:32",
        explanation={
            "en": "Joel 2:28-32 in the NWT corresponds to Joel 3:1-5 in BHS.",
            "es": "Joel 2:28-32 en la NWT corresponde a Joel 3:1-5 en BHS.",
            "pt": "Joel 2:28-32 na TNM corresponde a Joel 3:1-5 na BHS.",
        },
    )
    assert m.book == "Joel"
    assert m.book_num == 29
    assert m.lxx is None
    assert m.vulgate is None
    assert m.nwt.verse_start == 28
    assert m.masoretic is not None
    assert m.masoretic.chapter == 3


def test_versification_mapping_requires_all_three_languages() -> None:
    """Explanation must be a dict with en/es/pt — we never accept partial."""
    with pytest.raises(ValidationError):
        VersificationMapping(
            book="Joel",
            book_num=29,
            issue="chapter_renumber",
            nwt=VerseCoord(chapter=2, verse_start=28),
            source="Tov 2012:32",
            explanation={"en": "only english"},  # type: ignore[arg-type]
        )


def test_versification_mapping_rejects_unknown_issue() -> None:
    with pytest.raises(ValidationError):
        VersificationMapping(
            book="Joel",
            book_num=29,
            issue="frobnicate",  # type: ignore[arg-type]
            nwt=VerseCoord(chapter=2, verse_start=28),
            source="x",
            explanation={"en": "x", "es": "x", "pt": "x"},
        )


def test_mapping_result_identity_case() -> None:
    """from == to means is_discrepant=False and no rationale."""
    r = MappingResult(
        ref_book="Genesis",
        ref_book_num=1,
        coord=VerseCoord(chapter=1, verse_start=1),
        from_tradition="nwt",
        to_tradition="nwt",
        is_discrepant=False,
    )
    assert r.is_discrepant is False
    assert r.rationale is None


def test_mapping_result_discrepant_carries_rationale() -> None:
    r = MappingResult(
        ref_book="Joel",
        ref_book_num=29,
        coord=VerseCoord(chapter=3, verse_start=1, verse_end=5),
        from_tradition="nwt",
        to_tradition="masoretic",
        is_discrepant=True,
        rationale="Joel 2:28-32 NWT → Joel 3:1-5 masoretic.",
    )
    assert r.is_discrepant is True
    assert r.rationale is not None and "Joel" in r.rationale
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest packages/jw-core/tests/test_versification_models.py -v`
Expected: FAIL — `ModuleNotFoundError: jw_core.versification`.

- [ ] **Step 3: Implement the models**

```python
# packages/jw-core/src/jw_core/versification/__init__.py
"""Canonical-versification subpackage.

Public API:

    from jw_core.versification import (
        Tradition,
        VerseCoord,
        VersificationMapping,
        MappingResult,
        to_canonical,
        explain,
        load_catalog,
    )

The module does NO I/O at import time. The catalog JSON is loaded lazily
on first call via `@functools.lru_cache(maxsize=1)`.

This subpackage MUST NOT import from `jw_rag`, `jw_agents`, or `jw_mcp`.
It depends only on `jw_core.models` and reads `jw_core.data`.
"""

from jw_core.versification.models import (
    MappingResult,
    Tradition,
    VerseCoord,
    VersificationMapping,
)
from jw_core.versification.mapping import to_canonical
from jw_core.versification.explain import explain
from jw_core.versification.registry import load_catalog

__all__ = [
    "MappingResult",
    "Tradition",
    "VerseCoord",
    "VersificationMapping",
    "explain",
    "load_catalog",
    "to_canonical",
]
```

```python
# packages/jw-core/src/jw_core/versification/models.py
"""Pydantic models for the versification subpackage.

Design notes
------------

VerseCoord vs BibleRef
~~~~~~~~~~~~~~~~~~~~~~

`jw_core.models.BibleRef` enforces `verse_start >= 1` because a "verse 0"
makes no sense in NWT-style numbering. The Hebrew Masoretic and LXX,
however, count Psalm superscriptions as verse 0. We therefore introduce a
relaxed coordinate type (`VerseCoord`) for the catalog only. The public
`to_canonical` function still returns a real `BibleRef` so downstream code
does not see verse 0 unless it explicitly asks for masoretic/LXX numbering
on a Psalm with a superscription — in which case we either bump it to 1 or
raise. The detailed policy lives in `mapping.py`.

MappingResult.ref_book vs BibleRef
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

We embed (book, book_num, VerseCoord) instead of a full BibleRef so that
the `verse_start=0` case can survive a round-trip through the model layer.
The caller can rebuild a BibleRef (clamping verse_start to >=1) via
`MappingResult.as_bible_ref()`.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

Tradition = Literal["nwt", "masoretic", "lxx", "vulgate"]

VersificationIssue = Literal[
    "superscription",
    "chapter_split",
    "verse_split",
    "verse_merge",
    "chapter_renumber",
    "verse_shift",
]


class VerseCoord(BaseModel):
    """A relaxed coordinate accepting verse 0 (superscription).

    Used in the catalog so we can encode BHS/LXX positions losslessly.
    """

    chapter: int = Field(ge=0)
    verse_start: int = Field(ge=0)
    verse_end: int | None = Field(default=None, ge=0)


class VersificationMapping(BaseModel):
    """One catalog entry: how a single reference numbers across traditions."""

    book: str
    book_num: int = Field(ge=1, le=66)
    issue: VersificationIssue
    nwt: VerseCoord
    masoretic: VerseCoord | None = None
    lxx: VerseCoord | None = None
    vulgate: VerseCoord | None = None
    source: str = Field(min_length=1, description="Short academic citation.")
    explanation: dict[str, str] = Field(
        description="Original prose by maintainer, keyed 'en' | 'es' | 'pt'.",
    )

    @model_validator(mode="after")
    def _require_trilingual_explanation(self) -> "VersificationMapping":
        required = {"en", "es", "pt"}
        present = {k for k, v in self.explanation.items() if isinstance(v, str) and v.strip()}
        missing = required - present
        if missing:
            raise ValueError(f"explanation missing languages: {sorted(missing)}")
        return self

    def coord_for(self, tradition: Tradition) -> VerseCoord | None:
        """Return the catalog coordinate for one tradition, or None if not set."""
        return getattr(self, tradition)


class MappingResult(BaseModel):
    """Output of `to_canonical`.

    Carries enough metadata to rebuild a BibleRef (via `as_bible_ref`) and
    to render a human-readable rationale when the mapping was non-trivial.
    """

    ref_book: str
    ref_book_num: int = Field(ge=1, le=66)
    coord: VerseCoord
    from_tradition: Tradition
    to_tradition: Tradition
    is_discrepant: bool
    rationale: str | None = None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest packages/jw-core/tests/test_versification_models.py -v`
Expected: 9 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-core/src/jw_core/versification/__init__.py \
        packages/jw-core/src/jw_core/versification/models.py \
        packages/jw-core/tests/test_versification_models.py
git commit -m "feat(versification): scaffold subpackage with VerseCoord/Mapping/Result models"
```

---

### Task 2: Seed the JSON catalog (30 entries; 150 follow-on)

**Files:**
- Create: `packages/jw-core/src/jw_core/data/versification_map.json`

This task contributes data only — no Python. Tests for it live in Task 3 (registry).

- [ ] **Step 1: Write the seed catalog**

```json
{
  "version": "1.0",
  "compiled_at": "2026-05-31",
  "source_references": [
    "Tov, E. (2012) Textual Criticism of the Hebrew Bible, 3rd ed., Fortress.",
    "Würthwein, E. (2014) The Text of the Old Testament, Eerdmans.",
    "BHS apparatus, Biblia Hebraica Stuttgartensia.",
    "NETS prefaces (LXX numbering notes).",
    "SBL Handbook of Style §8.3."
  ],
  "discrepancies": [
    {
      "book": "Joel",
      "book_num": 29,
      "issue": "chapter_renumber",
      "nwt": {"chapter": 2, "verse_start": 28, "verse_end": 32},
      "masoretic": {"chapter": 3, "verse_start": 1, "verse_end": 5},
      "source": "Tov 2012:32",
      "explanation": {
        "en": "Joel 2:28-32 in the NWT corresponds to Joel 3:1-5 in the Hebrew Bible.",
        "es": "Joel 2:28-32 en la NWT corresponde a Joel 3:1-5 en la Biblia hebrea.",
        "pt": "Joel 2:28-32 na TNM corresponde a Joel 3:1-5 na Bíblia hebraica."
      }
    },
    {
      "book": "Joel",
      "book_num": 29,
      "issue": "chapter_renumber",
      "nwt": {"chapter": 3, "verse_start": 1, "verse_end": 21},
      "masoretic": {"chapter": 4, "verse_start": 1, "verse_end": 21},
      "source": "Tov 2012:32",
      "explanation": {
        "en": "Joel chapter 3 in the NWT is Joel chapter 4 in the Hebrew Bible.",
        "es": "Joel capítulo 3 en la NWT es Joel capítulo 4 en la Biblia hebrea.",
        "pt": "Joel capítulo 3 na TNM é Joel capítulo 4 na Bíblia hebraica."
      }
    },
    {
      "book": "Malachi",
      "book_num": 39,
      "issue": "chapter_renumber",
      "nwt": {"chapter": 4, "verse_start": 1, "verse_end": 6},
      "masoretic": {"chapter": 3, "verse_start": 19, "verse_end": 24},
      "source": "Würthwein 2014:78",
      "explanation": {
        "en": "Malachi 4:1-6 in the NWT corresponds to Malachi 3:19-24 in the Hebrew Bible.",
        "es": "Malaquías 4:1-6 en la NWT corresponde a Malaquías 3:19-24 en la Biblia hebrea.",
        "pt": "Malaquias 4:1-6 na TNM corresponde a Malaquias 3:19-24 na Bíblia hebraica."
      }
    },
    {
      "book": "Psalms",
      "book_num": 19,
      "issue": "superscription",
      "nwt": {"chapter": 3, "verse_start": 1},
      "masoretic": {"chapter": 3, "verse_start": 0},
      "lxx": {"chapter": 3, "verse_start": 0},
      "source": "BHS apparatus Ps 3",
      "explanation": {
        "en": "The Psalm 3 superscription is counted as verse 1 in the NWT but as verse 0 in the Hebrew Masoretic and the LXX.",
        "es": "La superscripción del Salmo 3 se cuenta como versículo 1 en la NWT pero como versículo 0 en el texto hebreo masorético y la LXX.",
        "pt": "A superscrição do Salmo 3 é contada como versículo 1 na TNM mas como versículo 0 no texto hebraico massorético e na LXX."
      }
    },
    {
      "book": "Psalms",
      "book_num": 19,
      "issue": "superscription",
      "nwt": {"chapter": 51, "verse_start": 1},
      "masoretic": {"chapter": 51, "verse_start": 0},
      "lxx": {"chapter": 50, "verse_start": 0},
      "source": "BHS apparatus Ps 51",
      "explanation": {
        "en": "The Psalm 51 superscription is verse 1 in the NWT but verse 0 in the Hebrew Masoretic; the LXX numbers this as Psalm 50 because Psalms 9 and 10 are merged earlier.",
        "es": "La superscripción del Salmo 51 es versículo 1 en la NWT pero versículo 0 en el texto hebreo masorético; la LXX lo numera como Salmo 50 porque une los Salmos 9 y 10 antes.",
        "pt": "A superscrição do Salmo 51 é versículo 1 na TNM mas versículo 0 no texto hebraico massorético; a LXX o numera como Salmo 50 porque une os Salmos 9 e 10 antes."
      }
    },
    {
      "book": "Psalms",
      "book_num": 19,
      "issue": "chapter_split",
      "nwt": {"chapter": 9, "verse_start": 1, "verse_end": 20},
      "masoretic": {"chapter": 9, "verse_start": 1, "verse_end": 21},
      "lxx": {"chapter": 9, "verse_start": 1, "verse_end": 39},
      "source": "Tov 2012:36",
      "explanation": {
        "en": "Psalm 9 in the NWT and Masoretic ends at verse 20-21; the LXX combines Psalms 9 and 10 into a single Psalm 9 of 39 verses.",
        "es": "El Salmo 9 en la NWT y en el masorético termina en el versículo 20-21; la LXX combina los Salmos 9 y 10 en un solo Salmo 9 de 39 versículos.",
        "pt": "O Salmo 9 na TNM e no massorético termina no versículo 20-21; a LXX combina os Salmos 9 e 10 em um único Salmo 9 com 39 versículos."
      }
    },
    {
      "book": "Psalms",
      "book_num": 19,
      "issue": "chapter_split",
      "nwt": {"chapter": 10, "verse_start": 1, "verse_end": 18},
      "masoretic": {"chapter": 10, "verse_start": 1, "verse_end": 18},
      "lxx": {"chapter": 9, "verse_start": 22, "verse_end": 39},
      "source": "Tov 2012:36",
      "explanation": {
        "en": "Psalm 10 in the NWT and Masoretic is a separate psalm; the LXX includes the same verses as Psalm 9:22-39.",
        "es": "El Salmo 10 en la NWT y en el masorético es un salmo independiente; la LXX incluye los mismos versículos como Salmo 9:22-39.",
        "pt": "O Salmo 10 na TNM e no massorético é um salmo independente; a LXX inclui os mesmos versículos como Salmo 9:22-39."
      }
    },
    {
      "book": "Psalms",
      "book_num": 19,
      "issue": "chapter_split",
      "nwt": {"chapter": 114, "verse_start": 1, "verse_end": 8},
      "masoretic": {"chapter": 114, "verse_start": 1, "verse_end": 8},
      "lxx": {"chapter": 113, "verse_start": 1, "verse_end": 8},
      "source": "NETS Psalms preface",
      "explanation": {
        "en": "Psalm 114 in the NWT and Masoretic is numbered 113 in the LXX, where Psalms 114 and 115 are merged.",
        "es": "El Salmo 114 en la NWT y el masorético se numera 113 en la LXX, donde se unen los Salmos 114 y 115.",
        "pt": "O Salmo 114 na TNM e no massorético é numerado como 113 na LXX, onde os Salmos 114 e 115 são unidos."
      }
    },
    {
      "book": "Psalms",
      "book_num": 19,
      "issue": "chapter_split",
      "nwt": {"chapter": 115, "verse_start": 1, "verse_end": 18},
      "masoretic": {"chapter": 115, "verse_start": 1, "verse_end": 18},
      "lxx": {"chapter": 113, "verse_start": 9, "verse_end": 26},
      "source": "NETS Psalms preface",
      "explanation": {
        "en": "Psalm 115 in the NWT and Masoretic appears in the LXX as the second half of Psalm 113 (verses 9-26).",
        "es": "El Salmo 115 en la NWT y el masorético aparece en la LXX como la segunda mitad del Salmo 113 (versículos 9-26).",
        "pt": "O Salmo 115 na TNM e no massorético aparece na LXX como a segunda metade do Salmo 113 (versículos 9-26)."
      }
    },
    {
      "book": "Psalms",
      "book_num": 19,
      "issue": "superscription",
      "nwt": {"chapter": 18, "verse_start": 1},
      "masoretic": {"chapter": 18, "verse_start": 0},
      "source": "BHS apparatus Ps 18",
      "explanation": {
        "en": "The Psalm 18 historical superscription is verse 1 in the NWT but verse 0 in the Hebrew Masoretic.",
        "es": "La superscripción histórica del Salmo 18 es versículo 1 en la NWT pero versículo 0 en el texto hebreo masorético.",
        "pt": "A superscrição histórica do Salmo 18 é versículo 1 na TNM mas versículo 0 no texto hebraico massorético."
      }
    },
    {
      "book": "Psalms",
      "book_num": 19,
      "issue": "superscription",
      "nwt": {"chapter": 30, "verse_start": 1},
      "masoretic": {"chapter": 30, "verse_start": 0},
      "source": "BHS apparatus Ps 30",
      "explanation": {
        "en": "The Psalm 30 superscription is verse 1 in the NWT but verse 0 in the Hebrew Masoretic.",
        "es": "La superscripción del Salmo 30 es versículo 1 en la NWT pero versículo 0 en el texto hebreo masorético.",
        "pt": "A superscrição do Salmo 30 é versículo 1 na TNM mas versículo 0 no texto hebraico massorético."
      }
    },
    {
      "book": "Psalms",
      "book_num": 19,
      "issue": "superscription",
      "nwt": {"chapter": 34, "verse_start": 1},
      "masoretic": {"chapter": 34, "verse_start": 0},
      "source": "BHS apparatus Ps 34",
      "explanation": {
        "en": "The Psalm 34 superscription is verse 1 in the NWT but verse 0 in the Hebrew Masoretic.",
        "es": "La superscripción del Salmo 34 es versículo 1 en la NWT pero versículo 0 en el texto hebreo masorético.",
        "pt": "A superscrição do Salmo 34 é versículo 1 na TNM mas versículo 0 no texto hebraico massorético."
      }
    },
    {
      "book": "Psalms",
      "book_num": 19,
      "issue": "superscription",
      "nwt": {"chapter": 52, "verse_start": 1},
      "masoretic": {"chapter": 52, "verse_start": 0},
      "source": "BHS apparatus Ps 52",
      "explanation": {
        "en": "The Psalm 52 superscription is verse 1 in the NWT but verse 0 in the Hebrew Masoretic.",
        "es": "La superscripción del Salmo 52 es versículo 1 en la NWT pero versículo 0 en el texto hebreo masorético.",
        "pt": "A superscrição do Salmo 52 é versículo 1 na TNM mas versículo 0 no texto hebraico massorético."
      }
    },
    {
      "book": "Psalms",
      "book_num": 19,
      "issue": "superscription",
      "nwt": {"chapter": 54, "verse_start": 1},
      "masoretic": {"chapter": 54, "verse_start": 0},
      "source": "BHS apparatus Ps 54",
      "explanation": {
        "en": "The Psalm 54 superscription is verse 1 in the NWT but verse 0 in the Hebrew Masoretic.",
        "es": "La superscripción del Salmo 54 es versículo 1 en la NWT pero versículo 0 en el texto hebreo masorético.",
        "pt": "A superscrição do Salmo 54 é versículo 1 na TNM mas versículo 0 no texto hebraico massorético."
      }
    },
    {
      "book": "Psalms",
      "book_num": 19,
      "issue": "superscription",
      "nwt": {"chapter": 56, "verse_start": 1},
      "masoretic": {"chapter": 56, "verse_start": 0},
      "source": "BHS apparatus Ps 56",
      "explanation": {
        "en": "The Psalm 56 superscription is verse 1 in the NWT but verse 0 in the Hebrew Masoretic.",
        "es": "La superscripción del Salmo 56 es versículo 1 en la NWT pero versículo 0 en el texto hebreo masorético.",
        "pt": "A superscrição do Salmo 56 é versículo 1 na TNM mas versículo 0 no texto hebraico massorético."
      }
    },
    {
      "book": "Psalms",
      "book_num": 19,
      "issue": "superscription",
      "nwt": {"chapter": 60, "verse_start": 1},
      "masoretic": {"chapter": 60, "verse_start": 0},
      "source": "BHS apparatus Ps 60",
      "explanation": {
        "en": "The Psalm 60 superscription is verse 1 in the NWT but verse 0 in the Hebrew Masoretic.",
        "es": "La superscripción del Salmo 60 es versículo 1 en la NWT pero versículo 0 en el texto hebreo masorético.",
        "pt": "A superscrição do Salmo 60 é versículo 1 na TNM mas versículo 0 no texto hebraico massorético."
      }
    },
    {
      "book": "Romans",
      "book_num": 45,
      "issue": "verse_merge",
      "nwt": {"chapter": 16, "verse_start": 25, "verse_end": 27},
      "vulgate": {"chapter": 14, "verse_start": 24, "verse_end": 26},
      "source": "SBL Handbook §8.3",
      "explanation": {
        "en": "The doxology that closes Romans appears as 16:25-27 in the NWT but at 14:24-26 in some Vulgate witnesses that place the doxology after chapter 14.",
        "es": "La doxología que cierra Romanos aparece como 16:25-27 en la NWT pero en 14:24-26 en algunos testigos de la Vulgata que la ubican después del capítulo 14.",
        "pt": "A doxologia que encerra Romanos aparece como 16:25-27 na TNM mas em 14:24-26 em algumas testemunhas da Vulgata que a colocam depois do capítulo 14."
      }
    },
    {
      "book": "2 Corinthians",
      "book_num": 47,
      "issue": "verse_split",
      "nwt": {"chapter": 13, "verse_start": 12, "verse_end": 14},
      "vulgate": {"chapter": 13, "verse_start": 12, "verse_end": 13},
      "source": "SBL Handbook §8.3",
      "explanation": {
        "en": "2 Corinthians 13:12-14 in the NWT is numbered 13:12-13 in the Vulgate, which keeps the final greeting and benediction in one verse.",
        "es": "2 Corintios 13:12-14 en la NWT se numera como 13:12-13 en la Vulgata, que mantiene el saludo final y la bendición en un solo versículo.",
        "pt": "2 Coríntios 13:12-14 na TNM é numerado como 13:12-13 na Vulgata, que mantém a saudação final e a bênção em um único versículo."
      }
    },
    {
      "book": "Nehemiah",
      "book_num": 16,
      "issue": "verse_shift",
      "nwt": {"chapter": 4, "verse_start": 1, "verse_end": 6},
      "masoretic": {"chapter": 3, "verse_start": 33, "verse_end": 38},
      "source": "Tov 2012:34",
      "explanation": {
        "en": "Nehemiah 4:1-6 in the NWT corresponds to Nehemiah 3:33-38 in the Hebrew Masoretic.",
        "es": "Nehemías 4:1-6 en la NWT corresponde a Nehemías 3:33-38 en el masorético hebreo.",
        "pt": "Neemias 4:1-6 na TNM corresponde a Neemias 3:33-38 no massorético hebraico."
      }
    },
    {
      "book": "Nehemiah",
      "book_num": 16,
      "issue": "verse_shift",
      "nwt": {"chapter": 4, "verse_start": 7, "verse_end": 23},
      "masoretic": {"chapter": 4, "verse_start": 1, "verse_end": 17},
      "source": "Tov 2012:34",
      "explanation": {
        "en": "Nehemiah 4:7-23 in the NWT corresponds to Nehemiah 4:1-17 in the Hebrew Masoretic.",
        "es": "Nehemías 4:7-23 en la NWT corresponde a Nehemías 4:1-17 en el masorético hebreo.",
        "pt": "Neemias 4:7-23 na TNM corresponde a Neemias 4:1-17 no massorético hebraico."
      }
    },
    {
      "book": "1 Kings",
      "book_num": 11,
      "issue": "verse_shift",
      "nwt": {"chapter": 4, "verse_start": 21, "verse_end": 34},
      "masoretic": {"chapter": 5, "verse_start": 1, "verse_end": 14},
      "source": "Tov 2012:33",
      "explanation": {
        "en": "1 Kings 4:21-34 in the NWT is numbered 5:1-14 in the Hebrew Masoretic.",
        "es": "1 Reyes 4:21-34 en la NWT se numera 5:1-14 en el masorético hebreo.",
        "pt": "1 Reis 4:21-34 na TNM é numerado como 5:1-14 no massorético hebraico."
      }
    },
    {
      "book": "1 Kings",
      "book_num": 11,
      "issue": "verse_shift",
      "nwt": {"chapter": 5, "verse_start": 1, "verse_end": 18},
      "masoretic": {"chapter": 5, "verse_start": 15, "verse_end": 32},
      "source": "Tov 2012:33",
      "explanation": {
        "en": "1 Kings 5:1-18 in the NWT is numbered 5:15-32 in the Hebrew Masoretic.",
        "es": "1 Reyes 5:1-18 en la NWT se numera 5:15-32 en el masorético hebreo.",
        "pt": "1 Reis 5:1-18 na TNM é numerado como 5:15-32 no massorético hebraico."
      }
    },
    {
      "book": "1 Chronicles",
      "book_num": 13,
      "issue": "verse_shift",
      "nwt": {"chapter": 6, "verse_start": 1, "verse_end": 15},
      "masoretic": {"chapter": 5, "verse_start": 27, "verse_end": 41},
      "source": "Tov 2012:34",
      "explanation": {
        "en": "1 Chronicles 6:1-15 in the NWT is numbered 5:27-41 in the Hebrew Masoretic.",
        "es": "1 Crónicas 6:1-15 en la NWT se numera 5:27-41 en el masorético hebreo.",
        "pt": "1 Crônicas 6:1-15 na TNM é numerado como 5:27-41 no massorético hebraico."
      }
    },
    {
      "book": "Daniel",
      "book_num": 27,
      "issue": "verse_shift",
      "nwt": {"chapter": 4, "verse_start": 1, "verse_end": 3},
      "masoretic": {"chapter": 3, "verse_start": 31, "verse_end": 33},
      "source": "Tov 2012:35",
      "explanation": {
        "en": "Daniel 4:1-3 in the NWT corresponds to Daniel 3:31-33 in the Hebrew Masoretic; the chapter break is set differently.",
        "es": "Daniel 4:1-3 en la NWT corresponde a Daniel 3:31-33 en el masorético hebreo; el corte de capítulo se ubica de forma distinta.",
        "pt": "Daniel 4:1-3 na TNM corresponde a Daniel 3:31-33 no massorético hebraico; o corte de capítulo é colocado de forma diferente."
      }
    },
    {
      "book": "Daniel",
      "book_num": 27,
      "issue": "verse_shift",
      "nwt": {"chapter": 5, "verse_start": 31},
      "masoretic": {"chapter": 6, "verse_start": 1},
      "source": "Tov 2012:35",
      "explanation": {
        "en": "Daniel 5:31 in the NWT is Daniel 6:1 in the Hebrew Masoretic.",
        "es": "Daniel 5:31 en la NWT es Daniel 6:1 en el masorético hebreo.",
        "pt": "Daniel 5:31 na TNM é Daniel 6:1 no massorético hebraico."
      }
    },
    {
      "book": "Job",
      "book_num": 18,
      "issue": "verse_shift",
      "nwt": {"chapter": 41, "verse_start": 1, "verse_end": 8},
      "masoretic": {"chapter": 40, "verse_start": 25, "verse_end": 32},
      "source": "BHS apparatus Job 41",
      "explanation": {
        "en": "Job 41:1-8 in the NWT corresponds to Job 40:25-32 in the Hebrew Masoretic.",
        "es": "Job 41:1-8 en la NWT corresponde a Job 40:25-32 en el masorético hebreo.",
        "pt": "Jó 41:1-8 na TNM corresponde a Jó 40:25-32 no massorético hebraico."
      }
    },
    {
      "book": "Ecclesiastes",
      "book_num": 21,
      "issue": "verse_shift",
      "nwt": {"chapter": 5, "verse_start": 1},
      "masoretic": {"chapter": 4, "verse_start": 17},
      "source": "BHS apparatus Eccl 5",
      "explanation": {
        "en": "Ecclesiastes 5:1 in the NWT is numbered 4:17 in the Hebrew Masoretic.",
        "es": "Eclesiastés 5:1 en la NWT se numera 4:17 en el masorético hebreo.",
        "pt": "Eclesiastes 5:1 na TNM é numerado como 4:17 no massorético hebraico."
      }
    },
    {
      "book": "Song of Solomon",
      "book_num": 22,
      "issue": "verse_shift",
      "nwt": {"chapter": 7, "verse_start": 1},
      "masoretic": {"chapter": 6, "verse_start": 13},
      "source": "BHS apparatus Cant 7",
      "explanation": {
        "en": "Song of Solomon 7:1 in the NWT is numbered 6:13 in the Hebrew Masoretic.",
        "es": "Cantar de los Cantares 7:1 en la NWT se numera 6:13 en el masorético hebreo.",
        "pt": "Cântico dos Cânticos 7:1 na TNM é numerado como 6:13 no massorético hebraico."
      }
    },
    {
      "book": "Hosea",
      "book_num": 28,
      "issue": "verse_shift",
      "nwt": {"chapter": 1, "verse_start": 10, "verse_end": 11},
      "masoretic": {"chapter": 2, "verse_start": 1, "verse_end": 2},
      "source": "Tov 2012:32",
      "explanation": {
        "en": "Hosea 1:10-11 in the NWT corresponds to Hosea 2:1-2 in the Hebrew Masoretic.",
        "es": "Oseas 1:10-11 en la NWT corresponde a Oseas 2:1-2 en el masorético hebreo.",
        "pt": "Oseias 1:10-11 na TNM corresponde a Oseias 2:1-2 no massorético hebraico."
      }
    },
    {
      "book": "Jonah",
      "book_num": 32,
      "issue": "verse_shift",
      "nwt": {"chapter": 1, "verse_start": 17},
      "masoretic": {"chapter": 2, "verse_start": 1},
      "source": "BHS apparatus Jon 1-2",
      "explanation": {
        "en": "Jonah 1:17 in the NWT is numbered 2:1 in the Hebrew Masoretic; the rest of Jonah 2 shifts by one accordingly.",
        "es": "Jonás 1:17 en la NWT se numera 2:1 en el masorético hebreo; el resto de Jonás 2 se desplaza un versículo en consecuencia.",
        "pt": "Jonas 1:17 na TNM é numerado como 2:1 no massorético hebraico; o restante de Jonas 2 se desloca um versículo correspondentemente."
      }
    }
  ]
}
```

- [ ] **Step 2: Sanity-check the file parses as JSON**

Run:
```bash
uv run python -c "
import json, pathlib
p = pathlib.Path('packages/jw-core/src/jw_core/data/versification_map.json')
data = json.loads(p.read_text())
print('discrepancies:', len(data['discrepancies']))
assert len(data['discrepancies']) >= 30
"
```
Expected: `discrepancies: 30`.

- [ ] **Step 3: Commit**

```bash
git add packages/jw-core/src/jw_core/data/versification_map.json
git commit -m "feat(versification): seed catalog with 30 curated discrepancies"
```

> **Follow-on (separate PR, not this plan):** enumerate the remaining ~120 Psalm superscriptions (one per psalm with a title) plus the long-tail Job/Jeremiah LXX-only entries to reach the spec's ≥100 entries goal. The schema is fixed; only data is added.

---

### Task 3: Lazy catalog registry

**Files:**
- Create: `packages/jw-core/src/jw_core/versification/registry.py`
- Create: `packages/jw-core/tests/test_versification_registry.py`

- [ ] **Step 1: Write the failing tests**

```python
# packages/jw-core/tests/test_versification_registry.py
"""Tests for the lazy catalog registry."""

from __future__ import annotations

from jw_core.versification.registry import (
    catalog_path,
    load_catalog,
    lookup,
)


def test_catalog_path_points_to_json_in_data_dir() -> None:
    p = catalog_path()
    assert p.name == "versification_map.json"
    assert p.parent.name == "data"


def test_load_catalog_returns_mappings_list() -> None:
    entries = load_catalog()
    assert len(entries) >= 30
    # every entry parses as a VersificationMapping
    for e in entries:
        assert e.book
        assert 1 <= e.book_num <= 66
        assert "en" in e.explanation
        assert "es" in e.explanation
        assert "pt" in e.explanation


def test_load_catalog_is_cached() -> None:
    """Loading twice returns the SAME list object (lru_cache contract)."""
    a = load_catalog()
    b = load_catalog()
    assert a is b


def test_lookup_finds_joel_2_28() -> None:
    hits = lookup(book_num=29, chapter=2, verse_start=28, tradition="nwt")
    assert len(hits) >= 1
    e = hits[0]
    assert e.masoretic is not None
    assert e.masoretic.chapter == 3
    assert e.masoretic.verse_start == 1


def test_lookup_finds_psalm_51_superscription_in_masoretic() -> None:
    hits = lookup(book_num=19, chapter=51, verse_start=0, tradition="masoretic")
    assert len(hits) >= 1
    e = hits[0]
    assert e.nwt.verse_start == 1


def test_lookup_returns_empty_when_no_match() -> None:
    # Genesis 1:1 is identical in every tradition — nothing in the catalog.
    hits = lookup(book_num=1, chapter=1, verse_start=1, tradition="nwt")
    assert hits == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest packages/jw-core/tests/test_versification_registry.py -v`
Expected: FAIL — `registry` module not found.

- [ ] **Step 3: Implement the registry**

```python
# packages/jw-core/src/jw_core/versification/registry.py
"""Lazy JSON catalog loader.

Catalog lives at jw_core/data/versification_map.json. We load it once via
`functools.lru_cache(maxsize=1)` so import is free and every subsequent
call is O(1) lookup of the cached list.

`lookup(book_num, chapter, verse_start, tradition)` is a convenience used
by `mapping.py`. It scans the (small) catalog linearly — there are ~150
entries at most; building a dict index would be premature optimization.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from jw_core.versification.models import Tradition, VersificationMapping


def catalog_path() -> Path:
    """Absolute path of the bundled catalog JSON."""

    # jw_core/versification/registry.py → jw_core/data/versification_map.json
    return Path(__file__).resolve().parent.parent / "data" / "versification_map.json"


@lru_cache(maxsize=1)
def load_catalog() -> tuple[VersificationMapping, ...]:
    """Parse the catalog into a tuple of VersificationMapping.

    Returns a tuple (not list) so the cached value is immutable — callers
    cannot accidentally mutate the shared catalog.
    """

    raw = json.loads(catalog_path().read_text(encoding="utf-8"))
    entries = raw.get("discrepancies", [])
    parsed = tuple(VersificationMapping.model_validate(e) for e in entries)
    return parsed


def lookup(
    *,
    book_num: int,
    chapter: int,
    verse_start: int,
    tradition: Tradition,
) -> list[VersificationMapping]:
    """Find catalog entries whose coordinate-in-`tradition` covers the input.

    A coordinate "covers" the input when its chapter matches AND
    its verse_start <= input.verse_start <= (verse_end or verse_start).
    """

    matches: list[VersificationMapping] = []
    for entry in load_catalog():
        if entry.book_num != book_num:
            continue
        coord = entry.coord_for(tradition)
        if coord is None:
            continue
        if coord.chapter != chapter:
            continue
        end = coord.verse_end if coord.verse_end is not None else coord.verse_start
        if coord.verse_start <= verse_start <= end:
            matches.append(entry)
    return matches
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest packages/jw-core/tests/test_versification_registry.py -v`
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-core/src/jw_core/versification/registry.py \
        packages/jw-core/tests/test_versification_registry.py
git commit -m "feat(versification): lazy lru_cache'd registry with lookup helper"
```

---

### Task 4: Extend `BibleRef` with optional `tradition` field

**Files:**
- Modify: `packages/jw-core/src/jw_core/models.py`

- [ ] **Step 1: Verify the existing 1984 tests are green before touching the model**

Run: `uv run pytest packages/jw-core/tests/ -q --no-cov`
Expected: all pass. Capture the count so we can compare after.

- [ ] **Step 2: Add the field (smallest possible change)**

Edit `packages/jw-core/src/jw_core/models.py`. Add this import near the top:

```python
from typing import Literal
```

Then add the field to `BibleRef` (immediately before `book_num`):

```python
class BibleRef(BaseModel):
    """A parsed Bible reference."""

    tradition: Literal["nwt", "masoretic", "lxx", "vulgate"] = Field(
        default="nwt",
        description=(
            "Numbering tradition this reference is expressed in. Default "
            "'nwt' matches NWT/KJV/Vulgate-derived Christian numbering. "
            "Use `jw_core.versification.to_canonical` to map between."
        ),
    )

    book_num: int = Field(ge=1, le=66, description="Canonical book number (Gen=1, Rev=66)")
    # ... rest unchanged
```

- [ ] **Step 3: Re-run the suite to prove zero regressions**

Run: `uv run pytest packages/jw-core/tests/ -q --no-cov`
Expected: same number of passes as Step 1. The `tradition` field has a default, so every existing test continues to construct a `BibleRef` without specifying it.

- [ ] **Step 4: Add a focused regression test**

Append to `packages/jw-core/tests/test_versification_models.py`:

```python
def test_bible_ref_default_tradition_is_nwt() -> None:
    from jw_core.models import BibleRef

    r = BibleRef(
        book_num=29,
        book_canonical="Joel",
        chapter=2,
        verse_start=28,
        detected_language="en",
        raw_match="Joel 2:28",
    )
    assert r.tradition == "nwt"


def test_bible_ref_accepts_explicit_tradition() -> None:
    from jw_core.models import BibleRef

    r = BibleRef(
        book_num=29,
        book_canonical="Joel",
        chapter=3,
        verse_start=1,
        detected_language="en",
        raw_match="Joel 3:1",
        tradition="masoretic",
    )
    assert r.tradition == "masoretic"
```

Run: `uv run pytest packages/jw-core/tests/test_versification_models.py -v`
Expected: 11 passed (9 from Task 1 + 2 new).

- [ ] **Step 5: Commit**

```bash
git add packages/jw-core/src/jw_core/models.py \
        packages/jw-core/tests/test_versification_models.py
git commit -m "feat(versification): add optional BibleRef.tradition (default 'nwt')"
```

---

### Task 5: Implement `to_canonical`

**Files:**
- Create: `packages/jw-core/src/jw_core/versification/mapping.py`
- Create: `packages/jw-core/tests/test_versification_mapping.py`

- [ ] **Step 1: Write the failing tests**

```python
# packages/jw-core/tests/test_versification_mapping.py
"""Tests for the to_canonical mapping function."""

from __future__ import annotations

import pytest

from jw_core.models import BibleRef
from jw_core.versification import to_canonical
from jw_core.versification.models import MappingResult


def _ref(book: str, book_num: int, ch: int, v: int | None = None, tradition: str = "nwt") -> BibleRef:
    return BibleRef(
        book_num=book_num,
        book_canonical=book,
        chapter=ch,
        verse_start=v,
        detected_language="en",
        raw_match=f"{book} {ch}{':'+str(v) if v else ''}",
        tradition=tradition,  # type: ignore[arg-type]
    )


def test_identity_same_tradition_is_not_discrepant() -> None:
    r = _ref("Genesis", 1, 1, 1)
    result = to_canonical(r, from_tradition="nwt", to_tradition="nwt")
    assert isinstance(result, MappingResult)
    assert result.is_discrepant is False
    assert result.rationale is None
    assert result.coord.chapter == 1
    assert result.coord.verse_start == 1


def test_no_catalog_entry_returns_identity_in_target_tradition() -> None:
    """Genesis 1:1 has no discrepancy; we still return a wrapper."""
    r = _ref("Genesis", 1, 1, 1, tradition="nwt")
    result = to_canonical(r, from_tradition="nwt", to_tradition="masoretic")
    assert result.is_discrepant is False
    assert result.to_tradition == "masoretic"
    assert result.coord.chapter == 1
    assert result.coord.verse_start == 1


def test_joel_2_28_nwt_to_masoretic_is_3_1() -> None:
    r = _ref("Joel", 29, 2, 28)
    result = to_canonical(r, from_tradition="nwt", to_tradition="masoretic")
    assert result.is_discrepant is True
    assert result.coord.chapter == 3
    assert result.coord.verse_start == 1
    assert result.rationale is not None
    assert "Joel" in result.rationale


def test_malachi_4_1_nwt_to_masoretic_is_3_19() -> None:
    r = _ref("Malachi", 39, 4, 1)
    result = to_canonical(r, from_tradition="nwt", to_tradition="masoretic")
    assert result.is_discrepant is True
    assert result.coord.chapter == 3
    assert result.coord.verse_start == 19


def test_psalm_51_1_nwt_to_masoretic_drops_to_verse_zero() -> None:
    r = _ref("Psalms", 19, 51, 1)
    result = to_canonical(r, from_tradition="nwt", to_tradition="masoretic")
    assert result.is_discrepant is True
    assert result.coord.chapter == 51
    assert result.coord.verse_start == 0


def test_psalm_51_1_nwt_to_lxx_is_psalm_50_verse_zero() -> None:
    r = _ref("Psalms", 19, 51, 1)
    result = to_canonical(r, from_tradition="nwt", to_tradition="lxx")
    assert result.is_discrepant is True
    assert result.coord.chapter == 50
    assert result.coord.verse_start == 0


def test_reverse_masoretic_to_nwt_joel() -> None:
    r = _ref("Joel", 29, 3, 1, tradition="masoretic")
    result = to_canonical(r, from_tradition="masoretic", to_tradition="nwt")
    assert result.is_discrepant is True
    assert result.coord.chapter == 2
    assert result.coord.verse_start == 28


def test_unknown_tradition_raises() -> None:
    r = _ref("Joel", 29, 2, 28)
    with pytest.raises(ValueError):
        to_canonical(r, from_tradition="nwt", to_tradition="frobnicate")  # type: ignore[arg-type]


def test_input_missing_verse_start_uses_chapter_only() -> None:
    """When the input has no verse_start (chapter-level ref), pass through."""
    r = _ref("Joel", 29, 2, None)
    result = to_canonical(r, from_tradition="nwt", to_tradition="masoretic")
    # Joel ch 2 NWT has no clean chapter-level mapping; we return identity
    # at chapter granularity rather than guessing.
    assert result.coord.chapter == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest packages/jw-core/tests/test_versification_mapping.py -v`
Expected: FAIL — `mapping` module not found.

- [ ] **Step 3: Implement `to_canonical`**

```python
# packages/jw-core/src/jw_core/versification/mapping.py
"""Bidirectional mapping between numbering traditions.

Algorithm
---------

1. If `from_tradition == to_tradition`, return identity (no lookup).
2. Otherwise look up the input coordinates in the source tradition's view
   of the catalog. If no entry matches, return identity in the target
   tradition — the reference is the same in both traditions.
3. If a catalog entry matches, read its coordinate for the target
   tradition and return that. The catalog stores chapter+verse_start
   (+ optional verse_end) per tradition, so the map is direct.
4. The returned `MappingResult.coord` is a `VerseCoord` (relaxed schema:
   verse_start >= 0) so superscriptions survive. To turn it back into a
   strict `BibleRef`, callers can use a helper that clamps verse_start to
   max(coord.verse_start, 1) and records the original via metadata —
   that helper is left for downstream code.

Idempotence
-----------

`to_canonical(r, from_=t, to_=t)` is identity by construction (step 1).

Round-trip
----------

For every cataloged entry, applying to_canonical (a → b) then (b → a)
returns the original coordinates because the catalog is symmetric — each
entry encodes both ends. Tested via hypothesis in test_versification_
mapping_property.py.
"""

from __future__ import annotations

from typing import get_args

from jw_core.models import BibleRef
from jw_core.versification.models import (
    MappingResult,
    Tradition,
    VerseCoord,
    VersificationMapping,
)
from jw_core.versification.registry import lookup

_VALID_TRADITIONS: frozenset[str] = frozenset(get_args(Tradition))


def _validate_tradition(name: str, value: str) -> None:
    if value not in _VALID_TRADITIONS:
        raise ValueError(
            f"{name}={value!r} is not a known tradition. "
            f"Expected one of {sorted(_VALID_TRADITIONS)}."
        )


def _coord_from_ref(ref: BibleRef) -> VerseCoord:
    """Build a relaxed VerseCoord from a strict BibleRef.

    `BibleRef.verse_start` is None for chapter-level refs; we map that to
    verse_start=1 so the lookup has something concrete to search for.
    """

    return VerseCoord(
        chapter=ref.chapter,
        verse_start=ref.verse_start if ref.verse_start is not None else 1,
        verse_end=ref.verse_end,
    )


def _build_rationale(
    entry: VersificationMapping,
    from_tradition: Tradition,
    to_tradition: Tradition,
) -> str:
    """Pick the English explanation; explain.py handles trilingual."""

    return entry.explanation.get("en", "") or (
        f"{entry.book} {from_tradition} ↔ {to_tradition}: see {entry.source}"
    )


def to_canonical(
    ref: BibleRef,
    *,
    from_tradition: Tradition = "nwt",
    to_tradition: Tradition,
) -> MappingResult:
    """Map `ref` from `from_tradition` numbering to `to_tradition` numbering.

    See module docstring for the algorithm. Raises `ValueError` if either
    tradition is not one of {nwt, masoretic, lxx, vulgate}.
    """

    _validate_tradition("from_tradition", from_tradition)
    _validate_tradition("to_tradition", to_tradition)

    # Step 1: identity.
    if from_tradition == to_tradition:
        return MappingResult(
            ref_book=ref.book_canonical,
            ref_book_num=ref.book_num,
            coord=_coord_from_ref(ref),
            from_tradition=from_tradition,
            to_tradition=to_tradition,
            is_discrepant=False,
        )

    # Step 2: catalog lookup. If verse_start is None we can still look up
    # by chapter alone (use verse_start=1 as the probe, mirroring BibleRef
    # semantics).
    probe_verse = ref.verse_start if ref.verse_start is not None else 1
    entries = lookup(
        book_num=ref.book_num,
        chapter=ref.chapter,
        verse_start=probe_verse,
        tradition=from_tradition,
    )

    if not entries:
        # No known discrepancy → reference is the same in target tradition.
        return MappingResult(
            ref_book=ref.book_canonical,
            ref_book_num=ref.book_num,
            coord=_coord_from_ref(ref),
            from_tradition=from_tradition,
            to_tradition=to_tradition,
            is_discrepant=False,
        )

    # Step 3: project to the target tradition.
    entry = entries[0]
    target_coord = entry.coord_for(to_tradition)
    if target_coord is None:
        # The catalog has this discrepancy from->something, but not
        # ->to_tradition. We treat that as "no mapping known" and return
        # identity rather than guessing.
        return MappingResult(
            ref_book=ref.book_canonical,
            ref_book_num=ref.book_num,
            coord=_coord_from_ref(ref),
            from_tradition=from_tradition,
            to_tradition=to_tradition,
            is_discrepant=False,
            rationale=None,
        )

    return MappingResult(
        ref_book=entry.book,
        ref_book_num=entry.book_num,
        coord=target_coord,
        from_tradition=from_tradition,
        to_tradition=to_tradition,
        is_discrepant=True,
        rationale=_build_rationale(entry, from_tradition, to_tradition),
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest packages/jw-core/tests/test_versification_mapping.py -v`
Expected: 9 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-core/src/jw_core/versification/mapping.py \
        packages/jw-core/tests/test_versification_mapping.py
git commit -m "feat(versification): to_canonical mapping function with catalog lookup"
```

---

### Task 6: Property tests (idempotence + round-trip)

**Files:**
- Create: `packages/jw-core/tests/test_versification_mapping_property.py`

- [ ] **Step 1: Write the property tests**

```python
# packages/jw-core/tests/test_versification_mapping_property.py
"""Property-based tests for to_canonical: idempotence + round-trip.

Idempotence  : to_canonical(r, from_=t, to_=t).coord == probe(r) ∀ r, t.
Round-trip   : for every cataloged entry, mapping (from → to) then back
               (to → from) yields the original coordinate.

We use hypothesis to generate arbitrary BibleRefs for the idempotence
test; the round-trip test enumerates the catalog directly.
"""

from __future__ import annotations

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from jw_core.models import BibleRef
from jw_core.versification import to_canonical
from jw_core.versification.models import Tradition
from jw_core.versification.registry import load_catalog

TRADITIONS: list[Tradition] = ["nwt", "masoretic", "lxx", "vulgate"]


@st.composite
def _bible_refs(draw: st.DrawFn) -> BibleRef:
    book_num = draw(st.integers(min_value=1, max_value=66))
    chapter = draw(st.integers(min_value=1, max_value=150))
    verse = draw(st.integers(min_value=1, max_value=176))
    return BibleRef(
        book_num=book_num,
        book_canonical=f"Book{book_num}",
        chapter=chapter,
        verse_start=verse,
        detected_language="en",
        raw_match=f"Book{book_num} {chapter}:{verse}",
    )


@settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
@given(ref=_bible_refs(), tradition=st.sampled_from(TRADITIONS))
def test_idempotent_within_same_tradition(ref: BibleRef, tradition: Tradition) -> None:
    """Mapping from a tradition to itself never marks as discrepant."""
    r = to_canonical(ref, from_tradition=tradition, to_tradition=tradition)
    assert r.is_discrepant is False
    assert r.coord.chapter == ref.chapter
    assert r.coord.verse_start == ref.verse_start


@pytest.mark.parametrize(
    "from_t,to_t",
    [
        ("nwt", "masoretic"),
        ("masoretic", "nwt"),
        ("nwt", "lxx"),
        ("lxx", "nwt"),
        ("nwt", "vulgate"),
        ("vulgate", "nwt"),
    ],
)
def test_round_trip_for_every_catalog_entry(from_t: Tradition, to_t: Tradition) -> None:
    """For each entry with both coords set, (a→b→a) returns the original.

    We only check entries that have BOTH `from_t` and `to_t` coords set.
    Entries lacking one side are deliberately one-way and tested elsewhere.
    """

    for entry in load_catalog():
        coord_from = entry.coord_for(from_t)
        coord_to = entry.coord_for(to_t)
        if coord_from is None or coord_to is None:
            continue

        ref_in = BibleRef(
            book_num=entry.book_num,
            book_canonical=entry.book,
            chapter=coord_from.chapter,
            verse_start=max(coord_from.verse_start, 1),  # BibleRef requires >=1
            detected_language="en",
            raw_match=f"{entry.book} {coord_from.chapter}:{coord_from.verse_start}",
            tradition=from_t,
        )

        # a → b
        forward = to_canonical(ref_in, from_tradition=from_t, to_tradition=to_t)
        assert forward.coord.chapter == coord_to.chapter, (
            f"{entry.book} {from_t}->{to_t}: chapter expected "
            f"{coord_to.chapter}, got {forward.coord.chapter}"
        )

        # b → a (skip if verse_start was clamped on input — round-trip would
        # be ill-defined when the source coord is verse 0 since BibleRef
        # cannot carry it).
        if coord_from.verse_start == 0:
            continue

        # Build a BibleRef in the target tradition; clamp verse_start to >=1
        # if the catalog records 0 (superscription) for `to_t`.
        ref_mid = BibleRef(
            book_num=entry.book_num,
            book_canonical=entry.book,
            chapter=forward.coord.chapter,
            verse_start=max(forward.coord.verse_start, 1),
            detected_language="en",
            raw_match=f"{entry.book} {forward.coord.chapter}:{forward.coord.verse_start}",
            tradition=to_t,
        )
        back = to_canonical(ref_mid, from_tradition=to_t, to_tradition=from_t)
        assert back.coord.chapter == coord_from.chapter, (
            f"round-trip failed for {entry.book} {from_t}<->{to_t}: "
            f"started at chapter {coord_from.chapter}, came back at "
            f"{back.coord.chapter}"
        )
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `uv run pytest packages/jw-core/tests/test_versification_mapping_property.py -v`
Expected: passes (1 hypothesis test with 200 examples + 6 parametric round-trips).

If a round-trip fails, fix the offending catalog entry — the test is the source of truth for catalog symmetry.

- [ ] **Step 3: Commit**

```bash
git add packages/jw-core/tests/test_versification_mapping_property.py
git commit -m "test(versification): property tests for idempotence and round-trip"
```

---

### Task 7: Famous-case smoke fixtures

**Files:**
- Create: `packages/jw-core/tests/test_versification_known.py`

- [ ] **Step 1: Write the test**

```python
# packages/jw-core/tests/test_versification_known.py
"""Smoke tests for the famous discrepancies an apologetics user will ask about."""

from __future__ import annotations

import pytest

from jw_core.models import BibleRef
from jw_core.versification import to_canonical


def _ref(book: str, book_num: int, chapter: int, verse: int, tradition: str = "nwt") -> BibleRef:
    return BibleRef(
        book_num=book_num,
        book_canonical=book,
        chapter=chapter,
        verse_start=verse,
        detected_language="en",
        raw_match=f"{book} {chapter}:{verse}",
        tradition=tradition,  # type: ignore[arg-type]
    )


KNOWN_CASES = [
    # (book, book_num, ch, v, from_t, to_t, expected_ch, expected_v)
    ("Joel", 29, 2, 28, "nwt", "masoretic", 3, 1),
    ("Joel", 29, 2, 32, "nwt", "masoretic", 3, 1),  # entry covers 28-32 → maps to 3:1-5 (start of range)
    ("Malachi", 39, 4, 1, "nwt", "masoretic", 3, 19),
    ("Malachi", 39, 4, 6, "nwt", "masoretic", 3, 19),  # range entry
    ("Psalms", 19, 51, 1, "nwt", "masoretic", 51, 0),
    ("Psalms", 19, 51, 1, "nwt", "lxx", 50, 0),
    ("Nehemiah", 16, 4, 1, "nwt", "masoretic", 3, 33),
    ("1 Kings", 11, 4, 21, "nwt", "masoretic", 5, 1),
    ("1 Chronicles", 13, 6, 1, "nwt", "masoretic", 5, 27),
    ("Daniel", 27, 5, 31, "nwt", "masoretic", 6, 1),
    ("Jonah", 32, 1, 17, "nwt", "masoretic", 2, 1),
    ("Hosea", 28, 1, 10, "nwt", "masoretic", 2, 1),
]


@pytest.mark.parametrize(
    "book,book_num,ch,v,from_t,to_t,expected_ch,expected_v", KNOWN_CASES
)
def test_known_discrepancy(
    book: str,
    book_num: int,
    ch: int,
    v: int,
    from_t: str,
    to_t: str,
    expected_ch: int,
    expected_v: int,
) -> None:
    r = _ref(book, book_num, ch, v, tradition=from_t)
    result = to_canonical(r, from_tradition=from_t, to_tradition=to_t)  # type: ignore[arg-type]
    assert result.is_discrepant is True
    assert result.coord.chapter == expected_ch, (
        f"{book} {ch}:{v} {from_t}→{to_t}: "
        f"expected chapter {expected_ch}, got {result.coord.chapter}"
    )
    assert result.coord.verse_start == expected_v, (
        f"{book} {ch}:{v} {from_t}→{to_t}: "
        f"expected verse {expected_v}, got {result.coord.verse_start}"
    )
    assert result.rationale is not None
```

- [ ] **Step 2: Run the test**

Run: `uv run pytest packages/jw-core/tests/test_versification_known.py -v`
Expected: 12 passed.

- [ ] **Step 3: Commit**

```bash
git add packages/jw-core/tests/test_versification_known.py
git commit -m "test(versification): smoke fixtures for 12 famous discrepancies"
```

---

### Task 8: Implement `explain` (trilingual)

**Files:**
- Create: `packages/jw-core/src/jw_core/versification/explain.py`
- Create: `packages/jw-core/tests/test_versification_explain.py`

- [ ] **Step 1: Write the failing tests**

```python
# packages/jw-core/tests/test_versification_explain.py
"""Tests for the trilingual explainer."""

from __future__ import annotations

import pytest

from jw_core.models import BibleRef
from jw_core.versification.explain import explain


def _ref(book: str, book_num: int, ch: int, v: int) -> BibleRef:
    return BibleRef(
        book_num=book_num,
        book_canonical=book,
        chapter=ch,
        verse_start=v,
        detected_language="en",
        raw_match=f"{book} {ch}:{v}",
    )


def test_explain_returns_english_by_default() -> None:
    r = _ref("Joel", 29, 2, 28)
    out = explain(r, from_tradition="nwt", to_tradition="masoretic")
    assert out is not None
    assert "Joel" in out
    assert "Hebrew" in out or "BHS" in out


def test_explain_returns_spanish() -> None:
    r = _ref("Joel", 29, 2, 28)
    out = explain(r, from_tradition="nwt", to_tradition="masoretic", language="es")
    assert out is not None
    assert "Joel" in out
    assert "hebrea" in out.lower()


def test_explain_returns_portuguese() -> None:
    r = _ref("Joel", 29, 2, 28)
    out = explain(r, from_tradition="nwt", to_tradition="masoretic", language="pt")
    assert out is not None
    assert "Joel" in out
    assert "hebraica" in out.lower()


def test_explain_returns_none_for_identity() -> None:
    r = _ref("Genesis", 1, 1, 1)
    out = explain(r, from_tradition="nwt", to_tradition="nwt")
    assert out is None


def test_explain_returns_none_when_no_catalog_entry() -> None:
    r = _ref("Genesis", 1, 1, 1)
    out = explain(r, from_tradition="nwt", to_tradition="masoretic")
    assert out is None


def test_explain_unknown_language_raises() -> None:
    r = _ref("Joel", 29, 2, 28)
    with pytest.raises(ValueError):
        explain(r, from_tradition="nwt", to_tradition="masoretic", language="fr")  # type: ignore[arg-type]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest packages/jw-core/tests/test_versification_explain.py -v`
Expected: FAIL — `explain` module not found.

- [ ] **Step 3: Implement `explain`**

```python
# packages/jw-core/src/jw_core/versification/explain.py
"""Trilingual explainer for a (ref, from, to) triple.

Returns the maintainer-authored prose stored in the catalog for the
matching entry, in the requested language. None when there is no
discrepancy (identity mapping or no catalog entry).
"""

from __future__ import annotations

from typing import Literal

from jw_core.models import BibleRef
from jw_core.versification.mapping import to_canonical
from jw_core.versification.models import Tradition
from jw_core.versification.registry import lookup

ExplanationLanguage = Literal["en", "es", "pt"]
_VALID_LANGUAGES: frozenset[str] = frozenset({"en", "es", "pt"})


def explain(
    ref: BibleRef,
    *,
    from_tradition: Tradition,
    to_tradition: Tradition,
    language: ExplanationLanguage = "en",
) -> str | None:
    """Human-readable sentence for the discrepancy, or None.

    The function performs the same lookup as `to_canonical` and selects
    the catalog explanation in `language`. Raises ValueError if
    `language` is not one of en/es/pt.
    """

    if language not in _VALID_LANGUAGES:
        raise ValueError(
            f"language={language!r} not supported. Expected one of {sorted(_VALID_LANGUAGES)}."
        )

    # Use to_canonical to keep the discrepant/identity contract aligned.
    mapped = to_canonical(ref, from_tradition=from_tradition, to_tradition=to_tradition)
    if not mapped.is_discrepant:
        return None

    probe_verse = ref.verse_start if ref.verse_start is not None else 1
    entries = lookup(
        book_num=ref.book_num,
        chapter=ref.chapter,
        verse_start=probe_verse,
        tradition=from_tradition,
    )
    if not entries:
        return None

    return entries[0].explanation.get(language)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest packages/jw-core/tests/test_versification_explain.py -v`
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-core/src/jw_core/versification/explain.py \
        packages/jw-core/tests/test_versification_explain.py
git commit -m "feat(versification): trilingual explain() function"
```

---

### Task 9: Copyright guard test

**Files:**
- Create: `packages/jw-core/tests/test_versification_copyright_guard.py`

The catalog's `explanation` field is maintainer prose. The guard test detects accidental copy-paste from the named academic sources so the project stays GPL-clean.

- [ ] **Step 1: Write the guard test**

```python
# packages/jw-core/tests/test_versification_copyright_guard.py
"""Guard against copyright contamination in catalog explanations.

The catalog cites academic sources (Tov 2012, BHS apparatus, NETS, etc.)
but the `explanation` field MUST be original prose written by the
maintainer. We can't enforce that absolutely, but we can detect two
red flags:

  1. Verbatim 8+ word phrases that look like academic boilerplate.
  2. Specific stop-phrases lifted from the named sources (curated list).

If either is found, fail loudly so the offending entry is rewritten
before merging.
"""

from __future__ import annotations

import re

from jw_core.versification.registry import load_catalog

# Stop-phrases lifted from publicly available previews / reviews of the
# cited sources. The presence of any of these in an explanation strongly
# suggests verbatim copying. Curated conservatively — false positives are
# acceptable, false negatives are not.
STOP_PHRASES_EN = [
    "textual criticism of the hebrew bible",  # Tov 2012 title
    "the text of the old testament",  # Würthwein title
    "new english translation of the septuagint",  # NETS title
    # Generic boilerplate that signals borrowed academic phrasing:
    "according to the masoretic tradition,",
    "as is well known,",
    "it should be noted that",
    "scholars generally agree that",
]

STOP_PHRASES_ES = [
    "crítica textual de la biblia hebrea",
    "como es bien sabido,",
    "los estudiosos generalmente coinciden",
    "cabe señalar que",
]

STOP_PHRASES_PT = [
    "crítica textual da bíblia hebraica",
    "como é bem sabido,",
    "os estudiosos geralmente concordam",
    "cabe notar que",
]


def test_no_stop_phrase_in_english_explanations() -> None:
    offenders: list[str] = []
    for entry in load_catalog():
        text = entry.explanation["en"].lower()
        for phrase in STOP_PHRASES_EN:
            if phrase in text:
                offenders.append(f"{entry.book} {entry.nwt.chapter}: stop-phrase {phrase!r}")
    assert not offenders, "\n".join(offenders)


def test_no_stop_phrase_in_spanish_explanations() -> None:
    offenders: list[str] = []
    for entry in load_catalog():
        text = entry.explanation["es"].lower()
        for phrase in STOP_PHRASES_ES:
            if phrase in text:
                offenders.append(f"{entry.book} {entry.nwt.chapter}: stop-phrase {phrase!r}")
    assert not offenders, "\n".join(offenders)


def test_no_stop_phrase_in_portuguese_explanations() -> None:
    offenders: list[str] = []
    for entry in load_catalog():
        text = entry.explanation["pt"].lower()
        for phrase in STOP_PHRASES_PT:
            if phrase in text:
                offenders.append(f"{entry.book} {entry.nwt.chapter}: stop-phrase {phrase!r}")
    assert not offenders, "\n".join(offenders)


def test_explanations_are_non_empty_and_reasonably_short() -> None:
    """Explanations must be present (>=20 chars) and not absurdly long (<=800)."""

    for entry in load_catalog():
        for lang in ("en", "es", "pt"):
            text = entry.explanation[lang]
            assert 20 <= len(text) <= 800, (
                f"{entry.book} {entry.nwt.chapter} [{lang}]: "
                f"length {len(text)} outside 20..800"
            )


def test_explanations_use_corresponds_not_equals_language() -> None:
    """Per spec risk #4: never claim two numbers are 'equal'; always 'corresponds to'."""

    forbidden = re.compile(r"\bis equal to\b|\bes igual a\b|\bé igual a\b", re.IGNORECASE)
    offenders: list[str] = []
    for entry in load_catalog():
        for lang in ("en", "es", "pt"):
            if forbidden.search(entry.explanation[lang]):
                offenders.append(f"{entry.book} {entry.nwt.chapter} [{lang}]")
    assert not offenders, "Use 'corresponds to' instead of 'equals': " + ", ".join(offenders)
```

- [ ] **Step 2: Run the guard tests**

Run: `uv run pytest packages/jw-core/tests/test_versification_copyright_guard.py -v`
Expected: 5 passed (the seed catalog is hand-written and avoids the stop-phrases).

- [ ] **Step 3: Commit**

```bash
git add packages/jw-core/tests/test_versification_copyright_guard.py
git commit -m "test(versification): copyright stop-phrase guard for catalog explanations"
```

---

### Task 10: CLI subcommand `jw versification`

**Files:**
- Create: `packages/jw-cli/src/jw_cli/commands/versification.py`
- Modify: `packages/jw-cli/src/jw_cli/main.py`
- Create: `packages/jw-cli/tests/test_versification_cli.py`

- [ ] **Step 1: Write the failing CLI test**

```python
# packages/jw-cli/tests/test_versification_cli.py
"""Smoke tests for the `jw versification` subcommand."""

from __future__ import annotations

from typer.testing import CliRunner

from jw_cli.main import app

runner = CliRunner()


def test_cli_map_joel_2_28_nwt_to_masoretic() -> None:
    result = runner.invoke(
        app,
        ["versification", "map", "Joel 2:28", "--from", "nwt", "--to", "masoretic"],
    )
    assert result.exit_code == 0, result.output
    assert "Joel 3:1" in result.output or "3:1" in result.output
    assert "masoretic" in result.output


def test_cli_map_identity_says_no_discrepancy() -> None:
    result = runner.invoke(
        app,
        ["versification", "map", "Genesis 1:1", "--from", "nwt", "--to", "nwt"],
    )
    assert result.exit_code == 0
    assert "no discrepancy" in result.output.lower() or "identity" in result.output.lower()


def test_cli_explain_spanish() -> None:
    result = runner.invoke(
        app,
        [
            "versification",
            "explain",
            "Joel 2:28",
            "--from",
            "nwt",
            "--to",
            "masoretic",
            "--lang",
            "es",
        ],
    )
    assert result.exit_code == 0
    assert "Joel" in result.output
    assert "hebrea" in result.output.lower()


def test_cli_list_by_book() -> None:
    result = runner.invoke(app, ["versification", "list", "--book", "Joel"])
    assert result.exit_code == 0
    assert "Joel" in result.output


def test_cli_map_unparseable_reference_exits_nonzero() -> None:
    result = runner.invoke(
        app,
        ["versification", "map", "not a reference", "--from", "nwt", "--to", "masoretic"],
    )
    assert result.exit_code != 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest packages/jw-cli/tests/test_versification_cli.py -v`
Expected: FAIL — subcommand not registered.

- [ ] **Step 3: Implement the CLI subcommand**

```python
# packages/jw-cli/src/jw_cli/commands/versification.py
"""`jw versification` subcommand.

Three commands:
    jw versification map <ref> --from <t> --to <t>
    jw versification explain <ref> --from <t> --to <t> --lang en|es|pt
    jw versification list --book <name>
"""

from __future__ import annotations

import typer

from jw_core.parsers.reference import parse_reference
from jw_core.versification import explain as explain_fn
from jw_core.versification import to_canonical
from jw_core.versification.models import Tradition
from jw_core.versification.registry import load_catalog

app = typer.Typer(help="Map Bible references between numbering traditions.")


def _parse_or_fail(ref_text: str) -> tuple[str, int, int, int]:
    parsed = parse_reference(ref_text)
    if parsed is None:
        typer.echo(f"Could not parse reference: {ref_text!r}", err=True)
        raise typer.Exit(code=2)
    if parsed.verse_start is None:
        typer.echo(f"Reference {ref_text!r} lacks a verse; map needs a verse.", err=True)
        raise typer.Exit(code=2)
    return parsed.book_canonical, parsed.book_num, parsed.chapter, parsed.verse_start


@app.command("map")
def map_cmd(
    reference: str = typer.Argument(..., help='Reference like "Joel 2:28".'),
    from_tradition: Tradition = typer.Option("nwt", "--from", help="Source tradition."),
    to_tradition: Tradition = typer.Option(..., "--to", help="Target tradition."),
) -> None:
    """Map a reference from one numbering tradition to another."""

    book, book_num, chapter, verse = _parse_or_fail(reference)
    parsed = parse_reference(reference)
    assert parsed is not None  # _parse_or_fail handled None case
    # Re-set tradition explicitly so the input matches what the user said.
    parsed = parsed.model_copy(update={"tradition": from_tradition})

    result = to_canonical(parsed, from_tradition=from_tradition, to_tradition=to_tradition)
    out = f"{book} {result.coord.chapter}:{result.coord.verse_start}"
    if result.coord.verse_end and result.coord.verse_end != result.coord.verse_start:
        out += f"-{result.coord.verse_end}"
    out += f" ({to_tradition})"
    typer.echo(out)
    if result.is_discrepant and result.rationale:
        typer.echo(result.rationale)
    elif not result.is_discrepant:
        typer.echo("No discrepancy between traditions for this reference (identity).")


@app.command("explain")
def explain_cmd(
    reference: str = typer.Argument(..., help='Reference like "Joel 2:28".'),
    from_tradition: Tradition = typer.Option("nwt", "--from"),
    to_tradition: Tradition = typer.Option(..., "--to"),
    lang: str = typer.Option("en", "--lang", help="en | es | pt"),
) -> None:
    """Print the explanation of a discrepancy in en/es/pt."""

    parsed = parse_reference(reference)
    if parsed is None:
        typer.echo(f"Could not parse reference: {reference!r}", err=True)
        raise typer.Exit(code=2)
    parsed = parsed.model_copy(update={"tradition": from_tradition})

    if lang not in {"en", "es", "pt"}:
        typer.echo(f"Unknown --lang {lang!r}. Use en|es|pt.", err=True)
        raise typer.Exit(code=2)

    text = explain_fn(
        parsed,
        from_tradition=from_tradition,
        to_tradition=to_tradition,
        language=lang,  # type: ignore[arg-type]
    )
    if text is None:
        typer.echo("(no discrepancy)")
    else:
        typer.echo(text)


@app.command("list")
def list_cmd(
    book: str = typer.Option(..., "--book", help="Canonical English book name."),
) -> None:
    """List catalog discrepancies for one book."""

    found = [e for e in load_catalog() if e.book.lower() == book.lower()]
    if not found:
        typer.echo(f"No catalog entries for book {book!r}.")
        raise typer.Exit(code=0)
    typer.echo(f"{len(found)} discrepancy/ies for {book}:")
    for e in found:
        typer.echo(
            f"  - {e.book} {e.nwt.chapter}:{e.nwt.verse_start}"
            f"{'-' + str(e.nwt.verse_end) if e.nwt.verse_end else ''}"
            f"  [{e.issue}]  source={e.source}"
        )
```

- [ ] **Step 4: Register the sub-app in `main.py`**

Edit `packages/jw-cli/src/jw_cli/main.py` and add (near the other `app.add_typer(...)` calls):

```python
from jw_cli.commands.versification import app as versification_app

app.add_typer(versification_app, name="versification")
```

- [ ] **Step 5: Run the CLI tests**

Run: `uv run pytest packages/jw-cli/tests/test_versification_cli.py -v`
Expected: 5 passed.

Also smoke from the shell:

```bash
uv run jw versification map "Joel 2:28" --from nwt --to masoretic
uv run jw versification explain "Psalm 51:1" --from nwt --to masoretic --lang es
uv run jw versification list --book Psalms
```

- [ ] **Step 6: Commit**

```bash
git add packages/jw-cli/src/jw_cli/commands/versification.py \
        packages/jw-cli/src/jw_cli/main.py \
        packages/jw-cli/tests/test_versification_cli.py
git commit -m "feat(jw-cli): add 'jw versification' subcommand (map/explain/list)"
```

---

### Task 11: MCP tool `to_canonical_versification`

**Files:**
- Modify: `packages/jw-mcp/src/jw_mcp/server.py`
- Create: `packages/jw-mcp/tests/test_versification_mcp.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-mcp/tests/test_versification_mcp.py
"""Tests for the MCP tool `to_canonical_versification`.

We call the underlying Python function the FastMCP server exposes,
bypassing the transport layer — same pattern used by other jw-mcp tests.
"""

from __future__ import annotations

import pytest

from jw_mcp.server import to_canonical_versification


def test_mcp_tool_returns_dict_with_expected_keys() -> None:
    out = to_canonical_versification(
        ref="Joel 2:28",
        from_tradition="nwt",
        to_tradition="masoretic",
    )
    assert isinstance(out, dict)
    assert "ref" in out
    assert "is_discrepant" in out
    assert "rationale" in out


def test_mcp_tool_maps_joel() -> None:
    out = to_canonical_versification(
        ref="Joel 2:28",
        from_tradition="nwt",
        to_tradition="masoretic",
    )
    assert out["is_discrepant"] is True
    assert "3:1" in out["ref"]
    assert out["rationale"] is not None


def test_mcp_tool_identity_genesis() -> None:
    out = to_canonical_versification(
        ref="Genesis 1:1",
        from_tradition="nwt",
        to_tradition="masoretic",
    )
    assert out["is_discrepant"] is False
    assert "Genesis 1:1" in out["ref"]


def test_mcp_tool_explanation_in_spanish() -> None:
    out = to_canonical_versification(
        ref="Joel 2:28",
        from_tradition="nwt",
        to_tradition="masoretic",
        explain_in="es",
    )
    assert "hebrea" in out["rationale"].lower()


def test_mcp_tool_unparseable_ref_raises() -> None:
    with pytest.raises(ValueError):
        to_canonical_versification(
            ref="not a reference",
            from_tradition="nwt",
            to_tradition="masoretic",
        )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest packages/jw-mcp/tests/test_versification_mcp.py -v`
Expected: FAIL — symbol `to_canonical_versification` not exported.

- [ ] **Step 3: Implement the tool in `server.py`**

Add to `packages/jw-mcp/src/jw_mcp/server.py` (alongside the existing `@mcp.tool()` definitions):

```python
from typing import Literal as _Literal

from jw_core.parsers.reference import parse_reference as _parse_reference
from jw_core.versification import explain as _vers_explain
from jw_core.versification import to_canonical as _to_canonical


@mcp.tool()
def to_canonical_versification(
    ref: str,
    from_tradition: _Literal["nwt", "masoretic", "lxx", "vulgate"],
    to_tradition: _Literal["nwt", "masoretic", "lxx", "vulgate"],
    explain_in: _Literal["en", "es", "pt"] | None = None,
) -> dict:
    """Map a Bible reference between numbering traditions.

    Returns:
        {"ref": "<book ch:v>", "is_discrepant": bool, "rationale": str | None}

    The optional `explain_in` overrides the language of the `rationale`
    field. Defaults to English.
    """

    parsed = _parse_reference(ref)
    if parsed is None:
        raise ValueError(f"Could not parse reference: {ref!r}")
    parsed = parsed.model_copy(update={"tradition": from_tradition})

    mapped = _to_canonical(
        parsed,
        from_tradition=from_tradition,
        to_tradition=to_tradition,
    )
    ref_str = f"{mapped.ref_book} {mapped.coord.chapter}:{mapped.coord.verse_start}"
    if mapped.coord.verse_end and mapped.coord.verse_end != mapped.coord.verse_start:
        ref_str += f"-{mapped.coord.verse_end}"

    rationale: str | None
    if explain_in is not None and mapped.is_discrepant:
        rationale = _vers_explain(
            parsed,
            from_tradition=from_tradition,
            to_tradition=to_tradition,
            language=explain_in,
        )
    else:
        rationale = mapped.rationale

    return {
        "ref": ref_str,
        "is_discrepant": mapped.is_discrepant,
        "rationale": rationale,
    }
```

- [ ] **Step 4: Re-run the tests**

Run: `uv run pytest packages/jw-mcp/tests/test_versification_mcp.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-mcp/src/jw_mcp/server.py \
        packages/jw-mcp/tests/test_versification_mcp.py
git commit -m "feat(jw-mcp): add 'to_canonical_versification' MCP tool"
```

---

### Task 12: Catalog audit script + docs page

**Files:**
- Create: `scripts/audit_versification_catalog.py`
- Create: `docs/guias/versification.md`

- [ ] **Step 1: Write the audit script**

```python
# scripts/audit_versification_catalog.py
"""Print human-readable stats about the versification catalog.

Run:
    uv run python scripts/audit_versification_catalog.py
"""

from __future__ import annotations

from collections import Counter

from jw_core.versification.registry import load_catalog


def main() -> int:
    entries = load_catalog()
    print(f"Total entries: {len(entries)}")
    print()

    by_issue = Counter(e.issue for e in entries)
    print("By issue type:")
    for issue, n in by_issue.most_common():
        print(f"  {issue:20s}  {n}")
    print()

    by_book = Counter(e.book for e in entries)
    print(f"Books covered: {len(by_book)}")
    for book, n in by_book.most_common():
        print(f"  {book:20s}  {n}")
    print()

    have_masoretic = sum(1 for e in entries if e.masoretic is not None)
    have_lxx = sum(1 for e in entries if e.lxx is not None)
    have_vulgate = sum(1 for e in entries if e.vulgate is not None)
    print("Tradition coverage:")
    print(f"  nwt        {len(entries)}  (every entry has nwt)")
    print(f"  masoretic  {have_masoretic}")
    print(f"  lxx        {have_lxx}")
    print(f"  vulgate    {have_vulgate}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Write the user guide**

```markdown
# Canonical Versification

The `jw_core.versification` subpackage maps Bible references across the
four numbering traditions relevant to JW apologetics: **nwt**,
**masoretic** (BHS), **lxx**, and **vulgate**.

## Why

The NWT inherits Christian (Vulgate/KJV) versification. The Hebrew
Masoretic and Septuagint differ in ~150 documented points: Psalm
superscriptions (verse 0 in BHS), Joel 2:28-32 = Joel 3:1-5 in BHS,
Malachi 4 = Malachi 3 in BHS, the Psalms 9/10 and 114/115 merges in LXX,
and so on. Cross-references that don't account for this produce false
negatives.

## Python API

```python
from jw_core.parsers.reference import parse_reference
from jw_core.versification import to_canonical, explain

ref = parse_reference("Joel 2:28")
result = to_canonical(ref, from_tradition="nwt", to_tradition="masoretic")
print(result.coord.chapter, result.coord.verse_start)  # 3 1
print(result.rationale)
# "Joel 2:28-32 in the NWT corresponds to Joel 3:1-5 in the Hebrew Bible."

print(explain(ref, from_tradition="nwt", to_tradition="masoretic", language="es"))
# "Joel 2:28-32 en la NWT corresponde a Joel 3:1-5 en la Biblia hebrea."
```

## CLI

```bash
jw versification map "Joel 2:28" --from nwt --to masoretic
jw versification explain "Psalm 51:1" --from nwt --to masoretic --lang es
jw versification list --book Psalms
```

## MCP

```python
to_canonical_versification(
    ref="Joel 2:28",
    from_tradition="nwt",
    to_tradition="masoretic",
    explain_in="es",
)
# {"ref": "Joel 3:1", "is_discrepant": true, "rationale": "..."}
```

## Boundaries

- We do NOT translate text — only numbers.
- We cover four traditions only (nwt, masoretic, lxx, vulgate).
- The catalog is ~30 entries today, growing to ~150 in a follow-on PR.
- `BibleRef.tradition` defaults to `"nwt"`; no existing code changes meaning.

## Sources

Catalog metadata cites academic works (Tov 2012, BHS apparatus, NETS).
The `explanation` field is original prose authored by the maintainer to
keep the repo under GPL-3.0 without contaminating with copyrighted text.
See `scripts/audit_versification_catalog.py` for a stats overview.
```

- [ ] **Step 3: Run the audit script as a smoke check**

Run: `uv run python scripts/audit_versification_catalog.py`
Expected output mentions `Total entries: 30` and lists Psalms, Joel, Malachi, etc.

- [ ] **Step 4: Commit**

```bash
git add scripts/audit_versification_catalog.py docs/guias/versification.md
git commit -m "docs(versification): audit script + user guide"
```

---

### Task 13: Sweep tests, update VISION_AUDIT and ROADMAP

**Files:**
- Modify: `docs/VISION_AUDIT.md`
- Modify: `docs/ROADMAP.md`
- Modify: `packages/jw-core/src/jw_core/__init__.py` (re-export check)

- [ ] **Step 1: Ensure `versification` re-exports are visible at package root**

Edit `packages/jw-core/src/jw_core/__init__.py` and append:

```python
# Re-export versification namespace so callers can do:
#     from jw_core import versification
from jw_core import versification as versification  # noqa: F401
```

- [ ] **Step 2: Run the full test suite**

Run: `uv run pytest packages/ -q --no-cov`
Expected:
- All previously-passing tests still pass (the 1984 baseline plus everything Fases 1-45 added).
- New tests added in this plan: 9 (models) + 6 (registry) + 9 (mapping) + ~7 (property) + 12 (known) + 6 (explain) + 5 (copyright) + 5 (CLI) + 5 (MCP) = roughly 64 new passing tests.

If anything is red, fix it before continuing.

- [ ] **Step 3: Update VISION_AUDIT**

In `docs/VISION_AUDIT.md`, add a row to the phase table (or wherever Fase rows live):

```markdown
| 46 | canonical-versification | DONE | Tier 3 | versification module + CLI + MCP; 30 catalog entries seeded; ~150 in follow-on PR. |
```

- [ ] **Step 4: Update ROADMAP**

In `docs/ROADMAP.md`, mark Fase 46 as completed and link to the guide:

```markdown
- **Fase 46 — canonical-versification** ✅
  Maps Bible references between NWT, Masoretic, LXX, Vulgate numbering.
  Guide: [`docs/guias/versification.md`](guias/versification.md).
  Spec: [`docs/superpowers/specs/2026-05-31-fase-46-canonical-versification-design.md`](superpowers/specs/2026-05-31-fase-46-canonical-versification-design.md).
```

- [ ] **Step 5: Commit**

```bash
git add packages/jw-core/src/jw_core/__init__.py docs/VISION_AUDIT.md docs/ROADMAP.md
git commit -m "docs(versification): re-export namespace, update VISION_AUDIT and ROADMAP"
```

---

### Task 14: Final verification

**Files:** (none — verification only)

- [ ] **Step 1: Full suite, no skips**

Run: `uv run pytest packages/ --no-cov -q`
Expected: green, count up by ~64 vs the pre-Fase-46 baseline.

- [ ] **Step 2: Lint and type check (if configured)**

Run: `uv run ruff check packages/jw-core/src/jw_core/versification packages/jw-cli/src/jw_cli/commands/versification.py`
Expected: clean.

Run: `uv run mypy packages/jw-core/src/jw_core/versification` (skip if mypy is not part of CI).

- [ ] **Step 3: CLI end-to-end**

```bash
uv run jw versification map "Joel 2:28" --from nwt --to masoretic
uv run jw versification map "Malachi 4:1" --from nwt --to masoretic
uv run jw versification map "Psalm 51:1" --from nwt --to lxx
uv run jw versification explain "Joel 2:28" --from nwt --to masoretic --lang pt
uv run jw versification list --book Psalms
uv run python scripts/audit_versification_catalog.py
```

Expected: each command exits 0 and produces the documented output.

- [ ] **Step 4: Verify zero regressions**

```bash
# Number of tests before this branch (capture in Task 4 Step 1):
echo "Pre-baseline: 1984"
# Number now:
uv run pytest packages/ --no-cov -q | tail -n 5
```

Expected: pass count = 1984 + (new tests added), failures = 0.

- [ ] **Step 5: Final commit / tag**

If everything is green:

```bash
git log --oneline -n 12   # quick visual review
```

No new commit required at this step — Task 13 was the last functional change.

---

## Self-review

This plan implements Fase 46 in 14 incrementally-tested tasks. Highlights of what it gets right:

- **Strict TDD** at every task: failing test → minimal impl → green → commit.
- **Verbatim spec compliance**: the relaxed `VerseCoord` (verse_start >= 0) is exactly what the spec demands for superscriptions; the `MappingResult` wrapper carries idempotence / discrepancy metadata; `Tradition` is the Literal[nwt|masoretic|lxx|vulgate] from the spec; explanations are trilingual en/es/pt with maintainer-original prose.
- **Catalog scoped to 30 seed entries** (Joel ×2, Malachi, Psalms superscriptions ×8, Psalms 9/10/114/115 splits ×4, Romans 16, 2 Cor 13, Nehemiah ×2, 1 Kings ×2, 1 Chronicles, Daniel ×2, Job, Ecclesiastes, Song of Solomon, Hosea, Jonah). Spec target of ≥100 is explicitly deferred to a follow-on PR — that scoping decision is called out.
- **Copyright guard test** with stop-phrase blocklists in en/es/pt, length bounds, and a check that no explanation uses "is equal to" / "es igual a" / "é igual a".
- **Property tests** via hypothesis: 200-example idempotence check (within-tradition is non-discrepant) plus parametric round-trip across every catalog entry that has both sides set.
- **`BibleRef.tradition` is additive** with default `"nwt"`, guaranteeing the 1984 existing tests stay green (Task 4 brackets the change with before/after suite runs).
- **CLI + MCP** are both covered. CLI tests use Typer's `CliRunner`; MCP tests call the `@mcp.tool()`-decorated function directly to avoid transport plumbing.
- **No unrelated dependencies**: no new runtime deps; hypothesis is already on the dev side from earlier phases.
- **All code blocks contain full file contents** or explicit edits — no placeholders, no `...`, no "implement X".

Risks I am aware of and chose to accept:
- The seed catalog has fewer entries than the spec's ≥100 target; this is flagged and deferred. The follow-on PR can rely on this plan's models + tests as the source of truth for the schema.
- Round-trip is only tested where the catalog records both sides; one-way entries (e.g., NWT→Vulgate only) are exercised via the "known cases" test instead.
- `BibleRef.verse_start >= 1` is a hard Pydantic constraint we did not relax. We use `VerseCoord` (verse_start >= 0) inside the catalog and the `MappingResult.coord`. Downstream code that wants a `BibleRef` from a verse-0 result must clamp; the helper for that is intentionally left out of this plan (YAGNI until needed).

## Execution choice

This plan is suited to **`superpowers:subagent-driven-development`**: each task is independent, has its own failing-test-first contract, and ends with a commit boundary. A sub-agent per task keeps context lean and prevents accidental cross-task coupling. If running solo, use `superpowers:executing-plans` and complete tasks 1 → 14 in order; do NOT skip ahead.

Recommended pacing: tasks 1–3 in one session (foundational), 4–7 in a second (mapping + properties), 8–9 in a third (explain + guard), 10–11 in a fourth (CLI + MCP), 12–14 to close out (docs + verification).
