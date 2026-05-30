# Referencia: jw-core

> Documentación exhaustiva de cada módulo, clase y función pública del paquete `jw-core`.

## Estructura del paquete

```
jw_core/
├── __init__.py            # Re-exporta BibleRef, parse_reference, parse_all_references
├── languages.py           # Registro Language + get_language + all_languages
├── models.py              # Modelos Pydantic
├── auth.py                # JWTManager (extraído de cdn) — Fase 9
├── cache.py               # DiskCache (SQLite + TTL + WAL) — Fase 9
├── throttle.py            # TokenBucket + Throttler + backoff_delay — Fase 9
├── telemetry.py           # Telemetry (opt-in drift detection) — Fase 9
├── data/
│   ├── __init__.py
│   └── books.py           # BOOKS — 66 libros × 3+ idiomas
├── clients/
│   ├── __init__.py
│   ├── _polite.py         # politely_get helper — Fase 9
│   ├── factory.py         # build_clients + ClientSuite — Fase 9
│   ├── cdn.py             # CDNClient + CDNError + VALID_FILTERS
│   ├── wol.py             # WOLClient + WOLError
│   ├── mediator.py        # MediatorClient + MediatorLanguage + MediatorError
│   ├── pub_media.py       # PubMediaClient + Publication + PubMediaFile + ...
│   ├── topic_index.py     # TopicIndexClient + TopicIndexError
│   └── weblang.py         # WeblangClient + WeblangLanguage + WeblangError — Fase 10
└── parsers/
    ├── __init__.py        # Re-exporta los entry points públicos
    ├── reference.py       # ReferenceParser + parse_reference + parse_all_references
    ├── article.py         # parse_article + Article
    ├── daily_text.py      # parse_daily_text + DailyText
    ├── verse.py           # parse_verses + get_verse
    ├── study_notes.py     # parse_study_notes + parse_cross_references + study_notes_for_verse
    ├── topic_index.py     # parse_subject_page
    ├── epub.py            # parse_epub
    └── jwpub.py           # parse_jwpub_metadata + parse_jwpub (decrypt) + JwpubError
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

Lee `manifest.json` + tabla `Document` sin descifrar el `Content` blob. Barato. `JwpubMetadata.decrypted_text_available` es `False`.

### `parse_jwpub(path: Path | str) -> JwpubMetadata`

Idem + descifra cada blob. Cada `JwpubDocument` resultante tiene `text` (XHTML descifrado) y `paragraphs` (texto plano). Blobs individuales que fallen al decryptarse quedan con `text=""` y se saltan silenciosamente.

### `_compute_key_iv(meps_language_index, symbol, year, issue_tag_number=0) -> tuple[bytes, bytes]`

Función interna (expuesta para tests) que reproduce el algoritmo de derivación:

```
pub_string = f"{lang}_{symbol}_{year}"  (+ "_{issue}" si non-zero)
material   = SHA256(pub_string) XOR _XOR_KEY    (XOR contra constante 32-byte)
key = material[:16]    # AES-128 key
iv  = material[16:32]  # CBC IV
```

`_XOR_KEY` es una constante fija (`11cbb5587e32846d4c26790c633da289f66fe5842a3a585ce1bc3a294af5ada7`) descubierta por [`gokusander/jwpub-toolkit`](https://github.com/gokusander/jwpub-toolkit) (MIT) inspeccionando los binarios de JW Library.

### `_decrypt_blob(blob, key, iv) -> str`

AES-128-CBC decrypt + strip PKCS7 padding + zlib inflate + UTF-8 decode. Lanza cualquier excepción al caller (que la atrapa por documento individual).

### `class JwpubError(RuntimeError)`

### Dependencia adicional

`cryptography` (módulo `cryptography.hazmat.primitives.ciphers`) — usado para AES-128-CBC. Está en `uv.lock` como dep transitiva; añadirlo explícitamente al `pyproject.toml` de jw-core sería más claro.

---

## Módulo `jw_core.clients.cdn`

### Constantes

- `SEARCH_BASE = "https://b.jw-cdn.org/apis/search/results"`
- `VALID_FILTERS = {"all", "publications", "videos", "audio", "bible", "indexes"}`

### `class CDNError(RuntimeError)`

### `class CDNClient`

**`__init__(http=None, *, throttler=None, cache=None, telemetry=None, auth=None)`** — Fase 9 deps opcionales. `auth` se autoconstruye como `JWTManager(http)` si no se pasa (extraído de cdn.py en Fase 9).

**`async search(query, *, filter_type="all", language="E", limit=10) -> dict`** — búsqueda autenticada con JWT. Si `filter_type` no está en `VALID_FILTERS`, levanta `ValueError`. Refresh automático en 401 vía `auth.invalidate()` + retry.

**`cache_stats() -> dict | None`** — stats del DiskCache si está configurado.

**`async aclose() -> None`** — cierra el HTTP si lo posee.

---

## Módulo `jw_core.clients.wol`

### Constantes

- `WOL_BASE = "https://wol.jw.org"`
- `USER_AGENT = "jw-agent-toolkit/0.1 (+research)"`

### `class WOLError(RuntimeError)`

### `class WOLClient`

**`__init__(http=None, *, throttler=None, cache=None, telemetry=None)`** — Fase 9 deps opcionales.

**`async fetch(url, *, cache_ttl_seconds=3600.0) -> str`** — GET arbitrario; si `url` no empieza por `http`, prepende `WOL_BASE`. TTL configurable.

**`async get_bible_chapter(book_num, chapter, *, language="en", publication=None) -> tuple[str, str]`** — `publication` defaulta a `Language.default_bible`. Devuelve `(url, html)`.

**`async get_today_homepage(language="en") -> tuple[str, str]`** — homepage del idioma `/wol/h/{r}/{lp_tag}`.

**`async get_daily_text_by_date(date, *, language="en") -> tuple[str, str]`** — Fase 10. URL `/wol/dt/{r}/{lp_tag}/{YYYY}/{M}/{D}`. `date` puede ser `str` ISO (`"2025-12-25"`) o `datetime.date`.

**`async get_document_by_id(doc_id, *, language="en") -> tuple[str, str]`** — Fase 10. URL `/wol/d/{r}/{lp_tag}/{docId}`. Útil para artículos arbitrarios o documentos de daily-text por año.

**`async get_publication_page(pub_code, number=None, *, language="en") -> tuple[str, str]`** — Fase 10. URL `/wol/publication/{r}/{lp_tag}/{pub}[/{number}]`. Para Bibles, `number=book_num`; para revistas, `number=issue`; para libros, `number=chapter`.

**`async get_cross_reference_panel(href) -> tuple[str, str]`** — panel señalado por un marcador `+`.

**`cache_stats() -> dict | None`** — stats del DiskCache si está configurado.

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

## Módulo `jw_core.clients.weblang` (Fase 10)

Cliente alternativo para `www.jw.org/{iso}/languages/`. Diferencias vs `mediator`:
- Más campos por idioma (vernacularName, script, direction, isSignLanguage, altSpellings).
- Actualizado con menor frecuencia (más estable).
- Disponible cuando mediator está throttled.

### `class WeblangError(RuntimeError)`

### `class WeblangLanguage(BaseModel)`

| Campo | Default | Descripción |
|---|---|---|
| `code` | — | JW code (`"E"`, `"S"`) |
| `iso` | `""` | ISO 639 (3-letter en este endpoint) |
| `name` | `""` | Nombre en el idioma del request |
| `vernacular` | `""` | Nombre nativo |
| `alt_names` | `[]` | Variantes ortográficas |
| `rtl` | `False` | RTL script |
| `script` | `""` | `"ROMAN"`, `"CYRILLIC"`, ... |
| `is_sign_language` | `False` | |

`from_api(data)` mapea las claves del endpoint (`langcode`, `symbol`, `vernacularName`, `altSpellings`, `direction`, `script`, `isSignLanguage`) al modelo.

### `class WeblangClient`

**`__init__(http=None, *, throttler=None, cache=None, telemetry=None)`** — Fase 9 deps opcionales.

**`async list_languages(*, in_language_iso="en") -> list[WeblangLanguage]`** — `in_language_iso` controla el idioma de display. Cachea 1 día (los idiomas son estables).

**`cache_stats() -> dict | None`**

**`async aclose() -> None`**

---

## Módulo `jw_core.auth` (Fase 9)

### `class JWTAuthError(RuntimeError)`

### `class JWTManager`

Holder async-safe del JWT para las APIs de `b.jw-cdn.org`.

**`__init__(http: httpx.AsyncClient, token_url: str = TOKEN_URL)`**.

**`async get_token(*, force_refresh=False) -> str`** — devuelve token cacheado o lo fetcha. Usa `asyncio.Lock` para evitar dos refreshes simultáneos.

**`async authorized_headers(extra=None, *, force_refresh=False) -> dict`** — `{Authorization: Bearer ..., Accept: application/json; charset=utf-8, Referer: https://www.jw.org/}` más cualquier `extra`.

**`invalidate() -> None`** — drop el token cacheado (típicamente tras un 401).

---

## Módulo `jw_core.cache` (Fase 9)

### `class DiskCache`

Cache TTL backed por SQLite con WAL. Esquema: `cache(key TEXT PK, value BLOB, expires_at REAL)`.

**`__init__(path=..., *, default_ttl_seconds=3600.0)`** — crea el archivo si no existe.

**`get(key) -> bytes | None`** — devuelve valor o None si missing/expirado (lazy eviction de la row expirada).

**`set(key, value, *, ttl_seconds=None)`** — INSERT OR REPLACE.

**`delete(key)`**, **`clear()`**.

**`cleanup_expired() -> int`** — borra todas las rows expiradas; devuelve rowcount.

**`stats() -> dict`** — `{"total": int, "live": int, "expired": int}`.

**`close()`** + soporte de context manager (`with DiskCache(...) as c:`).

---

## Módulo `jw_core.throttle` (Fase 9)

### `class TokenBucket` (dataclass)

| Campo | Default | Descripción |
|---|---|---|
| `rate_per_sec` | `2.0` | Refill rate |
| `capacity` | `5.0` | Burst máximo |

**`async acquire(n=1.0) -> None`** — bloquea hasta tener `n` tokens.

### `class Throttler`

**`__init__(default_rate=2.0, default_capacity=5.0)`**.

**`set_limit(host, rate_per_sec, capacity)`** — resetea el bucket de ese host con los nuevos valores.

**`bucket_for(host) -> TokenBucket`** — lazy crea per-host.

**`async acquire(host, n=1.0)`**.

### `backoff_delay(attempt, *, base=0.5, cap=30.0) -> float`

Full-jitter exponential backoff (AWS-style). Devuelve `random.uniform(0, min(cap, base * 2**attempt))`.

---

## Módulo `jw_core.telemetry` (Fase 9)

### `_shape_hash(obj, depth=0, max_depth=6) -> str`

Hashea la SHAPE estructural (claves, tipos, longitudes, sample de listas). Misma shape → mismo hash, independientemente de valores.

### `class Telemetry`

**`__init__(path=None)`** — lee `JW_TELEMETRY_PATH` env var o usa `~/.jw-agent-toolkit/telemetry.json`. Solo está `enabled=True` si `JW_TELEMETRY_ENABLED` ∈ `{"1", "true", "yes"}`.

**`record(endpoint, response) -> bool`** — registra/compara shape. Devuelve True si se detectó drift (no en el primer call que aprende baseline). Persiste a disco automáticamente.

**`report() -> dict`** — `{"enabled", "path", "baselines": {endpoint: shape}, "drift_events": [...]}`.

### `get_telemetry() -> Telemetry`

Singleton de proceso.

---

## Módulo `jw_core.clients._polite` (Fase 9)

### `async politely_get(http, url, *, params=None, headers=None, throttler=None, cache=None, telemetry=None, endpoint_id=None, cache_ttl_seconds=None, record_json_shape=False) -> httpx.Response`

Wrapper compartido por todos los clientes. Aplica:

1. Cache check (clave: `f"GET {url}?{sorted_params_json}"`).
2. Throttle acquire (host extraído con `urlparse`).
3. HTTP request.
4. Cache set en status 200 (TTL = `cache_ttl_seconds` o el default del cache).
5. Telemetry record si `record_json_shape=True` y content-type es JSON.

Cache hit construye un `httpx.Response(200, content=body)` sintético.

### `_cache_key(url, params) -> str`

Deterministic dada cualquier ordering de params (los sortea internamente).

---

## Módulo `jw_core.clients.factory` (Fase 9)

### `class ClientSuite` (dataclass)

Bundle de los 6 clientes + `throttler` + `cache`. Métodos: `async aclose()` (cierra los 6 clientes + el cache).

### `build_clients(cache_path="~/.jw-agent-toolkit/cache.db", *, enable_throttling=True, enable_cache=True, enable_telemetry=None) -> ClientSuite`

Arma una suite completa con infraestructura compartida. Por default:

- Throttler con rate 2 req/s, burst 5 — pero el CDN se limita a 1 req/s, burst 3 (es el más chatty).
- DiskCache en `cache_path`.
- Telemetry vía `get_telemetry()` si `enable_telemetry=None` (respeta env var).

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

Desde `jw_core.integrations` (Fase 19):

```python
from jw_core.integrations import (
    JWLibraryError, VerseRange,
    build_bible_url, build_bible_urls, build_publication_url, build_url_for_ref,
    detect_platform, open_jw_library,
    inspect_local_jw_library, check_macos_full_disk_access, read_macos_userdata,
    sync_backup_to_rag, MepsCatalog,
)
```

Desde `jw_core.parsers.jw_library_backup`:

```python
from jw_core.parsers.jw_library_backup import (
    parse_jw_library_backup,   # archivo .jwlibrary
    parse_user_data_db,        # SQLite standalone (caso macOS FDA)
    notes_for_chapter,
    BackupContents, BackupManifest,
    Location, UserNote, UserHighlight, Bookmark, Tag, InputField,
)
```

Contratos completos de la capa de integraciones: [`integraciones.md`](integraciones.md).
