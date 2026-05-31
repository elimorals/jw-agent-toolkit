# Fase 46 — `canonical-versification`: mapeo entre tradiciones de numeración

> **Fecha**: 2026-05-31
> **Estado**: Diseño aprobado (pendiente de implementación)
> **Owner**: Elias
> **Tier**: 3 (frontera técnica)
> **Depende de**: ninguna fase (solo del `BibleRef` ya consolidado en Fase 1)
> **Documento padre**: [`2026-05-31-fases-39-48-overview.md`](2026-05-31-fases-39-48-overview.md)

## Motivación

La New World Translation (NWT) adopta la numeración cristiana heredada de la Vulgata y la KJV. La Biblia Hebraica Stuttgartensia (BHS) usa la numeración masorética, y la Septuaginta (LXX) trae otra distinta más. Las tres difieren en aproximadamente 150 puntos documentados: las superscriptions de los Salmos (que en BHS son `verso 0` y en NWT entran en `verso 1`), Joel 2:28-32 = Joel 3 en BHS, Malaquías 4 = Mal 3 en BHS, fragmentación de Salmos 9/10 y 114/115, entre otros.

Esta diferencia tiene **dos consecuencias prácticas** para el toolkit:

1. **Falsos positivos en cross-references**: cuando una nota de estudio cita "Joel 2:28" y un comentario externo cita "Joel 3:1", el `cross_reference_finder` (Fase 8) los trata como distintos cuando son el **mismo versículo**.
2. **Pregunta apologética común**: "tu Biblia se salta versículos / tiene numeración rara". Sin un mapeo canónico es imposible responder con precisión.

El ROI puro de la feature es medio-bajo (afecta < 0.1% del tráfico), pero la **completitud del plan maestro** la requiere y su **valor apologético** justifica documentarla con rigor.

## Objetivos

1. **Tabla canónica de discrepancias** (~150 entradas) curada a mano contra fuentes académicas, con metadata mínima para mapeo bidireccional.
2. **API estable** `to_canonical(ref, *, from_tradition, to_tradition) -> BibleRef` que sea **idempotente** y **lossless** cuando no haya discrepancia.
3. **Explicador humano trilingüe** que devuelva una frase corta en/es/pt para mostrar cuando un mapeo es no-trivial.
4. **Integración no invasiva**: `BibleRef.tradition` es **opcional con default `"nwt"`**, así que ninguna API existente cambia su semántica.

## No-objetivos (boundaries vinculantes)

- **No** intentamos cubrir tradiciones siríaca, copta, etíope, ni samaritana. Solo nwt / masoretic / lxx / vulgate (las cuatro relevantes para apologética JW).
- **No** convertimos texto, solo numeración. La traducción del contenido sigue siendo responsabilidad de `WOLClient`.
- **No** publicamos el catálogo en una infra externa; vive como JSON en `jw-core/src/jw_core/data/`.
- **No** distribuimos texto bíblico de ninguna tradición — solo coordenadas (book, chapter, verse). El catálogo es metadata, no contenido.
- **No** generamos las explicaciones con LLM en tiempo real; son **prosa original** redactada por el maintainer y commiteada al JSON.

## Fuentes académicas del catálogo

Las ~150 discrepancias se compilan **manualmente** desde literatura abierta y academia pública. Fuentes consultadas (citadas en el `README.md` del módulo, no en el JSON):

1. **Tov, Emanuel** — *Textual Criticism of the Hebrew Bible* (3rd ed., Fortress 2012), apéndices sobre divisiones capitulares.
2. **Würthwein, Ernst** — *The Text of the Old Testament* (Eerdmans 2014).
3. **BHS apparatus** — Biblia Hebraica Stuttgartensia, marcas de división capitular vs LXX.
4. **NETS** — *New English Translation of the Septuagint*, prefacios por libro que listan numeraciones discrepantes.
5. **Society of Biblical Literature** — *SBL Handbook of Style* §8.3 (sistemas de versificación).
6. **Logos Bible Software academic notes** — tablas de mapeo público.

**Política de atribución**: el catálogo JSON contiene una clave `"source"` por entrada (ej. `"Tov 2012:32"`, `"BHS apparatus Ps 51"`). El campo `explanation` es **prosa original redactada por Elias**, no copia de las fuentes. Esto es esencial para mantener el repo bajo GPL-3.0 sin contaminación de copyright académico.

## Arquitectura

Nuevo módulo `packages/jw-core/src/jw_core/versification/`:

