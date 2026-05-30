---
title: Referencia — jw_core.integrations + parsers.jw_library_backup
audiencia: integradores
fase: 19
---

# Referencia: capa de integraciones con JW Library

> Contratos completos de los módulos de la Fase 19. Para el "porqué" ver [conceptos/integracion-jw-library.md](../conceptos/integracion-jw-library.md). Para casos de uso ver [guias/integracion-jw-library.md](../guias/integracion-jw-library.md).

## Mapa del paquete

```
jw_core/
├── integrations/
│   ├── __init__.py             # Re-exporta API pública de las 4 capas
│   ├── jw_library.py           # Deep linking jwlibrary://
│   ├── jw_library_local.py     # Inspector local + Full Disk Access (macOS)
│   ├── jw_library_sync.py      # Sync incremental con sidecar state
│   └── meps_catalog.py         # Catálogo SQLite docid ↔ pub_code
└── parsers/
    └── jw_library_backup.py    # Parser de archivos .jwlibrary
```

Los tests viven en `packages/jw-core/tests/test_jw_library_*.py` y `test_meps_catalog.py` (5 archivos, **77 tests**).

---

## `jw_core.integrations.jw_library` — Capa 1

Deep linking al esquema `jwlibrary://`.

### `class JWLibraryError(RuntimeError)`

Excepción raíz del módulo. Se eleva cuando un URL no puede construirse o despacharse.

### `class VerseRange`

```python
@dataclass(frozen=True)
class VerseRange:
    start: int
    end: int
```

Una sola rango contiguo. `end == start` para un versículo. Validación en `__post_init__`:

- 1 ≤ start ≤ 999, 1 ≤ end ≤ 999
- end ≥ start

### `build_bible_url(...) -> str`

```python
def build_bible_url(
    book_num: int,
    chapter: int,
    verse_start: int | None = None,
    *,
    verse_end: int | None = None,
    end_chapter: int | None = None,
    end_book: int | None = None,
    wtlocale: str | None = None,
) -> str
```

| Param | Descripción |
|---|---|
| `book_num` | 1..66 (Génesis=1, Apocalipsis=66). |
| `chapter` | Número de capítulo. |
| `verse_start` | Primer versículo. `None` ⇒ verso 1 implícito. |
| `verse_end` | Último verso del rango. `None` + `end_chapter=None` ⇒ verse único. |
| `end_chapter` | Para rangos multi-capítulo (Mat 3:1–4:11). > `chapter`. |
| `end_book` | Para rangos cross-libro (raro). Default = `book_num`. |
| `wtlocale` | ISO ("en"/"es"/"pt") o JW code ("E"/"S"/"T"). Pasa por `get_language` si conocido; otherwise pass-through uppercase. |

**Returns**: `jwlibrary:///finder?bible=BBCCCVVV[-BBCCCVVV][&wtlocale=LL]`.

**Raises**: `JWLibraryError` si inputs son inconsistentes (book fuera de rango, end_chapter < chapter, verse_end < verse_start en mismo capítulo).

### `build_bible_urls(...) -> list[str]`

```python
def build_bible_urls(
    book_num: int,
    chapter: int,
    ranges: list[VerseRange],
    *,
    wtlocale: str | None = None,
) -> list[str]
```

Para versos disjuntos ("Juan 1:1, 4, 7-8") devuelve una URL por rango — `?bible=` no soporta múltiples rangos. Vacía ⇒ raise.

### `build_publication_url(...) -> str`

```python
def build_publication_url(
    docid: int | str,
    *,
    paragraph: int | None = None,
    wtlocale: str | None = None,
) -> str
```

Genera `jwlibrary:///finder?wtlocale=LL&docid=N[&par=P]`. `docid` debe ser numérico > 0. `paragraph` opcional > 0.

### `build_url_for_ref(...) -> str`

```python
def build_url_for_ref(
    ref: BibleRef,
    *,
    wtlocale: str | None = None,
) -> str
```

Atajo a partir de un `BibleRef` parseado por `parse_reference`. Si `wtlocale` es `None`, usa `ref.detected_language`.

### `detect_platform() -> str`

Devuelve `"darwin"`, `"win32"`, `"linux"` o `"unknown"`. Se basa en `sys.platform`.

### `open_jw_library(url, *, dry_run, platform, runner) -> dict`

```python
def open_jw_library(
    url: str,
    *,
    dry_run: bool = False,
    platform: str | None = None,
    runner: object = subprocess,
) -> dict[str, object]
```

Despacha (o no, si `dry_run`) un URL `jwlibrary://`.

**Returns**: `{"url", "platform", "dispatched", ...}`. En dry_run incluye `"dry_run": True`. En despacho real incluye `"returncode"` y `"stderr"` (truncado a 500 chars).

