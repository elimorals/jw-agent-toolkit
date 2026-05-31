# Fase 30 — Compañero de cánticos del Reino: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `jw_core.songs`, a metadata-only registry of Kingdom Songs (number, titles in en/es/pt, theme, scriptures cited, canonical jw.org URL) and wire it into the CLI, MCP, and `workbook_helper` as an opt-in enrichment adapter — **without** ever storing lyrics.

**Architecture:** Three JSON seeds under `jw_core/data/kingdom_songs/{E,S,T}.json` loaded via `importlib.resources`. Pydantic `KingdomSong` model + `SongRegistry` with per-language `lru_cache`. Adapter `enrich_with_songs(AgentResult, language)` mutates a workbook helper result idempotently. CLI subcommand `jw song`. Two MCP tools (`lookup_song`, `songs_for_week`).

**Tech Stack:** Python 3.13 · Pydantic · `importlib.resources` · Typer + Rich (CLI) · FastMCP. No new third-party deps.

**Spec:** [`docs/superpowers/specs/2026-05-30-fase-30-kingdom-songs-design.md`](../specs/2026-05-30-fase-30-kingdom-songs-design.md).

---

## File map

Creates:
- `packages/jw-core/src/jw_core/data/kingdom_songs/__init__.py`
- `packages/jw-core/src/jw_core/data/kingdom_songs/E.json`
- `packages/jw-core/src/jw_core/data/kingdom_songs/S.json`
- `packages/jw-core/src/jw_core/data/kingdom_songs/T.json`
- `packages/jw-core/src/jw_core/songs/__init__.py`
- `packages/jw-core/src/jw_core/songs/models.py`
- `packages/jw-core/src/jw_core/songs/registry.py`
- `packages/jw-core/src/jw_core/songs/integration.py`
- `packages/jw-core/tests/test_kingdom_songs.py`
- `packages/jw-cli/src/jw_cli/commands/song.py`
- `docs/guias/canticos-del-reino.md`

Modifies:
- `packages/jw-core/pyproject.toml` — declare the JSON data files as package_data (Hatchling already includes `src/jw_core/**/*.json` by default for wheel; verify).
- `packages/jw-cli/src/jw_cli/main.py` — register `song` subcommand.
- `packages/jw-mcp/src/jw_mcp/server.py` — add `lookup_song` and `songs_for_week` tools.
- `docs/ROADMAP.md` — add Fase 30 section.
- `docs/VISION_AUDIT.md` — add row for VISION #8.

---

### Task 1: Seed JSON files (E/S/T) + data package marker

**Files:**
- Create: `packages/jw-core/src/jw_core/data/kingdom_songs/__init__.py`
- Create: `packages/jw-core/src/jw_core/data/kingdom_songs/E.json`
- Create: `packages/jw-core/src/jw_core/data/kingdom_songs/S.json`
- Create: `packages/jw-core/src/jw_core/data/kingdom_songs/T.json`

- [ ] **Step 1: Create the package marker**

```python
# packages/jw-core/src/jw_core/data/kingdom_songs/__init__.py
"""Bundled Kingdom Songs metadata (no lyrics, copyright-safe).

The JSON files in this package are factual metadata (number, title, theme
paraphrase, scriptures cited, canonical URL). They DO NOT contain lyrics,
scores or audio links. See docs/guias/canticos-del-reino.md for the policy.
"""
```

- [ ] **Step 2: Write the English seed**

```json
[
  {
    "number": 1,
    "title": "Jehovah's Attributes",
    "theme": "Jehovah's qualities and our heartfelt response of love.",
    "scriptures": ["Psalm 145:8-12"],
    "doc_id": null,
    "canonical_url": ""
  },
  {
    "number": 2,
    "title": "Jehovah Is Your Name",
    "theme": "The sacred name of God and its rightful place in worship.",
    "scriptures": ["Psalm 83:18"],
    "doc_id": null,
    "canonical_url": ""
  },
  {
    "number": 5,
    "title": "Christ's Self-Sacrificing Love",
    "theme": "Christ's self-sacrificing love as a pattern for Christians.",
    "scriptures": ["John 13:34-35", "1 John 3:16"],
    "doc_id": null,
    "canonical_url": ""
  },
  {
    "number": 17,
    "title": "\"I Will\"",
    "theme": "Wholehearted response to Jehovah's invitation to serve.",
    "scriptures": ["Isaiah 6:8"],
    "doc_id": null,
    "canonical_url": ""
  },
  {
    "number": 20,
    "title": "You Redeemed Us With Your Precious Blood",
    "theme": "Gratitude for the ransom sacrifice (Memorial).",
    "scriptures": ["1 Peter 1:18-19"],
    "doc_id": null,
    "canonical_url": ""
  },
  {
    "number": 47,
    "title": "A Daily Prayer",
    "theme": "Petition for wisdom and integrity each day.",
    "scriptures": ["Psalm 25:4-5"],
    "doc_id": null,
    "canonical_url": ""
  },
  {
    "number": 60,
    "title": "It Is the Life He Gave",
    "theme": "The value of the life Christ surrendered for us (Memorial).",
    "scriptures": ["John 15:13"],
    "doc_id": null,
    "canonical_url": ""
  },
  {
    "number": 95,
    "title": "\"The Light Gets Brighter\"",
    "theme": "Progressive understanding of spiritual truth.",
    "scriptures": ["Proverbs 4:18"],
    "doc_id": null,
    "canonical_url": ""
  },
  {
    "number": 102,
    "title": "\"Remember Your Grand Creator\"",
    "theme": "Drawing close to the Creator while young.",
    "scriptures": ["Ecclesiastes 12:1"],
    "doc_id": null,
    "canonical_url": ""
  },
  {
    "number": 109,
    "title": "Love Intensely From the Heart",
    "theme": "Wholehearted love among Christians.",
    "scriptures": ["1 Peter 1:22"],
    "doc_id": null,
    "canonical_url": ""
  },
  {
    "number": 134,
    "title": "See the Sons That God Has Given",
    "theme": "Children as a heritage from Jehovah.",
    "scriptures": ["Psalm 127:3-5"],
    "doc_id": null,
    "canonical_url": ""
  },
  {
    "number": 151,
    "title": "He Will Call",
    "theme": "Hope of the resurrection — Jehovah will call.",
    "scriptures": ["Job 14:14-15"],
    "doc_id": null,
    "canonical_url": ""
  }
]
```

- [ ] **Step 3: Write the Spanish seed**

