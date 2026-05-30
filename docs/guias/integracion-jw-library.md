---
title: Integración con la app oficial JW Library
status: estable
fase: 19
---

# Integración con la app oficial JW Library

> Cómo conectar **jw-agent-toolkit** con la app de **JW Library** instalada en macOS, Windows o Linux. Cubre las tres rutas estables: deep-linking, lectura de backups `.jwlibrary` y (sólo Windows) inspección de la biblioteca instalada.

## Resumen rápido

| Capa | Qué hace | macOS | Windows | Linux |
|---|---|---|---|---|
| **1. Deep-link `jwlibrary://`** | Abre un versículo o publicación en la app oficial | ✔ | ✔ | parcial (xdg-open) |
| **2a. Parser de backup `.jwlibrary`** | Lee notas, marcadores, resaltados, respuestas de campos | ✔ | ✔ | ✔ |
| **2b. Sync incremental** | Mantiene el RAG al día con delta cuando el usuario re-exporta | ✔ | ✔ | ✔ |
| **2c. Catálogo MEPS** | Resuelve `pub_code` → `document_id` desde `.jwpub` indexados | ✔ | ✔ | ✔ |
| **3a. Inspector publications.db** | Lista publicaciones instaladas | ✘ | ✔ | ✘ |
| **3b. Lectura live `userData.db`** | Lee notas directamente del container sin export | ✔ (con FDA) | (usa Capa 2) | ✘ |
| **4. Coexistencia con MCPs externos** | Combinar con `advenimus/jw-mcp` | ✔ | ✔ | ✔ |

Ninguna de las capas escribe en los datos de la app oficial. La sincronización con la cuenta JW sólo la hace la app — el toolkit nunca toca esa ruta.

## Capa 1 — Deep-linking (`jwlibrary://`)

JW Library registra el esquema `jwlibrary://` en todas sus plataformas. Es la **única vía oficialmente sancionada** para que un proceso externo le diga a la app "abre este versículo / esta publicación".

### Tool MCP

```text
open_in_jw_library(
    reference: str = "",          # "Juan 3:16", "Mateo 24:14"
    book_num: int | None = None,  # alternativa numérica
    chapter: int | None = None,
    verse_start: int | None = None,
    verse_end: int | None = None,
    end_chapter: int | None = None,
    docid: int | None = None,     # para publicaciones (MEPS id)
    paragraph: int | None = None,
    language: str = "",           # "en"/"es"/"pt" o "E"/"S"/"T"
    dry_run: bool = True,         # True: devuelve el URL sin abrir
)
```

Por defecto `dry_run=True` para que un cliente de chat pueda mostrar el enlace en lugar de abrir algo sin permiso. Pásalo a `False` para disparar el `open` real.

### Sintaxis del URL

```
jwlibrary:///finder?bible=BBCCCVVV[-BBCCCVVV][&wtlocale=LL]
jwlibrary:///finder?wtlocale=LL&docid=N[&par=P]
```

`BB` = libro (2 dígitos), `CCC` = capítulo (3), `VVV` = versículo (3). `LL` = código JW (`E`/`S`/`T`/`F`/`X`/`I`/`J`/`U`/`CHS`/`KO`/...).

Ejemplos:

```python
from jw_core.integrations.jw_library import build_bible_url, build_publication_url

build_bible_url(43, 3, 16, wtlocale="es")
# 'jwlibrary:///finder?bible=43003016&wtlocale=S'

build_bible_url(40, 3, 1, verse_end=11, end_chapter=4)
# 'jwlibrary:///finder?bible=40003001-40004011'

build_publication_url(1102021201, paragraph=2, wtlocale="en")
# 'jwlibrary:///finder?wtlocale=E&docid=1102021201&par=2'
```

### Cómo decide el toolkit qué `wtlocale` poner

Si el usuario llama con `language=""`, y la referencia fue parseada con `parse_reference`, se usa el idioma detectado (`Juan` → español → `S`). En llamadas explícitas, el código del usuario gana.

