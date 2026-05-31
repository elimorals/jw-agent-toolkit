# Fase 30 — Compañero de cánticos del Reino (metadata-only registry)

> **Fecha**: 2026-05-30
> **Estado**: Diseño aprobado (pendiente de implementación)
> **Owner**: Elias
> **Tier**: 4 (capa de UX / nicho)
> **Tamaño**: S (~2 días)
> **Depende de**: ninguna fase. Se integra de forma opt-in con `workbook_helper` (Fase 11).
> **Documento padre**: [`2026-05-30-fases-22-32-overview.md`](2026-05-30-fases-22-32-overview.md)
> **Sección de VISION**: #8 — Cánticos del Reino como apoyo a la reunión y al estudio personal.

## Motivación

El cancionero "Cantemos con gozo a Jehová" (símbolo `sjj`) tiene 151 cánticos. Cada reunión congregacional usa tres (apertura/intermedio/cierre) y el `workbook_helper` ya parsea sus números desde el HTML de la semana. Hoy el toolkit no entiende **qué** son esos números: aparecen como enteros sueltos en `metadata.songs`. Falta una capa que diga *"el cántico 5 es ‘El amor abnegado de Cristo’, basado en Juan 13:34-35, sobre el tema del amor cristiano"*.

Fase 30 cierra ese hueco entregando un **registro local de metadatos** — número, títulos por idioma (en/es/pt), tema, textos bíblicos citados y URL canónica en jw.org. Suficiente para enriquecer la salida del workbook helper, exponer una herramienta MCP `lookup_song`, y un comando `jw song <N>`.

## Límite legal duro — sin letra (lyrics)

**Las letras de los cánticos están bajo copyright de Watch Tower Bible and Tract Society of Pennsylvania.** El registro NO almacena letra, ni siquiera fragmentos. Lo que sí almacena:

1. **Número** del cántico (información factual no protegible).
2. **Títulos** en en/es/pt (información factual, paráfrasis cortas si la traducción literal del título canónico fuera dudosa).
3. **Tema** — una sola línea descriptiva escrita por el contribuidor (paráfrasis, no copia).
4. **Scriptures cited** — las referencias bíblicas que el cántico cita o desarrolla, en notación normalizada (`Juan 13:34-35`).
5. **URL canónica** en jw.org/wol.jw.org cuando exista.

Lo que **NO** almacena (no negociable):

- Letra de ninguna estrofa, ni siquiera la primera línea.
- Partitura, MP3, MIDI, ni enlaces directos a esos archivos.
- Traducciones de la letra que no sean el título oficial.

El seed inicial cubre **los ~10-12 cánticos más frecuentes** (apertura/cierre de reunión, los del Memorial, los más usados en asambleas). Expansión hasta los 151 vía PR comunitario — explícitamente etiquetada como "no exhaustiva" en la guía para reducir riesgo de "compilación derivativa". El usuario que necesite los 151 los tiene en la app oficial JW Library.

Esta política se hace eco de las decisiones ya tomadas para `jw-finetune` (no distribuir pesos derivados de corpus protegido) y se documenta en `docs/guias/canticos-del-reino.md`.

## Objetivos

1. Crear `jw_core.songs` — paquete con registro JSON por idioma y API de consulta.
2. Integrar opt-in con `workbook_helper` para que los números de cántico se enriquezcan con metadatos.
3. Exponer `lookup_song(number, language)` y `songs_for_week(year_iso_week, language)` por CLI + MCP.
4. Garantizar que cada `scriptures_cited` se resuelve con `parse_reference` y produce `BibleRef` con URL canónica.
5. CERO red en tests. El registro es local; el lookup de URL en jw.org es derivado por patrón documentado.

## No-objetivos (boundaries vinculantes)

- **No** distribuir letra, partitura, ni audio. Ver sección anterior.
- **No** auto-scrape del sitio para construir el registro. La curaduría es manual, en PRs revisables.
- **No** modificar `workbook_helper` destructivamente. El enriquecimiento se hace en un adapter `enrich_with_songs(meeting_outline)` que se llama de forma opcional.
- **No** intentar buscar por tema/palabra clave en una primera versión (sería re-implementar el índice del cancionero — alcance Fase 31 si surge demanda).
- **No** persistir cánticos "favoritos" del usuario (alcance de `personal_notes` futuro si llega a pedirse).

## Arquitectura

Dos componentes nuevos en `jw-core` (sin paquete propio — el módulo es pequeño y la información es estática):