```json
[
  {
    "number": 1,
    "title": "Las cualidades de Jehová",
    "theme": "Las cualidades de Jehová y nuestra respuesta de amor.",
    "scriptures": ["Salmo 145:8-12"],
    "doc_id": null,
    "canonical_url": ""
  },
  {
    "number": 2,
    "title": "Jehová es tu nombre",
    "theme": "El nombre sagrado de Dios y su lugar en la adoración.",
    "scriptures": ["Salmo 83:18"],
    "doc_id": null,
    "canonical_url": ""
  },
  {
    "number": 5,
    "title": "El amor abnegado de Cristo",
    "theme": "El amor sacrificial de Cristo como modelo para los cristianos.",
    "scriptures": ["Juan 13:34-35", "1 Juan 3:16"],
    "doc_id": null,
    "canonical_url": ""
  },
  {
    "number": 17,
    "title": "\"Iré, envíame a mí\"",
    "theme": "Respuesta entusiasta a la invitación de Jehová a servir.",
    "scriptures": ["Isaías 6:8"],
    "doc_id": null,
    "canonical_url": ""
  },
  {
    "number": 20,
    "title": "Nos redimiste con tu sangre preciosa",
    "theme": "Gratitud por el sacrificio del rescate (Conmemoración).",
    "scriptures": ["1 Pedro 1:18-19"],
    "doc_id": null,
    "canonical_url": ""
  },
  {
    "number": 47,
    "title": "Una oración diaria",
    "theme": "Súplica por sabiduría e integridad cada día.",
    "scriptures": ["Salmo 25:4-5"],
    "doc_id": null,
    "canonical_url": ""
  },
  {
    "number": 60,
    "title": "Es la vida que él dio",
    "theme": "El valor de la vida que Cristo entregó por nosotros (Conmemoración).",
    "scriptures": ["Juan 15:13"],
    "doc_id": null,
    "canonical_url": ""
  },
  {
    "number": 95,
    "title": "\"La luz brilla cada vez más\"",
    "theme": "Comprensión progresiva de la verdad espiritual.",
    "scriptures": ["Proverbios 4:18"],
    "doc_id": null,
    "canonical_url": ""
  },
  {
    "number": 102,
    "title": "\"Acuérdate de tu Gran Creador\"",
    "theme": "Acercarse al Creador desde la juventud.",
    "scriptures": ["Eclesiastés 12:1"],
    "doc_id": null,
    "canonical_url": ""
  },
  {
    "number": 109,
    "title": "Amaos intensamente con el corazón",
    "theme": "El amor cristiano como sello de la verdadera fe.",
    "scriptures": ["1 Pedro 1:22"],
    "doc_id": null,
    "canonical_url": ""
  },
  {
    "number": 134,
    "title": "Mira, los hijos son una herencia",
    "theme": "Los hijos como herencia de Jehová.",
    "scriptures": ["Salmo 127:3-5"],
    "doc_id": null,
    "canonical_url": ""
  },
  {
    "number": 151,
    "title": "Nos llamará Jehová",
    "theme": "Esperanza de la resurrección — Jehová llamará.",
    "scriptures": ["Job 14:14-15"],
    "doc_id": null,
    "canonical_url": ""
  }
]
```

- [ ] **Step 4: Write the Portuguese seed**

Mirror the Spanish file with these 12 numbers. Use the Brazilian Portuguese titles (the publication is the same `sjj` in Portuguese). Each entry shape is identical to Steps 2-3. Example for the first three; the remaining 9 follow the same pattern:

```json
[
  {
    "number": 1,
    "title": "As qualidades de Jeová",
    "theme": "As qualidades de Jeová e nossa resposta de amor.",
    "scriptures": ["Salmo 145:8-12"],
    "doc_id": null,
    "canonical_url": ""
  },
  {
    "number": 2,
    "title": "Jeová é o seu nome",
    "theme": "O nome sagrado de Deus e seu lugar na adoração.",
    "scriptures": ["Salmo 83:18"],
    "doc_id": null,
    "canonical_url": ""
  },
  {
    "number": 5,
    "title": "O amor abnegado de Cristo",
    "theme": "O amor sacrificial de Cristo como modelo para os cristãos.",
    "scriptures": ["João 13:34-35", "1 João 3:16"],
    "doc_id": null,
    "canonical_url": ""
  }
  /* …repeat for 17, 20, 47, 60, 95, 102, 109, 134, 151 with the official PT titles… */
]
```

(Implementer: include all 12 entries — they exist in the public JW Library PT cancioneiro and are factual title translations.)

- [ ] **Step 5: Sanity-check the JSON**

Run:
```bash
.venv/bin/python -c "
import json, pathlib
root = pathlib.Path('packages/jw-core/src/jw_core/data/kingdom_songs')
for f in sorted(root.glob('*.json')):
    data = json.loads(f.read_text())
    print(f.name, len(data), [e['number'] for e in data])
"
```
Expected: each file prints 12 entries with identical number list.

- [ ] **Step 6: Commit**

```bash
git add packages/jw-core/src/jw_core/data/kingdom_songs
git commit -m "feat(jw-core): seed Kingdom Songs metadata (12 entries × en/es/pt, no lyrics)"
```

---

### Task 2: `KingdomSong` model + `SongLookupError`

**Files:**
- Create: `packages/jw-core/src/jw_core/songs/__init__.py`
- Create: `packages/jw-core/src/jw_core/songs/models.py`
- Create: `packages/jw-core/tests/test_kingdom_songs.py` (start with model tests only)

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-core/tests/test_kingdom_songs.py
"""Tests for jw_core.songs — Kingdom Songs metadata registry."""

from __future__ import annotations

import pytest


def test_model_round_trip_minimum_fields() -> None:
    from jw_core.songs import KingdomSong

    s = KingdomSong(
        number=5,
        title="Christ's Self-Sacrificing Love",
        theme="Christ's self-sacrificing love as a pattern.",
        scriptures=["John 13:34-35"],
        language="en",
    )
    assert s.number == 5
    assert s.pub_symbol == "sjj"
    assert s.canonical_url == ""


def test_model_rejects_out_of_range_number() -> None:
    from jw_core.songs import KingdomSong

    with pytest.raises(ValueError):
        KingdomSong(number=999, title="x", theme="y", scriptures=[], language="en")


def test_song_lookup_error_is_lookup_error() -> None:
    from jw_core.songs import SongLookupError

    assert issubclass(SongLookupError, LookupError)


def test_resolved_scriptures_filters_unparseable() -> None:
    from jw_core.songs import KingdomSong

    s = KingdomSong(
        number=5,
        title="x",
        theme="y",
        scriptures=["Juan 13:34-35", "not-a-ref"],
        language="es",
    )
    refs = s.resolved_scriptures()
    assert len(refs) == 1
    assert refs[0].book == 43  # John
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest packages/jw-core/tests/test_kingdom_songs.py -v`
Expected: FAIL — `jw_core.songs` module missing.

- [ ] **Step 3: Implement the model**

```python
# packages/jw-core/src/jw_core/songs/__init__.py
"""Kingdom Songs metadata registry (no lyrics).

Public API:
    from jw_core.songs import KingdomSong, SongLookupError, SongRegistry, get_registry
"""

from jw_core.songs.models import KingdomSong, SongLookupError
from jw_core.songs.registry import SongRegistry, get_registry

