---
title: Integración con la app oficial JW Library — concepto
audiencia: arquitectos y colaboradores
fase: 19
---

# Concepto: integración con la app oficial JW Library

> Cómo y por qué `jw-agent-toolkit` se conecta con la app de JW Library, qué garantías ofrece y qué riesgos evita. Para casos prácticos ver [guía de integración](../guias/integracion-jw-library.md). Para contratos API ver [`referencia/integraciones.md`](../referencia/integraciones.md).

## Por qué existe esta capa

El toolkit ya cubre 100% del corpus público (parsers EPUB y JWPUB descifrado, RAG, agentes), pero la **realidad operacional** del usuario tiene tres elementos que ningún parser ofrece:

1. **La app oficial está en su dispositivo**. Si abrimos un versículo desde el agente, el usuario espera verlo *en la app que ya tiene configurada* — con su tema, sus marcadores y su sync de cuenta JW.
2. **Las notas y resaltados son del usuario**. El agente que ignora esas anotaciones está ciego al estudio que la persona ya hizo.
3. **Cada plataforma tiene reglas distintas**. Windows expone más; macOS está blindado por la sandbox de la Mac App Store; Linux no tiene build.

Esta capa cubre esas tres realidades sin pelearse con la app oficial ni con los términos de uso de jw.org.

## Las 4 capas de integración

```
┌──────────────────────────────────────────────────────────────────┐
│  Capa 4 — Coexistencia con MCPs externos (advenimus/jw-mcp)      │
│  Documentación operativa; sin código en el toolkit.              │
└──────────────────────────────────────────────────────────────────┘
┌──────────────────────────────────────────────────────────────────┐
│  Capa 3 — Inspector de biblioteca local (read-only)              │
│  • Windows: publications.db en LocalState (UWP package)          │
│  • macOS:   userData.db vía Full Disk Access (sandbox container) │
│  Opt-in con env var JW_LIBRARY_LOCAL_READ=1.                     │
└──────────────────────────────────────────────────────────────────┘
┌──────────────────────────────────────────────────────────────────┐
│  Capa 2 — Parser de backup `.jwlibrary` + sync incremental       │
│  Cross-platform 100%. Lee notas, marcadores, resaltados, campos. │
│  Sidecar JSON con last_modified → diff → solo nuevos/cambiados.  │
└──────────────────────────────────────────────────────────────────┘
┌──────────────────────────────────────────────────────────────────┐
│  Capa 1 — Deep-linking via `jwlibrary://`                        │
│  Construcción + dispatch del esquema URL registrado por la app.  │
│  Es la **única vía oficialmente sancionada** de control externo. │
└──────────────────────────────────────────────────────────────────┘
```

Las capas son **independientes**: puedes usar la 1 sin tocar las otras. Apilarlas (1+2+catálogo MEPS) habilita el caso de uso completo: *"abre la publicación X párrafo Y en la app del usuario, y considera sus notas como contexto adicional para responder"*.

## El esquema `jwlibrary://`

El esquema lo registra la app oficial al instalarse (vía `windows.protocol` en UWP, `CFBundleURLTypes` en la app iPad). Cualquier proceso puede llamarlo; el sistema operativo lo dirige a la app.

### Sintaxis derivada por la comunidad

```
jwlibrary:///finder?bible=BBCCCVVV[-BBCCCVVV][&wtlocale=LL]
jwlibrary:///finder?wtlocale=LL&docid=N[&par=P]
```

`BB` = libro 1..66 (2 dígitos). `CCC` = capítulo (3 dígitos). `VVV` = versículo (3 dígitos). `LL` = código JW (`E`/`S`/`T`/`F`/`X`/`I`/`J`/`U`/`CHS`/`KO`/...). `N` = MEPS document_id. `P` = paragraph anchor.

### Por qué no UI Automation / AppleScript

| Vía | Estabilidad | Pros | Cons |
|---|---|---|---|
| **`jwlibrary://`** | alta | oficial, registrada, multi-plataforma | sólo "ir a versículo/doc"; no controla scroll, marcadores, etc. |
| UI Automation Windows | baja | control fino de la UI | rompe en cada update de la app; sandbox UWP limita |
| AppleScript macOS | nula | rico ecosistema en Mac | la app iPad no expone diccionario `.sdef` |
| Accessibility (AXUIElement) | media | independiente del lenguaje | frágil contra cambios de UI; requiere permisos de Accessibility |

El toolkit opta por `jwlibrary://` y mantiene las demás vías documentadas pero no implementadas.

## El formato `.jwpub`

Cada publicación es un ZIP con un `manifest.json` y un SQLite donde los contenidos HTML van zlib-comprimidos y cifrados con AES-128-CBC. La derivación de clave (descubierta por `gokusander/jwpub-toolkit`) está implementada en `jw_core.parsers.jwpub` y no es un objetivo de esta fase. Lo que nos interesa aquí es que **cada documento de un `.jwpub` tiene un `document_id` y un `meps_document_id`** — exactamente los identificadores que `jwlibrary:///finder?docid=N` espera.

