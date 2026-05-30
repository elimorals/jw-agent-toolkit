# jw-core

Librería principal de `jw-agent-toolkit`. Importable desde los demás paquetes del workspace.

## Módulos

### Parsers

- `jw_core.parsers.reference` — Parser multiidioma de citas bíblicas ("Juan 3:16", "1 Co 13:4-7")
- `jw_core.parsers.article` — wol.jw.org HTML → `Article` estructurado
- `jw_core.parsers.daily_text` — Parser del texto diario
- `jw_core.parsers.verse` — Extracción limpia de versículos individuales desde nwtsty
- `jw_core.parsers.study_notes` — Notas de estudio + marcadores de referencias cruzadas desde nwtsty
- `jw_core.parsers.topic_index` — Páginas de temas del Índice de Publicaciones Watch Tower
- `jw_core.parsers.epub` — Parser EPUB 3 estándar (XHTML sin cifrar)
- `jw_core.parsers.jwpub` — Parser JWPUB **con descifrado AES-128-CBC** (Fase 5.5). Algoritmo de derivación de clave de [`gokusander/jwpub-toolkit`](https://github.com/gokusander/jwpub-toolkit) (MIT). Expone `parse_jwpub_metadata()` (sin desencriptar — barato) y `parse_jwpub()` (con texto completo).

### Clientes HTTP

- `jw_core.clients.cdn` — `b.jw-cdn.org` (búsqueda autenticada con JWT)
- `jw_core.clients.wol` — Scraping HTML de wol.jw.org (Bible, articles, daily-text, document by id, publication TOC, cross-ref panels)
- `jw_core.clients.mediator` — `data.jw-api.org/mediator/*` (registro de idiomas + finder)
- `jw_core.clients.pub_media` — `GETPUBMEDIALINKS` para inventario de archivos + descargas streaming
- `jw_core.clients.topic_index` — Cliente de alto nivel para Índice de Publicaciones
- `jw_core.clients.weblang` — Cliente alterno `www.jw.org/{iso}/languages/` (más campos por idioma, actualizado con menor frecuencia)
- `jw_core.clients._polite` — Helper interno `politely_get()` que cablea throttler + cache + telemetría en cada GET
- `jw_core.clients.factory` — `build_clients()` arma una `ClientSuite` con los 6 clientes compartiendo infraestructura Fase 9

### Infraestructura (Fase 9)

- `jw_core.auth` — `JWTManager` async-safe para la API de búsqueda
- `jw_core.cache` — `DiskCache` SQLite con TTL, WAL, lazy eviction y `stats()`
- `jw_core.throttle` — `TokenBucket` + `Throttler` per-host + `backoff_delay` (full jitter exponencial)
- `jw_core.telemetry` — `Telemetry` opt-in (`JW_TELEMETRY_ENABLED=1`); fingerprint estructural de respuestas + detección de drift de API

### Soporte

- `jw_core.languages` — Registro de códigos de idiomas JW (ISO ↔ JW ↔ wol)
- `jw_core.models` — Modelos Pydantic (BibleRef, Verse, StudyNote, CrossReference, TopicSubject/Subheading/Citation, Epub/EpubDocument, JwpubMetadata/JwpubDocument)
- `jw_core.data.books` — Registro estático de 66 libros bíblicos × 3 idiomas

## API pública re-exportada

Desde `jw_core` directamente:

```python
from jw_core import BibleRef, parse_reference, parse_all_references
```

Desde `jw_core.parsers`:

```python
from jw_core.parsers import (
    BibleRef,
    parse_reference, parse_all_references,
    parse_verses, get_verse,
    parse_study_notes, parse_cross_references, study_notes_for_verse,
    parse_subject_page,
)
```

## Dependencias

- `httpx>=0.27.0` (HTTP async)
- `beautifulsoup4>=4.12.0` + `lxml>=5.0.0` (parsing HTML)
- `pydantic>=2.9.0` (modelos)
- `brotli>=1.1.0` (descompresión de respuestas WOL)
- `defusedxml>=0.7.1` (parsing seguro de XML para EPUB)
- `cryptography` (AES-128-CBC para descifrar JWPUB — resuelta vía dependencias transitivas; sirve añadirla explícitamente para ser claro)

## Referencia detallada

Ver [`docs/referencia/jw-core.md`](../../docs/referencia/jw-core.md) para la documentación exhaustiva módulo a módulo.