__all__ = ["KingdomSong", "SongLookupError", "SongRegistry", "get_registry"]
```

```python
# packages/jw-core/src/jw_core/songs/models.py
"""Metadata-only model for a Kingdom Song.

IMPORTANT: this model NEVER carries lyrics. The `theme` field is a single-
line paraphrase by the contributor — not a copy of the printed subtitle.
See docs/guias/canticos-del-reino.md for the rationale.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from jw_core.parsers.reference import parse_reference

if TYPE_CHECKING:
    from jw_core.models import BibleRef


class SongLookupError(LookupError):
    """Raised when a Kingdom Song number is not in the registry."""


class KingdomSong(BaseModel):
    """One row in the Kingdom Songs registry. NO LYRICS."""

    number: int = Field(ge=1, le=200)
    title: str = Field(min_length=1, max_length=200)
    theme: str = Field(min_length=1, max_length=200)
    scriptures: list[str] = Field(default_factory=list)
    language: str
    pub_symbol: str = Field(default="sjj")
    canonical_url: str = Field(default="")

    def resolved_scriptures(self) -> list["BibleRef"]:
        """Parse each `scriptures` entry via `parse_reference`.
        Unparseable entries are silently dropped.
        """

        refs: list[BibleRef] = []
        for raw in self.scriptures:
            ref = parse_reference(raw)
            if ref is not None:
                refs.append(ref)
        return refs
```

- [ ] **Step 4: Run test to verify it passes**

Note: the `registry` import in `__init__.py` will FAIL until Task 3. So gate this step:

Temporarily change `packages/jw-core/src/jw_core/songs/__init__.py` to only re-export from `models`:

```python
from jw_core.songs.models import KingdomSong, SongLookupError

__all__ = ["KingdomSong", "SongLookupError"]
```

Run: `.venv/bin/python -m pytest packages/jw-core/tests/test_kingdom_songs.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-core/src/jw_core/songs packages/jw-core/tests/test_kingdom_songs.py
git commit -m "feat(jw-core): KingdomSong model + SongLookupError"
```

---

### Task 3: `SongRegistry` loader with `importlib.resources`

**Files:**
- Create: `packages/jw-core/src/jw_core/songs/registry.py`
- Modify: `packages/jw-core/src/jw_core/songs/__init__.py` (restore registry imports)
- Modify: `packages/jw-core/tests/test_kingdom_songs.py` (append registry tests)

- [ ] **Step 1: Append failing tests**

Add to `test_kingdom_songs.py`:

```python
def test_get_registry_loads_three_languages() -> None:
    from jw_core.songs import get_registry

    for lang in ["en", "es", "pt"]:
        reg = get_registry(lang)
        assert len(reg.all()) >= 10, f"{lang} registry too small"


def test_get_registry_caches_per_language() -> None:
    from jw_core.songs import get_registry

    a = get_registry("en")
    b = get_registry("en")
    assert a is b


def test_lookup_returns_song() -> None:
    from jw_core.songs import get_registry

    reg = get_registry("es")
    song = reg.lookup(5)
    assert song.number == 5
    assert "amor" in song.title.lower() or "amor" in song.theme.lower()


def test_lookup_unknown_raises() -> None:
    from jw_core.songs import SongLookupError, get_registry

    reg = get_registry("en")
    with pytest.raises(SongLookupError):
        reg.lookup(999)


def test_unknown_language_returns_empty_registry() -> None:
    from jw_core.songs import get_registry

    reg = get_registry("xx")
    assert reg.all() == []


def test_canonical_url_falls_back_to_finder_pattern() -> None:
    from jw_core.songs import get_registry

    reg = get_registry("es")
    song = reg.lookup(5)
    # Spanish wtlocale = "S".
    assert song.canonical_url == "https://www.jw.org/finder?wtlocale=S&pub=sjj"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest packages/jw-core/tests/test_kingdom_songs.py -v`
Expected: new tests FAIL — `get_registry` missing.

- [ ] **Step 3: Implement the registry**

```python
# packages/jw-core/src/jw_core/songs/registry.py
"""Load Kingdom Songs metadata from bundled JSON, cache per language.

Loader uses `importlib.resources` so it works from a wheel install as well
as from a source checkout. There is no network and no filesystem write.

Each JSON file is a list of dicts with the schema declared in
docs/superpowers/specs/2026-05-30-fase-30-kingdom-songs-design.md.
"""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from importlib import resources

from jw_core.languages import get_language
from jw_core.songs.models import KingdomSong, SongLookupError

logger = logging.getLogger(__name__)

# JW-internal codes used for the `wtlocale` query parameter.
_WTLOCALE_FOR_ISO = {"en": "E", "es": "S", "pt": "T"}


class SongRegistry:
    """Per-language Kingdom Songs registry, loaded from bundled JSON."""

    def __init__(self, language: str, songs: list[KingdomSong]) -> None:
        self._language = language
        self._by_number: dict[int, KingdomSong] = {s.number: s for s in songs}

    @classmethod
    def for_language(cls, language: str) -> SongRegistry:
        """Load the registry for one language from package data.

        Returns an empty registry (and emits a warning) when the requested
        language has no bundled JSON.
        """

        try:
            iso = get_language(language).iso
        except Exception:  # noqa: BLE001
            iso = language

        code = _WTLOCALE_FOR_ISO.get(iso)
        if code is None:
            logger.warning("kingdom-songs: no seed for language %r", language)
            return cls(language=iso, songs=[])

        package = "jw_core.data.kingdom_songs"
        filename = f"{code}.json"
        try:
            raw = resources.files(package).joinpath(filename).read_text(encoding="utf-8")
        except (FileNotFoundError, ModuleNotFoundError):
            logger.warning("kingdom-songs: missing data file %s", filename)
            return cls(language=iso, songs=[])

        records = json.loads(raw)
        songs: list[KingdomSong] = []
        for rec in records:
            payload = dict(rec)
            payload["language"] = iso
            if not payload.get("canonical_url"):
                payload["canonical_url"] = _derive_canonical_url(payload, code)
            payload.pop("doc_id", None)  # only used by the URL deriver
            songs.append(KingdomSong.model_validate(payload))
        return cls(language=iso, songs=songs)

    def lookup(self, number: int) -> KingdomSong:
        """Return the song or raise SongLookupError."""

        try:
            return self._by_number[number]
        except KeyError as exc:
            raise SongLookupError(
                f"song #{number} not in registry for language={self._language!r}"
            ) from exc

    def get(self, number: int) -> KingdomSong | None:
        return self._by_number.get(number)

    def all(self) -> list[KingdomSong]:
        return sorted(self._by_number.values(), key=lambda s: s.number)

    def language(self) -> str:
        return self._language


def _derive_canonical_url(rec: dict, wtlocale: str) -> str:
    """Stable jw.org URL for a song.

    Preference order (no network):
      1. If `rec["doc_id"]` is set → build a WOL discovery URL.
      2. Else → fall back to the public `finder?wtlocale=X&pub=sjj` page
         (always valid; lands on the songbook for that language).
    """

    doc_id = rec.get("doc_id")
    pub = rec.get("pub_symbol", "sjj")
    if doc_id:
        # We deliberately keep this minimal — the WOL URL pattern needs
        # `r1`/`lp-e` segments per language; that lives in `languages.get_language`
        # but we want this function to be cheap and offline-safe, so we use the
        # well-known public `finder` redirector which works for any pub+lang.
        return f"https://www.jw.org/finder?wtlocale={wtlocale}&pub={pub}&docid={doc_id}"
    return f"https://www.jw.org/finder?wtlocale={wtlocale}&pub={pub}"


@lru_cache(maxsize=8)
def get_registry(language: str = "en") -> SongRegistry:
    """Cached factory: return the registry for `language` (en/es/pt)."""

    return SongRegistry.for_language(language)
```

- [ ] **Step 4: Restore the full `__init__.py`**

```python
# packages/jw-core/src/jw_core/songs/__init__.py
"""Kingdom Songs metadata registry (no lyrics).

