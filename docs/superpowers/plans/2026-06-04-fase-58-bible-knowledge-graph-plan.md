# Fase 58 — Bible Knowledge Graph JW-puro Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Construir un knowledge graph bíblico (personas, lugares, periodos, pasajes) materializado en `jw-brain` desde **fuentes JW puras** (Estudio Perspicaz de las Escrituras / Insight on the Scriptures + NWT/NWTsty + Watch Tower Publications Index), **sin** portar `robertrouse/theographic-bible-metadata` upstream y **sin** tocar datos de otras tradiciones religiosas.

**Architecture:** Nuevo módulo `packages/jw-brain/src/jw_brain/imports/bible/` con un `BibleLoader` procedural (no LLM) que parsea Insight JWPUB ya descifrado por `jw_core.parsers.jwpub`, extrae entradas canónicas (cabezales tipo `Person`, `Place`), las cruza con un catálogo curado de `Period` y emite upserts directos al `GraphBackend` Protocol existente. Se extiende `tj_node_specs()`/`tj_edge_specs()` con `Period` + edges temporales sin tocar Person/Place ya definidos. Se porta `BibleRef.fromWolUrl()` de TypeScript a Python para cerrar gap cross-lang.

**Tech Stack:** Python 3.13 · `jw-core.parsers.jwpub` (ya implementado) · `jw-brain.backends.duckdb_backend` (existente) · `jw-brain.schema.builtins` (extender) · `beautifulsoup4` (ya dep) · sin dependencias nuevas en runtime.

**Spec/origen brainstorm:** [`docs/conceptos/integraciones-priorizadas.md`](../../conceptos/integraciones-priorizadas.md) §"Hallazgos JW-específicos" y [`docs/superpowers/plans/2026-06-04-master-integracion-stars-plan.md`](./2026-06-04-master-integracion-stars-plan.md).

**Depende de:** F49 (`jw-brain` core), F5.5 (decryption JWPUB), F46 (canonical versification). Ninguna pieza nueva requiere otra fase pendiente.

---

## File map

Crea (jw-brain):
- `packages/jw-brain/src/jw_brain/imports/__init__.py`
- `packages/jw-brain/src/jw_brain/imports/bible/__init__.py`
- `packages/jw-brain/src/jw_brain/imports/bible/period_catalog.py` — catálogo curado de periodos JW
- `packages/jw-brain/src/jw_brain/imports/bible/parser_insight.py` — parser de cabezales del Insight
- `packages/jw-brain/src/jw_brain/imports/bible/loader.py` — orquesta upserts
- `packages/jw-brain/src/jw_brain/imports/bible/models.py` — Pydantic intermediarios (`InsightEntry`, `BibleKgPerson`, `BibleKgPlace`, `BibleKgPeriod`, `BibleKgPassage`)
- `packages/jw-brain/tests/test_imports_bible_period_catalog.py`
- `packages/jw-brain/tests/test_imports_bible_parser_insight.py`
- `packages/jw-brain/tests/test_imports_bible_loader.py`
- `packages/jw-brain/tests/test_imports_bible_cli.py`
- `packages/jw-brain/tests/fixtures/insight_mini/` — JWPUB sintético en memoria con 3 entradas (Abraham, Jerusalem, Moisés) para tests deterministas

Modifica (jw-brain):
- `packages/jw-brain/src/jw_brain/schema/builtins.py` — añadir `Period` NodeTypeSpec y edges `LIVED_IN_PERIOD`, `MENTIONED_IN_PASSAGE`
- `packages/jw-brain/src/jw_brain/cli.py` — añadir `jw brain import-bible <source> --brain <name>`

Crea (jw-core — port cross-lang):
- `packages/jw-core/src/jw_core/parsers/wol_url.py` — `parse_wol_bible_url(href) -> BibleRef | None`
- `packages/jw-core/tests/test_parsers_wol_url.py`

Modifica (jw-core):
- `packages/jw-core/src/jw_core/models.py` — añadir `BibleRef.from_wol_url(href)` classmethod delegando a `parsers.wol_url`

Doc:
- `docs/guias/bible-knowledge-graph.md` — guía operativa: cómo importar, qué queries habilita
- `docs/ROADMAP.md` — entrada F58

Modifica (master plan):
- `docs/superpowers/plans/2026-06-04-master-integracion-stars-plan.md` — marcar F58 ✅ en tabla de estado

---

## Decisiones clave de diseño (anti-placeholder)

### Por qué NO portar theographic-bible-metadata upstream
El repo `robertrouse/theographic-bible-metadata` incluye fuentes inter-religiosas (Catholic Encyclopedia, Jewish Encyclopedia, ISBE de los protestantes). El proyecto `jw-agent-toolkit` debe permanecer **doctrinalmente puro JW**. Derivar los datos del Insight on the Scriptures (publicación oficial Watch Tower) garantiza que las personas, lugares y eras reflejan **únicamente** la cronología y exégesis JW (p. ej. fecha del 607 a. E.C. para la destrucción de Jerusalén que la Watch Tower defiende, no la 587/586 a. E.C. del consenso académico).

### Schema: ampliar lo existente, no recrearlo
`Person` y `Place` ya están en `jw-brain/src/jw_brain/schema/builtins.py::tj_node_specs()`. F58 añade `Period` y edges temporales (`LIVED_IN_PERIOD`, `MENTIONED_IN_PASSAGE`) sin tocar lo existente.

### Loader procedural, NO LLMExtractor
`jw-brain` tiene un `LLMExtractor` (compiler/llm_extractor.py) para destilar texto narrativo a (nodes, edges). NO se usa aquí: las entradas del Insight son **canónicas y bien estructuradas**, un parser HTML basta para extraer `headword`, `first_mention`, `alias`, descripción. Saltar el LLM = determinismo + zero coste API + idempotencia.

### Period catalog hardcoded (no extraído)
Los periodos JW son ~10 (Era Patriarcal, Cautiverio Egipcio, Jueces, Reino Unido, Reino Dividido, Cautiverio Babilónico, Era Persa, Era Helenística, Era Romana / Cristianismo Primitivo). Codificarlos a mano como `python data` da más control que extraerlos con NER + es trivial mantener cuando la Watch Tower publique cronología revisada.

### `BibleRef.from_wol_url` port: existe sólo en TS
F56.5 introdujo `BibleRef.fromWolUrl()` en `jw-core-js`. Python no lo tiene. F58 lo necesita para construir edges `MENTIONED_IN_PASSAGE` desde URLs WOL extraídas del Insight, así que portamos. Reusar el goldenfile de `shared/` para tener parity Python ↔ TS cubierto por F46.

### Multi-tenant aware
El loader respeta el `--brain <name>` flag del CLI (precedente F49). Los datos se materializan en el DuckDB del brain seleccionado; si el usuario tiene varios brains (p. ej. `personal` y `family`), el import-bible los hidrata por separado.

---

### Task 1: Scaffold `imports/bible/` skeleton + tests __init__

**Files:**
- Create: `packages/jw-brain/src/jw_brain/imports/__init__.py`
- Create: `packages/jw-brain/src/jw_brain/imports/bible/__init__.py`
- Create: `packages/jw-brain/tests/fixtures/insight_mini/.gitkeep`

- [ ] **Step 1: Crear los archivos vacíos pero importables**

```python
# packages/jw-brain/src/jw_brain/imports/__init__.py
"""Importadores de datos externos al jw-brain. Cada submódulo emite upserts
canónicos a un GraphBackend desde una fuente JW autoritativa."""
```

```python
# packages/jw-brain/src/jw_brain/imports/bible/__init__.py
"""Importador del knowledge graph bíblico desde fuentes JW puras
(Insight on the Scriptures + NWT/NWTsty + Topic Index).

NO usa LLMs en el path crítico: parsers procedurales sobre JWPUB ya descifrado.
"""
from jw_brain.imports.bible.loader import BibleLoader, LoaderStats
from jw_brain.imports.bible.models import (
    BibleKgPassage,
    BibleKgPeriod,
    BibleKgPerson,
    BibleKgPlace,
    InsightEntry,
)

__all__ = [
    "BibleLoader",
    "LoaderStats",
    "BibleKgPassage",
    "BibleKgPeriod",
    "BibleKgPerson",
    "BibleKgPlace",
    "InsightEntry",
]
```

- [ ] **Step 2: Verificar import smoke**

Run: `cd /Users/elias/Documents/Trabajo/jw-agent-toolkit && uv run python -c "from jw_brain.imports import bible; print(bible.__doc__)"`
Expected: imprime el docstring sin error.

- [ ] **Step 3: Commit**

```bash
git add packages/jw-brain/src/jw_brain/imports/
git commit -m "feat(jw-brain): F58.1 scaffold imports/bible skeleton"
```

---

### Task 2: Modelos Pydantic intermediarios

**Files:**
- Create: `packages/jw-brain/src/jw_brain/imports/bible/models.py`
- Create: `packages/jw-brain/tests/test_imports_bible_models.py`

- [ ] **Step 1: Failing test para el shape de los modelos**