```
packages/jw-core/src/jw_core/
├── data/
│   └── kingdom_songs/
│       ├── __init__.py            # marker
│       ├── E.json                 # English seed (~10-12 inicial; PRs amplían)
│       ├── S.json                 # Spanish seed
│       └── T.json                 # Portuguese seed
└── songs/
    ├── __init__.py                # exporta SongRegistry, KingdomSong, get_registry
    ├── models.py                  # Pydantic KingdomSong + SongsByWeek
    ├── registry.py                # loader + lookup, lru_cache por idioma
    └── integration.py             # enrich_with_songs(AgentResult, language)
```

Las superficies (CLI/MCP) se extienden:

```
packages/jw-cli/src/jw_cli/commands/song.py    # nuevo subcomando
packages/jw-cli/src/jw_cli/main.py             # registrar el subcomando
packages/jw-mcp/src/jw_mcp/server.py           # añadir lookup_song + songs_for_week
```

**Reglas duras**:

1. `jw_core.songs.registry` se carga vía `importlib.resources` desde `jw_core.data.kingdom_songs` (no rutas relativas en disco — funciona desde wheel instalado).
2. `lru_cache` por (idioma) — el JSON se parsea una sola vez.
3. La validación Pydantic ocurre en carga; un seed mal formado falla rápido y ruidosamente.
4. La integración con `workbook_helper` es por adapter en `songs/integration.py` — el agente no se toca.
5. La URL canónica en jw.org se deriva con un patrón **declarado** (ver más abajo); no se hace ningún GET en runtime.

## Modelo de datos

```python
# jw_core/songs/models.py

class KingdomSong(BaseModel):
    """Metadata-only descriptor for one Kingdom Song.

    NEVER include lyrics. The `theme` field is a single-line paraphrase
    by the contributor — not a copy of the printed subtitle.
    """

    number: int = Field(ge=1, le=200, description="Songbook number (1..151 for sjj)")
    title: str = Field(description="Official song title in the registry's language")
    theme: str = Field(description="One-line paraphrase by the contributor. NO LYRICS.")
    scriptures: list[str] = Field(
        default_factory=list,
        description="Bible references the song develops, e.g. ['Juan 13:34-35'].",
    )
    language: str = Field(description="ISO code: en, es, pt")
    pub_symbol: str = Field(default="sjj", description="Songbook publication code")
    canonical_url: str = Field(
        default="",
        description="Derived URL on jw.org/wol.jw.org. Empty = unknown.",
    )

    def resolved_scriptures(self) -> list["BibleRef"]:
        """Run each `scriptures` entry through `parse_reference` and return
        the successful BibleRef objects (drops the ones that fail to parse)."""

class SongLookupError(LookupError):
    pass
```

`canonical_url` se rellena al cargar usando el patrón documentado:

```
https://wol.jw.org/{iso}/wol/d/{wol_resource}/{lp_tag}/{docId}
```

Para el cancionero `sjj` no conocemos el `docId` por número de canto sin scraping. **Fallback escalonado**, sin red:

1. Si el registro JSON trae `doc_id`, construir la URL completa.
2. Si no, usar la URL del cancionero completo: `https://www.jw.org/finder?wtlocale={CODE}&pub=sjj` con el código JW (`E`, `S`, `T`). Esto siempre resuelve a la página de discoverability de jw.org y es estable.
3. Si la entrada tiene un `canonical_url` explícito en el JSON, gana sobre los dos anteriores.

`pub_media.PubMediaClient` queda **disponible pero no se llama** desde el registro. Una utilidad de mantenimiento `scripts/refresh_song_urls.py` (one-shot, fuera del paquete) puede usar pub_media para rellenar `doc_id` antes de un PR — pero el código de runtime nunca hace red.

## API pública

```python
# jw_core/songs/__init__.py
from jw_core.songs.models import KingdomSong, SongLookupError
from jw_core.songs.registry import SongRegistry, get_registry

# jw_core/songs/registry.py
class SongRegistry:
    @classmethod
    def for_language(cls, language: str) -> SongRegistry: ...
    def lookup(self, number: int) -> KingdomSong: ...   # raises SongLookupError
    def get(self, number: int) -> KingdomSong | None: ...
    def all(self) -> list[KingdomSong]: ...
    def language(self) -> str: ...

def get_registry(language: str = "en") -> SongRegistry: ...  # cached
```

```python
# jw_core/songs/integration.py
def enrich_with_songs(result: AgentResult, language: str = "en") -> AgentResult:
    """Walk `result.findings`, find the workbook_week finding (Fase 11
    emits `citation.metadata.songs = {opening,middle,closing}`), and
    append three SONG findings — one per slot. Idempotent: re-running
    doesn't duplicate.

    Returns the SAME AgentResult, mutated. Findings emitted have
    `metadata['source'] = 'kingdom_song'`.
    """
```

## Esquema JSON del seed