Public API:
    from jw_core.songs import KingdomSong, SongLookupError, SongRegistry, get_registry
"""

from jw_core.songs.models import KingdomSong, SongLookupError
from jw_core.songs.registry import SongRegistry, get_registry

__all__ = ["KingdomSong", "SongLookupError", "SongRegistry", "get_registry"]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest packages/jw-core/tests/test_kingdom_songs.py -v`
Expected: 10 passed (4 from Task 2 + 6 new).

- [ ] **Step 6: Commit**

```bash
git add packages/jw-core/src/jw_core/songs/registry.py packages/jw-core/src/jw_core/songs/__init__.py packages/jw-core/tests/test_kingdom_songs.py
git commit -m "feat(jw-core): SongRegistry loader (importlib.resources, per-language lru_cache)"
```

---

### Task 4: Seed integrity test (anti-lyrics guard)

**Files:**
- Modify: `packages/jw-core/tests/test_kingdom_songs.py`

- [ ] **Step 1: Append the integrity test**

```python
def test_seed_integrity() -> None:
    """Invariants that protect the seed from accidentally storing lyrics."""

    from jw_core.songs import get_registry

    # Heuristic anti-lyrics tokens — flag obvious copy-paste from a lyric sheet.
    FORBIDDEN_TOKENS = [
        "verse 1", "estrofa", "estribillo", "refrão", "refrain",
        "chorus", "stanza", "©", "copyright watch tower",
    ]

    parallel_numbers: dict[str, set[int]] = {}
    for lang in ["en", "es", "pt"]:
        reg = get_registry(lang)
        nums = set()
        for s in reg.all():
            assert 1 <= s.number <= 200, f"{lang}/#{s.number}: out of 1..200"
            assert len(s.theme) <= 200, f"{lang}/#{s.number}: theme too long"
            assert len(s.title) <= 200, f"{lang}/#{s.number}: title too long"
            lower_blob = (s.title + " " + s.theme).lower()
            for tok in FORBIDDEN_TOKENS:
                assert tok not in lower_blob, (
                    f"{lang}/#{s.number}: forbidden token {tok!r}"
                )
            # Every scripture must parse cleanly.
            assert s.resolved_scriptures() or not s.scriptures, (
                f"{lang}/#{s.number}: scriptures {s.scriptures} all unparseable"
            )
            nums.add(s.number)
        parallel_numbers[lang] = nums

    # All three languages cover the same numbers (parallel coverage).
    assert parallel_numbers["en"] == parallel_numbers["es"] == parallel_numbers["pt"], (
        f"language coverage mismatch: {parallel_numbers}"
    )
```

- [ ] **Step 2: Run the test**

Run: `.venv/bin/python -m pytest packages/jw-core/tests/test_kingdom_songs.py::test_seed_integrity -v`
Expected: pass. If it fails, fix the offending seed entry until clean — do NOT relax the assertions.

- [ ] **Step 3: Commit**

```bash
git add packages/jw-core/tests/test_kingdom_songs.py
git commit -m "test(jw-core): seed integrity invariants for kingdom songs (anti-lyrics guard)"
```

---

### Task 5: `enrich_with_songs` adapter

**Files:**
- Create: `packages/jw-core/src/jw_core/songs/integration.py`
- Modify: `packages/jw-core/src/jw_core/songs/__init__.py` (re-export)
- Modify: `packages/jw-core/tests/test_kingdom_songs.py`

- [ ] **Step 1: Append failing tests**

```python
def _make_workbook_result(songs_dict: dict[str, int | None]):
    """Build a minimal AgentResult mirroring what workbook_helper emits."""

    from jw_agents.base import AgentResult, Citation, Finding

    result = AgentResult(query="2026-W23", agent_name="workbook_helper")
    result.findings.append(
        Finding(
            summary="Workbook week of 2026-06-08",
            excerpt="PROVERBIOS 1-3",
            citation=Citation(
                url="https://wol.jw.org/example",
                title="Reunión",
                kind="workbook_week",
                metadata={"songs": songs_dict},
            ),
            metadata={"source": "workbook_week"},
        )
    )
    return result


def test_enrich_adds_three_findings_when_all_slots_present() -> None:
    from jw_core.songs.integration import enrich_with_songs

    result = _make_workbook_result({"opening": 5, "middle": 47, "closing": 151})
    out = enrich_with_songs(result, language="es")
    song_findings = [f for f in out.findings if f.metadata.get("source") == "kingdom_song"]
    assert len(song_findings) == 3
    assert {f.citation.metadata["slot"] for f in song_findings} == {"opening", "middle", "closing"}


def test_enrich_is_idempotent() -> None:
    from jw_core.songs.integration import enrich_with_songs

    result = _make_workbook_result({"opening": 5, "middle": 47, "closing": 151})
    enrich_with_songs(result, language="en")
    enrich_with_songs(result, language="en")
    song_findings = [f for f in result.findings if f.metadata.get("source") == "kingdom_song"]
    assert len(song_findings) == 3


def test_enrich_handles_unknown_song_gracefully() -> None:
    from jw_core.songs.integration import enrich_with_songs

    result = _make_workbook_result({"opening": 999, "middle": 5, "closing": None})
    out = enrich_with_songs(result, language="en")
    song_findings = [f for f in out.findings if f.metadata.get("source") == "kingdom_song"]
    # Only #5 should land as a finding.
    assert len(song_findings) == 1
    assert song_findings[0].citation.metadata["number"] == 5
    # The unknown number surfaces as a warning.
    assert any("999" in w for w in out.warnings)


def test_enrich_no_workbook_week_finding_is_noop() -> None:
    from jw_agents.base import AgentResult

    from jw_core.songs.integration import enrich_with_songs

    result = AgentResult(query="x", agent_name="other")
    enrich_with_songs(result, language="en")
    assert result.findings == []
    assert result.warnings == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest packages/jw-core/tests/test_kingdom_songs.py -v`
Expected: 4 new tests FAIL.

- [ ] **Step 3: Implement the adapter**

```python
# packages/jw-core/src/jw_core/songs/integration.py
"""Opt-in adapter: enrich a workbook_helper AgentResult with song metadata.

The agent itself (jw_agents.workbook_helper) is NOT modified. Callers
choose whether to wrap its output with this adapter — used by CLI flag
`--with-songs` and by the MCP tool `songs_for_week`.