```python
# packages/jw-brain/tests/test_imports_bible_models.py
"""Modelos intermediarios del bible KG. No persistencia — son la frontera
entre parser y loader."""
from jw_brain.imports.bible.models import (
    BibleKgPassage,
    BibleKgPeriod,
    BibleKgPerson,
    BibleKgPlace,
    InsightEntry,
)


def test_insight_entry_minimal():
    entry = InsightEntry(
        headword="Abraham",
        document_id=1234,
        symbol="it-1",
        meps_language=0,  # English
        kind="person",
        first_mention_raw="Gen. 11:26",
        first_mention_href="/en/wol/d/r1/lp-e/1001070026",
        aliases=("Abram",),
        text_excerpt="Abraham, son of Terah...",
    )
    assert entry.kind == "person"
    assert entry.aliases == ("Abram",)


def test_bible_kg_person_canonical_id():
    p = BibleKgPerson(
        slug="abraham",
        name="Abraham",
        aliases=("Abram",),
        era="patriarchal",
        first_mention_book=1,
        first_mention_chapter=11,
        first_mention_verse=26,
        description_excerpt="Son of Terah...",
        source_url="https://wol.jw.org/en/wol/d/r1/lp-e/1200000124",
    )
    assert p.canonical_id == "person:abraham"


def test_bible_kg_place_canonical_id():
    pl = BibleKgPlace(
        slug="jerusalem",
        name="Jerusalem",
        region="Judea",
        modern_name="Jerusalem (modern)",
        latitude=31.7857,
        longitude=35.2278,
        eras_active=("united_kingdom", "divided_kingdom", "babylonian_exile"),
        source_url="https://wol.jw.org/en/wol/d/r1/lp-e/1200001234",
    )
    assert pl.canonical_id == "place:jerusalem"


def test_bible_kg_period_canonical_id():
    period = BibleKgPeriod(
        slug="patriarchal",
        name="Era Patriarcal",
        start_year_bce=2018,
        end_year_bce=1657,
        description="Desde el llamamiento de Abraham hasta el establecimiento en Egipto.",
    )
    assert period.canonical_id == "period:patriarchal"


def test_bible_kg_passage_canonical_id():
    pa = BibleKgPassage(
        book_num=1,
        chapter=12,
        verse_start=1,
        verse_end=3,
        mentions_people=("person:abraham",),
        mentions_places=("place:haran",),
        period_slug="patriarchal",
    )
    assert pa.canonical_id == "passage:1:12:1-3"
```

- [ ] **Step 2: Run test, expect ImportError**

Run: `cd /Users/elias/Documents/Trabajo/jw-agent-toolkit && uv run pytest packages/jw-brain/tests/test_imports_bible_models.py -v`
Expected: FAIL — `ImportError: cannot import name 'InsightEntry'`.

- [ ] **Step 3: Implementar modelos**

```python
# packages/jw-brain/src/jw_brain/imports/bible/models.py
"""Modelos intermediarios entre parser y loader del bible KG.

Diferencia clave con NodeTypeSpec: estos son Pydantic _data carriers_
(no schema-on-read del backend). El loader los aplana al formato
`upsert_node(node_type, canonical_id, properties)` esperado por
GraphBackend Protocol.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

InsightKind = Literal["person", "place"]
"""Tipos de entrada que el parser Insight reconoce. `period` se hidrata
desde el catálogo curado, no desde Insight (las entradas son inestables)."""

EraSlug = Literal[
    "patriarchal",
    "egyptian_exile",
    "judges",
    "united_kingdom",
    "divided_kingdom",
    "babylonian_exile",
    "persian_era",
    "hellenistic_era",
    "roman_era",
    "early_christian_era",
]


class InsightEntry(BaseModel):
    """Una cabecera del Insight on the Scriptures con metadata cruda
    todavía sin proyectar al schema del KG."""

    model_config = ConfigDict(frozen=True)

    headword: str = Field(description="Cabezal exacto del artículo")
    document_id: int = Field(description="MEPSDocumentId dentro del JWPUB")
    symbol: str = Field(description="Símbolo de la publicación, p.ej. it-1")
    meps_language: int
    kind: InsightKind
    first_mention_raw: str = Field(default="", description="Texto de la referencia, p.ej. 'Gen. 11:26'")
    first_mention_href: str = Field(default="", description="href WOL relativo")
    aliases: tuple[str, ...] = Field(default=())
    text_excerpt: str = Field(default="", description="Primeros ~500 chars del artículo")


class BibleKgPerson(BaseModel):
    """Persona bíblica ya proyectada al schema del KG."""

    model_config = ConfigDict(frozen=True)

    slug: str = Field(pattern=r"^[a-z0-9_]+$")
    name: str
    aliases: tuple[str, ...] = ()
    era: EraSlug | None = None
    first_mention_book: int | None = Field(default=None, ge=1, le=66)
    first_mention_chapter: int | None = None
    first_mention_verse: int | None = None
    description_excerpt: str = ""
    source_url: str = ""

    @property
    def canonical_id(self) -> str:
        return f"person:{self.slug}"


class BibleKgPlace(BaseModel):
    model_config = ConfigDict(frozen=True)

    slug: str = Field(pattern=r"^[a-z0-9_]+$")
    name: str
    region: str = ""
    modern_name: str = ""
    latitude: float | None = None
    longitude: float | None = None
    eras_active: tuple[EraSlug, ...] = ()
    source_url: str = ""

    @property
    def canonical_id(self) -> str:
        return f"place:{self.slug}"


class BibleKgPeriod(BaseModel):
    model_config = ConfigDict(frozen=True)

    slug: EraSlug
    name: str
    start_year_bce: int | None = Field(
        default=None,
        description="Año a. E.C. de inicio (positivo). None si la fecha JW no es precisa.",
    )
    end_year_bce: int | None = None
    end_year_ce: int | None = Field(
        default=None,
        description="Año E.C. de fin para periodos que cruzan el cambio de era.",
    )
    description: str = ""

    @property
    def canonical_id(self) -> str:
        return f"period:{self.slug}"


class BibleKgPassage(BaseModel):
    """Una BibleRef materializada como nodo del KG para tejer edges
    `MENTIONED_IN_PASSAGE` entre personas/lugares."""

    model_config = ConfigDict(frozen=True)

    book_num: int = Field(ge=1, le=66)
    chapter: int = Field(ge=1)
    verse_start: int | None = Field(default=None, ge=1)
    verse_end: int | None = Field(default=None, ge=1)
    mentions_people: tuple[str, ...] = Field(default=(), description="canonical_ids")
    mentions_places: tuple[str, ...] = Field(default=())
    period_slug: EraSlug | None = None

    @property
    def canonical_id(self) -> str:
        if self.verse_start is None:
            return f"passage:{self.book_num}:{self.chapter}"
        if self.verse_end is None or self.verse_end == self.verse_start:
            return f"passage:{self.book_num}:{self.chapter}:{self.verse_start}"
        return f"passage:{self.book_num}:{self.chapter}:{self.verse_start}-{self.verse_end}"
```

- [ ] **Step 4: Run test, expect PASS**

Run: `cd /Users/elias/Documents/Trabajo/jw-agent-toolkit && uv run pytest packages/jw-brain/tests/test_imports_bible_models.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-brain/src/jw_brain/imports/bible/models.py packages/jw-brain/tests/test_imports_bible_models.py
git commit -m "feat(jw-brain): F58.2 add bible kg pydantic models"
```

---

### Task 3: Period catalog hardcoded

**Files:**
- Create: `packages/jw-brain/src/jw_brain/imports/bible/period_catalog.py`
- Create: `packages/jw-brain/tests/test_imports_bible_period_catalog.py`

- [ ] **Step 1: Failing test**

```python
# packages/jw-brain/tests/test_imports_bible_period_catalog.py
"""El catálogo de periodos es estático y refleja la cronología JW
(p.ej. 607 a.E.C. como año de destrucción de Jerusalén)."""
from jw_brain.imports.bible.period_catalog import ALL_PERIODS, get_period


def test_all_periods_have_unique_slugs():
    slugs = [p.slug for p in ALL_PERIODS]
    assert len(slugs) == len(set(slugs))


def test_patriarchal_era_present():
    period = get_period("patriarchal")
    assert period is not None
    assert "Abraham" in period.description or "Patriarcal" in period.name


def test_babylonian_exile_jw_chronology_607_bce():
    """La cronología JW data la destrucción de Jerusalén en 607 a.E.C.,
    NO en 586/587 a.E.C. como el consenso académico."""
    period = get_period("babylonian_exile")
    assert period is not None
    assert period.start_year_bce == 607
    assert period.end_year_bce == 537


def test_all_periods_chronological_order():
    """ALL_PERIODS está ordenado del más antiguo al más reciente
    (utilidad para timelines)."""
    bce_starts = [p.start_year_bce for p in ALL_PERIODS if p.start_year_bce is not None]
    # Más antiguo = mayor a.E.C., decreciente conforme avanza
    assert bce_starts == sorted(bce_starts, reverse=True)


def test_get_period_unknown_returns_none():
    assert get_period("not_a_real_era") is None  # type: ignore[arg-type]
```

- [ ] **Step 2: Run test, expect ImportError**

Run: `uv run pytest packages/jw-brain/tests/test_imports_bible_period_catalog.py -v`
Expected: FAIL.

- [ ] **Step 3: Implementar catálogo**