**Raises**: `JWLibraryError` si el URL no empieza por `jwlibrary://`, contiene caracteres de control, o el opener (`open` / `xdg-open`) no está disponible.

Argv por plataforma:

| Plataforma | argv |
|---|---|
| `darwin` | `["open", url]` |
| `win32` | `["cmd", "/c", "start", "", url]` |
| `linux` | `["xdg-open", url]` |

---

## `jw_core.parsers.jw_library_backup` — Capa 2 (parser)

### `class JWLibraryBackupError(RuntimeError)`

Excepción raíz.

### `class BackupManifest(BaseModel)`

| Campo | Tipo | Origen JSON |
|---|---|---|
| `name` | str | `name` |
| `creation_date` | str | `creationDate` |
| `device_name` | str | `userDataBackup.deviceName` |
| `schema_version` | int \| None | `userDataBackup.schemaVersion` |
| `last_modified_date` | str | `userDataBackup.lastModifiedDate` |
| `database_name` | str | `userDataBackup.databaseName` (default `"userData.db"`) |
| `hash` | str | `hash` o `userDataBackup.hash` |
| `type` | int \| None | `type` |
| `version` | int \| None | `version` |
| `extra` | dict | campos no reconocidos |

### `class Location(BaseModel)`

Direccionable bíblico o publicación. `is_bible` ⇔ `book_number` y `chapter_number` no son `None`.

### `class UserNote(BaseModel)`

| Campo | Tipo | Notas |
|---|---|---|
| `note_id` | int | PK SQLite. |
| `guid` | str | Estable cross-schema. |
| `title`, `content` | str | Cuerpo de la nota. |
| `last_modified`, `created` | str | ISO timestamp del backup. |
| `block_type`, `block_identifier` | int \| None | Anclaje a párrafo/verso. |
| `location` | Location \| None | Resuelto por LocationId. |
| `user_mark_id` | int \| None | UserMark al que está atada. |
| `tags` | list[str] | Nombres de tags vía TagMap. |

### `class UserHighlight(BaseModel)`

| Campo | Tipo | Notas |
|---|---|---|
| `user_mark_id` | int | PK SQLite. |
| `color_index`, `style_index` | int | Color / estilo del resaltado. |
| `user_mark_guid` | str | Estable. |
| `location` | Location | Siempre presente — orphans se skippean. |
| `block_ranges` | list[dict] | Lista de `{block_type, identifier, start_token, end_token}`. |

### `class Bookmark(BaseModel)`

| Campo | Tipo |
|---|---|
| `bookmark_id` | int |
| `slot` | int (0..9 por publicación) |
| `title`, `snippet` | str |
| `block_type`, `block_identifier` | int \| None |
| `location` | Location |

### `class Tag(BaseModel)` / `class InputField(BaseModel)`

Tag: `tag_id`, `name`, `type` (1=user, 2=Favorite built-in, etc.). InputField: `location_id`, `text_tag`, `value`, `location` (opcional).

### `class BackupContents(BaseModel)`

Contenedor top-level. Atributos: `source_path`, `manifest`, `locations`, `notes`, `highlights`, `bookmarks`, `tags`, `input_fields`. Property `counts` devuelve dict de tamaños.

### `parse_jw_library_backup(path) -> BackupContents`

Abre el ZIP, parsea manifest, extrae `userData.db` a tempfile, lo abre en URI `mode=ro`, proyecta cada tabla. Schema-resistant: `PRAGMA table_info` + select sólo de columnas presentes.

**Raises**: `JWLibraryBackupError` si el archivo no existe, no es ZIP, le falta `manifest.json` o `userData.db`.

### `parse_user_data_db(path, *, manifest=None, source="") -> BackupContents`

Para cuando ya tienes el SQLite (caso: macOS Full Disk Access). Reutiliza el mismo backend.

### `notes_for_chapter(backup, *, book_num, chapter) -> list[UserNote]`

Filtra notas cuya `Location` apunta al capítulo dado.

---

## `jw_core.integrations.jw_library_sync` — Capa 2 (sync incremental)

### `class SyncEntry`

```python
@dataclass
class SyncEntry:
    item_id: str
    source_id: str
    last_modified: str = ""
    content_hash: str = ""
```

### `class SyncState`

Sidecar para un `backup_id`. Contiene `notes`, `bookmarks`, `input_fields` (dicts `key → SyncEntry`) y metadata. Serializable vía `to_dict` / `from_dict`.

### `class SyncStateStore(path)`

Backend JSON. Métodos:

| Método | Descripción |
|---|---|
| `load(backup_id) -> SyncState` | Devuelve state vacío si el archivo no existe o está corrupto. |
| `save(state)` | Persiste preservando otros `backup_id`s. |

### `class SyncPlan` / `class SyncReport`

| Campo (Plan) | Tipo |
|---|---|
| `new_notes`, `updated_notes` | list[UserNote] |
| `deleted_note_source_ids` | list[str] |
| `new_bookmarks`, `updated_bookmarks` | list[Bookmark] |
| `deleted_bookmark_source_ids` | list[str] |
| `new_input_fields`, `updated_input_fields` | list[InputField] |
| `deleted_input_field_source_ids` | list[str] |

Property `is_noop`. Method `summary() -> dict[str,int]`.

### `compute_sync_plan(backup, state) -> SyncPlan`

Sin efectos secundarios. Una entrada se considera **updated** cuando su `content_hash` cambia. Notas se identifican por `guid` (fallback `id:<note_id>`). Bookmarks por `bookmark_id`. InputFields por `(location_id, text_tag)`.

### `sync_backup_to_rag(backup_path, store, *, ...) -> SyncReport`

| Param | Default | Descripción |
|---|---|---|
| `state_path` | `<store.path>/jw_library_sync.json` | Sidecar JSON. |
| `include_bookmarks` | True | Trackear marcadores. |
| `include_input_fields` | True | Trackear respuestas de campos. |
| `dry_run` | False | Si True, computa plan y nada más. |
| `min_chars` | 8 | Skip de chunks demasiado cortos. |

Pasos:

1. Parse backup → diff vs state.
2. Si no es dry_run: `store.delete_by_source_ids(...)` para eliminar viejos.
3. Para cada new/updated: `chunk_paragraphs` + `store.add`. **El state se actualiza incluso si se skippeó por `min_chars`** (invariante para no re-reportar como new).
4. Evict de state los deleted.
5. `state_store.save(state)`.

Source ids canónicos:

- Notas: `jwlib:note:{note_id}`
- Marcadores: `jwlib:bookmark:{bookmark_id}`
- Campos: `jwlib:input:{location_id}:{text_tag}`

### Metadata adjunta a cada chunk

| kind | Campos extras |
|---|---|
| `user_note` | `note_id`, `guid`, `created`, `last_modified`, `tags[]`, `book_num`, `chapter`, `key_symbol`, `document_id`, `meps_language` |
| `user_bookmark` | `bookmark_id`, `slot`, `book_num`, `chapter`, `key_symbol`, `document_id` |
| `user_input` | `location_id`, `text_tag`, `key_symbol`, `document_id` |

Todas llevan `source_backup` (nombre del manifest o path original).

---

## `jw_core.integrations.meps_catalog` — Catálogo MEPS

### `default_catalog_path() -> Path`

Lee env `JW_MEPS_CATALOG_PATH`; default `~/.jw-agent-toolkit/meps_catalog.db`.

### `class CatalogPublication` / `class CatalogDocument`

Dataclasses simples. `CatalogPublication` por `(pub_code, language_index)`. `CatalogDocument` por `(pub_code, language_index, document_id)` con `meps_document_id`, `title`, `chapter_number`, etc.

### `class MepsCatalog(db_path=None)`

Context manager. Métodos:

| Método | Descripción |
|---|---|
| `index_jwpub(jwpub_path) -> dict` | Parse metadata (sin descifrar). Upsert publication + documentos. Idempotente. |
| `list_publications(*, pub_code=None, language_index=None)` | Filtra y ordena. |
| `find_documents(*, pub_code, document_id, meps_document_id, language_index, chapter_number, limit)` | Filtros componibles. |
| `resolve_docid(pub_code, *, chapter_number=None, language_index=None) -> CatalogDocument \| None` | Selector inteligente: prefiere inglés (idx 0) si no se especifica idioma. |
| `stats() -> dict` | `{db_path, publications, documents}`. |

### Schema interno

```sql
CREATE TABLE publication (
    pub_code TEXT, language_index INTEGER, title TEXT, short_title TEXT,
    year INTEGER, publication_type TEXT, source_path TEXT, last_indexed_at TEXT,
    PRIMARY KEY (pub_code, language_index)
);
CREATE TABLE document (
    document_id INTEGER, meps_document_id INTEGER, pub_code TEXT,
    language_index INTEGER, title TEXT, toc_title TEXT, chapter_number INTEGER,
    section_number INTEGER, first_page_number INTEGER, last_page_number INTEGER,
    PRIMARY KEY (pub_code, language_index, document_id)
);
CREATE INDEX idx_document_meps ON document(meps_document_id);
CREATE INDEX idx_document_chapter ON document(pub_code, chapter_number);
```