Un archivo por idioma. Lista plana ordenada por número:

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
    "number": 5,
    "title": "El amor abnegado de Cristo",
    "theme": "El amor sacrificial de Cristo como modelo para los cristianos.",
    "scriptures": ["Juan 13:34-35", "1 Juan 3:16"],
    "doc_id": null,
    "canonical_url": ""
  }
]
```

El loader rellena `language`, `pub_symbol` (siempre `"sjj"` por ahora) y deriva `canonical_url` si no viene.

## Seed mínimo viable

12 entradas por idioma (cánticos altamente frecuentes en reuniones, asambleas y Memorial — todos ellos información factual, los títulos son traducciones oficiales conocidas que existen en el dominio público vía la app JW Library):

| # | Tema funcional |
|---|---|
| 1 | Las cualidades de Jehová |
| 2 | Jehová es nuestro nombre |
| 5 | El amor abnegado de Cristo |
| 17 | "Yo iré, envíame a mí" |
| 20 | Tú redimiste con tu sangre preciosa (Memorial) |
| 47 | Una oración diaria |
| 60 | Es la vida que él dio (Memorial) |
| 95 | "La luz hace su entrada" |
| 102 | "Acordándote del Creador" |
| 109 | Cantemos con todo el corazón |
| 134 | Mira, los hijos son una herencia |
| 151 | Nos llamará Jehová |

(Conjuntos espejados en E.json / S.json / T.json con títulos oficiales en cada idioma.)

Extensión hasta cobertura total: PR comunitario incremental, cada PR añade ≤ 20 entradas y debe pasar el lint `test_seed_integrity` (ver Riesgos).

## Integración con `workbook_helper`

`workbook_helper` ya emite, en el primer `Finding` (kind `workbook_week`), un metadata:

```python
citation.metadata = {
    ...,
    "songs": {"opening": 5, "middle": 47, "closing": 151},
}
```

`enrich_with_songs(result, language)`:

1. Busca el primer finding con `citation.kind == "workbook_week"`.
2. Lee `citation.metadata["songs"]` — un dict con `opening|middle|closing → int|None`.
3. Para cada slot no-nulo, `registry.get(number)`; si existe, añade un nuevo `Finding`:

```python
Finding(
    summary=f"Cántico {n} (apertura): {song.title}",
    excerpt=song.theme,
    citation=Citation(
        url=song.canonical_url,
        title=song.title,
        kind="kingdom_song",
        metadata={"number": n, "slot": "opening", "scriptures": song.scriptures},
    ),
    metadata={"source": "kingdom_song"},
)
```

Idempotencia: antes de añadir, comprueba si ya existe un finding con `citation.kind == "kingdom_song"` y mismo `metadata.number+slot`. Si sí, no duplica.

`workbook_helper` queda intacto. El call-site (CLI workbook + tool MCP `workbook_helper`) puede decidir si llama o no a `enrich_with_songs`. Para Fase 30 lo cableamos como opt-in en CLI (flag `--with-songs`) y siempre activo en una nueva tool `workbook_with_songs` (que es composición pura sin modificar la existente).

## CLI

Nuevo subcomando `jw song`:

```
jw song 5                       # default: en
jw song 5 --lang es             # → "Cántico 5 · El amor abnegado de Cristo"
                                #    Tema: amor sacrificial de Cristo
                                #    Textos: Juan 13:34-35, 1 Juan 3:16
                                #    URL: https://www.jw.org/finder?wtlocale=S&pub=sjj
jw song week                    # cánticos de la semana en curso (lee workbook)
jw song week --date 2026-07-13 --lang pt
```

`jw song week` orquesta `workbook_helper` + `enrich_with_songs` y solo imprime los findings `source=kingdom_song`.

Renderiza con Rich (Panel + Table coherente con `jw workbook`).

## MCP

Dos nuevas tools en `jw_mcp.server`:

```python
@mcp.tool()
def lookup_song(number: int, language: str = "en") -> dict[str, Any]:
    """Look up Kingdom Song metadata by number. Returns:
       {number, title, theme, scriptures, scriptures_resolved, canonical_url,
        language, pub_symbol}.
       Returns {"error": "..."} on unknown number."""

@mcp.tool()
async def songs_for_week(
    date: str | None = None,            # ISO date, default today
    language: str = "en",
    include_watchtower: bool = False,   # passthrough to workbook_helper
) -> dict[str, Any]:
    """Resolve the workbook for the week containing `date`, then enrich
    with song metadata. Returns AgentResult-as-dict with only the
    kingdom_song findings extracted, plus the underlying workbook metadata
    for context."""