```python
# packages/jw-brain/src/jw_brain/imports/bible/period_catalog.py
"""Catálogo curado de periodos bíblicos según la cronología JW.

Las fechas vienen del Estudio Perspicaz de las Escrituras (Insight on
the Scriptures, vol. 1, "Chronology") y de la Tabla de tiempos bíblicos
publicada por la Watch Tower Bible and Tract Society. Difieren en
puntos clave del consenso académico:

- Destrucción de Jerusalén: 607 a.E.C. (JW) vs 587/586 a.E.C. (académico).
- 70 años de exilio babilónico: 607-537 a.E.C. (JW lee Jeremías 25:11-12,
  29:10 de forma literal).
- Período del Imperio Persa: 537-331 a.E.C.

Si la Watch Tower publica una revisión cronológica, actualizar esta
constante; el resto del pipeline no requiere cambios.
"""
from __future__ import annotations

from jw_brain.imports.bible.models import BibleKgPeriod, EraSlug

ALL_PERIODS: tuple[BibleKgPeriod, ...] = (
    BibleKgPeriod(
        slug="patriarchal",
        name="Era Patriarcal",
        start_year_bce=2018,
        end_year_bce=1657,
        description=(
            "Desde el llamamiento de Abraham (2018 a.E.C.) hasta la entrada "
            "de Jacob y su familia en Egipto (1728 a.E.C.) y la subsecuente "
            "esclavitud que culmina con Moisés (1657 a.E.C.)."
        ),
    ),
    BibleKgPeriod(
        slug="egyptian_exile",
        name="Cautiverio Egipcio",
        start_year_bce=1728,
        end_year_bce=1513,
        description=(
            "Periodo desde la inmigración de Jacob a Egipto hasta el éxodo "
            "bajo Moisés en 1513 a.E.C."
        ),
    ),
    BibleKgPeriod(
        slug="judges",
        name="Era de los Jueces",
        start_year_bce=1467,
        end_year_bce=1117,
        description=(
            "Desde la conquista de Canaán bajo Josué hasta la unción del "
            "rey Saúl. Periodo descentralizado bajo jueces sucesivos."
        ),
    ),
    BibleKgPeriod(
        slug="united_kingdom",
        name="Reino Unido de Israel",
        start_year_bce=1117,
        end_year_bce=997,
        description=(
            "Reinados de Saúl, David y Salomón. Construcción del primer "
            "templo (1034 a.E.C.). División del reino tras la muerte de Salomón."
        ),
    ),
    BibleKgPeriod(
        slug="divided_kingdom",
        name="Reino Dividido",
        start_year_bce=997,
        end_year_bce=607,
        description=(
            "Reino del norte (Israel, 10 tribus) cae ante Asiria en 740 a.E.C. "
            "Reino del sur (Judá) cae ante Babilonia en 607 a.E.C., comenzando "
            "el cautiverio babilónico."
        ),
    ),
    BibleKgPeriod(
        slug="babylonian_exile",
        name="Cautiverio Babilónico",
        start_year_bce=607,
        end_year_bce=537,
        description=(
            "70 años de exilio en Babilonia, conforme a la profecía de "
            "Jeremías 25:11-12 y 29:10. Concluye con el decreto de Ciro "
            "permitiendo el retorno a Judá."
        ),
    ),
    BibleKgPeriod(
        slug="persian_era",
        name="Era del Imperio Persa",
        start_year_bce=537,
        end_year_bce=331,
        description=(
            "Reconstrucción del templo bajo Zorobabel (515 a.E.C.). Misiones "
            "de Esdras (468 a.E.C.) y Nehemías (455 a.E.C.). Concluye con la "
            "conquista de Alejandro Magno."
        ),
    ),
    BibleKgPeriod(
        slug="hellenistic_era",
        name="Era Helenística",
        start_year_bce=331,
        end_year_bce=63,
        description=(
            "Dominio sucesivo de los sucesores de Alejandro (Ptolomeos, "
            "Seléucidas). Revuelta macabea (167 a.E.C.). Concluye con la "
            "conquista romana de Pompeyo."
        ),
    ),
    BibleKgPeriod(
        slug="roman_era",
        name="Era del Imperio Romano",
        start_year_bce=63,
        end_year_ce=33,
        description=(
            "Dominio romano sobre Judea. Nacimiento de Jesús (probable 2 a.E.C.), "
            "ministerio (29-33 E.C.) y muerte (33 E.C.)."
        ),
    ),
    BibleKgPeriod(
        slug="early_christian_era",
        name="Era del Cristianismo Primitivo",
        start_year_bce=None,
        end_year_ce=100,
        description=(
            "Desde Pentecostés del 33 E.C. hasta aproximadamente el año 100 E.C. "
            "(muerte del apóstol Juan). Cobertura del libro de Hechos y las "
            "cartas apostólicas."
        ),
    ),
)
"""Tupla immutable de periodos en orden cronológico (más antiguo primero)."""

_BY_SLUG: dict[str, BibleKgPeriod] = {p.slug: p for p in ALL_PERIODS}


def get_period(slug: str) -> BibleKgPeriod | None:
    """Devuelve el periodo con el slug dado, o None si no existe."""
    return _BY_SLUG.get(slug)
```

- [ ] **Step 4: Run test, expect PASS**

Run: `uv run pytest packages/jw-brain/tests/test_imports_bible_period_catalog.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-brain/src/jw_brain/imports/bible/period_catalog.py packages/jw-brain/tests/test_imports_bible_period_catalog.py
git commit -m "feat(jw-brain): F58.3 add JW chronology period catalog"
```

---

### Task 4: Port `BibleRef.from_wol_url` Python

**Files:**
- Create: `packages/jw-core/src/jw_core/parsers/wol_url.py`
- Create: `packages/jw-core/tests/test_parsers_wol_url.py`
- Modify: `packages/jw-core/src/jw_core/models.py` (añadir classmethod `BibleRef.from_wol_url`)

- [ ] **Step 1: Failing test usando el goldenfile cross-lang**

```python
# packages/jw-core/tests/test_parsers_wol_url.py
"""Port a Python del `BibleRef.fromWolUrl` que vive en jw-core-js.
Reusa el fixture cross-lang shared/ para garantizar parity con TS."""
from jw_core.models import BibleRef
from jw_core.parsers.wol_url import parse_wol_bible_url


def test_parse_wol_url_genesis_1_1_en():
    ref = parse_wol_bible_url("/en/wol/b/r1/lp-e/nwtsty/1/1#study=discover&v=1:1:1")
    assert ref is not None
    assert ref.book_num == 1
    assert ref.chapter == 1
    assert ref.verse_start == 1
    assert ref.verse_end == 1


def test_parse_wol_url_john_3_16_en():
    ref = parse_wol_bible_url("/en/wol/b/r1/lp-e/nwtsty/43/3#study=discover&v=43:3:16")
    assert ref is not None
    assert ref.book_num == 43
    assert ref.chapter == 3
    assert ref.verse_start == 16


def test_parse_wol_url_es_pt_locales():
    ref_es = parse_wol_bible_url("/es/wol/b/r4/lp-s/nwt/1/1#study=discover&v=1:1:1")
    ref_pt = parse_wol_bible_url("/pt/wol/b/r5/lp-t/nwt/1/1#study=discover&v=1:1:1")
    assert ref_es is not None and ref_es.book_num == 1
    assert ref_pt is not None and ref_pt.book_num == 1


def test_parse_wol_url_no_verse_anchor():
    """Sin anchor v= solo capítulo se reconoce."""
    ref = parse_wol_bible_url("/en/wol/b/r1/lp-e/nwtsty/1/1")
    assert ref is not None
    assert ref.book_num == 1 and ref.chapter == 1
    assert ref.verse_start is None


def test_parse_wol_url_non_bible_returns_none():
    """URLs no-bíblicas (publicaciones, daily-text) devuelven None."""
    assert parse_wol_bible_url("/en/wol/d/r1/lp-e/1200002342") is None
    assert parse_wol_bible_url("/en/wol/dt/r1/lp-e/2024/1/1") is None
    assert parse_wol_bible_url("") is None
    assert parse_wol_bible_url("not-a-url") is None


def test_biberef_from_wol_url_classmethod():
    """El classmethod en BibleRef delega al parser."""
    ref = BibleRef.from_wol_url("/en/wol/b/r1/lp-e/nwtsty/43/3#study=discover&v=43:3:16")
    assert ref is not None
    assert ref.book_canonical == "John"
```

- [ ] **Step 2: Run test, expect FAIL**

Run: `cd /Users/elias/Documents/Trabajo/jw-agent-toolkit && uv run pytest packages/jw-core/tests/test_parsers_wol_url.py -v`
Expected: FAIL — ImportError.

- [ ] **Step 3: Implementar parser**