```
packages/jw-core/src/jw_core/versification/
├── __init__.py             # re-exports públicos
├── models.py               # Tradition, VersificationMapping, MappingResult
├── registry.py             # load_catalog() — lazy + cached
├── mapping.py              # to_canonical(ref, *, from_, to_)
└── explain.py              # explain(ref, from_, to_) -> str (en/es/pt)
```

Datos:

```
packages/jw-core/src/jw_core/data/
└── versification_map.json  # ~150 entradas curadas
```

### Reglas duras de diseño

1. `versification` **no importa nada** de `jw_rag`, `jw_agents`, `jw_mcp`. Solo `jw_core.models` y `jw_core.data`.
2. El JSON se carga **lazy** vía `functools.lru_cache(maxsize=1)`. No I/O en import.
3. `to_canonical` es **idempotente**: `to_canonical(to_canonical(r, a, b), b, a) == r` (round-trip property).
4. Si no hay discrepancia conocida entre `from_` y `to_`, la función devuelve el `BibleRef` original con `tradition` reasignado — **nunca** falla silenciosamente.
5. Todo el módulo es **puro Python**, sin red, sin LLM. Tests offline al 100%.

## Modelos (Pydantic)

```python
# src/jw_core/versification/models.py
from typing import Literal
from pydantic import BaseModel, Field

Tradition = Literal["nwt", "masoretic", "lxx", "vulgate"]

class VerseCoord(BaseModel):
    """Una coordenada (chapter, verse_start, verse_end) en una tradición."""
    chapter: int = Field(ge=0)              # 0 permitido para superscript LXX/BHS
    verse_start: int = Field(ge=0)          # 0 = superscript
    verse_end: int | None = Field(default=None, ge=0)

class VersificationMapping(BaseModel):
    """Una entrada del catálogo de discrepancias."""
    book: str                                # canonical English name
    book_num: int = Field(ge=1, le=66)
    issue: Literal[
        "superscription", "chapter_split", "verse_split",
        "verse_merge", "chapter_renumber", "verse_shift",
    ]
    nwt: VerseCoord
    masoretic: VerseCoord | None = None
    lxx: VerseCoord | None = None
    vulgate: VerseCoord | None = None
    source: str = Field(description="Academic citation, e.g. 'Tov 2012:32'")
    explanation: dict[str, str] = Field(
        description="Original prose by maintainer, keyed 'en'|'es'|'pt'",
    )

class MappingResult(BaseModel):
    """Resultado de un mapeo, con metadata de si fue trivial o no."""
    ref: "BibleRef"
    from_tradition: Tradition
    to_tradition: Tradition
    is_discrepant: bool                     # False = identity, True = real shift
    rationale: str | None = None            # explicación corta si is_discrepant
```

Extensión opcional al `BibleRef` existente (sin romper compat):

```python
# src/jw_core/models.py (cambio mínimo)
class BibleRef(BaseModel):
    ...
    tradition: Tradition = Field(
        default="nwt",
        description="Numbering tradition. Default 'nwt' matches NWT/KJV.",
    )
```

## Formato del catálogo

`packages/jw-core/src/jw_core/data/versification_map.json`:

```json
{
  "version": "1.0",
  "compiled_at": "2026-05-31",
  "source_references": [
    "Tov, E. (2012) Textual Criticism of the Hebrew Bible, 3rd ed.",
    "BHS apparatus",
    "NETS prefaces (LXX numbering notes)"
  ],
  "discrepancies": [
    {
      "book": "Psalms",
      "book_num": 19,
      "issue": "superscription",
      "nwt": {"chapter": 51, "verse_start": 1},
      "masoretic": {"chapter": 51, "verse_start": 0},
      "lxx": {"chapter": 50, "verse_start": 0},
      "source": "BHS apparatus Ps 51",
      "explanation": {
        "en": "The superscription is counted as verse 1 in the NWT but as verse 0 in the Hebrew Masoretic; the LXX numbers the psalm as 50 because Psalms 9 and 10 are merged.",
        "es": "La superscripción se cuenta como versículo 1 en la NWT pero como versículo 0 en el texto hebreo masorético; la LXX lo numera como Salmo 50 porque une los Salmos 9 y 10.",
        "pt": "A superscrição é contada como versículo 1 na TNM mas como versículo 0 no texto hebraico massorético; a LXX o numera como Salmo 50 porque une os Salmos 9 e 10."
      }
    },
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
    }
  ]
}
```

