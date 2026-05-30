# Referencia: jw-core

> Documentación exhaustiva de cada módulo, clase y función pública del paquete `jw-core`.

## Estructura del paquete

```
jw_core/
├── __init__.py            # Re-exporta BibleRef, parse_reference, parse_all_references
├── languages.py           # Registro Language + get_language + all_languages
├── models.py              # Modelos Pydantic: BibleRef, Verse, StudyNote, ...
├── data/
│   ├── __init__.py
│   └── books.py           # BOOKS — 66 libros × 3+ idiomas
├── clients/
│   ├── __init__.py
│   ├── cdn.py             # CDNClient + CDNError + VALID_FILTERS
│   ├── wol.py             # WOLClient + WOLError
│   ├── mediator.py        # MediatorClient + MediatorLanguage + MediatorError
│   ├── pub_media.py       # PubMediaClient + Publication + PubMediaFile + ...
│   └── topic_index.py     # TopicIndexClient + TopicIndexError
└── parsers/
    ├── __init__.py        # Re-exporta los entry points públicos
    ├── reference.py       # ReferenceParser + parse_reference + parse_all_references
    ├── article.py         # parse_article + Article
    ├── daily_text.py      # parse_daily_text + DailyText
    ├── verse.py           # parse_verses + get_verse
    ├── study_notes.py     # parse_study_notes + parse_cross_references + study_notes_for_verse
    ├── topic_index.py     # parse_subject_page
    ├── epub.py            # parse_epub
    └── jwpub.py           # parse_jwpub_metadata + JwpubError
```

---

## Módulo `jw_core.languages`

### `class Language`

`@dataclass(frozen=True)` — describe un idioma soportado.

| Campo | Tipo | Descripción |
|---|---|---|
| `iso` | `str` | ISO 639-1 lowercase (`"en"`, `"es"`, `"pt"`) |
| `jw_code` | `str` | Código interno JW (`"E"`, `"S"`, `"T"`) |
| `lp_tag` | `str` | Tag de URL WOL (`"lp-e"`, `"lp-s"`, `"lp-t"`) |
| `display` | `str` | Nombre legible (`"English"`, `"Spanish"`, ...) |
| `wol_resource` | `str` | Token `r{N}` usado en URLs WOL |
| `default_bible` | `str` | Código de Biblia por defecto (`"nwtsty"` o `"nwt"`) |

### `get_language(iso_or_jw: str) -> Language`

Resuelve un idioma por ISO (`"es"`) o código JW (`"S"`).

**Excepciones**: `KeyError` si el idioma no está registrado.

### `all_languages() -> list[Language]`

Devuelve la lista completa de idiomas registrados.

---

## Módulo `jw_core.models`

Todos los modelos son `pydantic.BaseModel` (excepto `Article` y `DailyText` que son `@dataclass`).

### `class BibleRef`

Cita bíblica parseada.

| Campo | Tipo | Constraints | Descripción |
|---|---|---|---|
| `book_num` | `int` | `1..66` | Número canónico del libro |
| `book_canonical` | `str` | — | Nombre canónico en inglés |
| `chapter` | `int` | `≥1` | Número de capítulo |
| `verse_start` | `int \| None` | `≥1` | Primer versículo del rango |
| `verse_end` | `int \| None` | `≥1` | Último versículo del rango |
| `detected_language` | `str` | — | ISO code detectado |
| `raw_match` | `str` | — | Substring que matcheó en la entrada |

**Propiedades**:
- `has_verse: bool` — True si `verse_start` no es None.
- `verse_range: str` — `"4-7"` para rango, `"4"` para uno, `""` si no hay versículo.

**Métodos**:
- `display(lang: str | None = None) -> str` — Renderiza como `"Book Chapter:Verse"`.
- `wol_url(lang: str = "en", pub: str | None = None) -> str` — Construye URL canónica de wol.jw.org. Si `verse_start` está set, añade ancla `#study=discover&v=...`.

### `class Verse`

Un versículo extraído del HTML nwtsty.

| Campo | Tipo | Constraints | Descripción |
|---|---|---|---|
| `book_num` | `int` | `1..66` | |
| `chapter` | `int` | `≥1` | |
| `verse` | `int` | `≥1` | |
| `text` | `str` | — | Texto limpio (sin `·`, `ʹ`, `+`, `*`, ni número de versículo inicial) |
| `language` | `str` | default `"en"` | ISO code |