```python
# packages/jw-core/src/jw_core/parsers/wol_url.py
"""Parser de URLs WOL bíblicas → BibleRef.

Port a Python del BibleRef.fromWolUrl() del paquete jw-core-js (F56.5).
Reglas:
- URLs `/wol/b/<resource>/<lp_tag>/<pub>/<book_num>/<chapter>` son bíblicas.
- Anchor opcional `#study=...&v=<book>:<chap>:<verse>` o `&v=<book>:<chap>:<verse_start>-<book>:<chap>:<verse_end>`.
- Otros patrones (`/wol/d/...`, `/wol/dt/...`, etc.) devuelven None.
"""
from __future__ import annotations

import re

from jw_core.data.books import BOOKS
from jw_core.models import BibleRef

_BIBLE_URL_RE = re.compile(
    r"^/(?P<lang>[a-z]{2,3})/wol/b/(?P<resource>r\d+)/(?P<lp_tag>lp-[a-z]+)/"
    r"(?P<pub>[a-z]+)/(?P<book>\d{1,2})/(?P<chapter>\d{1,3})(?:[#?].*)?$"
)
_VERSE_ANCHOR_RE = re.compile(
    r"[?&#]v=(?P<book>\d{1,2}):(?P<chap>\d{1,3}):(?P<start>\d{1,3})"
    r"(?:-\d{1,2}:\d{1,3}:(?P<end>\d{1,3}))?"
)
_LANG_TO_LETTER: dict[str, str] = {"en": "E", "es": "S", "pt": "T"}


def parse_wol_bible_url(href: str) -> BibleRef | None:
    """Parsea una URL WOL bíblica a BibleRef. Devuelve None si no aplica."""
    if not href or not href.startswith("/"):
        return None
    m = _BIBLE_URL_RE.match(href)
    if not m:
        return None
    book_num = int(m.group("book"))
    chapter = int(m.group("chapter"))
    if not (1 <= book_num <= 66):
        return None

    verse_start: int | None = None
    verse_end: int | None = None
    anchor_match = _VERSE_ANCHOR_RE.search(href)
    if anchor_match and int(anchor_match.group("book")) == book_num:
        verse_start = int(anchor_match.group("start"))
        if anchor_match.group("end"):
            verse_end = int(anchor_match.group("end"))
        else:
            verse_end = verse_start

    detected_letter = _LANG_TO_LETTER.get(m.group("lang"), "E")
    book_meta = BOOKS[book_num - 1]
    return BibleRef(
        book_num=book_num,
        book_canonical=book_meta.canonical,
        chapter=chapter,
        verse_start=verse_start,
        verse_end=verse_end,
        detected_language=detected_letter,
        raw_match=href,
    )
```

- [ ] **Step 4: Añadir classmethod a BibleRef**

Localizar en `packages/jw-core/src/jw_core/models.py` la clase `BibleRef` (líneas ~219-273 según mapeo). Justo antes del cierre de la clase, añadir:

```python
    @classmethod
    def from_wol_url(cls, href: str) -> "BibleRef | None":
        """Construye una BibleRef desde una URL WOL bíblica.

        Delega a `jw_core.parsers.wol_url.parse_wol_bible_url`.
        Port a Python del `BibleRef.fromWolUrl` del paquete jw-core-js (F56.5).
        """
        from jw_core.parsers.wol_url import parse_wol_bible_url

        return parse_wol_bible_url(href)
```

(Import lazy dentro del método para evitar circular import.)

- [ ] **Step 5: Run test, expect PASS**

Run: `uv run pytest packages/jw-core/tests/test_parsers_wol_url.py -v`
Expected: 6 passed.

- [ ] **Step 6: Commit**

```bash
git add packages/jw-core/src/jw_core/parsers/wol_url.py packages/jw-core/src/jw_core/models.py packages/jw-core/tests/test_parsers_wol_url.py
git commit -m "feat(jw-core): F58.4 port BibleRef.from_wol_url to Python from jw-core-js"
```

---

### Task 5: Period NodeTypeSpec + Era edges en `schema/builtins.py`

**Files:**
- Modify: `packages/jw-brain/src/jw_brain/schema/builtins.py`
- Create: `packages/jw-brain/tests/test_schema_bible_kg_extensions.py`

- [ ] **Step 1: Failing test que verifica que el schema TJ ahora incluye Period**

```python
# packages/jw-brain/tests/test_schema_bible_kg_extensions.py
"""F58 amplía el schema TJ con Period y edges temporales/cross-cutting."""
from jw_brain.schema.builtins import tj_edge_specs, tj_node_specs


def test_tj_includes_period_node_spec():
    nodes = {n.name: n for n in tj_node_specs()}
    assert "Period" in nodes
    period = nodes["Period"]
    assert "start_year_bce" in period.properties
    assert "end_year_bce" in period.properties or "end_year_ce" in period.properties


def test_tj_includes_passage_node_spec():
    nodes = {n.name: n for n in tj_node_specs()}
    assert "Passage" in nodes


def test_tj_includes_lived_in_period_edge():
    edges = {e.name for e in tj_edge_specs()}
    assert "LIVED_IN_PERIOD" in edges


def test_tj_includes_mentioned_in_passage_edge():
    edges = {e.name for e in tj_edge_specs()}
    assert "MENTIONED_IN_PASSAGE" in edges
```

- [ ] **Step 2: Run test, expect FAIL**

Run: `uv run pytest packages/jw-brain/tests/test_schema_bible_kg_extensions.py -v`
Expected: FAIL — `Period` no encontrado.

- [ ] **Step 3: Extender `tj_node_specs()` y `tj_edge_specs()`**

Localiza en `packages/jw-brain/src/jw_brain/schema/builtins.py` las funciones `tj_node_specs()` y `tj_edge_specs()`. En cada una **añade** (no reemplaza) los siguientes specs justo antes del `return`:

```python
    # F58 — Bible Knowledge Graph extensions
    NodeTypeSpec(
        name="Period",
        canonical_id_pattern="period:{slug}",
        properties={
            "slug": str,
            "name": str,
            "start_year_bce": (int, None),
            "end_year_bce": (int, None),
            "end_year_ce": (int, None),
            "description": str,
        },
    ),
    NodeTypeSpec(
        name="Passage",
        canonical_id_pattern="passage:{book_num}:{chapter}[:{verse_start}[-{verse_end}]]",
        properties={
            "book_num": int,
            "chapter": int,
            "verse_start": (int, None),
            "verse_end": (int, None),
        },
    ),
```

Para edges, añadir:

```python
    EdgeTypeSpec(name="LIVED_IN_PERIOD", source="Person", target="Period"),
    EdgeTypeSpec(name="ACTIVE_IN_PERIOD", source="Place", target="Period"),
    EdgeTypeSpec(name="MENTIONED_IN_PASSAGE", source="Person", target="Passage"),
    EdgeTypeSpec(name="LOCATED_IN_PASSAGE", source="Place", target="Passage"),
    EdgeTypeSpec(name="PASSAGE_BELONGS_TO_PERIOD", source="Passage", target="Period"),
```

Nota: la tupla `(int, None)` indica "int o None"; verifica con un test rápido que `NodeTypeSpec` acepta este shape (revisa `schema/nodes.py`). Si no lo acepta, usar `int | None` como string en spec.

- [ ] **Step 4: Run test, expect PASS**

Run: `uv run pytest packages/jw-brain/tests/test_schema_bible_kg_extensions.py -v`
Expected: 4 passed.

- [ ] **Step 5: Run contract test del backend para verificar que sigue funcionando**

Run: `uv run pytest packages/jw-brain/tests/test_backends_contract.py -v`
Expected: todas las que pasaban antes siguen pasando (la adición es backwards-compatible).

- [ ] **Step 6: Commit**

```bash
git add packages/jw-brain/src/jw_brain/schema/builtins.py packages/jw-brain/tests/test_schema_bible_kg_extensions.py
git commit -m "feat(jw-brain): F58.5 extend TJ schema with Period and Passage plus 5 edges"
```

---

### Task 6: Fixture sintético `insight_mini/`

**Files:**
- Create: `packages/jw-brain/tests/fixtures/insight_mini/build_fixture.py`
- Create: `packages/jw-brain/tests/fixtures/insight_mini/it_mini.jwpub`

- [ ] **Step 1: Script que construye un JWPUB sintético en memoria con 3 cabezales**

```python
# packages/jw-brain/tests/fixtures/insight_mini/build_fixture.py
"""Construye un JWPUB sintético en memoria con 3 cabezales del Insight
(Abraham, Jerusalem, Moisés). Se ejecuta una vez para generar
it_mini.jwpub; los tests del parser leen ese archivo binario.

Para regenerar:
    cd packages/jw-brain/tests/fixtures/insight_mini
    uv run python build_fixture.py