Idempotent: re-running on an already-enriched result does not duplicate.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from jw_core.songs.registry import get_registry

if TYPE_CHECKING:
    from jw_agents.base import AgentResult


_SLOTS: tuple[str, ...] = ("opening", "middle", "closing")


def enrich_with_songs(result: "AgentResult", language: str = "en") -> "AgentResult":
    """Mutate `result` in place by appending kingdom_song findings.

    Returns the same `result` (for chaining).
    """

    # Local import to avoid a jw_core → jw_agents cycle at module load.
    from jw_agents.base import Citation, Finding

    workbook_finding = _find_workbook_week(result)
    if workbook_finding is None:
        return result

    songs_dict = (workbook_finding.citation.metadata or {}).get("songs") or {}
    if not isinstance(songs_dict, dict):
        result.warnings.append(
            f"enrich_with_songs: songs metadata has unexpected shape {type(songs_dict).__name__}"
        )
        return result

    registry = get_registry(language)
    existing = _existing_song_keys(result)

    for slot in _SLOTS:
        number = songs_dict.get(slot)
        if number is None:
            continue
        if not isinstance(number, int):
            result.warnings.append(
                f"enrich_with_songs: songs[{slot}] is {number!r}, expected int"
            )
            continue
        key = (slot, number)
        if key in existing:
            continue
        song = registry.get(number)
        if song is None:
            result.warnings.append(
                f"enrich_with_songs: song #{number} ({slot}) not in registry for {language!r}"
            )
            continue
        result.findings.append(
            Finding(
                summary=f"Song {number} ({slot}): {song.title}",
                excerpt=song.theme,
                citation=Citation(
                    url=song.canonical_url,
                    title=song.title,
                    kind="kingdom_song",
                    metadata={
                        "number": number,
                        "slot": slot,
                        "scriptures": song.scriptures,
                        "pub_symbol": song.pub_symbol,
                    },
                ),
                metadata={"source": "kingdom_song"},
            )
        )
        existing.add(key)

    return result


def _find_workbook_week(result: "AgentResult") -> Any | None:
    for f in result.findings:
        citation = getattr(f, "citation", None)
        if citation is not None and getattr(citation, "kind", "") == "workbook_week":
            return f
    return None


def _existing_song_keys(result: "AgentResult") -> set[tuple[str, int]]:
    seen: set[tuple[str, int]] = set()
    for f in result.findings:
        citation = getattr(f, "citation", None)
        if citation is None or getattr(citation, "kind", "") != "kingdom_song":
            continue
        meta = citation.metadata or {}
        slot = meta.get("slot")
        number = meta.get("number")
        if isinstance(slot, str) and isinstance(number, int):
            seen.add((slot, number))
    return seen
```

- [ ] **Step 4: Re-export from `__init__.py`**

```python
# packages/jw-core/src/jw_core/songs/__init__.py
"""Kingdom Songs metadata registry (no lyrics)."""

from jw_core.songs.integration import enrich_with_songs
from jw_core.songs.models import KingdomSong, SongLookupError
from jw_core.songs.registry import SongRegistry, get_registry

__all__ = [
    "KingdomSong",
    "SongLookupError",
    "SongRegistry",
    "enrich_with_songs",
    "get_registry",
]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest packages/jw-core/tests/test_kingdom_songs.py -v`
Expected: 14 passed.

- [ ] **Step 6: Commit**

```bash
git add packages/jw-core/src/jw_core/songs/integration.py packages/jw-core/src/jw_core/songs/__init__.py packages/jw-core/tests/test_kingdom_songs.py
git commit -m "feat(jw-core): enrich_with_songs adapter (idempotent, opt-in workbook integration)"
```

---

### Task 6: CLI subcommand `jw song`

**Files:**
- Create: `packages/jw-cli/src/jw_cli/commands/song.py`
- Modify: `packages/jw-cli/src/jw_cli/main.py`
- Modify: `packages/jw-core/tests/test_kingdom_songs.py` (CLI smoke test)

- [ ] **Step 1: Append the CLI test**

```python
def test_cli_song_number_renders_table() -> None:
    from typer.testing import CliRunner

    from jw_cli.main import app

    runner = CliRunner()
    result = runner.invoke(app, ["song", "5", "--lang", "es"])
    assert result.exit_code == 0, result.stdout
    assert "5" in result.stdout
    assert "amor" in result.stdout.lower() or "amor" in result.stdout.lower()


def test_cli_song_unknown_number_reports_error() -> None:
    from typer.testing import CliRunner

    from jw_cli.main import app

    runner = CliRunner()
    result = runner.invoke(app, ["song", "999", "--lang", "en"])
    assert result.exit_code != 0
    assert "not in registry" in result.stdout.lower() or "999" in result.stdout
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/python -m pytest packages/jw-core/tests/test_kingdom_songs.py::test_cli_song_number_renders_table -v`
Expected: FAIL — command not registered.

- [ ] **Step 3: Implement the CLI**

```python
# packages/jw-cli/src/jw_cli/commands/song.py
"""`jw song` — Kingdom Songs metadata lookup (no lyrics).

Examples:
    jw song 5                       # English, song #5
    jw song 5 --lang es
    jw song week                    # this week's songs (workbook + enrich)
    jw song week --date 2026-07-13 --lang pt
"""

from __future__ import annotations

import asyncio

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from jw_core.songs import SongLookupError, get_registry
from jw_core.songs.integration import enrich_with_songs

console = Console()

song_app = typer.Typer(
    name="song",
    help="Kingdom Songs metadata (no lyrics).",
    no_args_is_help=True,
    invoke_without_command=True,
)


@song_app.callback()
def _root(
    ctx: typer.Context,
    number: int | None = typer.Argument(None, help="Song number (1..151)"),
    language: str = typer.Option("en", "--lang", "-l", help="ISO language (en/es/pt)"),
) -> None:
    """Top-level: `jw song 5 --lang es`."""

    if ctx.invoked_subcommand is not None:
        return
    if number is None:
        console.print("[red]Usage:[/red] jw song <number> [--lang en|es|pt]")
        raise typer.Exit(code=2)
    _print_song(number, language)


@song_app.command("week")
def _week(
    date: str = typer.Option("", "--date", "-d", help="ISO date (default: today)"),
    language: str = typer.Option("en", "--lang", "-l", help="ISO language (en/es/pt)"),
) -> None:
    """Print the three songs scheduled for the meeting week containing `date`."""

    from jw_agents import workbook_helper

    result = asyncio.run(
        workbook_helper(date or None, language=language, include_comments=False)
    )
    enrich_with_songs(result, language=language)
    song_findings = [
        f for f in result.findings if f.metadata.get("source") == "kingdom_song"
    ]
    if not song_findings:
        console.print(
            "[yellow]No song metadata found for this week. "
            "The workbook may not have declared song numbers.[/yellow]"
        )
        raise typer.Exit(code=0)

    week_of = result.metadata.get("week_of", "?")
    console.print(
        Panel(f"Songs for the week of [bold]{week_of}[/bold]", title="jw song week", border_style="cyan")
    )

    table = Table(show_header=True, header_style="bold magenta", expand=True)
    table.add_column("slot", width=10)
    table.add_column("#", width=5, justify="right")
    table.add_column("title", overflow="fold")
    table.add_column("theme", overflow="fold")
    table.add_column("scriptures", overflow="fold")
    for f in song_findings:
        meta = f.citation.metadata
        table.add_row(
            str(meta.get("slot", "")),
            str(meta.get("number", "")),
            f.citation.title,
            f.excerpt,
            ", ".join(meta.get("scriptures") or []),
        )
    console.print(table)


