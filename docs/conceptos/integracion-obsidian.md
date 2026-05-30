---
title: Integración con Obsidian — concepto
audiencia: arquitectos y usuarios avanzados
fase: 20
---

# Concepto: integración con Obsidian (second brain)

> Por qué `jw-agent-toolkit` se conecta con un vault de Obsidian, qué porta del plugin `obsidian-library-linker`, y cómo se monta el flujo end-to-end de "second brain" para estudio personal y ministerio. Para casos prácticos ver [`guias/usar-con-obsidian.md`](../guias/usar-con-obsidian.md). Para contratos API ver [`referencia/integraciones.md`](../referencia/integraciones.md).

## Resumen

La Fase 20 toma las utilidades de manipulación de markdown del plugin Obsidian [`msakowski/obsidian-library-linker`](https://github.com/msakowski/obsidian-library-linker) (MIT) y las re-implementa como **funciones Python puras** dentro de `jw-core`, expuestas vía:

1. **API Python** — `jw_core.integrations.markdown.*`.
2. **Tools MCP** — `linkify_markdown_text`, `convert_jw_links_in_markdown`, `get_verse_as_markdown`, `index_obsidian_vault`, `export_jw_library_backup_to_vault`.
3. **REST API** — `POST /api/v1/linkify`, `/convert_links`, `/verse_markdown`, `/vault/index`, `/vault/export`.
4. **Plugin Obsidian nativo** — `apps/obsidian-jw-bridge/` invoca la REST API.

Esto cierra el ciclo "second brain": un agente LLM puede tomar tu markdown de Obsidian, enriquecerlo con enlaces `jwlibrary://`, insertar citas bíblicas con quote callouts, e indexar todo el vault al RAG para que el propio agente razone sobre tus notas y las notas de tu JW Library simultáneamente.

## Qué portamos del plugin

| Función original (TS) | Equivalente Python | Tool MCP / REST |
|---|---|---|
| `parseBibleReference` | (ya teníamos: `jw_core.parsers.reference.parse_reference`) | — |
| `formatJWLibraryLink` | `jw_core.integrations.jw_library.build_bible_url` (Fase 19) | — |
| `convertBibleTextToMarkdownLink` | `markdown.render_markdown_link` | — |
| `convertPublicationReference` | `markdown.convert_jwpub_publication_url` | — |
| `parseJWLibraryLink` (URL → ref) | `markdown.parse_jwlibrary_url` | — |
| `convertLinks` | `markdown.convert_jw_links_in_text` | `convert_jw_links_in_markdown` / `/convert_links` |
| `linkUnlinkedBibleReferences` | `markdown.linkify_markdown` | `linkify_markdown_text` / `/linkify` |
| `signLanguage.getBookLanguage` | `jw_core.languages.get_book_language` + `data.book_locales.SIGN_LANGUAGE_BASE_MAP` | — |
| Quote templates (callouts) | `markdown.render_verse_block` | `get_verse_as_markdown` / `/verse_markdown` |
| `locale/bibleBooks/*.yaml` (17 idiomas) | `jw_core/data/bible_books/*.json` + `data.book_locales.merge_into_books` | — |

Adicionalmente, **construimos** lo que el plugin no tenía:

- **Sync vault → RAG incremental**: `markdown.index_vault_to_rag` con sidecar JSON.
- **Export backup → vault**: `obsidian_vault.export_backup_to_vault`.
- **Plugin Obsidian propio** (`apps/obsidian-jw-bridge/`) que invoca la REST.

## Por qué un plugin Obsidian propio en lugar del original

El plugin original es un excelente convertidor de texto pero **no conecta con un agente LLM**. Nuestro plugin:

- **Habla REST con el toolkit local**: cualquier comando dispara un POST → procesado en Python (parser multi-idioma, sin red salvo cuando explícitamente se pide texto bíblico).
- **Lee y escribe el vault**: linkify in-place, export de backups como nuevas notas, indexa al RAG.
- **No reimplementa la lógica**: cero duplicación. Toda la inteligencia vive en Python; el plugin TS es una capa de UX delgada.
- **Comparte settings con la línea de comandos**: la misma instancia del toolkit sirve a Claude Desktop, scripts CLI, bots, REST y este plugin.

## Locales (17 idiomas)

Portados desde `obsidian-library-linker/locale/bibleBooks/`:

| JW code | ISO | Nombre |
|---|---|---|
| `E` | en | English |
| `S` | es | Spanish |
| `TPO` | pt-PT | Portuguese (Portugal) |
| `F` | fr | French |
| `X` | de | German |
| `I` | it | Italian |
| `U` | ru | Russian |
| `J` | ja | Japanese |
| `KO` | ko | Korean |
| `B` | cs | Czech |
| `C` | hr | Croatian |
| `D` | da | Danish |
| `O` | nl | Dutch |
| `FI` | fi | Finnish |
| `TG` | tl | Tagalog |
| `VT` | vi | Vietnamese |
| `CW` | bem | Cibemba |

Cada JSON tiene 66 entries con `name.long`, `name.medium`, `name.short` y `aliases[]`. El merger inteligente (`book_locales.merge_into_books`) los inyecta en el registry `BOOKS` con prioridad por idioma para evitar colisiones (ej. el alias "Ap" se queda como Apocalipsis en español/portugués/francés/portugués-PT, no como Áp-đia vietnamita).

## Sign languages

El mapping LSM/ASL/DGS/etc. → idioma base hablado está en `SIGN_LANGUAGE_BASE_MAP`. Cuando el usuario opera en una lengua de signos:

- El `wtlocale=` del URL conserva el código de la lengua de signos (la app oficial sabe qué hacer).
- La resolución de nombres de libros cae al idioma base (LSM → español).

`get_book_language("LSM") == "S"` permite que un agente que recibe "Juan 3:16" del usuario en contexto LSM construya un URL que abre la app en LSM y muestra el verso en su versión señada.

## Sync vault → RAG (incremental)

`index_vault_to_rag(vault_root, store, *, state_path=None, require_tag=None, glob='**/*.md', min_chars=16)`:

```
~/.jw-agent-toolkit/rag/vault_sync.json
{
  "/Users/me/Vault": {
    "last_synced_at": "2026-05-30T11:30:00+00:00",
    "notes": {
      "JW Library/bible/43/chapter-003/43003-Amor.md": {
        "path": "...",
        "mtime": 1717061700.0,
        "content_hash": "…",
        "source_id": "vault:JW Library/bible/43/chapter-003/43003-Amor.md"
      }
    }
  }
}
```

Diff lógica: por `mtime` y `content_hash` decidimos `unchanged` / `updated` / `new` / `deleted`. Eviction de chunks por `source_id` reutiliza `VectorStore.delete_by_source_ids` (de Fase 19).

Metadata en cada chunk: `kind="vault_note"`, `path`, `title`, `tags[]` (de frontmatter YAML), `frontmatter` completo, `mtime`. Esto permite preguntas tipo "qué notas mías con tag #ministerio mencionan Mateo 24".

## Export backup → vault

`export_backup_to_vault(backup_path, vault_dir, *, template='callout', length='medium', language='en', subdir='JW Library', overwrite=False)`:

```
<vault>/JW Library/
├── bible/
│   ├── 01/chapter-001/01001-Inicio-del-relato.md
│   └── 43/chapter-003/43003-Amor-divino.md
└── publications/
    └── w24/2024-04-articulo.md
```

Cada `.md` tiene frontmatter completo (book, chapter, key_symbol, document_id, created, last_modified, tags) más el contenido de la nota y un deep link callout a la posición en JW Library. El default es **no sobreescribir** archivos existentes (`overwrite=False`) para no perder edits del usuario.

## Arquitectura del plugin Obsidian (`apps/obsidian-jw-bridge/`)

```
apps/obsidian-jw-bridge/
├── manifest.json          # id, name, minAppVersion, isDesktopOnly=false
├── package.json           # deps: obsidian@1.7, esbuild, typescript
├── tsconfig.json
├── esbuild.config.mjs     # bundle CJS → main.js
├── README.md              # uso, build, settings
└── src/
    ├── main.ts            # JwBridgePlugin class, 8 comandos, settings tab, modals
    └── toolkitClient.ts   # JwToolkitClient — wrapper requestUrl alrededor del REST
```

8 comandos exportados a la paleta:

1. Linkify selection
2. Linkify current note
3. Linkify entire vault
4. Convert jwpub:// links in current note
5. Insert Bible verse at cursor…
6. Export JW Library backup into vault…
7. Index this vault into the toolkit RAG store
8. Check bridge health

Settings persistidos via `Plugin.loadData/saveData`: API URL, idioma, wtlocale override, length, template, include_verse_text, auto-linkify-on-save.

El cliente REST usa `requestUrl` de Obsidian (en lugar de `fetch`) para máxima compatibilidad cross-origin y mobile.

## Estado del flujo "second brain"

End-to-end:

```
Usuario escribe en Obsidian        ┐
   ↓ (Cmd-P → Linkify current)     │
Plugin POSTea a localhost:8765     │
   ↓                               │
jw-mcp REST (FastAPI)              │
   ↓ jw_core.integrations.markdown │ ← tools también accesibles a
   ↓                               │   Claude Desktop directamente
Texto enriquecido devuelto         │
   ↓                               │
Plugin reescribe el .md            │
   ↓                               │
Vault Obsidian actualizado         ┘
```

Y la dirección inversa:

```
Usuario exporta backup .jwlibrary  ┐
   ↓ (Cmd-P → Export backup)       │
Plugin POSTea a /vault/export      │
   ↓                               │
parse_jw_library_backup            │
   ↓                               │
Escribe N .md bajo <vault>/JW Library/
   ↓
Vault contiene ahora notas         │
+ backlinks + frontmatter          ┘
```

Y el agente LLM (Claude Desktop, Claude Code) ve TODO:

- Tools MCP `semantic_search` ahora puede mezclar:
  - chunks `kind="bible_chapter"` (corpus público)
  - chunks `kind="jwpub_document"` (publicaciones descifradas)
  - chunks `kind="user_note"` (notas exportadas del backup JW Library)
  - chunks `kind="vault_note"` (notas Obsidian del usuario)
- Tools deep-linking (`open_in_jw_library`, `open_publication_by_symbol`) permiten al agente cerrar el loop abriendo la posición exacta en la app del usuario.
- Tools markdown (`linkify_markdown_text`, `get_verse_as_markdown`) permiten al agente devolver texto **listo para pegar** en cualquier nota de Obsidian.

## Decisiones de diseño

| Decisión | Razonamiento |
|---|---|
| Yamls → JSON al portar | Evita añadir PyYAML como dep mandatoria. Los JSON pesan menos y son nativos de Python. |
| Locales con prioridad explícita | `_PRIORITY_LOCALES = ("E", "S", "TPO", "F", "X", "I", "U", "J", "KO")`. Garantiza que aliases ambiguos (ej. "Ap" para Apocalipsis vs Áp-đia) se resuelven a favor del idioma principal del usuario típico. |
| `_alias_key` espejo del parser | Las colisiones se detectan exactamente como las verá el parser en runtime: lowercase + NFD strip + sin puntuación. Sin esto, `Áp` (vi) colisionaba con `Ap` (es) en el lookup pero no en el merge. |
| Plugin TS delgado | Toda la lógica vive en Python. El plugin no tiene su propio parser ni catálogo de libros: si quieres mejorar el comportamiento, editas Python una vez y todos los clientes (CLI, MCP, REST, plugin) se benefician. |
| `requestUrl` en lugar de `fetch` | Obsidian Desktop usa Electron pero el plugin debe funcionar en mobile también; `requestUrl` es la API oficial cross-plataforma. |
| Sidecar JSON para vault sync | Mismo patrón que Fase 19 (`jw_library_sync.json`). Múltiples vaults conviven en el mismo archivo. |
| Defaults conservadores | `dry_run=True` en deep-links, `overwrite=False` en export, `autoLinkifyOnSave=false` en el plugin. La idea: nada irreversible sin acción explícita del usuario. |

## Lo que se queda fuera (por ahora)

- **Auto-completion in-editor**: el plugin original suggesta links mientras escribes. Lo recreamos como modal por simplicidad — el suggester completo es trabajo de UI Obsidian no trivial.
- **Templates configurables custom**: solo built-in templates. El plugin original permite definir prefijos/sufijos arbitrarios.
- **Modo offline para fetch de versos**: el toolkit ya descifra JWPUB localmente; cablear `get_verse_as_markdown` para preferir un JWPUB descargado en lugar de WOL es una mejora natural pero no implementada.
- **Backup writes**: el toolkit nunca escribe a `userData.db` por seguridad (rompe sync con cuenta JW). Por tanto, las edits en Obsidian no se reflejan en JW Library; el flujo es one-way (JW Library → Obsidian).

## Mapa al código

| Concepto | Ubicación |
|---|---|
| Locales | `packages/jw-core/src/jw_core/data/bible_books/*.json` + `data/book_locales.py` |
| Markdown utilities | `packages/jw-core/src/jw_core/integrations/markdown.py` |
| Vault sync | `packages/jw-core/src/jw_core/integrations/obsidian_vault.py` |
| Tools MCP | `packages/jw-mcp/src/jw_mcp/server.py` (sección Phase 20) |
| Endpoints REST | `packages/jw-mcp/src/jw_mcp/rest_api.py` (sección Phase 20) |
| Plugin Obsidian | `apps/obsidian-jw-bridge/` |
| Tests | `packages/jw-core/tests/test_markdown_utils.py`, `test_obsidian_vault.py` |

## Referencias externas

- [`msakowski/obsidian-library-linker`](https://github.com/msakowski/obsidian-library-linker) — origen de las utilidades portadas (MIT).
- [Obsidian Plugin API](https://docs.obsidian.md/Plugins/Getting+started/Build+a+plugin) — referencia para `apps/obsidian-jw-bridge/`.
- [Obsidian callouts](https://help.obsidian.md/Editing+and+formatting/Callouts) — sintaxis de los templates `[!quote]`.
- [FastAPI](https://fastapi.tiangolo.com/) — runtime del REST en `jw_mcp.rest_api`.