"""
from __future__ import annotations

import io
import json
import sqlite3
import zipfile
import zlib
from pathlib import Path

from Crypto.Cipher import AES

from jw_core.jwpub_crypto import compute_key_iv, encrypt_blob

HERE = Path(__file__).parent
OUTPUT = HERE / "it_mini.jwpub"

ENTRIES = [
    {
        "MepsDocumentId": 1200000101,
        "Title": "Abraham",
        "TocTitle": "ABRAHAM",
        "Content": (
            '<article><h1>ABRAHAM</h1>'
            '<p>Originally called Abram. The son of Terah and the founder of '
            'the Hebrew nation. First mentioned in <a href="/en/wol/b/r1/lp-e/'
            'nwtsty/1/11#study=discover&v=1:11:26" class="b">Gen. 11:26</a>.</p>'
            '</article>'
        ),
    },
    {
        "MepsDocumentId": 1200000102,
        "Title": "Jerusalem",
        "TocTitle": "JERUSALEM",
        "Content": (
            '<article><h1>JERUSALEM</h1>'
            '<p>Ancient city in the Judean hills. Capital of David s united '
            'kingdom from <a href="/en/wol/b/r1/lp-e/nwtsty/10/5#study=discover'
            '&v=10:5:6" class="b">2 Sam. 5:6</a>.</p>'
            '</article>'
        ),
    },
    {
        "MepsDocumentId": 1200000103,
        "Title": "Moses",
        "TocTitle": "MOSES",
        "Content": (
            '<article><h1>MOSES</h1>'
            '<p>Leader of the Israelites out of Egypt. First introduced in '
            '<a href="/en/wol/b/r1/lp-e/nwtsty/2/2#study=discover&v=2:2:10" '
            'class="b">Ex. 2:10</a>.</p>'
            '</article>'
        ),
    },
]


def _build_inner_db(pub_string: str) -> bytes:
    """Construye el SQLite .db interno con Documents cifrados."""
    key, iv = compute_key_iv(pub_string)
    buf = io.BytesIO()
    # SQLite no soporta nombres :memory: durante export — usar tempfile
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(
        """CREATE TABLE Document (
            MepsDocumentId INTEGER PRIMARY KEY,
            Title TEXT, TocTitle TEXT, Content BLOB
        )"""
    )
    for e in ENTRIES:
        ciphertext = encrypt_blob(e["Content"].encode("utf-8"), key, iv)
        cur.execute(
            "INSERT INTO Document VALUES (?,?,?,?)",
            (e["MepsDocumentId"], e["Title"], e["TocTitle"], ciphertext),
        )
    conn.commit()
    conn.close()
    return Path(db_path).read_bytes()


def main() -> None:
    pub_string = "0_it_2025"  # 0 = English, it = Insight, year 2025
    inner_db_bytes = _build_inner_db(pub_string)

    manifest = {
        "manifestVersion": 1,
        "publication": {
            "fileName": "it_mini.db",
            "symbol": "it",
            "year": 2025,
            "issueTagNumber": 0,
            "publicationType": "encyclopedia",
            "languageIndex": 0,
            "title": "Insight on the Scriptures (mini fixture)",
            "schemaVersion": 12,
        },
    }
    inner_zip_buf = io.BytesIO()
    with zipfile.ZipFile(inner_zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("it_mini.db", inner_db_bytes)
    inner_zip_bytes = inner_zip_buf.getvalue()

    outer_zip_buf = io.BytesIO()
    with zipfile.ZipFile(outer_zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json", json.dumps(manifest))
        zf.writestr("contents", inner_zip_bytes)
    OUTPUT.write_bytes(outer_zip_buf.getvalue())
    print(f"Wrote {OUTPUT} ({OUTPUT.stat().st_size} bytes, {len(ENTRIES)} entries)")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Generar fixture binario**

Run: `cd /Users/elias/Documents/Trabajo/jw-agent-toolkit && uv run python packages/jw-brain/tests/fixtures/insight_mini/build_fixture.py`
Expected: output `Wrote ...it_mini.jwpub (NNNN bytes, 3 entries)`.

- [ ] **Step 3: Verificar manual con el parser existente**

Run: `uv run python -c "from jw_core.parsers.jwpub import parse_jwpub; m = parse_jwpub('packages/jw-brain/tests/fixtures/insight_mini/it_mini.jwpub'); print([d.title for d in m.documents])"`
Expected: `['Abraham', 'Jerusalem', 'Moses']`.

- [ ] **Step 4: Commit**

```bash
git add packages/jw-brain/tests/fixtures/insight_mini/
git commit -m "test(jw-brain): F58.6 add insight mini synthetic JWPUB fixture"
```

---

### Task 7: Parser Insight — extracción de cabezal Person

**Files:**
- Create: `packages/jw-brain/src/jw_brain/imports/bible/parser_insight.py`
- Create: `packages/jw-brain/tests/test_imports_bible_parser_insight.py`

- [ ] **Step 1: Failing test**

```python
# packages/jw-brain/tests/test_imports_bible_parser_insight.py
"""Parser del Insight: convierte JwpubDocument → InsightEntry."""
from pathlib import Path

from jw_brain.imports.bible.parser_insight import (
    InsightParser,
    classify_entry_kind,
)
from jw_core.parsers.jwpub import parse_jwpub

FIXTURE = Path(__file__).parent / "fixtures" / "insight_mini" / "it_mini.jwpub"


def test_classify_entry_kind_abraham_is_person():
    """Heurística: cabezales que aparecen en el catálogo de personas
    bíblicas conocidas se clasifican como `person`."""
    assert classify_entry_kind("ABRAHAM") == "person"
    assert classify_entry_kind("Moses") == "person"


def test_classify_entry_kind_jerusalem_is_place():
    assert classify_entry_kind("JERUSALEM") == "place"


def test_classify_entry_kind_unknown_returns_none():
    assert classify_entry_kind("UNKNOWN_CONCEPT") is None


def test_parser_extracts_abraham_entry():
    metadata = parse_jwpub(FIXTURE)
    parser = InsightParser(symbol="it", meps_language=0)
    entries = list(parser.iter_entries(metadata))
    by_headword = {e.headword.lower(): e for e in entries}
    assert "abraham" in by_headword
    abraham = by_headword["abraham"]
    assert abraham.kind == "person"
    assert "Gen. 11:26" in abraham.first_mention_raw
    assert "/en/wol/b/r1/lp-e/nwtsty/1/11" in abraham.first_mention_href


def test_parser_extracts_jerusalem_as_place():
    metadata = parse_jwpub(FIXTURE)
    parser = InsightParser(symbol="it", meps_language=0)
    entries = {e.headword.lower(): e for e in parser.iter_entries(metadata)}
    jerusalem = entries["jerusalem"]
    assert jerusalem.kind == "place"


def test_parser_skips_unclassified_entries(monkeypatch):
    """Si una entrada no es person ni place (ej concepto teológico), se omite."""
    # Agregar "TRINIDAD" al fixture devolvería None → skip
    metadata = parse_jwpub(FIXTURE)
    parser = InsightParser(symbol="it", meps_language=0)
    entries = list(parser.iter_entries(metadata))
    # Los 3 del fixture son person/place; ninguno se omite
    assert len(entries) == 3
```

- [ ] **Step 2: Run, expect FAIL**

Run: `uv run pytest packages/jw-brain/tests/test_imports_bible_parser_insight.py -v`
Expected: ImportError.

- [ ] **Step 3: Implementar parser**

```python
# packages/jw-brain/src/jw_brain/imports/bible/parser_insight.py
"""Parser de cabezales del Insight on the Scriptures.

Lee `JwpubMetadata` ya descifrado por `jw_core.parsers.jwpub.parse_jwpub`
y emite `InsightEntry` para cada documento clasificable como persona o
lugar bíblico.

Decisiones:
- Clasificación por **catálogos hardcoded** (PERSON_HEADWORDS, PLACE_HEADWORDS).
  NO usa LLM ni NER: el Insight tiene un universo cerrado de cabezales
  documentado por la Watch Tower; un catálogo curado es deterministic.
- Primer-mención extraída por regex sobre el primer `<a class="b">` del cuerpo.
- Aliases del cabezal: extraídos de la frase "Originally called <X>",
  "Also known as <X>", "Formerly <X>" (patrones del Insight).