def _print_song(number: int, language: str) -> None:
    registry = get_registry(language)
    try:
        song = registry.lookup(number)
    except SongLookupError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    body = Table.grid(padding=(0, 2))
    body.add_column(style="bold cyan", no_wrap=True)
    body.add_column()
    body.add_row("Number", str(song.number))
    body.add_row("Title", song.title)
    body.add_row("Theme", song.theme)
    body.add_row("Scriptures", ", ".join(song.scriptures) or "—")
    body.add_row("URL", song.canonical_url or "—")
    body.add_row("Publication", song.pub_symbol)
    body.add_row("Language", song.language)
    console.print(Panel(body, title=f"Kingdom Song #{song.number}", border_style="green"))
```

- [ ] **Step 4: Register the subcommand**

Edit `packages/jw-cli/src/jw_cli/main.py`:
- Add `from jw_cli.commands import song` next to the other command imports.
- After `app.add_typer(ministry.ministry_app, name="ministry")` append:
  ```python
  app.add_typer(song.song_app, name="song")
  ```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest packages/jw-core/tests/test_kingdom_songs.py -v`
Expected: 16 passed.

Smoke-run:
```bash
.venv/bin/jw song 5 --lang es
.venv/bin/jw song 999 --lang en   # exit code 1, prints "not in registry"
```

- [ ] **Step 6: Commit**

```bash
git add packages/jw-cli/src/jw_cli/commands/song.py packages/jw-cli/src/jw_cli/main.py packages/jw-core/tests/test_kingdom_songs.py
git commit -m "feat(jw-cli): jw song <N> and jw song week subcommands"
```

---

### Task 7: MCP tool `lookup_song`

**Files:**
- Modify: `packages/jw-mcp/src/jw_mcp/server.py`
- Create: `packages/jw-mcp/tests/test_lookup_song_tool.py` (new tiny test file)

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-mcp/tests/test_lookup_song_tool.py
from __future__ import annotations


def test_lookup_song_returns_metadata() -> None:
    from jw_mcp.server import lookup_song

    out = lookup_song(number=5, language="es")
    assert out["number"] == 5
    assert "amor" in out["title"].lower() or "amor" in out["theme"].lower()
    assert isinstance(out["scriptures"], list)
    assert isinstance(out["scriptures_resolved"], list)
    assert out["canonical_url"].startswith("https://www.jw.org/")


def test_lookup_song_unknown_returns_error_dict() -> None:
    from jw_mcp.server import lookup_song

    out = lookup_song(number=999, language="en")
    assert "error" in out
    assert "999" in out["error"]
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/python -m pytest packages/jw-mcp/tests/test_lookup_song_tool.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement the tool**

Edit `packages/jw-mcp/src/jw_mcp/server.py`:

Near the other tool imports add:
```python
from jw_core.songs import SongLookupError, get_registry as _get_song_registry
from jw_core.songs.integration import enrich_with_songs as _enrich_with_songs
```

Below the existing tools (before `if __name__ == "__main__":` or its equivalent), add:

```python
@mcp.tool()
def lookup_song(number: int, language: str = "en") -> dict[str, Any]:
    """Look up Kingdom Song metadata by number.

    Returns a dict with: number, title, theme, scriptures, scriptures_resolved
    (list of BibleRef-as-dict), canonical_url, language, pub_symbol.
    On unknown number returns `{"error": "..."}`.

    Copyright-safe: this tool NEVER returns lyrics, only metadata.
    """

    try:
        registry = _get_song_registry(language)
        song = registry.lookup(number)
    except SongLookupError as exc:
        return {"error": str(exc)}
    return {
        "number": song.number,
        "title": song.title,
        "theme": song.theme,
        "scriptures": song.scriptures,
        "scriptures_resolved": [r.model_dump() for r in song.resolved_scriptures()],
        "canonical_url": song.canonical_url,
        "language": song.language,
        "pub_symbol": song.pub_symbol,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest packages/jw-mcp/tests/test_lookup_song_tool.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-mcp/src/jw_mcp/server.py packages/jw-mcp/tests/test_lookup_song_tool.py
git commit -m "feat(jw-mcp): lookup_song tool (metadata-only, no lyrics)"
```

---

### Task 8: MCP tool `songs_for_week`