Cobertura objetivo del catálogo v1 (suma ≈ 150):

| Tipo de discrepancia | # aprox | Libros principales |
|---|---|---|
| Superscriptions Salmos | 116 | Psalms (todos los que tienen título) |
| Chapter renumber Joel/Mal | 4 | Joel, Malachi |
| Split Salmos 9/10, 114/115 | 4 | Psalms |
| Verse shifts en 1 Reyes / 1 Crónicas | ~10 | 1 Kings, 1 Chronicles |
| Numbering Nehemías | ~6 | Nehemiah |
| 2 Corintios 13 (12/13 split) | 1 | 2 Corinthians |
| Romanos 16 (doxología) | 1 | Romans |
| Misceláneos LXX-only | ~10 | Job, Jeremiah |

## API pública

```python
# mapping.py
from jw_core.models import BibleRef
from jw_core.versification.models import Tradition, MappingResult

def to_canonical(
    ref: BibleRef,
    *,
    from_tradition: Tradition = "nwt",
    to_tradition: Tradition,
) -> MappingResult:
    """Map a BibleRef from one numbering tradition to another.

    Idempotent: if `from_tradition == to_tradition`, returns the input
    wrapped in a MappingResult with `is_discrepant=False`.

    Lossless on round-trip: `to_canonical(to_canonical(r, from_=a,
    to_=b).ref, from_=b, to_=a).ref == r` for every cataloged entry.

    Raises:
        ValueError: if either tradition is unknown.
    """

# explain.py
def explain(
    ref: BibleRef,
    *,
    from_tradition: Tradition,
    to_tradition: Tradition,
    language: Literal["en", "es", "pt"] = "en",
) -> str | None:
    """Return a human-readable sentence describing the discrepancy.

    Returns None when no mapping is needed (identical reference).
    """
```

## Integraciones del toolkit

### `BibleRef` extendido

Campo opcional `tradition: Tradition = "nwt"`. Default preserva el comportamiento de los 1984 tests actuales.

### CLI `jw-cli`

Nuevo subcomando `jw versification`:

```
jw versification map "Joel 2:28" --from nwt --to masoretic
# Joel 3:1 (masoretic)
# Joel 2:28-32 in the NWT corresponds to Joel 3:1-5 in the Hebrew Bible.

jw versification list --book Psalms          # lista discrepancias del libro
jw versification explain "Psalm 51:1" --from nwt --to masoretic --lang es
```

### MCP tool

Nueva herramienta MCP:

```python
@mcp.tool()
def to_canonical_versification(
    ref: str,                      # "Joel 2:28"
    from_tradition: Tradition,
    to_tradition: Tradition,
    explain_in: Literal["en", "es", "pt"] | None = None,
) -> dict:
    """Returns {'ref': str, 'is_discrepant': bool, 'rationale': str|None}"""
```

### `compare_translations` (Fase pre-existente)

Gana un flag `--canonicalize`:

```bash
jw compare-translations "Joel 2:28" --langs en,es,he --canonicalize
# Al ver `he` (BHS-based), automáticamente mapea a masoretic antes de fetch.
```

### Agentes

`apologetics` (Fase 11) gana un módulo opcional **versification_clarifier**: si el usuario pregunta "por qué tu Biblia se salta versículos" sobre un libro con entradas en el catálogo, el agente añade una `Finding` con explicación.

## Test plan

Cuatro grupos, **todos sin red**:

1. **Carga del catálogo** — `tests/test_registry.py`
   - JSON válido, schema-conforme, ≥ 100 entradas.
   - Cada entrada tiene `explanation` en en/es/pt (no None, no string vacío).
   - `source` no vacío.

2. **Property-based** — `tests/test_mapping_property.py`
   - **Idempotencia**: `to_canonical(r, from_=t, to_=t).ref == r` ∀ t, r.
   - **Round-trip**: `to_canonical(to_canonical(r, a, b).ref, b, a).ref == r` ∀ entrada del catálogo.
   - Usa `hypothesis` con strategies para `BibleRef`.

3. **Casos famosos** — `tests/test_mapping_known.py`
   - Joel 2:28 (NWT) → Joel 3:1 (masoretic)
   - Psalm 51 superscription edge case
   - Malachi 4 (NWT) → Malachi 3 (masoretic) — chapter renumber
   - Romans 16 doxology (vulgate sigue numeración cristiana, idempotente con NWT)
   - LXX Psalms 9-10 merge

