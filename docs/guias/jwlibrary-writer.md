---
title: "Escritor de backups .jwlibrary (Fase 52)"
description: "Generar .jwlibrary con notas/highlights desde agentes. Cierra read-write loop con JW Library nativo."
date: "2026-06-02"
---

# Guía — Escritor de backups .jwlibrary (Fase 52)

> Generar archivos `.jwlibrary` (notas, marcadores, highlights, bookmarks)
> que **JW Library nativo puede importar**. Cierra el read-write loop
> con la app oficial (Fase 19 fue solo parser).

## ¿Cuándo necesito esto?

- Un agente sintetiza **notas de estudio** y quieres llevarlas a la
  app oficial para repasar offline (Atalaya, libro de estudio, etc.).
- Sincronizar el vault de Obsidian con JW Library: notas en Markdown
  se transforman a estructura `.jwlibrary`.
- Migrar entre dispositivos sin pasar por la GUI de jwlmanager.
- Inyectar **bookmarks** programáticos a versículos relevantes para
  una serie de discursos.

## Algoritmo (heredado de jwlmanager MIT)

```
INPUT  : userData.db SQLite preexistente (o creado de cero)
                    │
                    │ write_backup(out_path, *, user_data_db_path, ...)
                    │   1. UPDATE LastModified SET LastModified = now()
                    │   2. PRAGMA user_version → schema_version
                    │   3. SHA-256 del archivo .db
                    │   4. manifest.json (name + creationDate + version +
                    │      userDataBackup{lastModifiedDate, deviceName,
                    │                     databaseName, hash, schemaVersion})
                    │   5. ZIP outer:
                    │      - manifest.json
                    │      - userData.db
                    ▼
OUTPUT : .jwlibrary importable en JW Library
```

> **Lo que NO está portado**: el **merge** de jwlmanager (combinar dos
> backups respetando conflictos en notas/marcadores). Esa lógica vive
> en `libs/libjwlCore.{so,dylib,dll}`, un blob nativo opaco invocado
> via ctypes — no es código abierto. Para merge manual, sigue
> usando la app jwlmanager.

## CLI

### Inspect — resumen de un backup

```bash
jw library inspect mi-backup.jwlibrary
# name jw-core
# device jw-core
# schema v16
# locations 142
# notes 87
# highlights 234
# bookmarks 12
# tags 5
```

### From-notes — agente → .jwlibrary

El caso de uso principal: un agente escribió notas en JSON, las
empaquetas como `.jwlibrary`.

```bash
# notas.json:
# [
#   {
#     "title": "Reflexión sobre Juan 3:16",
#     "content": "El amor de Dios manifestado...",
#     "key_symbol": "nwt",
#     "book_number": 43,
#     "chapter_number": 3,
#     "meps_language": 1
#   },
#   {
#     "title": "Estudio del Cap. 1 de la Biblia enseña",
#     "content": "Tomó nota del párrafo 5...",
#     "key_symbol": "bh",
#     "doc_id": 1,
#     "meps_language": 1
#   }
# ]

jw library from-notes mi-backup.jwlibrary \
    --notes notas.json \
    --device "jw-core-agent"

# Wrote /Users/.../mi-backup.jwlibrary (2 notes)
```

Formato JSON por nota:

| Campo | Tipo | Notas |
|---|---|---|
| `title` | str | título de la nota |
| `content` | str | cuerpo |
| `key_symbol` | str | "nwt" para Biblia, otro para publicaciones |
| `book_number` | int | sólo para versículos bíblicos |
| `chapter_number` | int | sólo para versículos bíblicos |
| `doc_id` | int | sólo para publicaciones (id del documento) |
| `meps_language` | int | 0=EN, 1=ES, … |
| `issue_tag_number` | int | opcional (Atalaya con número) |
| `location_title` | str | opcional (visible en JW Library) |

### Re-export — edición de un backup existente

Para round-trip: leer un backup, mutar el SQLite con un script
custom, re-empaquetarlo.

```bash
# modify.py:
# def modify(conn):
#     conn.execute("UPDATE Note SET Title = ? WHERE NoteId = 1", ("Editado",))

jw library re-export original.jwlibrary modificado.jwlibrary \
    --script modify.py \
    --device "jw-core-script"
```

El callback `modify(conn: sqlite3.Connection)` recibe una conexión al
userData.db extraído. Cualquier UPDATE/INSERT/DELETE se commitea y se
re-empaqueta automáticamente.

## API Python

### Caso simple: escribir desde un db ya construido

