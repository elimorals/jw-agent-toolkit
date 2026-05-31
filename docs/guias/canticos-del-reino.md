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
│ Theme       El amor sacrificial de Cristo como modelo │
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
    print(ref.book_num, ref.chapter, ref.verse_start)

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