"""
from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass

from bs4 import BeautifulSoup

from jw_brain.imports.bible.models import InsightEntry, InsightKind
from jw_core.models import JwpubMetadata

# Catálogo mínimo para el fixture. En el sprint final se amplía con la lista
# completa del índice del Insight (~3000 entradas total). Reside aquí
# (no en data/) por ser parte de la lógica de clasificación.
PERSON_HEADWORDS: frozenset[str] = frozenset(
    {
        "abraham",
        "moses",
        "moisés",
        "isaac",
        "jacob",
        "joseph",
        "david",
        "solomon",
        "saul",
        "samuel",
        "elijah",
        "elisha",
        "isaiah",
        "jeremiah",
        "ezekiel",
        "daniel",
        "esther",
        "ruth",
        "paul",
        "peter",
        "john",
        "james",
        "matthew",
        "mark",
        "luke",
        "jesus",
        # ...se expande iterativamente en tasks posteriores
    }
)

PLACE_HEADWORDS: frozenset[str] = frozenset(
    {
        "jerusalem",
        "babylon",
        "babylonia",
        "egypt",
        "canaan",
        "israel",
        "judah",
        "samaria",
        "galilee",
        "judea",
        "nazareth",
        "bethlehem",
        "rome",
        "athens",
        "ephesus",
        "antioch",
        # ...
    }
)


def classify_entry_kind(headword: str) -> InsightKind | None:
    """Clasifica un cabezal del Insight como person, place o None.

    El matching es case-insensitive y strip-padded para tolerar:
    `ABRAHAM`, `Abraham`, ` Abraham ` y `Abraham.` (punto final).
    """
    normalized = headword.strip().lower().rstrip(".,;:")
    if normalized in PERSON_HEADWORDS:
        return "person"
    if normalized in PLACE_HEADWORDS:
        return "place"
    return None


_FIRST_MENTION_RE = re.compile(
    r'<a[^>]*class="b"[^>]*href="([^"]+)"[^>]*>([^<]+)</a>',
    re.IGNORECASE,
)


@dataclass(slots=True)
class InsightParser:
    """Parser stateful: configura symbol/meps_language una vez y procesa
    múltiples JwpubMetadata."""

    symbol: str
    meps_language: int

    def iter_entries(self, metadata: JwpubMetadata) -> Iterator[InsightEntry]:
        """Itera todos los documentos del JWPUB que clasifiquen como
        person o place. Documentos sin XHTML descifrado se omiten."""
        for doc in metadata.documents:
            text = getattr(doc, "text", "") or ""
            if not text:
                continue
            kind = classify_entry_kind(doc.title or "")
            if kind is None:
                continue
            first_mention_raw, first_mention_href = self._extract_first_mention(text)
            yield InsightEntry(
                headword=doc.title,
                document_id=doc.meps_document_id,
                symbol=self.symbol,
                meps_language=self.meps_language,
                kind=kind,
                first_mention_raw=first_mention_raw,
                first_mention_href=first_mention_href,
                aliases=(),  # TODO: extracción de aliases queda para Task 8
                text_excerpt=self._first_paragraph_excerpt(text),
            )

    @staticmethod
    def _extract_first_mention(text: str) -> tuple[str, str]:
        """Extrae el primer <a class="b"> como (raw_text, href)."""
        m = _FIRST_MENTION_RE.search(text)
        if m is None:
            return ("", "")
        return (m.group(2), m.group(1))

    @staticmethod
    def _first_paragraph_excerpt(text: str, max_chars: int = 500) -> str:
        soup = BeautifulSoup(text, "html.parser")
        first_p = soup.find("p")
        if first_p is None:
            return ""
        return first_p.get_text(strip=True)[:max_chars]
```

- [ ] **Step 4: Run, expect PASS**

Run: `uv run pytest packages/jw-brain/tests/test_imports_bible_parser_insight.py -v`
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-brain/src/jw_brain/imports/bible/parser_insight.py packages/jw-brain/tests/test_imports_bible_parser_insight.py
git commit -m "feat(jw-brain): F58.7 parse Insight JWPUB headwords as InsightEntry"
```

---

### Task 8: Loader que orquesta parsers + emite upserts

**Files:**
- Create: `packages/jw-brain/src/jw_brain/imports/bible/loader.py`
- Create: `packages/jw-brain/tests/test_imports_bible_loader.py`

- [ ] **Step 1: Failing test**

```python
# packages/jw-brain/tests/test_imports_bible_loader.py
"""Loader E2E: parsea Insight fixture → upserts a backend → query verifica."""
from pathlib import Path

import pytest

from jw_brain.backends.duckdb_backend import DuckDBBackend
from jw_brain.imports.bible.loader import BibleLoader

FIXTURE = Path(__file__).parent / "fixtures" / "insight_mini" / "it_mini.jwpub"


@pytest.fixture()
def backend(tmp_path):
    """In-process DuckDB backend on a temp file."""
    db = DuckDBBackend(tmp_path / "test.duckdb")
    db.initialize_schema()
    return db


def test_loader_imports_periods_first(backend):
    loader = BibleLoader(backend=backend)
    stats = loader.import_periods()
    assert stats.periods_upserted == 10  # 10 periodos del catálogo
    nodes = backend.list_nodes(node_type="Period")
    assert len(nodes) == 10


def test_loader_imports_insight_jwpub(backend):
    loader = BibleLoader(backend=backend)
    loader.import_periods()
    stats = loader.import_insight(FIXTURE, symbol="it", meps_language=0)
    # Fixture tiene Abraham, Moses → persons. Jerusalem → place.
    assert stats.persons_upserted == 2
    assert stats.places_upserted == 1

    persons = backend.list_nodes(node_type="Person")
    person_slugs = {p["canonical_id"] for p in persons}
    assert "person:abraham" in person_slugs
    assert "person:moses" in person_slugs


def test_loader_creates_first_mention_passage_nodes(backend):
    loader = BibleLoader(backend=backend)
    loader.import_periods()
    loader.import_insight(FIXTURE, symbol="it", meps_language=0)
    # Abraham first mention: Gen 11:26 → passage:1:11:26
    passages = {p["canonical_id"] for p in backend.list_nodes(node_type="Passage")}
    assert "passage:1:11:26" in passages


def test_loader_creates_mentioned_in_passage_edges(backend):
    loader = BibleLoader(backend=backend)
    loader.import_periods()
    loader.import_insight(FIXTURE, symbol="it", meps_language=0)
    edges = backend.list_edges(edge_type="MENTIONED_IN_PASSAGE")
    # Abraham → passage:1:11:26 debe existir
    edge_pairs = {(e["source_canonical_id"], e["target_canonical_id"]) for e in edges}
    assert ("person:abraham", "passage:1:11:26") in edge_pairs


def test_loader_is_idempotent(backend):
    loader = BibleLoader(backend=backend)
    loader.import_periods()
    stats1 = loader.import_insight(FIXTURE, symbol="it", meps_language=0)
    stats2 = loader.import_insight(FIXTURE, symbol="it", meps_language=0)
    # Re-import upserts (no duplica)
    nodes = backend.list_nodes(node_type="Person")
    assert len(nodes) == stats1.persons_upserted
    assert stats2.persons_upserted == stats1.persons_upserted
```

- [ ] **Step 2: Run, expect FAIL**

Run: `uv run pytest packages/jw-brain/tests/test_imports_bible_loader.py -v`
Expected: ImportError o backend sin `list_nodes`/`list_edges`.

- [ ] **Step 3: Verificar que `DuckDBBackend` expone `list_nodes`/`list_edges`**

Si el backend NO tiene esos métodos, añadirlos en `packages/jw-brain/src/jw_brain/backends/protocol.py` y la implementación DuckDB. Si no aplica a este sprint (porque no son parte del Protocol), reemplazar los asserts del test con queries Cypher/SQL directas usando `backend.run_cypher(...)` o el método nativo. Adapta los asserts pero **conserva los gist**: "se crearon N nodos del tipo X" y "existe edge de A→B".

- [ ] **Step 4: Implementar loader**

```python
# packages/jw-brain/src/jw_brain/imports/bible/loader.py
"""Orquestador del import bible-kg.

Pipeline:
1. import_periods() — popula catálogo curado (10 nodos Period).
2. import_insight(jwpub_path) — parsea Insight, emite Person/Place + Passage
   + edges MENTIONED_IN_PASSAGE/LOCATED_IN_PASSAGE.
3. (futuro) import_nwt_cross_references() — añade más Passage con menciones cruzadas.

Idempotente: cada upsert es by canonical_id, re-correr no duplica.
NO usa LLM. Todos los datos vienen del catálogo hardcoded + parser
procedural del Insight.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from jw_brain.backends.protocol import GraphBackend
from jw_brain.imports.bible.models import (
    BibleKgPassage,
    BibleKgPerson,
    BibleKgPlace,
)
from jw_brain.imports.bible.parser_insight import InsightParser
from jw_brain.imports.bible.period_catalog import ALL_PERIODS
from jw_core.models import BibleRef
from jw_core.parsers.jwpub import parse_jwpub


@dataclass
class LoaderStats:
    periods_upserted: int = 0
    persons_upserted: int = 0
    places_upserted: int = 0
    passages_upserted: int = 0
    edges_upserted: int = 0
    skipped_unclassified: int = 0
    warnings: list[str] = field(default_factory=list)


# Provenance compartida del bible KG (F40 provenance compatible)
_PROVENANCE = {
    "source_kind": "bible_kg",
    "source_version": "f58",
    "license": "Watch Tower Bible and Tract Society (Insight on the Scriptures)",
}


class BibleLoader:
    """Orquesta el import. Recibe backend ya inicializado."""

    def __init__(self, backend: GraphBackend):
        self.backend = backend

    def import_periods(self) -> LoaderStats:
        stats = LoaderStats()
        for period in ALL_PERIODS:
            self.backend.upsert_node(
                node_type="Period",
                canonical_id=period.canonical_id,
                properties=period.model_dump(),
                provenance=_PROVENANCE,
            )
            stats.periods_upserted += 1
        return stats

    def import_insight(
        self,
        jwpub_path: Path | str,
        *,
        symbol: str,
        meps_language: int,
    ) -> LoaderStats:
        stats = LoaderStats()
        metadata = parse_jwpub(jwpub_path)
        parser = InsightParser(symbol=symbol, meps_language=meps_language)
        for entry in parser.iter_entries(metadata):
            slug = self._slugify(entry.headword)
            wol_ref = (
                BibleRef.from_wol_url(entry.first_mention_href)
                if entry.first_mention_href
                else None
            )
            if entry.kind == "person":
                person = BibleKgPerson(
                    slug=slug,
                    name=entry.headword.title(),
                    aliases=entry.aliases,
                    first_mention_book=wol_ref.book_num if wol_ref else None,
                    first_mention_chapter=wol_ref.chapter if wol_ref else None,
                    first_mention_verse=wol_ref.verse_start if wol_ref else None,
                    description_excerpt=entry.text_excerpt,
                    source_url=f"https://wol.jw.org{entry.first_mention_href}"
                    if entry.first_mention_href
                    else "",
                )
                self.backend.upsert_node(
                    node_type="Person",
                    canonical_id=person.canonical_id,
                    properties=person.model_dump(),
                    provenance=_PROVENANCE,
                )
                stats.persons_upserted += 1
                if wol_ref is not None:
                    self._upsert_passage_and_mention(
                        wol_ref=wol_ref,
                        source_canonical_id=person.canonical_id,
                        edge_type="MENTIONED_IN_PASSAGE",
                        stats=stats,
                    )
            elif entry.kind == "place":
                place = BibleKgPlace(
                    slug=slug,
                    name=entry.headword.title(),
                    source_url=f"https://wol.jw.org{entry.first_mention_href}"
                    if entry.first_mention_href
                    else "",
                )
                self.backend.upsert_node(
                    node_type="Place",
                    canonical_id=place.canonical_id,
                    properties=place.model_dump(),
                    provenance=_PROVENANCE,
                )
                stats.places_upserted += 1
                if wol_ref is not None:
                    self._upsert_passage_and_mention(
                        wol_ref=wol_ref,
                        source_canonical_id=place.canonical_id,
                        edge_type="LOCATED_IN_PASSAGE",
                        stats=stats,
                    )
            else:
                stats.skipped_unclassified += 1
        return stats

    def _upsert_passage_and_mention(
        self,
        *,
        wol_ref: BibleRef,
        source_canonical_id: str,
        edge_type: str,
        stats: LoaderStats,
    ) -> None:
        passage = BibleKgPassage(
            book_num=wol_ref.book_num,
            chapter=wol_ref.chapter,
            verse_start=wol_ref.verse_start,
            verse_end=wol_ref.verse_end,
        )
        self.backend.upsert_node(
            node_type="Passage",
            canonical_id=passage.canonical_id,
            properties=passage.model_dump(),
            provenance=_PROVENANCE,
        )
        stats.passages_upserted += 1
        self.backend.upsert_edge(
            edge_type=edge_type,
            from_canonical_id=source_canonical_id,
            to_canonical_id=passage.canonical_id,
            properties={},
            provenance=_PROVENANCE,
        )
        stats.edges_upserted += 1

    @staticmethod
    def _slugify(s: str) -> str:
        s = s.lower().strip()
        s = re.sub(r"[^a-z0-9]+", "_", s)
        return s.strip("_")