### Helper `index_jwpub(path, *, db_path=None)`

Shortcut sin context manager para indexing puntual.

---

## `jw_core.integrations.jw_library_local` — Capa 3

### `ENV_OPT_IN = "JW_LIBRARY_LOCAL_READ"`

Variable de entorno obligatoria salvo `force=True`.

### `class MacOSFullDiskAccessError(RuntimeError)`

Específica para casos donde TCC bloquea la lectura del container.

### `class InstalledPublication`

Refleja una fila de Windows `publications.db`. Campos: `publication_id`, `key_symbol`, `title`, `short_title`, `publication_type`, `year`, `issue_tag_number`, `meps_language`, `last_modified`.

### `class LocalInspectionResult`

| Campo | Descripción |
|---|---|
| `platform` | "darwin" / "win32" / "linux" / "unknown" |
| `supported` | True sólo si pudimos leer datos del usuario. |
| `opt_in` | Estado del opt-in. |
| `app_detected` | Si encontramos la app. |
| `library_path` | Ruta a `publications.db` o `JW Library.app` según plataforma. |
| `user_data_path` | Ruta a `userData.db` si accesible. |
| `publications` | Lista `InstalledPublication`. |
| `reasons[]` / `suggestions[]` | Mensajes legibles para el usuario. |

### `inspect_local_jw_library(*, force=False) -> LocalInspectionResult`

Dispatcher principal:

| Plataforma | Acción |
|---|---|
| `win32` | Glob `%LOCALAPPDATA%\Packages\WatchtowerBibleandTractSocietyofNewYorkInc.JWLibrary_*\LocalState\` → lee `publications.db` con PRAGMA-projected select. |
| `darwin` | Llama `check_macos_full_disk_access()`. Si OK → busca `userData.db`. Si bloqueado → instrucciones FDA. |
| `linux` | Devuelve `supported=False` con sugerencia de exportar backup. |
| `unknown` | Devuelve `supported=False`. |

### `check_macos_full_disk_access() -> dict`

Probe barata: intenta `os.scandir(container)`. Returns `{path, readable, error}`. No falla — devuelve estado.

### `read_macos_userdata() -> BackupContents`

Workflow:

1. `check_macos_full_disk_access()`; si bloqueado, raise `MacOSFullDiskAccessError`.
2. `_find_userdata_in_container()`: probe paths conocidos + rglob de fallback.
3. `shutil.copy` a tempfile (el live DB puede estar en WAL mode).
4. `parse_user_data_db(tmp, manifest=…)` → `BackupContents`.
5. Cleanup del tempfile.

---

## Tools MCP expuestos

Inventario completo de la Fase 19 (11 tools nuevos):

| Tool | Capa | Side effects |
|---|---|---|
| `open_in_jw_library` | 1 | dry_run=True por default; opcional `open` real |
| `import_jw_library_backup` | 2 | Read-only. |
| `list_user_notes` | 2 | Read-only. |
| `ingest_user_notes` | 2 | Escribe al RAG store. |
| `sync_jw_library_backup` | 2 | Diff incremental. Escribe al RAG store y al state file. |
| `register_jwpub_in_catalog` | — | Escribe al catálogo MEPS SQLite. |
| `find_publication_in_catalog` | — | Read-only. |
| `open_publication_by_symbol` | 1 + cat | dry_run=True por default. |
| `check_jw_library_full_disk_access` | 3 | Read-only probe. |
| `read_jw_library_live_userdata` | 3 | Read-only (copia a tempfile). |
| `inspect_local_jw_library_tool` | 3 | Read-only. Requiere `JW_LIBRARY_LOCAL_READ=1` o `force=True`. |

## Variables de entorno

| Var | Default | Usado por |
|---|---|---|
| `JW_LIBRARY_LOCAL_READ` | — | `inspect_local_jw_library` (opt-in obligatorio). |
| `JW_MEPS_CATALOG_PATH` | `~/.jw-agent-toolkit/meps_catalog.db` | `default_catalog_path` → `MepsCatalog`. |
| (sidecar sync) | `<store.path>/jw_library_sync.json` | `sync_backup_to_rag` (override por parámetro `state_path`). |

## Cobertura de tests

| Archivo | Tests | Cubre |
|---|---|---|
| `test_jw_library_integration.py` | 30 | URL builders + dispatcher + safety |
| `test_jw_library_backup.py` | 16 | Parser ZIP + schema-resilience |
| `test_jw_library_local.py` | 19 | Inspector + FDA detection + live read |
| `test_jw_library_sync.py` | 9 | State store + diff engine + apply |
| `test_meps_catalog.py` | 13 | SQLite catalog + resolve_docid |
| **Total** | **87** | — |