### Disjoint ranges (Juan 1:1, 4, 7)

`jwlibrary:///finder?bible=...` **no soporta** versículos sueltos en un solo URL. Usa `build_bible_urls()` (plural) para obtener una lista — uno por rango — y muéstralos como bullets al usuario.

### Probar end-to-end

```bash
# macOS
open "jwlibrary:///finder?bible=43003016&wtlocale=S"

# Windows
start jwlibrary:///finder?bible=43003016&wtlocale=S

# Linux (la app no es nativa; necesita Wine + handler)
xdg-open "jwlibrary:///finder?bible=43003016"
```

## Capa 2 — Parser de backup `.jwlibrary`

Un archivo `.jwlibrary` es un ZIP con `manifest.json` + `userData.db` (SQLite). Lo produce la app cuando el usuario va a **Ajustes → Copia de seguridad → Guardar copia de seguridad**. Es la **única vía cross-plataforma** para que el toolkit lea las notas, marcadores, resaltados y respuestas del usuario.

### Cómo obtener un backup

1. En la app, ve a **Ajustes** → **Copia de seguridad / Backup**.
2. Pulsa **Guardar copia de seguridad** (Save Backup).
3. Mueve el archivo `.jwlibrary` a tu Mac/PC.
4. Llama a `import_jw_library_backup` con la ruta.

### Tools MCP

```text
import_jw_library_backup(backup_path: str)
   → manifest + counts por categoría

list_user_notes(backup_path, book_num?, chapter?, tag?, limit=50)
   → notas (con su Location y tags), filtradas opcionalmente

ingest_user_notes(backup_path, include_bookmarks=True, include_input_fields=True)
   → indexa notas/marcadores/respuestas en el RAG local (full re-ingest)

sync_jw_library_backup(backup_path, state_path="", include_bookmarks=True,
                       include_input_fields=True, dry_run=False)
   → sync incremental: diff vs sidecar state; sólo new/updated/deleted
```

Después de `ingest_user_notes` o `sync_jw_library_backup`, `semantic_search` puede mezclar lo que el usuario escribió con el corpus público. Los chunks llevan `kind="user_note" | "user_bookmark" | "user_input"` para que el agente pueda filtrar.

### Sync incremental — flujo recomendado

`sync_jw_library_backup` es el flujo **idiomático** para mantener el RAG al día. La primera llamada se comporta como un import completo; las siguientes sólo procesan la delta. El sidecar JSON vive por defecto en `<rag-store>/jw_library_sync.json` (override con `state_path`).

```text
Primera vez:     sync → todas las notas como new → indexar todo
Segunda corrida: sync → no-op si nada cambió (0 add, 0 remove)
Usuario edita N: sync → 1 updated → chunk viejo evictado + nuevo indexado
Usuario borra:   sync → 1 deleted → chunks evictados sin reemplazo
```

Si quieres ver qué haría el sync sin ejecutarlo: `dry_run=True`. Devuelve el plan sin tocar nada.

El **content_hash** detecta cambios silenciosos (LastModified inalterado pero cuerpo distinto — pasa al revertir y re-editar). Es una belt-and-suspenders adicional a `last_modified`.

### Catálogo MEPS (docid ↔ pub_code)

Para abrir publicaciones (no Biblia) por símbolo legible, el toolkit construye un catálogo local desde `.jwpub` ya descifrados:

```text
register_jwpub_in_catalog(jwpub_path, catalog_db="")
   → indexa publication + documents en SQLite (idempotente)

find_publication_in_catalog(pub_code?, document_id?, meps_document_id?,
                             language_index?, chapter_number?, limit=25)
   → query libre

open_publication_by_symbol(pub_code, chapter_number?, paragraph?,
                            language_index?, language?, dry_run=True)
   → resuelve docid local + construye + dispara jwlibrary://?docid=...
```

Workflow típico:

```python
# 1. Una vez por publicación que quieras hacer addressable
register_jwpub_in_catalog("/Downloads/bh_E.jwpub")

# 2. Después puedes referirte a "bh" por símbolo
open_publication_by_symbol("bh", chapter_number=3, dry_run=False)
# → jwlibrary:///finder?docid=… resuelto desde tu catálogo
```

Catálogo por defecto en `~/.jw-agent-toolkit/meps_catalog.db` (override con env `JW_MEPS_CATALOG_PATH` o param `catalog_db`).

### Modelo de datos expuesto

| Categoría | Origen SQLite | Campos clave |
|---|---|---|
| `Location` | tabla Location | book_number, chapter_number, document_id, key_symbol, issue_tag_number, meps_language |
| `UserNote` | Note + TagMap + Tag | note_id, title, content, created, last_modified, tags[], location |
| `UserHighlight` | UserMark + BlockRange | color_index, style_index, location, block_ranges[] |
| `Bookmark` | Bookmark | bookmark_id, slot, title, snippet, location |
| `InputField` | InputField | location_id, text_tag, value (respuestas a campos de workbook / publicaciones) |
| `Tag` | Tag | tag_id, name, type |

El parser es **defensivo**: si una columna falta en el schema (cambia entre versiones), la salta; si una tabla entera falta, devuelve lista vacía.

### Lectura mínima en Python

```python
from jw_core.parsers.jw_library_backup import parse_jw_library_backup, notes_for_chapter

backup = parse_jw_library_backup("~/Downloads/UserDataBackup_2024-11-15.jwlibrary")
print(backup.counts)
# {'locations': 152, 'notes': 87, 'highlights': 412, 'bookmarks': 23, 'tags': 5, 'input_fields': 64}

for n in notes_for_chapter(backup, book_num=43, chapter=3):
    print(n.title, n.content[:80])
```

## Capa 3 — Inspector de biblioteca instalada

### Opt-in obligatorio

```bash
export JW_LIBRARY_LOCAL_READ=1
```

Sin esa variable, todos los tools de esta capa responden `opt_in: false` y no tocan el filesystem.

### Windows (UWP package)

`%LOCALAPPDATA%\Packages\WatchtowerBibleandTractSocietyofNewYorkInc.JWLibrary_<hash>\LocalState\` contiene:

- `Publications\publications.db` — tabla `Publication` con `key_symbol`, `title`, `publication_type`, `year`, `issue_tag_number`, `meps_language`. Conexión `mode=ro`.
- `userData.db` — el mismo SQLite que se exporta en los backups. Reportado por path.

```text
inspect_local_jw_library_tool(force=False)
   → publications[] + user_data_path + reasons/suggestions
```

### macOS (Full Disk Access)

A diferencia de Windows, la sandbox de la Mac App Store esconde el container de la app por defecto. Pero **si el usuario concede Full Disk Access al proceso huésped** (Terminal, iTerm, Claude Desktop, VS Code), el toolkit puede leer `userData.db` directamente desde:

```
~/Library/Containers/org.jw.jwlibrary/Data/Library/Application Support/userData.db
```

#### Cómo conceder Full Disk Access en macOS

1. Abre **System Settings → Privacy & Security → Full Disk Access**.
2. Click en `+` y añade el proceso huésped del MCP (Terminal / iTerm / Claude Desktop / VS Code).
3. Reinicia ese proceso por completo (no solo cerrar la ventana — quit y relanzar).
4. Re-ejecuta `check_jw_library_full_disk_access` para confirmar.

#### Tools MCP

```text
check_jw_library_full_disk_access()
   → {path, readable, error} sin tocar el sandbox

read_jw_library_live_userdata(book_num?, chapter?, limit=50)
   → lee userData.db live (vía copia a tempfile) y proyecta notas con filtros
   → falla con `needs_full_disk_access: True` si TCC bloquea