De ahí nace la idea del [catálogo MEPS local](#capa-catálogo-meps): indexar cada `.jwpub` que el usuario descargue para que `pub_code` ("bh", "lff", "w24") sea suficiente para construir un deep link a una publicación específica.

## El formato `.jwlibrary`

El backup del usuario también es un ZIP, con dos miembros:

```
.jwlibrary
├── manifest.json   # name, creationDate, version, type, hash, userDataBackup{}
└── userData.db     # SQLite con el schema oficial documentado por la propia app
```

El schema oficial vive en `/Applications/JW Library.app/WrappedBundle/Userdata_Userdata.bundle/Scripts/Schema.sql` (v16 al cierre de esta fase). Tablas:

| Tabla | Rol |
|---|---|
| `Location` | direccionable: bíblica (book+chapter) o publicación (key_symbol+document_id) |
| `UserMark` | resaltado coloreado anclado a una `Location` |
| `BlockRange` | offsets de carácter del resaltado dentro del bloque |
| `Note` | título + cuerpo, opcionalmente anclado a `UserMark` o `Location` |
| `Bookmark` | acceso rápido (max 10 por publicación) |
| `Tag` + `TagMap` | etiquetado usuario (incluye built-in "Favorite") |
| `InputField` | respuestas a campos de publicación (workbook, etc.) |
| `PlaylistItem*` | playlist de medios — no consumida por el toolkit hoy |

El parser del toolkit es **defensivo por diseño**: usa `PRAGMA table_info()` y proyecta sólo columnas presentes. Sobrevive a futuras versiones de schema sin recompilar.

## Sync incremental

Re-ingerir el backup completo en cada export sería:
1. Duplicar notas que el agente ya vio (ruido en el RAG).
2. Dejar fantasmas: notas que el usuario borró siguen en el índice.

La solución es un **sidecar JSON** que recuerda, por backup, qué hemos visto:

```
~/.jw-agent-toolkit/rag/jw_library_sync.json
{
  "<manifest.hash>": {
    "last_synced_at": "2026-05-30T10:00:00+00:00",
    "notes":      { "<guid>": {"item_id":"…", "source_id":"jwlib:note:10",
                               "last_modified":"2024-11-15", "content_hash":"…"} },
    "bookmarks":  { "<id>":   {…} },
    "input_fields": { "<loc>:<tag>": {…} }
  }
}
```

El **`content_hash`** captura cambios silenciosos donde `LastModified` no se actualiza (raro pero observado al revertir y re-editar). El diff produce 3 conjuntos por categoría:

- **new** — guid nuevo. Indexar.
- **updated** — content_hash cambió. Eliminar chunks viejos (`source_id`), re-indexar.
- **deleted** — guid en state pero no en backup. Eliminar.

La invariante del state file: **toda nota vista del backup queda registrada**, incluso si no se indexó (por ser muy corta). Esto evita que el siguiente sync la reporte como "new" eternamente.

## Catálogo MEPS

Construir `jwlibrary:///finder?docid=N` requiere saber el `document_id`. No hay catálogo público que mapee `pub_code` ("bh") → `docid`. Lo construimos localmente:

```
~/.jw-agent-toolkit/meps_catalog.db
├── publication(pub_code, language_index, title, year, …)
└── document   (pub_code, language_index, document_id, meps_document_id,
                title, chapter_number, …)
```

`MepsCatalog.index_jwpub(path)` parsea el manifest (sin descifrar — barato) y hace upsert. Idempotente. Una vez poblado:

- `resolve_docid("bh", chapter_number=3)` → CatalogDocument para el capítulo 3
- `find_documents(meps_document_id=12345)` → publicación a la que pertenece

Y se compone con la Capa 1: `open_publication_by_symbol("bh", chapter_number=3)` resuelve internamente y dispara el deep link.

## macOS Full Disk Access

Por defecto, la sandbox de la Mac App Store esconde el container de la app a procesos externos. Sin embargo, si el usuario:

1. Abre **System Settings → Privacy & Security → Full Disk Access**.
2. Añade el proceso huésped (Terminal, iTerm, Claude Desktop, VS Code).
3. Reinicia ese proceso.

…entonces `~/Library/Containers/org.jw.jwlibrary/Data/...` se vuelve legible. El `userData.db` está allí (formato SQLite estándar — los frameworks `Realm` que carga la app son para otras bases). El toolkit:

- Sondea con `os.scandir` para distinguir "no existe" vs "TCC bloqueó".
- Si pasa, copia el `userData.db` a un tempfile (la app puede tenerlo abierto en WAL mode — copiar es la opción segura) y lo parsea con el mismo backend del parser `.jwlibrary`.
- Si no, devuelve instrucciones paso a paso de cómo conceder FDA.

**Esta capa no es destructiva**: nunca abre el DB en modo escritura ni toca el sync de la cuenta JW. Si el usuario revoca FDA, la lectura simplemente vuelve a fallar.

## Restricciones legales y éticas

ToS jw.org (verbatim del 2026-05-30):

> "You agree not to … use any robot, spider, site search/retrieval application, or other automated device, process, or means to access, retrieve, scrape, or index any portion of the Site or any Content"

…con la excepción explícita:

> "Public Web sites may provide the option to permit users to copy the Content for private and non-commercial uses."

Implicación: el toolkit **debe** mantenerse gratuito y no comercial. Las 4 capas de esta integración:

| Capa | Impacto en ToS |
|---|---|
| 1. Deep linking | Neutro — no descarga nada de jw.org. |
| 2. Backup parser | Neutro — lee un archivo del propio usuario. |
| 3. Inspector local | Neutro — lee archivos locales del usuario. |
| 4. Coexistencia | Neutro — documentación. |

El uso de `b.jw-cdn.org/apis/pub-media/GETPUBMEDIALINKS` para descargar EPUB/PDF/MP3/MP4 (ya implementado en Fase 2) está cubierto por el carve-out de uso personal y no comercial.

## Decisiones de diseño relevantes

| Decisión | Razonamiento |
|---|---|
| `dry_run=True` por defecto en deep links | Un cliente de chat (Claude Desktop) puede preferir mostrar el link al usuario en lugar de abrir la app sin pedirle confirmación. |
| `_assert_safe_jwlibrary_url` | Defensa en profundidad: aunque los builders del toolkit nunca emitan otro esquema, el dispatcher se exporta y un caller externo podría intentar abusarlo. |
| Sync state keyed por `manifest.hash` | Permite trackear N backups (iPhone + iPad + Mac) en un único sidecar sin colisiones. |
| Catálogo MEPS en SQLite (no JSON) | Lookups por `chapter_number` y `meps_document_id` necesitan índice; con tens of thousands de docs el costo de un JSON full-scan no escala. |
| FDA es **opt-in** explícito | Reducir la sorpresa: nadie quiere que su MCP scaneé el filesystem sin pedirle permiso. `JW_LIBRARY_LOCAL_READ=1` lo hace explícito. |
| Schema parser defensivo | El schema oficial está en v16 al cierre de Fase 19. Versiones anteriores (v9-v15) y futuras siguen funcionando porque proyectamos sólo columnas presentes. |
| No tocar la cuenta JW del usuario | La app oficial es la única que sube/baja datos al servidor. El toolkit nunca emula el endpoint de sync ni manipula cookies de jw.org/auth. |

## Lo que se queda fuera (por ahora)

- **UI Automation Windows** para casos no cubiertos por el deep link.
- **AXUIElement macOS** para igualar la cobertura de Windows.
- **Sync inverso** (toolkit → app): escribir notas en el `userData.db` mientras la app no corre. Técnicamente factible, pero invalidaría el sync con cuenta JW y forzaría restore manual del backup.
- **Mapping completo MEPS docid → URL wol**: hoy mapeamos pub_code → docid; el inverso (docid → URL navegable en wol.jw.org) es trivial con el catálogo + el `WOLClient`.
- **Parser de PlaylistItem**: el backup tiene playlists; el toolkit los expone como conteo pero no proyecta el contenido.

## Mapa al código

| Concepto | Ubicación |
|---|---|
| Deep links | `packages/jw-core/src/jw_core/integrations/jw_library.py` |
| Backup parser | `packages/jw-core/src/jw_core/parsers/jw_library_backup.py` |
| Sync incremental | `packages/jw-core/src/jw_core/integrations/jw_library_sync.py` |
| Catálogo MEPS | `packages/jw-core/src/jw_core/integrations/meps_catalog.py` |
| Inspector local | `packages/jw-core/src/jw_core/integrations/jw_library_local.py` |
| Tools MCP | `packages/jw-mcp/src/jw_mcp/server.py` (sección Phase 19) |
| Tests | `packages/jw-core/tests/test_jw_library_*.py` (4 archivos, 77 tests) |

## Referencias externas

- [`msakowski/obsidian-library-linker`](https://github.com/msakowski/obsidian-library-linker) — plugin Obsidian que documenta la sintaxis `jwlibrary://` empíricamente.
- [`MrCyjaneK/jwapi`](https://github.com/MrCyjaneK/jwapi) — documentación abierta del formato `.jwpub`.
- [`gokusander/jwpub-toolkit`](https://github.com/gokusander/jwpub-toolkit) — derivación de clave AES para JWPUB (origen del descifrado en `jw_core.parsers.jwpub`).
- [`allejok96/jwlib`](https://github.com/allejok96/jwlib) — wrapper Python sobre las APIs públicas de jw.org.
- [`2good2flex/jw-backup-tool`](https://github.com/2good2flex/jw-backup-tool) — merge de múltiples `.jwlibrary` en navegador.
- [`AntonyCorbett/SbJwlLauncher`](https://github.com/AntonyCorbett/SbJwlLauncher) — lanzador CLI Windows para JW Library.
- [Schema oficial v16](file:///Applications/JW%20Library.app/WrappedBundle/Userdata_Userdata.bundle/Scripts/Schema.sql) — distribuido con la app, contiene `CREATE TABLE` autoritativo.
- [Apple TCC](https://developer.apple.com/documentation/security/protecting_user_data_with_app_sandbox) — Privacy framework que regula Full Disk Access en macOS.