4. **Explainer trilingüe** — `tests/test_explain.py`
   - Para cada idioma {en, es, pt}, la frase no es None y contiene al menos un keyword esperado.
   - Falla si alguna explicación contiene palabras de fuente académica copiadas literalmente (lista de stop-phrases hard-codeada como guard).

5. **CLI/MCP smoke** — `tests/test_cli.py`
   - `jw versification map "Joel 2:28" --from nwt --to masoretic` produce salida esperada.
   - Tool MCP retorna dict conforme a schema declarado.

Cobertura objetivo: **≥ 95%** del módulo.

## Riesgos y mitigaciones

| # | Riesgo | Mitigación |
|---|---|---|
| 1 | Errores en el catálogo se propagan silenciosamente | Property tests + fixtures con 20+ casos famosos cross-checked manualmente contra Tov/BHS |
| 2 | Copyright en explicaciones | Política explícita: prosa **original** del maintainer, guard test que detecta copia literal de stop-phrases de las fuentes citadas |
| 3 | Cobertura incompleta (~150 vs todas las discrepancias reales) | v1 cubre los casos académicamente documentados; v2 acepta PRs comunitarios con citación obligatoria |
| 4 | Usuarios asumen que mapeo implica equivalencia textual | El `explanation` siempre aclara "corresponde a"; nunca usamos "es igual a" |
| 5 | Performance al cargar JSON en cada call | `@lru_cache(maxsize=1)` en `load_catalog()` — un solo parse por proceso |
| 6 | Compatibilidad regresiva con `BibleRef` | `tradition` es Field con default; los 1984 tests existentes no se tocan |
| 7 | Confusión entre `verse_start=0` (superscript) y "no verse" | Documentar en docstring; tests específicos para Psalms |

## Métricas de éxito

- ✅ Catálogo JSON con ≥ 100 entradas validadas vs fuentes académicas citadas.
- ✅ `to_canonical` produce mapeo correcto para los 20 casos famosos del fixture.
- ✅ Property tests de idempotencia y round-trip pasan al 100%.
- ✅ Explicaciones en en/es/pt validadas como prosa original (guard test).
- ✅ CLI + MCP tool documentados en `docs/guias/versification.md`.
- ✅ Cero regresiones en los 1984 tests existentes.

## Pendientes explícitos (post-Fase 46)

- **Tradiciones adicionales**: siríaca peshitta, samaritana, copta — fase futura cuando haya demanda real.
- **Mapeo de fragmentos LXX-only** (Daniel adiciones, Susana, etc.): no aplica directamente al canon NWT, se documenta como "fuera de scope".
- **UI visual**: una vista web del catálogo es trabajo posterior; este spec entrega solo data + API.

## Cómo verificar al cerrar

```bash
# 1. Instalar
uv sync --all-packages

# 2. Tests del módulo
.venv/bin/python -m pytest packages/jw-core/tests/test_versification* -v

# 3. CLI smoke
uv run jw versification map "Joel 2:28" --from nwt --to masoretic
uv run jw versification explain "Psalm 51:1" --from nwt --to masoretic --lang es

# 4. MCP tool smoke
uv run jw mcp serve &
# llamar to_canonical_versification(ref="Mal 4:1", from_tradition="nwt", to_tradition="masoretic")

# 5. Audit de catálogo
uv run python scripts/audit_versification_catalog.py
# Imprime: # entradas, distribución por issue, libros cubiertos
```

## Plan de implementación (alto nivel)

Spec hijo: `docs/superpowers/plans/2026-05-31-fase-46-canonical-versification-plan.md`.

Pasos:

1. Scaffold `packages/jw-core/src/jw_core/versification/` + `models.py` con tests Pydantic.
2. Curar catálogo inicial (~30 entradas core: Joel, Mal, Salmos famosos) + `registry.py`.
3. Implementar `to_canonical` + property tests con hypothesis.
4. Extender `BibleRef.tradition` (campo opcional con default).
5. Completar catálogo a ≥ 100 entradas (Psalm superscriptions en lote).
6. Implementar `explain.py` con prosa trilingüe + guard test anti-copia.
7. CLI `jw versification` (Typer subcommand).
8. MCP tool `to_canonical_versification`.
9. Flag `--canonicalize` en `compare_translations`.
10. Guía `docs/guias/versification.md` + entrada en `docs/VISION_AUDIT.md`.
11. Audit script `scripts/audit_versification_catalog.py`.

Cada paso con su PR + tests + sin regresiones en los 1984 tests existentes.