**Files:**
- Modify: `packages/jw-mcp/src/jw_mcp/server.py`
- Create: `packages/jw-mcp/tests/test_songs_for_week_tool.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-mcp/tests/test_songs_for_week_tool.py
from __future__ import annotations

from typing import Any

import pytest


@pytest.mark.asyncio
async def test_songs_for_week_with_stubbed_workbook(monkeypatch) -> None:
    """Stub workbook_helper so the test stays offline; verify the tool
    extracts the kingdom_song findings produced by enrich_with_songs."""

    from jw_agents.base import AgentResult, Citation, Finding
    from jw_mcp import server as srv

    async def fake_workbook_helper(*args: Any, **kwargs: Any):
        result = AgentResult(query="2026-W23", agent_name="workbook_helper")
        result.metadata["week_of"] = "2026-06-08"
        result.findings.append(
            Finding(
                summary="Workbook week",
                excerpt="Proverbios 1-3",
                citation=Citation(
                    url="https://wol.jw.org/example",
                    title="x",
                    kind="workbook_week",
                    metadata={"songs": {"opening": 5, "middle": 47, "closing": 151}},
                ),
                metadata={"source": "workbook_week"},
            )
        )
        return result

    monkeypatch.setattr(srv, "_workbook_helper_agent", fake_workbook_helper, raising=False)

    out = await srv.songs_for_week(date="2026-06-08", language="es")
    assert out["week_of"] == "2026-06-08"
    assert len(out["songs"]) == 3
    slots = {s["slot"] for s in out["songs"]}
    assert slots == {"opening", "middle", "closing"}
    numbers = {s["number"] for s in out["songs"]}
    assert numbers == {5, 47, 151}
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/python -m pytest packages/jw-mcp/tests/test_songs_for_week_tool.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement the tool**

In `packages/jw-mcp/src/jw_mcp/server.py`, ensure there is a module-level reference to the workbook helper agent that the test can patch:

```python
from jw_agents import workbook_helper as _workbook_helper_agent
```

(Most likely already imported with a different name — keep this exact alias for the test.)

Then add the tool:

```python
@mcp.tool()
async def songs_for_week(
    date: str | None = None,
    language: str = "en",
) -> dict[str, Any]:
    """Resolve the workbook for the meeting week containing `date` (ISO,
    default today) and return the three kingdom-song metadata entries
    (opening / middle / closing) for that week.

    Output shape:
        {
          "week_of": "2026-06-08",
          "language": "es",
          "songs": [
             {"slot": "opening", "number": 5, "title": "...", "theme": "...",
              "scriptures": [...], "canonical_url": "..."},
             ...
          ],
          "warnings": [...]
        }
    """

    try:
        result = await _workbook_helper_agent(
            date, language=language, include_comments=False
        )
    except Exception as exc:  # noqa: BLE001
        return {"error": f"workbook_helper failed: {exc!r}"}

    _enrich_with_songs(result, language=language)

    songs: list[dict[str, Any]] = []
    for f in result.findings:
        if f.metadata.get("source") != "kingdom_song":
            continue
        meta = f.citation.metadata
        songs.append(
            {
                "slot": meta.get("slot"),
                "number": meta.get("number"),
                "title": f.citation.title,
                "theme": f.excerpt,
                "scriptures": meta.get("scriptures") or [],
                "canonical_url": f.citation.url,
            }
        )

    return {
        "week_of": result.metadata.get("week_of", ""),
        "language": language,
        "songs": songs,
        "warnings": list(result.warnings),
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest packages/jw-mcp/tests/test_songs_for_week_tool.py -v`
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-mcp/src/jw_mcp/server.py packages/jw-mcp/tests/test_songs_for_week_tool.py
git commit -m "feat(jw-mcp): songs_for_week tool composing workbook_helper + enrich"
```

---

### Task 9: Documentation guide

**Files:**
- Create: `docs/guias/canticos-del-reino.md`

- [ ] **Step 1: Write the guide**

```markdown
# Cánticos del Reino — guía de uso

> Módulo de metadatos de los Cánticos del Reino del cancionero `sjj` ("Cantemos con gozo a Jehová"). **No incluye letra** — solo número, título, tema en una línea y referencias bíblicas relacionadas. Disponible desde Fase 30.

## Política de copyright (lee esto primero)

Las letras de los cánticos pertenecen a Watch Tower Bible and Tract Society of Pennsylvania. Este toolkit:

- **No almacena letra** de ninguna estrofa, ni fragmento.
- **No distribuye** partitura, MP3, MIDI ni enlaces directos a esos archivos.
- **Sí almacena** información factual: número, título oficial, tema en paráfrasis propia del contribuidor, y las referencias bíblicas que el cántico desarrolla.

El cancionero completo (151 cánticos con letra y música) está en la app oficial **JW Library** y en jw.org. Si necesitas la letra, ve allí.

## Qué puedes hacer

### Buscar metadatos de un cántico

```bash
jw song 5 --lang es
```

```
┌─ Kingdom Song #5 ─────────────────────────────────────┐
│ Number      5                                         │
│ Title       El amor abnegado de Cristo                │
│ Theme       El amor sacrificial de Cristo como modelo│
│             para los cristianos.                      │
│ Scriptures  Juan 13:34-35, 1 Juan 3:16                │
│ URL         https://www.jw.org/finder?wtlocale=S&...  │
│ Publication sjj                                       │
│ Language    es                                        │
└───────────────────────────────────────────────────────┘
```

### Ver los cánticos de la semana

```bash
jw song week --lang es
jw song week --date 2026-07-13 --lang pt
```

Compone el `workbook_helper` con el adaptador `enrich_with_songs` y muestra solo los tres slots: apertura/intermedio/cierre.

### Desde Claude Desktop (MCP)

- `lookup_song(number=5, language="es")` — metadatos por número.
- `songs_for_week(date="2026-06-08", language="es")` — los tres cánticos de la semana.

### Desde Python

```python
from jw_core.songs import get_registry, enrich_with_songs

registry = get_registry("es")
song = registry.lookup(5)
print(song.title, song.scriptures)
for ref in song.resolved_scriptures():
    print(ref.book_num, ref.chapter, ref.verse)

# Adaptador para el workbook helper
from jw_agents import workbook_helper
result = await workbook_helper(language="es")
enrich_with_songs(result, language="es")
song_findings = [f for f in result.findings
                 if f.metadata.get("source") == "kingdom_song"]
```

## Cobertura del seed

El seed inicial incluye **12 cánticos** en cada uno de en/es/pt:

| # | Razón de inclusión |
|---|---|
| 1, 2 | Apertura frecuente; las cualidades y nombre de Jehová |
| 5 | Amor cristiano (uso muy frecuente) |
| 17 | "Iré, envíame a mí" (asambleas, asignaciones) |
| 20, 60 | Conmemoración |
| 47 | Oración diaria |
| 95, 102 | Luz progresiva / juventud |
| 109 | Amor entre hermanos |
| 134 | Familia |
| 151 | Esperanza de la resurrección |

**No es exhaustivo y no pretende serlo**. La cobertura de los 151 cánticos completos está en la app JW Library oficial. Las contribuciones para añadir más entradas son bienvenidas vía PR — cada PR debe pasar `test_seed_integrity` (que enforza ausencia de letra y paralelismo en/es/pt).

## Cómo contribuir una entrada

1. Edita los tres archivos a la vez:
   - `packages/jw-core/src/jw_core/data/kingdom_songs/E.json`
   - `packages/jw-core/src/jw_core/data/kingdom_songs/S.json`
   - `packages/jw-core/src/jw_core/data/kingdom_songs/T.json`
2. Cada entrada con: `number`, `title` (oficial), `theme` (paráfrasis de una línea, ≤120 chars, **sin copiar la letra**), `scriptures` (referencias parseables por `parse_reference`).
3. Ejecuta `pytest packages/jw-core/tests/test_kingdom_songs.py -v`.
4. Si añades más de 20 entradas en un PR, divide en PRs más pequeños.

## Lo que NO está en esta fase

- Búsqueda por tema/palabra clave en el catálogo (potencial Fase 31+).
- Cánticos favoritos del usuario o playlists (privacidad/local-first; no urgente).
- Audio / partituras / MP3. Cubierto por la app oficial.

## Verificar al cerrar

```bash
.venv/bin/python -m pytest packages/jw-core/tests/test_kingdom_songs.py
jw song 5 --lang es
jw song week --lang en
```
```

- [ ] **Step 2: Commit**

```bash
git add docs/guias/canticos-del-reino.md
git commit -m "docs: kingdom songs usage guide with copyright policy"
```

---

### Task 10: Update `docs/ROADMAP.md` and `docs/VISION_AUDIT.md`

**Files:**
- Modify: `docs/ROADMAP.md`
- Modify: `docs/VISION_AUDIT.md`

- [ ] **Step 1: Append Fase 30 to ROADMAP**

After the Fase 20 section (or last existing fase block) append:

```markdown

---

## Fase 30 — Compañero de cánticos del Reino ✅

> Objetivo: registro local de metadatos de Cánticos del Reino (`sjj`) — número, títulos en/es/pt, tema en una línea, referencias bíblicas citadas, URL canónica en jw.org. Sin letra (copyright). Integración opt-in con `workbook_helper`. Spec en [`superpowers/specs/2026-05-30-fase-30-kingdom-songs-design.md`](superpowers/specs/2026-05-30-fase-30-kingdom-songs-design.md).

- ✅ `jw_core.data.kingdom_songs/{E,S,T}.json` — seed de 12 cánticos paralelos en los 3 idiomas.
- ✅ `jw_core.songs.models.KingdomSong` (Pydantic, máximo 200 chars en `theme`, scriptures parseables).
- ✅ `jw_core.songs.registry.SongRegistry` con `importlib.resources` + `lru_cache` por idioma.
- ✅ `jw_core.songs.integration.enrich_with_songs` — adapter idempotente para `workbook_helper`.
- ✅ Test de integridad anti-letra (`test_seed_integrity`).
- ✅ CLI `jw song <N>` y `jw song week`.
- ✅ Tools MCP `lookup_song`, `songs_for_week`.
- ✅ Guía `docs/guias/canticos-del-reino.md` con sección legal al frente.
```

- [ ] **Step 2: Append VISION_AUDIT row**

Find the "Resumen ejecutivo" table and ensure the row for VISION sección #8 references this fase. If a row exists, expand it; otherwise add:

```markdown
| 8. Cánticos del Reino (apoyo a reunión/estudio personal) | ✅ Cubierto | Fase 30 — registro de metadatos sin letra (jw_core.songs) |
```

(Edit only what is needed; do not rewrite existing rows.)

- [ ] **Step 3: Commit**

```bash
git add docs/ROADMAP.md docs/VISION_AUDIT.md
git commit -m "docs: add Fase 30 to roadmap + vision audit (kingdom songs)"
```

---

### Task 11: Full suite + smoke + audit checklist

**Files:** none (verification only)

- [ ] **Step 1: Run full test suite**

Run: `.venv/bin/python -m pytest`
Expected: 551 prior tests still pass + the 16 new tests from this fase ⇒ ≥ 563 passed. **Zero regressions.**

- [ ] **Step 2: CLI smoke**

Run each:
```bash
.venv/bin/jw song 5 --lang en
.venv/bin/jw song 5 --lang es
.venv/bin/jw song 5 --lang pt
.venv/bin/jw song 999 --lang en       # exit 1
.venv/bin/jw song --lang en           # exit 2 (missing arg)
```

- [ ] **Step 3: MCP smoke**

```bash
.venv/bin/python -c "
from jw_mcp.server import lookup_song
import json
print(json.dumps(lookup_song(number=5, language='es'), indent=2, ensure_ascii=False))
"
```
Expected: a JSON blob with `number`, `title`, `theme`, `canonical_url`, `scriptures_resolved`.

- [ ] **Step 4: Lint**

Run:
```bash
.venv/bin/ruff check packages/jw-core/src/jw_core/songs packages/jw-cli/src/jw_cli/commands/song.py
.venv/bin/ruff format --check packages/jw-core/src/jw_core/songs packages/jw-cli/src/jw_cli/commands/song.py
.venv/bin/mypy packages/jw-core/src/jw_core/songs
```

Fix anything that fails. Commit fixes as `style(jw-core): ruff/mypy on jw_core.songs`.

- [ ] **Step 5: Final check — copyright guardrail**

Manually inspect the three JSON files:

```bash
grep -iE "verse|chorus|estrofa|estribillo|refrão|refrain|©" \
  packages/jw-core/src/jw_core/data/kingdom_songs/*.json
```
Expected: no matches. If anything turns up — remove or rephrase, then re-run `test_seed_integrity`.

- [ ] **Step 6: Done**

No commit at this step — this is verification.

---

### Task 12: PR + close fase

**Files:** none (operational)

- [ ] **Step 1: Branch + push**

```bash
git checkout -b feature/fase-30-kingdom-songs
git push -u origin feature/fase-30-kingdom-songs
```

- [ ] **Step 2: Open PR**

Title: `feat(songs): Fase 30 — kingdom songs metadata registry (no lyrics)`

Body (template):
```
## Summary
- Adds `jw_core.songs` — metadata-only Kingdom Songs registry (no lyrics) with 12-song seeds in en/es/pt.
- New adapter `enrich_with_songs(AgentResult)` integrates opt-in with `workbook_helper`.
- New CLI: `jw song <N>` and `jw song week`.
- New MCP tools: `lookup_song`, `songs_for_week`.
- Documented copyright stance in `docs/guias/canticos-del-reino.md`.

## Test plan
- [x] `pytest packages/jw-core/tests/test_kingdom_songs.py` — 16 passed.
- [x] `pytest` — 567 passed, 0 failed.
- [x] Manual smoke: `jw song 5 --lang es`, `jw song week`.
- [x] `lookup_song(5, "es")` via MCP returns metadata + resolved scriptures.
- [x] `grep -iE "verse|chorus|estrofa|refrão" data/kingdom_songs/*.json` — zero matches.

Spec: docs/superpowers/specs/2026-05-30-fase-30-kingdom-songs-design.md
Plan: docs/superpowers/plans/2026-05-30-fase-30-kingdom-songs-plan.md
```

- [ ] **Step 2: Done.**

---

## Self-review

Before declaring the plan finished, the implementer should verify each of these claims by re-reading the spec:

1. The registry **never** carries lyrics. Test `test_seed_integrity` enforces this with forbidden tokens and a 200-char cap. Manual grep step at Task 11 confirms.
2. The integration with `workbook_helper` is **non-destructive** — the agent code is untouched; `enrich_with_songs` is a separate adapter that callers opt into. Test `test_enrich_no_workbook_week_finding_is_noop` confirms the adapter degrades cleanly.
3. **Local-first / no network**: `jw_core.songs.registry` uses `importlib.resources` only. `_derive_canonical_url` returns a string with no HTTP. The only network in this fase is whatever `workbook_helper` already does (cached). MCP tool `lookup_song` has zero red flag for network usage.
4. **Idempotency** of `enrich_with_songs` is tested explicitly.
5. **Multi-language**: en/es/pt seeds + `_WTLOCALE_FOR_ISO` map. Unknown languages return empty registries with a warning, not an error.
6. **Citations verifiable**: `KingdomSong.resolved_scriptures()` produces `BibleRef` instances that already have `wol_url()`.
7. **Spec ⇄ plan parity**: every "decision" in the spec (loader via importlib.resources, fallback URL pattern, anti-lyrics test, opt-in integration, 12-song seed) appears as a task or step in this plan.

## Execution choice

Recommended for the implementer: **`superpowers:subagent-driven-development`** with one sub-agent per task. Tasks 1-5 are mostly file scaffolding and pure CPU TDD; tasks 6-8 touch the CLI and MCP surfaces and benefit from isolation; tasks 9-12 are docs + verification.

Alternative: **`superpowers:executing-plans`** linearly — viable because there are no inter-task ambiguities and every task is self-contained with explicit file paths.

Either choice converges to the same diff; pick subagents if the harness is healthy (faster wall time), executing-plans if you want sequential safety.
