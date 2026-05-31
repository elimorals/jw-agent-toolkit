# Concordancia exacta NWT + publicaciones

> Búsqueda **literal** sobre tu corpus local descifrado (NWT, JWPUB, EPUB). Complementa el RAG semántico — no lo reemplaza.

## Cuándo usar concordancia y cuándo RAG

| Pregunta | Herramienta |
|---|---|
| ¿Dónde aparece exactamente la frase "conocimiento exacto"? | `jw grep "\"conocimiento exacto\""` |
| ¿Qué versículos hablan sobre el conocimiento? | `jw rag "qué dice la Biblia sobre el conocimiento"` |
| ¿Cuántas veces aparece "Jehová" en el NT? | `jw grep "Jehová" --kind nwt --max 500` |

## Construir el índice

```bash
# Indexar un archivo concreto
jw grep --build-index ~/jw-publications/w24.jwpub --language es

# Indexar una carpeta entera (recursivo)
jw grep --build-index ~/jw-publications --language es --recursive

# Ingerir un capítulo NWT desde WOL (red sólo en este paso)
jw grep --build-nwt "Juan 3" --language es

# Forzar re-indexación de un archivo modificado
jw grep --build-index w24.jwpub --language es --force

# Ver estadísticas
jw grep --stats
```

El índice vive en `~/.jw-agent-toolkit/concordance.db` (override con `JW_CONCORDANCE_DB`). Es SQLite WAL — abierto en lectura por múltiples procesos sin bloqueo.

## Gramática de consultas

Soporta la sintaxis nativa **FTS5** (no regex):

| Operador | Ejemplo | Significado |
|---|---|---|
| Phrase | `"reino de Dios"` | Frase exacta |
| AND | `Jehová amor` | Ambos términos (orden libre) |
| OR | `"reino de Dios" OR "reino del cielo"` | Cualquiera |
| NOT | `Jehová NOT espíritu` | Excluir |
| NEAR | `Jehová NEAR/3 amor` | Distancia ≤ 3 tokens |
| Prefix | `inteli*` | "inteligente", "inteligencia"... |

### Diacríticos

El tokenizador es `unicode61 remove_diacritics 2` → **busca `"espiritu"` y encuentras `"Espíritu"`** (y viceversa). Esto vale en español/portugués/inglés. Si necesitas búsqueda sensible a acentos, abre un issue.

### Sin regex

`\b`, `[abc]`, `+`, `^`, `$` y compañía **no** funcionan — el comando se rehúsa con un mensaje claro. Para variantes morfológicas usa el RAG semántico.

## Filtros

```bash
jw grep "amó" --language es
jw grep "amó" --kind nwt          # sólo Biblia
jw grep "amó" --kind jwpub        # sólo publicaciones
jw grep "amó" --max 200           # techo de resultados
```

## API Python

```python
from jw_core.concordance import build_index, concordance_search
from pathlib import Path

build_index(
    paths=[Path("~/jw-publications/w24.jwpub").expanduser()],
    language="es",
)
hits = concordance_search('"conocimiento exacto"', language="es")
for h in hits:
    print(h.ref, "→", h.snippet, "·", h.url or "(sin URL canónica)")
```

## MCP tools

- `concordance_build_index(paths, language, force)` → `{inserted, files}` ó `{error}`.
- `concordance_search(query, language?, source_kind?, max_results?)` → `{hits: [...]}` ó `{error}`.

## Limitaciones conocidas

- No indexa fuentes Obsidian (Fase 20) — pendiente.
- No persiste el contexto antes/después del párrafo — sólo el párrafo en sí. Si quieres más contexto, abre el `url` en navegador.
- El tamaño del índice crece linealmente con el corpus. ~50 MB cada 25 publicaciones.

## Privacidad y copyright

La DB queda **sólo en tu máquina**. Nada se sube. Las publicaciones siguen siendo propiedad de Watch Tower Bible and Tract Society — el toolkit solo facilita búsqueda offline sobre el material que ya tienes legalmente descargado.