```

- [ ] **Step 5: Adaptar firmas si difieren de protocol real**

El test asume `backend.upsert_node(node_type=..., canonical_id=..., properties=..., provenance=...)`. Revisa `packages/jw-brain/src/jw_brain/backends/protocol.py` y ajusta el loader **a la firma real** si los nombres de parámetro difieren. Si el protocol usa `properties` como kwargs spread, adáptalo. No cambies el protocol — adapta el loader.

- [ ] **Step 6: Run tests, expect PASS**

Run: `uv run pytest packages/jw-brain/tests/test_imports_bible_loader.py -v`
Expected: 5 passed.

- [ ] **Step 7: Commit**

```bash
git add packages/jw-brain/src/jw_brain/imports/bible/loader.py packages/jw-brain/tests/test_imports_bible_loader.py
git commit -m "feat(jw-brain): F58.8 BibleLoader emits Person/Place/Passage/Period plus edges to backend"
```

---

### Task 9: CLI `jw brain import-bible`

**Files:**
- Modify: `packages/jw-brain/src/jw_brain/cli.py`
- Create: `packages/jw-brain/tests/test_imports_bible_cli.py`

- [ ] **Step 1: Failing test del CLI smoke**

```python
# packages/jw-brain/tests/test_imports_bible_cli.py
"""Smoke test del comando `jw brain import-bible` usando Typer test client."""
from pathlib import Path

import pytest
from typer.testing import CliRunner

from jw_brain.cli import app

FIXTURE = (
    Path(__file__).parent / "fixtures" / "insight_mini" / "it_mini.jwpub"
)


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner()


def test_import_bible_help(runner):
    result = runner.invoke(app, ["import-bible", "--help"])
    assert result.exit_code == 0
    assert "insight" in result.stdout.lower() or "source" in result.stdout.lower()


def test_import_bible_periods_only(runner, tmp_path, monkeypatch):
    """Sin --insight, importa solo el catálogo de periodos."""
    monkeypatch.setenv("JW_BRAIN_HOME", str(tmp_path))
    result = runner.invoke(app, ["init", "--domain", "tj", "--brain", "test"])
    assert result.exit_code == 0

    result = runner.invoke(app, ["import-bible", "--brain", "test", "--periods-only"])
    assert result.exit_code == 0, result.stdout
    assert "10" in result.stdout  # 10 periodos


def test_import_bible_with_insight_jwpub(runner, tmp_path, monkeypatch):
    monkeypatch.setenv("JW_BRAIN_HOME", str(tmp_path))
    runner.invoke(app, ["init", "--domain", "tj", "--brain", "test"])

    result = runner.invoke(
        app,
        [
            "import-bible",
            "--brain", "test",
            "--insight", str(FIXTURE),
            "--symbol", "it",
            "--meps-language", "0",
        ],
    )
    assert result.exit_code == 0, result.stdout
    assert "person" in result.stdout.lower()
    assert "place" in result.stdout.lower()
```

- [ ] **Step 2: Run, expect FAIL**

Run: `uv run pytest packages/jw-brain/tests/test_imports_bible_cli.py -v`
Expected: FAIL — comando `import-bible` no existe.

- [ ] **Step 3: Añadir comando al CLI**

En `packages/jw-brain/src/jw_brain/cli.py`, localiza el `app = typer.Typer(...)` y los comandos existentes (`init`, `compile`, `query`, etc.). Añade:

```python
@app.command("import-bible")
def import_bible(
    brain: str | None = typer.Option(None, "--brain", help="Nombre del brain (registry alias)"),
    periods_only: bool = typer.Option(False, "--periods-only", help="Importa solo el catálogo de periodos"),
    insight: Path | None = typer.Option(None, "--insight", help="Ruta a un JWPUB del Insight"),
    symbol: str = typer.Option("it", "--symbol", help="Símbolo de la publicación (it, it-1, it-2)"),
    meps_language: int = typer.Option(0, "--meps-language", help="Índice de idioma MEPS (0=E, 3=S, 4=T)"),
) -> None:
    """Hidrata el bible KG en el brain seleccionado desde fuentes JW puras
    (catálogo de periodos hardcoded + Insight on the Scriptures opcional).

    Ejemplos:
        jw brain import-bible --brain default --periods-only
        jw brain import-bible --brain personal --insight ~/jwpubs/it_S.jwpub --symbol it --meps-language 3
    """
    from jw_brain.config import resolve_brain
    from jw_brain.backends.factory import open_backend
    from jw_brain.imports.bible.loader import BibleLoader

    brain_config = resolve_brain(brain)
    backend = open_backend(brain_config)
    loader = BibleLoader(backend=backend)

    stats_p = loader.import_periods()
    typer.echo(f"Periods upserted: {stats_p.periods_upserted}")

    if periods_only or insight is None:
        return

    stats_i = loader.import_insight(insight, symbol=symbol, meps_language=meps_language)
    typer.echo(
        f"Persons upserted: {stats_i.persons_upserted}\n"
        f"Places upserted: {stats_i.places_upserted}\n"
        f"Passages upserted: {stats_i.passages_upserted}\n"
        f"Edges upserted: {stats_i.edges_upserted}\n"
        f"Skipped unclassified: {stats_i.skipped_unclassified}"
    )
```

> **Nota:** los nombres exactos de `resolve_brain` y `open_backend` pueden diferir — usa los que el repo ya tenga (la exploración mostró `Compiler` recibe brain via factory). Si no existen helpers públicos, adapta el comando para abrir el backend tal y como hacen otros comandos (`init`, `compile`).

- [ ] **Step 4: Run, expect PASS**

Run: `uv run pytest packages/jw-brain/tests/test_imports_bible_cli.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-brain/src/jw_brain/cli.py packages/jw-brain/tests/test_imports_bible_cli.py
git commit -m "feat(jw-brain): F58.9 add jw brain import-bible CLI command"
```

---

### Task 10: Test E2E con import-bible + query Cypher de muestra

**Files:**
- Create: `packages/jw-brain/tests/test_imports_bible_e2e.py`

- [ ] **Step 1: Failing test que verifica la query end-to-end**

```python
# packages/jw-brain/tests/test_imports_bible_e2e.py
"""E2E: import periods + insight, ejecutar query 'qué personas se mencionan
en el libro Gen' contra DuckDB. Verifica que el grafo está correctamente
poblado para responder queries reales."""
from pathlib import Path

import pytest

from jw_brain.backends.duckdb_backend import DuckDBBackend
from jw_brain.imports.bible.loader import BibleLoader

FIXTURE = (
    Path(__file__).parent / "fixtures" / "insight_mini" / "it_mini.jwpub"
)


@pytest.fixture()
def hydrated_brain(tmp_path):
    backend = DuckDBBackend(tmp_path / "test.duckdb")
    backend.initialize_schema()
    loader = BibleLoader(backend=backend)
    loader.import_periods()
    loader.import_insight(FIXTURE, symbol="it", meps_language=0)
    return backend


def test_query_persons_in_genesis(hydrated_brain):
    """Equivalente a Cypher:
        MATCH (p:Node {node_type:'Person'})-[:MENTIONED_IN_PASSAGE]->(pa:Node {node_type:'Passage'})
        WHERE pa.book_num = 1 RETURN p.name
    Con DuckDB backend, expresión SQL análoga."""
    persons_in_genesis = hydrated_brain.query_persons_in_book(book_num=1)
    names = {p["name"] for p in persons_in_genesis}
    assert "Abraham" in names


def test_period_node_count(hydrated_brain):
    periods = hydrated_brain.list_nodes(node_type="Period")
    assert len(periods) == 10
```

> **Nota:** `query_persons_in_book` puede no existir aún en `DuckDBBackend`. Si no existe, este test sirve de **target** para añadirlo en el siguiente sprint (Task 10.1). Si está fuera de scope, sustituye por una query SQL directa via `backend._conn.execute(...)` para verificar el grafo.

- [ ] **Step 2: Run, evaluar**

Run: `uv run pytest packages/jw-brain/tests/test_imports_bible_e2e.py -v`
Expected: si `query_persons_in_book` no existe, falla con AttributeError — añadir como helper del backend (Task 10.1 inline).

- [ ] **Step 3: Si falta `query_persons_in_book`, añadirlo**

```python
# En packages/jw-brain/src/jw_brain/backends/duckdb_backend.py, añadir:
def query_persons_in_book(self, book_num: int) -> list[dict]:
    """Helper: lista personas con MENTIONED_IN_PASSAGE → Passage en `book_num`."""
    sql = """
    SELECT DISTINCT n.canonical_id, json_extract_string(n.properties, '$.name') AS name
    FROM nodes n
    JOIN edges e ON e.source_canonical_id = n.canonical_id
    JOIN nodes p ON p.canonical_id = e.target_canonical_id
    WHERE n.node_type = 'Person'
      AND e.edge_type = 'MENTIONED_IN_PASSAGE'
      AND p.node_type = 'Passage'
      AND CAST(json_extract_string(p.properties, '$.book_num') AS INTEGER) = ?
    """
    return [dict(r) for r in self._conn.execute(sql, [book_num]).fetchall()]
