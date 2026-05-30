# jw-core

Librería principal de `jw-agent-toolkit`. Importable desde los demás paquetes del workspace.

## Módulos

- `jw_core.parsers.reference` — Parser multiidioma de citas bíblicas ("Juan 3:16", "1 Co 13:4-7")
- `jw_core.parsers.article` — wol.jw.org HTML → `Article` estructurado
- `jw_core.parsers.daily_text` — Parser del texto diario
- `jw_core.parsers.verse` — Extracción limpia de versículos individuales desde nwtsty
- `jw_core.parsers.study_notes` — Notas de estudio + marcadores de referencias cruzadas desde nwtsty
- `jw_core.parsers.topic_index` — Páginas de temas del Índice de Publicaciones Watch Tower
- `jw_core.parsers.epub` — Parser EPUB 3 estándar (alternativa abierta al JWPUB)
- `jw_core.parsers.jwpub` — Extractor de metadata JWPUB (texto cifrado no disponible — ver Fase 5 en ROADMAP)
- `jw_core.clients.cdn` — `b.jw-cdn.org` (búsqueda + tokens JWT)
- `jw_core.clients.wol` — Scraping HTML de wol.jw.org
- `jw_core.clients.mediator` — `data.jw-api.org/mediator/*` (registro de idiomas + finder)
- `jw_core.clients.pub_media` — `GETPUBMEDIALINKS` para inventario de archivos + descargas
- `jw_core.clients.topic_index` — Cliente de alto nivel para Índice de Publicaciones
- `jw_core.languages` — Registro de códigos de idiomas JW (ISO ↔ JW ↔ wol)
- `jw_core.models` — Modelos Pydantic (BibleRef, Verse, StudyNote, CrossReference,
  TopicSubject, TopicSubheading, TopicCitation, Epub, EpubDocument,
  JwpubMetadata, JwpubDocument)
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
- `defusedxml` (parsing seguro de XML para EPUB)

## Referencia detallada

Ver [`docs/referencia/jw-core.md`](../../docs/referencia/jw-core.md) para la documentación exhaustiva módulo a módulo.
