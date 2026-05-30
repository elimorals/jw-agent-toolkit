# Guía: scripts de exploración y reverse engineering

> Los 20 scripts en `scripts/` son herramientas de un solo uso que sirvieron para diseñar parsers, validar APIs en vivo y revertir el formato JWPUB. No son parte del producto; quedan en el repo como **memoria de cómo se hicieron las cosas** y como sandbox para experimentos nuevos.

## Cómo se ejecutan

Cada script es un `.py` ejecutable que asume `uv sync --all-packages` previo:

```bash
uv run python scripts/<nombre>.py
```

Algunos requieren archivos en `data/` (JWPUB/EPUB descargados) o `packages/jw-core/tests/fixtures/` (HTML fixtures).

## Familias

### Discovery / fixtures

| Script | Propósito |
|---|---|
| `fetch_topic_fixtures.py` | Descarga 3 páginas de tema (`wt_pub_index_home.html`, `wt_pub_index_trinity.html`, `wt_research_guide.html`) y las guarda como fixtures para los parser tests. |
| `fetch_religions_subject.py` | Descarga el subject "Religions, Customs, and Beliefs" (formato article-title-style) → `wt_pub_index_alt_1204387.html`. |

### Exploración de HTML

Estos scripts cargan un fixture o URL en vivo y dumpean estructura (clases más frecuentes, anchors, atributos) para guiar el diseño del parser.

| Script | Sobre qué |
|---|---|
| `explore_topic_index.py` | Páginas de tema del Índice de Publicaciones — top 15 clases en el `<article>`. |
| `explore_trinity.py` | El subject "Trinity" específicamente. |
| `explore_alt_subject.py` | Subject estilo "article_title" (formato distinto a Trinity). |
| `explore_nwtsty.py` | Capítulos de la NWT Study Edition — cómo está marcado el contenido. |
| `explore_nwtsty2.py` | Segunda iteración con énfasis en notas de estudio. |
| `explore_datapid.py` | Hipótesis: ¿el `data-pid` de las notas matchea con el del cuerpo? (Resultado: no — números independientes). |
| `explore_datapid2.py` | Segunda iteración del análisis. |
| `explore_pubcode_anchors.py` | Códigos de publicación dentro de subjects: `<a>` sin clase apuntando a `/pc/`. |

### JWPUB — reverse engineering del formato

JWPUB es ZIP doble + SQLite con `Content` cifrado AES-128-CBC sobre zlib. Documentamos cada intento:

| Script | Estrategia probada |
|---|---|
| `inspect_jwpub.py` | Estructura general: outer ZIP → `manifest.json` + ZIP interno → SQLite. Lista las tablas y la longitud de `Content`. |
| `inspect_jwpub2.py` | Versión refinada: extrae el `manifest.publication` y la primera fila `Document`. |
| `try_jwpub_decrypt.py` | Combinaciones AES-128/256 con claves derivadas de `manifest.hash` (SHA256, 32 bytes) y `publication.hash` (SHA1, 20 bytes). **Falló.** |
| `try_jwpub_decrypt2.py` | Variantes con claves derivadas por documento: `sha256(meps_id_{LE,BE}{4,8} + manifest_hash)`, IVs múltiples. **Falló.** |
| `try_jwpub_decrypt3.py` | Combinaciones de zlib en diferentes offsets, raw deflate, gzip. **Falló.** |
| `try_jwpub_decrypt4.py` | Hipótesis: `"z-a"` no significa AES — variantes con plain zlib offset/deflate. **Falló.** |

**El éxito vino de afuera**: `gokusander/jwpub-toolkit` (MIT) publicó la derivación correcta:
`SHA256(f"{lang_index}_{symbol}_{year}") XOR magic_32byte`. Lo implementamos en `parsers/jwpub._compute_key_iv`.

### EPUB

| Script | Propósito |
|---|---|
| `inspect_epub.py` | Vuelca la estructura: archivos del ZIP, `container.xml`, OPF preview. Útil para entender variantes EPUB de JW antes de escribir el parser. |

### Descarga de fixtures binarios

| Script | Propósito |
|---|---|
| `download_jwpub.py` | Baja `fg` y `ti` en formato JWPUB vía `GETPUBMEDIALINKS` a `data/jwpub_test/`. Idempotente (chequea tamaño). |

### Live tests end-to-end

Smoke tests que confirman que el toolkit funciona contra la API real (no mockeado).

| Script | Verifica |
|---|---|
| `live_test_phase3.py` | `verse_explainer("Juan 3:16")` + `parse_study_notes` + `parse_cross_references` contra wol.jw.org en vivo. |
| `live_test_phase4.py` | `TopicIndexClient.search_subjects("Trinity")` + `get_subject_page` + `apologetics("What does the Bible teach about the Trinity?")`. Cuenta findings por `source` para verificar el ordering del agente. |

## Cuándo crear un script nuevo

- **Caso**: estás diseñando un parser para una página de JW que aún no soportamos.
- **Patrón**: copia `explore_*` o `fetch_topic_fixtures.py` como punto de partida. Descarga 1-2 ejemplos, dumpea estructura, escribe el parser, luego añade el fixture a `packages/jw-core/tests/fixtures/`.

## Cuándo NO

- Para **debugging puntual**, los REPL `python -i` o tests one-off funcionan mejor.
- Para **cassettes pytest-recording**, ver `packages/jw-core/tests/test_cassettes.py` — no necesitan script aparte.

## Limpieza periódica

Los scripts no se ejecutan en CI. Si uno duplica funcionalidad ya cubierta por una función pública o un agente, considera borrarlo (la memoria histórica vale, pero la deuda de mantenimiento también).

## Ver también

- [`docs/conceptos/ci-y-testing.md`](../conceptos/ci-y-testing.md) — CI workflow y sistema de cassettes
- [`packages/jw-core/tests/fixtures/`](../../packages/jw-core/tests/fixtures/) — 5 fixtures HTML usadas por los tests