```

`lookup_song` no hace red. `songs_for_week` sí (la parte de `workbook_helper`).

## Tests (todos sin red)

`packages/jw-core/tests/test_kingdom_songs.py`:

1. `test_seed_loads_three_languages` — los 3 JSON cargan sin errores, ≥ 10 entradas cada uno.
2. `test_seed_integrity` — invariantes:
   - Cada `number` es 1..151.
   - Mismo `number` en E/S/T (cobertura paralela).
   - No hay `lyrics`, `verse`, `stanza` ni longitudes >120 chars en `theme` (heurística anti-letra).
   - Todas las `scriptures` parsean con `parse_reference`.
3. `test_lookup_by_number` — `registry.lookup(5)` devuelve un `KingdomSong`.
4. `test_lookup_unknown_raises_song_lookup_error`.
5. `test_get_registry_caches_per_language` — mismo objeto al llamar dos veces.
6. `test_resolved_scriptures_returns_biblerefs`.
7. `test_canonical_url_falls_back_to_finder_pattern` — sin `doc_id` ni `canonical_url`, el URL es `https://www.jw.org/finder?wtlocale=S&pub=sjj` (S para es).
8. `test_enrich_with_songs_adds_three_findings` — fixture sintética de `AgentResult` con un `workbook_week` finding cuyos `songs={opening:5,middle:47,closing:151}` produce 3 nuevos findings.
9. `test_enrich_with_songs_is_idempotent` — llamar dos veces no duplica.
10. `test_enrich_with_songs_handles_unknown_song_gracefully` — número 999 → warning, no crash.
11. `test_enrich_with_songs_no_workbook_week_finding` — sin el finding base, devuelve el `AgentResult` sin cambios.
12. `test_cli_song_renders_table` — usa `typer.testing.CliRunner`.

Existing 551 tests no se tocan. La suite global pasa de 551 → ≥ 563 verdes.

## Riesgos y mitigaciones

| # | Riesgo | Mitigación |
|---|---|---|
| 1 | Alguien contribuye un PR con letra en `theme` | `test_seed_integrity` enforza longitud ≤ 120 chars; revisión humana en PR; guía explícita. |
| 2 | Distribución acumulada (151 entradas) podría leerse como compilación derivativa | El seed inicial es ~12 entradas; guía advierte "no exhaustivo"; comentario al inicio de cada JSON cita la política. |
| 3 | URLs derivadas rotas (jw.org cambia el `finder`) | Patrón documentado; cobertura por `test_canonical_url_*`; fallback a string vacío + warning, nunca crash. |
| 4 | El workbook helper en futuras versiones cambia su `metadata.songs` | `enrich_with_songs` valida shape antes de leer; warning si el shape cambió. |
| 5 | Idiomas distintos de en/es/pt | El loader devuelve registro vacío para idiomas desconocidos y emite warning; lookup falla limpiamente. |
| 6 | Test de integridad falso negativo bloquea PRs legítimos | Los thresholds (≤120 chars, palabras prohibidas) están parametrizadas con override en `pytest.ini` para casos justificados. |
| 7 | Importlib.resources cambia API entre Python 3.13 mantenimientos | Uso `importlib.resources.files()` (estable desde 3.9). |

## Métricas de éxito de la fase

- ✅ `jw song 5 --lang es` imprime título + tema + textos + URL en <100ms.
- ✅ `jw song week` orquesta workbook + enrich sin red en tests (con cassette).
- ✅ Tool MCP `lookup_song` devuelve JSON parseable.
- ✅ `enrich_with_songs(workbook_result)` añade exactamente 3 findings cuando los 3 slots están llenos.
- ✅ Seed E/S/T con 12 entradas cada uno + 17 archivos JSON válidos (3 idiomas × {1,2,5,17,20,47,60,95,102,109,134,151}).
- ✅ `test_seed_integrity` pasa.
- ✅ Documentado en `docs/guias/canticos-del-reino.md` con la sección legal al frente.
- ✅ Audit row en `docs/VISION_AUDIT.md` apuntando a sección VISION #8.

## Cómo verificar al cerrar

```bash
# 1. Instalar
uv sync --all-packages

# 2. Tests del nuevo módulo
.venv/bin/python -m pytest packages/jw-core/tests/test_kingdom_songs.py -v

# 3. Suite global no regresa
.venv/bin/python -m pytest

# 4. CLI
jw song 5 --lang es
jw song week --lang en --date 2026-07-13

# 5. Lint del seed
.venv/bin/python -m pytest packages/jw-core/tests/test_kingdom_songs.py::test_seed_integrity
```

## Plan de implementación

Hijo: [`2026-05-30-fase-30-kingdom-songs-plan.md`](../plans/2026-05-30-fase-30-kingdom-songs-plan.md). 12 tareas TDD secuenciales sumando ~2 días.