```

El `userData.db` se copia a un tempfile antes de leer porque la app puede tenerlo abierto en WAL mode; cerrar la conexión limpia el tempfile.

### Linux

No soportado — no hay build nativa de JW Library para Linux. La única vía es usar Capa 2 con un backup exportado desde otro dispositivo.

## Capa 4 — Coexistir con otros MCPs JW

Hay dos MCP servers JW open-source de referencia:

| Server | Lenguaje | Cubre |
|---|---|---|
| `advenimus/jw-mcp` | Node/TS | versículos bíblicos, workbook, watchtower study, captions de video (vía wol.jw.org + cfp2.jw-cdn.org) |
| `Bjern/jw-org-mcp` | Node/TS | búsqueda agregada de artículos/videos/publicaciones con caching |

**jw-agent-toolkit** los complementa con: parser JWPUB descifrado, parser EPUB, RAG híbrido local, 12 agentes especializados, multi-idioma (10 ISO), local-first sin red en tests, **+ las 4 capas de integración con JW Library de esta guía**.

### Claude Desktop con ambos MCP

`claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "jw-agent-toolkit": {
      "command": "uv",
      "args": [
        "--directory",
        "/Users/elias/Documents/Trabajo/jw-agent-toolkit",
        "run",
        "jw-mcp"
      ]
    },
    "advenimus-jw-mcp": {
      "command": "node",
      "args": [
        "/Users/elias/Documents/Trabajo/jw-mcp/server.js"
      ]
    }
  }
}
```

El cliente verá tools de ambos. Para evitar colisiones, los nombres de tools en `jw-agent-toolkit` viven bajo el prefijo natural del paquete (`open_in_jw_library`, `import_jw_library_backup`, `list_user_notes`, `ingest_user_notes`, `sync_jw_library_backup`, `register_jwpub_in_catalog`, `find_publication_in_catalog`, `open_publication_by_symbol`, `inspect_local_jw_library_tool`, `check_jw_library_full_disk_access`, `read_jw_library_live_userdata`).

## Restricciones legales (ToS jw.org)

Estas integraciones están alineadas con los términos de uso oficiales:

- **Permitido explícitamente**: apps **gratuitas y no comerciales** que descarguen EPUB/PDF/MP3/MP4 públicos. El toolkit ya respeta esta política vía `download_publication` + APIs CDN.
- **No tocamos** la cuenta JW del usuario ni la sincronización. La app es la única que sube/baja datos al servidor.
- **No reverse-engineering** activo de la app: el deep-link `jwlibrary://` es un esquema de URL registrado públicamente y documentado por la comunidad open-source.
- **Backups `.jwlibrary`**: son archivos del usuario que la app genera para él. Leerlos en su propia máquina entra en uso personal.

## Solución de problemas

| Síntoma | Causa probable | Cómo arreglar |
|---|---|---|
| `Required URL opener 'open' not found on PATH` (macOS) | `open` no está en PATH del proceso MCP | Reinicia Claude Desktop o asegúrate de que `/usr/bin` esté en PATH |
| El deep-link se dispara pero la app no se abre | App no instalada o esquema no registrado | Abre la app una vez manualmente; el sistema entonces registra el handler |
| `manifest.json is missing` al importar backup | No es un backup real (puede ser un `.jwpub`) | Verifica que el ZIP tenga `manifest.json` y `userData.db` en la raíz |
| `inspect_local_jw_library` devuelve `opt_in: false` | Falta `JW_LIBRARY_LOCAL_READ=1` | Exporta la variable y reinicia el servidor MCP |
| Notas vacías tras `list_user_notes` | El backup es muy antiguo (versión < 12) | Re-exporta desde una versión reciente de la app |

## Próximos pasos

- **Sync incremental**: detectar `last_modified_date` del backup y re-ingestar sólo las notas nuevas (sin necesidad de reset del RAG).
- **Mapping inverso docid → BibleRef**: derivar IDs MEPS desde el `.jwpub` y `wol.jw.org` para que el agente pueda abrir publicaciones por título.
- **macOS read via TCC**: explorar si con permiso Full Disk Access la lectura del container es posible. Hoy no está garantizado.