```python
from pathlib import Path
from jw_core.writers.jw_library_backup import write_backup

out = write_backup(
    Path("mi-backup.jwlibrary"),
    user_data_db_path=Path("/tmp/userData.db"),
    device_name="jw-core",
)
```

### Caso round-trip: extract → modify → repack

```python
import sqlite3
from pathlib import Path
from jw_core.writers.jw_library_backup import update_backup

def add_note(conn: sqlite3.Connection) -> None:
    conn.execute(
        "INSERT INTO Note (NoteId, Guid, LocationId, Title, Content, "
        "LastModified, Created, BlockType) "
        "VALUES (999, 'agent-001', 1, 'Reflexión auto', 'cuerpo', "
        "datetime('now'), datetime('now'), 0)"
    )

out = update_backup(
    Path("input.jwlibrary"),
    Path("output.jwlibrary"),
    modify_fn=add_note,
    device_name="jw-core-agent",
)
```

### Validar el resultado

```python
from jw_core.parsers.jw_library_backup import parse_jw_library_backup

parsed = parse_jw_library_backup(out)
assert parsed.manifest.schema_version >= 14
assert len(parsed.notes) > 0
```

`parsers/jw_library_backup.py` lee la versión exacta del archivo que
escribiste (manifest hash propagado, schemaVersion del `PRAGMA
user_version`).

## Pipeline end-to-end: Obsidian vault → JW Library

Combinando con la integración Obsidian (Fase 20):

```python
import json
from pathlib import Path
from jw_core.integrations.obsidian_vault import scan_vault_for_jw_notes

vault = Path("~/Obsidian/JW").expanduser()
notes_raw = scan_vault_for_jw_notes(vault)  # → [{title, content, ref, ...}]

# Convertir a formato from-notes (con detección de book/chapter)
notes_json = []
for n in notes_raw:
    item = {
        "title": n.title,
        "content": n.content,
        "key_symbol": "nwt",
        "meps_language": 1,  # ES
    }
    if n.ref is not None:
        item["book_number"] = n.ref.book_num
        item["chapter_number"] = n.ref.chapter
    notes_json.append(item)

(vault / ".export").mkdir(exist_ok=True)
(vault / ".export" / "notes.json").write_text(json.dumps(notes_json))

# Empaquetar
import subprocess
subprocess.run([
    "jw", "library", "from-notes",
    str(vault / "obsidian-export.jwlibrary"),
    "--notes", str(vault / ".export" / "notes.json"),
])
```

## Schema version mínimo soportado

JW Library 12+ usa schema v14+. El writer escribe `PRAGMA user_version
= 16` por defecto en `from-notes`. Si el caller pasa un userData.db con
versión menor, el manifest la honra:

```python
write_backup(out, user_data_db_path=db, schema_version_fallback=14)
```

`schema_version_fallback` solo se usa si `PRAGMA user_version` retorna 0
(DB nuevo sin pragma seteado).

## Limitaciones reconocidas

- **No genera tags ni TagMap** automáticamente desde el JSON. Las notas
  quedan sin etiquetar (puedes etiquetarlas en JW Library después).
- **No genera UserMark + BlockRange + highlight**. Para highlights con
  rangos exactos a nivel de carácter, escribe directamente el SQLite
  (`update_backup` con callback) o usa jwlmanager GUI.
- **GUIDs no son únicos globales**. Si reimportas el backup en otro
  dispositivo que ya tenía notas con el mismo NoteId, JW Library
  preguntará por estrategia de merge.
- **Sin sync con jw.org cloud**. El backup es local-first; el usuario
  decide explícitamente cuándo importarlo en su app.

## Tests

`packages/jw-core/tests/test_jw_library_writer.py` (9 tests):

- Round-trip con parser existente: notas leídas idénticas a las
  escritas.
- `LastModified` se re-stamper a `datetime.now()`.
- Tolerancia a DB sin tabla `LastModified` (no crashea).
- Hash SHA-256 manifest coincide con bytes DB embebidos.
- `update_backup` callback que añade una nota y verifica que sobrevive
  al repack.
- `update_backup` sin callback funciona como re-stamp del manifest.
- Errores: archivo no existe, ZIP malformado.

## Crédito y licencia

Pipeline ported de `erykjj/jwlmanager` (MIT, Python). La GUI completa
de jwlmanager (PySide6, ~3500 commits) sigue siendo la herramienta
recomendada cuando necesitas el merge — el toolkit cubre solo
write/round-trip.

Ver `README.md` raíz para atribuciones completas.