**Método**: `wol_url(pub: str | None = None) -> str` — URL al ancla del versículo.

### `class StudyNote`

Una nota de estudio del NWT Study Edition (nwtsty).

| Campo | Tipo | Default | Descripción |
|---|---|---|---|
| `book_num` | `int` | — | `1..66` |
| `chapter` | `int` | — | `≥1` |
| `verse` | `int \| None` | `None` | Verso al que se mapea (puede ser None si `confidence="unmatched"`) |
| `headword` | `str` | — | Frase que la nota anota (`"born again"`, etc.) |
| `body` | `str` | — | Comentario en texto plano |
| `inline_refs` | `list[str]` | `[]` | Cross-refs mencionados en el cuerpo |
| `language` | `str` | `"en"` | |
| `confidence` | `str` | `"headword"` | `"headword"` / `"positional"` / `"unmatched"` |

### `class CrossReference`

Un marcador inline `+` dentro de un versículo.

| Campo | Tipo | Constraints | Descripción |
|---|---|---|---|
| `book_num` | `int` | `1..66` | |
| `chapter` | `int` | `≥1` | |
| `verse` | `int` | `≥1` | |
| `href` | `str` | — | URL relativa del panel WOL (`/en/wol/bc/...`) |
| `marker` | `str` | default `"+"` | Símbolo usado inline |
| `language` | `str` | default `"en"` | |

**Método**: `full_url() -> str` — Convierte `href` relativo a URL absoluta.

### `class TopicCitation`

Una cita dentro de un subtítulo del índice temático.

| Campo | Tipo | Descripción |
|---|---|---|
| `text` | `str` | Texto visible de la cita |
| `kind` | `str` | `"bible"`, `"publication"`, `"section"`, `"document"`, `"other"` |
| `url` | `str \| None` | URL absoluta cuando se conoce |

### `class TopicSubheading`

| Campo | Tipo | Descripción |
|---|---|---|
| `heading` | `str` | Texto del subtítulo (antes del primer `:`) |
| `citations` | `list[TopicCitation]` | Citas dentro de este subtítulo |
| `is_top_level` | `bool` | `True` para `<p class="su">`, `False` para `sv` |

### `class TopicSubject`

Una página de tema del Índice de Publicaciones Watch Tower.

| Campo | Tipo | Descripción |
|---|---|---|
| `docid` | `str` | WOL document id |
| `title` | `str` | Título del tema |
| `see_also` | `list[str]` | Referencias a otros temas |
| `subheadings` | `list[TopicSubheading]` | Subtítulos en orden |
| `source_url` | `str` | URL completa |
| `language` | `str` | |
| `style` | `str` | `"trinity"` o `"article_title"` |

**Propiedad**: `total_citations: int` — suma de citas en todos los subtítulos.

### `class Epub`

EPUB 3 parseado.

| Campo | Tipo | Descripción |
|---|---|---|
| `title`, `creator`, `language`, `publisher`, `identifier` | `str` | Metadata del OPF |
| `documents` | `list[EpubDocument]` | En orden del spine |
| `source_path` | `str` | Path absoluto del archivo |

**Propiedades**: `document_count`, `paragraph_count`.

### `class EpubDocument`

Un documento dentro del spine.

| Campo | Tipo | Descripción |
|---|---|---|
| `id` | `str` | Spine item id |
| `title` | `str` | Del `<title>` o primer heading |
| `href` | `str` | Path interno del EPUB |
| `paragraphs` | `list[str]` | Párrafos extraídos |
| `spine_index` | `int` | Posición 0-based en el spine |

### `class JwpubMetadata` y `class JwpubDocument`

Metadata-only del JWPUB (el contenido está cifrado). Ver código fuente para campos completos — incluye `manifest_hash`, `schema_version`, `decrypted_text_available=False`, y TOC vía `documents`.

---

## Módulo `jw_core.data.books`

### `BOOKS: list[BookEntry]`

Registro estático de los 66 libros bíblicos. Cada entrada:

```python
{
    "num": int,              # 1..66
    "canonical": str,        # Nombre canónico inglés
    "names": {
        "en": list[str],     # [principal, alias1, alias2, ...]
        "es": list[str],
        "pt": list[str],
    }
}
```

Sanity checks al import: `assert len(BOOKS) == 66`, números 1..66 en orden.

---

## Módulo `jw_core.parsers.reference`

### `class ReferenceParser`

Parser de citas bíblicas multi-idioma.