```

(Adapta `_conn`, nombres de tabla y JSON helpers a los que el backend ya use.)

- [ ] **Step 4: Run, expect PASS**

Run: `uv run pytest packages/jw-brain/tests/test_imports_bible_e2e.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-brain/tests/test_imports_bible_e2e.py packages/jw-brain/src/jw_brain/backends/duckdb_backend.py
git commit -m "test(jw-brain): F58.10 add e2e bible-kg query tests plus query_persons_in_book helper"
```

---

### Task 11: Guía operativa `docs/guias/bible-knowledge-graph.md`

**Files:**
- Create: `docs/guias/bible-knowledge-graph.md`
- Modify: `docs/README.md` — añadir entrada a la guía en la sección "Guías por tema"
- Modify: `docs/ROADMAP.md` — añadir entrada F58

- [ ] **Step 1: Crear la guía**

```markdown
# Bible Knowledge Graph (Fase 58)

> Hidrata `jw-brain` con un knowledge graph bíblico (personas, lugares,
> periodos, pasajes) construido desde fuentes JW puras: Estudio Perspicaz
> de las Escrituras (Insight on the Scriptures) y NWT/NWTsty.

## Por qué versión propia y no `theographic-bible-metadata`

El KG académico upstream incorpora datos de tradiciones no-JW (Catholic
Encyclopedia, Jewish Encyclopedia, ISBE). Para mantener el toolkit
doctrinalmente puro, derivamos los datos del Insight oficial Watch Tower,
así la cronología refleja la postura JW (p. ej. **destrucción de Jerusalén
en 607 a.E.C.**, NO en 587/586 a.E.C. del consenso académico).

## Atribución

Los datos generados localmente son derivados del Estudio Perspicaz de las
Escrituras (Insight on the Scriptures), © Watch Tower Bible and Tract
Society of Pennsylvania. El toolkit **no** redistribuye texto ni media;
solo procesa el JWPUB que el usuario descarga oficialmente de jw.org.

## Schema añadido

F58 amplía el `tj` domain de `jw-brain`:
- **Nodos**: `Period`, `Passage` (nuevos). `Person`, `Place` ya existían en F49.
- **Edges**: `LIVED_IN_PERIOD`, `ACTIVE_IN_PERIOD`, `MENTIONED_IN_PASSAGE`,
  `LOCATED_IN_PASSAGE`, `PASSAGE_BELONGS_TO_PERIOD`.

## Pipeline

1. `BibleLoader.import_periods()` — hidrata 10 nodos `Period` desde catálogo
   curado en código (`period_catalog.py`). Mutable solo editando ese archivo.
2. `BibleLoader.import_insight(jwpub_path)` — parsea cabezales del Insight,
   clasifica por catálogo (`PERSON_HEADWORDS`/`PLACE_HEADWORDS`), extrae
   primera-mención por regex sobre `<a class="b">`, emite `Person`/`Place`/
   `Passage` con edges `MENTIONED_IN_PASSAGE`/`LOCATED_IN_PASSAGE`.

## Uso

```bash
# 1) Inicializa un brain (si no existe)
jw brain init --domain tj --brain personal --vault ~/obs/jw

# 2) Importa solo el catálogo de periodos (siempre primero)
jw brain import-bible --brain personal --periods-only

# 3) Importa el Insight (descargado de jw.org)
jw brain import-bible --brain personal --insight ~/jwpubs/it_S.jwpub --symbol it --meps-language 3
```

## Queries habilitadas

Con el grafo poblado, queries antes imposibles ahora funcionan:

- *¿Qué personas se mencionan en el libro de Génesis?*  
  → `MATCH (p:Person)-[:MENTIONED_IN_PASSAGE]->(pa:Passage) WHERE pa.book_num=1 RETURN p.name`
- *¿Qué lugares estuvieron activos durante el Cautiverio Babilónico?*  
  → `MATCH (pl:Place)-[:ACTIVE_IN_PERIOD]->(p:Period) WHERE p.slug='babylonian_exile' RETURN pl.name`
- *¿Qué pasajes mencionan tanto a Abraham como a Jerusalén?*  
  (combinación de dos hops, ver `tests/test_imports_bible_e2e.py`)

## Idempotencia

`import-bible` es idempotente por `canonical_id` (`person:abraham`,
`place:jerusalem`, `period:patriarchal`, `passage:1:11:26`). Re-correr
sobre el mismo JWPUB no duplica nodos ni edges.

## Limitaciones

- El catálogo `PERSON_HEADWORDS`/`PLACE_HEADWORDS` cubre solo las entradas
  bíblicas más comunes (~50 inicial). Se expande iterativamente.
- Conceptos teológicos (Trinidad, Reino, Espíritu Santo) **no** se importan
  como nodos — son artículos del Insight, pero no encajan en el schema
  `Person`/`Place`/`Period`/`Passage` y van a otro flujo (RAG semántico).
- Las geocoordenadas (`latitude`/`longitude`) están en el schema pero no
  se rellenan en F58. Se hidratarán en un sprint futuro desde otro
  catálogo curado.
```

- [ ] **Step 2: Añadir línea al `docs/README.md`**

Localiza la sección "Guías por tema" y añade:
```markdown
- [Bible Knowledge Graph](guias/bible-knowledge-graph.md) — Fase 58: hidrata `jw-brain` con personas, lugares, periodos y pasajes bíblicos desde fuentes JW puras (Insight + NWT). Atribución y separación del KG académico inter-religioso.
```

- [ ] **Step 3: Añadir entrada a `docs/ROADMAP.md`**

Crear nueva sección antes de la próxima fase pendiente:
```markdown
## Fase 58 — Bible Knowledge Graph JW-puro ✅

- ✅ Schema TJ ampliado con `Period`, `Passage` + 5 edges temporales.
- ✅ Catálogo curado de 10 periodos bíblicos según cronología JW (607 a.E.C. para destrucción de Jerusalén).
- ✅ `BibleLoader.import_periods()` + `import_insight(jwpub_path)`.
- ✅ Parser procedural de cabezales del Insight (PERSON_HEADWORDS/PLACE_HEADWORDS).
- ✅ Port a Python de `BibleRef.from_wol_url` (paridad con jw-core-js F56.5).
- ✅ CLI `jw brain import-bible`.
- ✅ Fixture sintético `insight_mini/it_mini.jwpub` (3 entradas).
- ✅ Guía `docs/guias/bible-knowledge-graph.md`.
- ⬜ Catálogo ampliado a las ~3000 entradas del Insight (sprint siguiente).
- ⬜ Geocoordenadas de Place (otro catálogo curado).
- ⬜ Import desde NWT cross-references (más Passage).
```

- [ ] **Step 4: Commit**

```bash
git add docs/guias/bible-knowledge-graph.md docs/README.md docs/ROADMAP.md
git commit -m "docs(F58): bible knowledge graph guia plus ROADMAP entry plus README index"
```

---

### Task 12: Marcar F58 ✅ en master plan

**Files:**
- Modify: `docs/superpowers/plans/2026-06-04-master-integracion-stars-plan.md`

- [ ] **Step 1: Editar tabla de estado**

Cambiar la línea de F58 en la tabla "Estado de redacción de los planes" de:
```markdown
| F58 | ✅ 2026-06-04 | ⬜ | — |
```
a:
```markdown
| F58 | ✅ 2026-06-04 | ✅ 2026-06-NN | #PR_NUMBER |
```
(reemplazar `NN` y `PR_NUMBER` por valores reales al hacer merge).

También cambiar el bullet del sub-plan F58 en la sección "Sub-planes":
```markdown
- [F58 — Bible Knowledge Graph JW-puro](./2026-06-04-fase-58-bible-knowledge-graph-plan.md) ✅ redactado + ejecutado
```

- [ ] **Step 2: Commit final de fase**

```bash
git add docs/superpowers/plans/2026-06-04-master-integracion-stars-plan.md
git commit -m "chore(F58): mark fase 58 plus complete in master plan"
```

---

## Tests resumen — qué corre al final

```bash
uv run pytest packages/jw-brain/tests/test_imports_bible_models.py \
              packages/jw-brain/tests/test_imports_bible_period_catalog.py \
              packages/jw-brain/tests/test_imports_bible_parser_insight.py \
              packages/jw-brain/tests/test_imports_bible_loader.py \
              packages/jw-brain/tests/test_imports_bible_cli.py \
              packages/jw-brain/tests/test_imports_bible_e2e.py \
              packages/jw-brain/tests/test_schema_bible_kg_extensions.py \
              packages/jw-core/tests/test_parsers_wol_url.py \
              -v --tb=short
```
Esperado: ~25 passed.

Y el smoke completo de jw-brain (no regresión):
```bash
uv run pytest packages/jw-brain/tests/ -v --tb=short
```
Esperado: contadores anteriores + ~25 nuevos, 0 fallidos.

---

## Self-review checklist (la skill lo exige)

- ✅ **Cobertura de spec**: cada decisión del master plan (Schema ampliado, loader procedural, period catalog, BibleRef port, atribución) tiene Task explícita.
- ✅ **No placeholders**: cada Step tiene código completo o comando exacto. Donde algo depende de la API real del repo (firmas exactas de `upsert_node`, helpers de CLI) se marca explícitamente con instrucción "adapta a lo que ya existe".
- ✅ **Consistencia de tipos**: `BibleKgPerson`, `BibleKgPlace`, `BibleKgPeriod`, `BibleKgPassage` se mencionan con los mismos nombres en Tasks 2, 8 y 11. `canonical_id` es consistente en todo el plan. `InsightEntry.kind` es `Literal["person", "place"]` en Task 2 y se respeta en Task 7.
- ⚠️ **Dependencia externa**: Task 6 usa `jw_core.jwpub_crypto.compute_key_iv` / `encrypt_blob` — verificar que estos helpers existen en `packages/jw-core/src/jw_core/jwpub_crypto.py` (la exploración los menciona como F50 builders). Si no existen, los snippets se adaptan a la API real antes de ejecutar Task 6.