**`__init__()`**: construye el índice y compila la regex maestra. No tiene parámetros.

**`parse(text: str) -> list[BibleRef]`**: encuentra todas las citas en `text`.

**`parse_one(text: str) -> BibleRef | None`**: devuelve la primera cita o None.

### `parse_reference(text: str) -> BibleRef | None`

Wrapper sobre el singleton. Equivalente a `_singleton().parse_one(text)`.

### `parse_all_references(text: str) -> list[BibleRef]`

Wrapper sobre el singleton. Equivalente a `_singleton().parse(text)`.

### `_singleton()` (interno)

`@lru_cache(maxsize=1)` — devuelve un `ReferenceParser` global.

---

## Módulo `jw_core.parsers.article`

### `class Article` (dataclass)

| Campo | Tipo | Descripción |
|---|---|---|
| `title` | `str` | Del `<h1>` o `<title>` |
| `paragraphs` | `list[str]` | Párrafos con `data-pid` o `id="pN"` |
| `references` | `list[str]` | Cross-refs (anchors `<a class="b">`) deduplicadas + ordenadas |

### `parse_article(html: str) -> Article`

Parsea cualquier página de artículo o capítulo de wol.jw.org.

---

## Módulo `jw_core.parsers.daily_text`

### `class DailyText` (dataclass)

| Campo | Tipo | Descripción |
|---|---|---|
| `date` | `str` | Fecha tal como aparece en la página |
| `scripture` | `str` | Referencia + texto del versículo |
| `commentary` | `str` | Párrafo de comentario |

### `parse_daily_text(html: str) -> DailyText | None`

Parsea la homepage `/wol/h/...`. Devuelve None si no encuentra el contenedor del texto diario.

---

## Módulo `jw_core.parsers.verse`

### `parse_verses(html, *, book_num=None, chapter=None, language="en", strip_pronunciation=True) -> list[Verse]`

Extrae todos los versículos de un capítulo nwtsty. Limpia: `·`, `ʹ`, `+`, `*`, número inicial.

### `get_verse(html, book_num, chapter, verse, *, language="en") -> Verse | None`

Conveniencia: devuelve solo el versículo pedido.

---

## Módulo `jw_core.parsers.study_notes`

### `parse_study_notes(html, *, book_num, chapter, language="en", fallback_to_position=True) -> list[StudyNote]`

Extrae notas de estudio del nwtsty con mapeo headword → versículo (monotónico + fallback posicional).

### `parse_cross_references(html, *, book_num, chapter, language="en") -> list[CrossReference]`

Extrae marcadores inline `+` con sus `href` al panel.

### `study_notes_for_verse(notes, verse) -> list[StudyNote]`

Filtra una lista de notas a las que matchean un versículo específico.

---

## Módulo `jw_core.parsers.topic_index`

### `parse_subject_page(html, *, docid=None, source_url=None, language="en") -> TopicSubject | None`

Parsea una página de tema del Índice de Publicaciones. Maneja dos estilos:
- `"trinity"`: `heading: cite; cite; cite`
- `"article_title"`: un anchor por párrafo

Detecta el estilo automáticamente (`>60% de subheadings con 1 cita y sin `;``).

---

## Módulo `jw_core.parsers.epub`

### `parse_epub(path: Path | str) -> Epub`

Abre un `.epub`, lee `META-INF/container.xml` → OPF → manifest + spine, y extrae cada documento XHTML con su título y párrafos. Usa `defusedxml` para XML seguro.

**Excepciones**: `ValueError` si no encuentra el OPF.

---

## Módulo `jw_core.parsers.jwpub`

### `parse_jwpub_metadata(path: Path | str) -> JwpubMetadata`

Abre un `.jwpub`, lee `manifest.json`, abre el ZIP interno, lee la tabla `Document` del SQLite. **No decodifica el contenido cifrado.**

**Excepciones**: `JwpubError` si el archivo no es válido.

### `class JwpubError(RuntimeError)`

---

## Módulo `jw_core.clients.cdn`

### Constantes

- `TOKEN_URL = "https://b.jw-cdn.org/tokens/jworg.jwt"`
- `SEARCH_BASE = "https://b.jw-cdn.org/apis/search/results"`
- `VALID_FILTERS = {"all", "publications", "videos", "audio", "bible", "indexes"}`

### `class CDNError(RuntimeError)`

### `class CDNClient`

**`__init__(http: httpx.AsyncClient | None = None)`** — opcionalmente acepta cliente HTTP compartido.

**`async search(query, *, filter_type="all", language="E", limit=10) -> dict`** — búsqueda autenticada con JWT. Si `filter_type` no está en `VALID_FILTERS`, levanta `ValueError`. Refresh automático del token en 401.

**`async aclose() -> None`** — cierra el HTTP si lo posee.

---

## Módulo `jw_core.clients.wol`

### Constantes

- `WOL_BASE = "https://wol.jw.org"`
- `USER_AGENT = "jw-agent-toolkit/0.1 (+research)"`

### `class WOLError(RuntimeError)`

### `class WOLClient`

**`__init__(http=None)`** — opcional, con `User-Agent` y `Accept-Language` por defecto.

**`async fetch(url) -> str`** — GET arbitrario; si `url` no empieza por `http`, prepende `WOL_BASE`.

**`async get_bible_chapter(book_num, chapter, *, language="en", publication=None) -> tuple[str, str]`** — `publication` defaulta a `Language.default_bible`. Devuelve `(url, html)`.

**`async get_today_homepage(language="en") -> tuple[str, str]`** — homepage del idioma.

**`async get_cross_reference_panel(href) -> tuple[str, str]`** — panel señalado por un marcador `+`.

**`async aclose() -> None`**

---

## Módulo `jw_core.clients.mediator`

### Constantes

- `MEDIATOR_BASE = "https://data.jw-api.org/mediator"`

### `class MediatorError(RuntimeError)`

### `class MediatorLanguage(BaseModel)`

| Campo | Default | Descripción |
|---|---|---|
| `code` | — | Código JW (`"E"`, `"S"`) |
| `locale` | `""` | ISO 639-1 |
| `name` | `""` | Nombre en el idioma del request |
| `vernacular` | `""` | Nombre nativo |
| `rtl` | `False` | Script de derecha a izquierda |
| `is_sign_language` | `False` | |
| `has_web_content` | `True` | |

Método de clase: `from_api(data: dict)` — convierte la entrada cruda del endpoint.

### `class MediatorClient`

**`async list_languages(in_language="E") -> list[MediatorLanguage]`** — registro completo de idiomas.

**`async find_item(item_code, language="E") -> dict`** — resuelve un código de contenido a URLs deliverable. Devuelve JSON crudo.

**`async aclose() -> None`**

---

## Módulo `jw_core.clients.pub_media`

### Constantes

- `PUB_MEDIA_URL = "https://b.jw-cdn.org/apis/pub-media/GETPUBMEDIALINKS"`
- `VALID_FORMATS = {"PDF", "EPUB", "JWPUB", "MP3", "RTF", "BRL"}`

### `class PubMediaError(RuntimeError)`

### `class PubMediaFile(BaseModel)`

Un archivo descargable con `url`, `filename`, `title`, `language` (JW code), `file_format`, `size_bytes`, `checksum`, `bible_book`, `track`, `duration_s`, `mime_type`.

Método de clase: `from_api(language, fmt, data)`.

### `class Publication(BaseModel)`

`pub_code`, `pub_name`, `files: list[PubMediaFile]`.

Métodos: `files_by_format(fmt)`, `files_by_language(lang_code)`.

### `class PubMediaClient`

**`async get_publication(pub_code, *, language="E", issue=None, bible_book=None, file_format=None, all_languages=False) -> Publication`** — inventario de archivos. 404 → `PubMediaError`. `bible_book` debe estar en `0..66`.

**`async download(file: PubMediaFile, dest, *, chunk_size=64*1024) -> Path`** — streaming a disco. Si `dest` es directorio, usa `file.filename` dentro.

**`async aclose() -> None`**

---

## Módulo `jw_core.clients.topic_index`

### `class TopicIndexError(RuntimeError)`

### `class TopicIndexClient`

**`__init__(cdn=None, wol=None, http=None)`** — acepta clientes compartidos.

**`async search_subjects(query, *, language="E", limit=10, rerank_by_title_match=True) -> list[dict]`** — devuelve dicts con `title`, `snippet`, `wol_url`, `docid`, `subtype`, `original_rank`, `score`.

**`async get_subject_page(docid_or_url, *, language="en") -> TopicSubject`** — acepta tanto docid bare como URL completa.

**`async aclose() -> None`** — cierra solo los clientes que posee.

---

## Re-exports principales

Desde `jw_core`:

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
