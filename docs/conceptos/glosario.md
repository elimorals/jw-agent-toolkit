# Glosario JW.org

> Términos del ecosistema jw.org / wol.jw.org / Watch Tower que aparecen en el código y la documentación.

## Sitios y dominios

| Término | Descripción |
|---|---|
| **jw.org** | Sitio público principal de los Testigos de Jehová. Contiene publicaciones, videos, audios. |
| **wol.jw.org** | "Watchtower ONLINE Library". Vista web de la biblioteca completa: Biblia (varias ediciones), libros, folletos, revistas. Es la fuente principal de contenido que parseamos. |
| **b.jw-cdn.org** | CDN de jw.org. Sirve la API de búsqueda JSON (`/apis/search/...`), los tokens JWT (`/tokens/...`) y el `pub-media` (descargas: PDF, EPUB, JWPUB, MP3). |
| **data.jw-api.org** | Endpoint público no autenticado para metadata: registro de idiomas (`/mediator/v1/languages/...`), finder de contenido (`/mediator/finder`). |

## Códigos de publicaciones

JW asigna un "pub code" corto a cada publicación. Aparecen en URLs y en el inventario `GETPUBMEDIALINKS`.

| Código | Publicación |
|---|---|
| `nwt` | New World Translation (Traducción del Nuevo Mundo) — versión estándar |
| `nwtsty` | NWT Study Edition (Edición de Estudio del Nuevo Mundo) — incluye notas de estudio + cross-refs. Solo inglés por ahora. |
| `Rbi8` | Edición Reference Bible 1984 (legado) |
| `fg` | Folleto *Good News from God!* (¡Buenas noticias de parte de Dios!) |
| `bh` | Libro *What Does the Bible Really Teach?* (¿Qué enseña realmente la Biblia?) |
| `bhs` | Versión corta del anterior |
| `lff` | Libro *Enjoy Life Forever!* (Disfruta de la vida para siempre) |
| `w` / `ws` | Watchtower edición pública / edición de estudio |
| `g` | Awake! (¡Despertad!) |
| `it-1` / `it-2` | *Insight on the Scriptures*, volúmenes 1 y 2 |
| `ti` | Folleto *Should You Believe in the Trinity?* |
| `rr` | Libro *Pure Worship of Jehovah — Restored at Last!* |

## Códigos de idioma

JW usa tres convenciones simultáneas:

| Convención | Ejemplo (Inglés) | Ejemplo (Español) | Ejemplo (Portugués) |
|---|---|---|---|
| **JW code** (interno) | `E` | `S` | `T` |
| **ISO 639-1** (URLs jw.org) | `en` | `es` | `pt` |
| **lp-tag** (URLs wol.jw.org) | `lp-e` | `lp-s` | `lp-t` |

Adicionalmente, cada idioma tiene una versión de recurso `wol_resource`:

| Idioma | `wol_resource` | Biblia por defecto |
|---|---|---|
| Inglés | `r1` | `nwtsty` |
| Español | `r4` | `nwt` |
| Portugués | `r5` | `nwt` |

El número `r{N}` es la versión del bundle de recursos que sirve WOL para ese idioma. Cambia con el tiempo y entre idiomas; debe mantenerse al día en `jw_core.languages._REGISTRY`.

## Estructura de URLs en wol.jw.org

```
https://wol.jw.org/{iso}/wol/{tipo}/{wol_resource}/{lp_tag}/{...path...}
```

donde `{tipo}` es uno de:

| Tipo | Significado | Path adicional |
|---|---|---|
| `b` | Bible — capítulo | `/{pub}/{book_num}/{chapter}` |
| `d` | Documento — artículo o página de tema | `/{docid}` |
| `h` | Homepage del idioma — contiene el texto diario | (vacío) |
| `bc` | Cross-reference panel | `/{doc_id}/{group}/{index}` |
| `pc` | Publication citation panel | `/{doc_id}/{group}/{index}` |
| `tc` | Table-of-contents | `/{doc_id}/{group}/{index}` |

Anclas:

- `#study=discover&v={book}:{chapter}:{verse}` posiciona en el versículo objetivo y abre el panel de estudio.

## Estructura HTML que parseamos

### Capítulo bíblico (`/wol/b/...`)

- `<article id="article">` contiene todo el cuerpo del capítulo.
- Cada párrafo: `<p id="pN" data-pid="N">`.
- Cada versículo dentro de un párrafo: `<span class="v" id="v{book}-{ch}-{verse}-{instance}">`.
- Marcadores inline de cross-refs: `<a class="b" href="/{iso}/wol/bc/...">+</a>`.
- Marcas de pronunciación: `·` (interpunct), `ʹ` (Modifier Letter Prime), `*` (asterisco para notas al pie).

### Página de tema del Índice de Publicaciones (`/wol/d/...{subject_docid}`)

- `<p class="st">TÍTULO DEL TEMA</p>` — título.
- `<p class="sa">(See also …)</p>` — referencias a otros temas relacionados.
- `<p class="su">subtítulo: <a>cita</a>; <a>cita</a></p>` — subtítulo de nivel superior con citas.
- `<p class="sv">sub-subtítulo: <a>cita</a></p>` — entrada de nivel valor (anidada).

Las citas se distinguen por el path del href:

| Path | `kind` |
|---|---|
| `/bc/` | `bible` |
| `/pc/` | `publication` |
| `/tc/` | `section` |
| `/d/` | `document` |
| otro | `other` |

### Notas de estudio (`/wol/b/.../{nwtsty}/...`)

Cada nota: `<li class="item studyNote">`.

- `<strong>headword:</strong>` — palabra/frase que la nota anota.
- Cuerpo: comentario en texto plano.
- Referencias inline dentro del cuerpo: `<a class="b" href="...">`.

### Texto diario (`/wol/h/...`)

- Contenedor: `<div class="todayItem">` (o `.dailyText`, varía).
- Fecha: `.itemHeader` o `<h2>`.
- Versículo + cita: `.themeScrp`.
- Comentario: `.sb` o `<p>` no-themeScrp.

## Pub Media (`GETPUBMEDIALINKS`)

Endpoint que devuelve un JSON con todos los archivos descargables de una publicación, agrupados por idioma y formato. Cada entrada incluye URL, checksum, tamaño, mime-type. Útil para:

- Descargar la Biblia entera en EPUB.
- Bajar el JWPUB de un libro para procesarlo offline (futura Fase 5).
- Listar archivos de audio (MP3) de una revista.

Parámetros principales: `pub` (código), `langwritten` (JW code), `issue` (yyyymm para revistas), `booknum` (1-66 para libros bíblicos), `fileformat` (PDF/EPUB/JWPUB/MP3/RTF), `alllangs` (booleano).

## Índice de Publicaciones (Publications Index / Research Guide)

Index temático maestro de Watch Tower. Cada tema (p.ej. "Trinity", "Soul", "Last Days") es una página `d` en WOL con la siguiente estructura semántica:

- **Título** (`<p class="st">`).
- **Ver también** (`<p class="sa">`): referencias a otros temas.
- **Subtítulos** (`<p class="su">`): categorías de nivel superior.
- **Sub-entradas** (`<p class="sv">`): entradas anidadas bajo un subtítulo.
- **Citas**: cada `<a>` dentro de un subtítulo. Pueden ser referencias bíblicas (clase `b`, path `/bc/`), códigos de publicación (`/pc/`), secciones (`/tc/`) o documentos completos (`/d/`).

Es la **fuente autoritativa** para investigación doctrinal: el agente `apologetics` lo consulta primero antes que cualquier otra fuente.

## JWPUB

Formato de archivo offline de Watch Tower. Estructura (revertida en Fase 5.5):

1. Archivo `.jwpub` = ZIP estándar.
2. Dentro: `manifest.json` con metadata + un ZIP interno (entry `"contents"`).
3. ZIP interno: imágenes + un SQLite `.db` con:
   - Tabla `Document`: una fila por documento. Columna `Content` cifrada AES-128-CBC sobre zlib (`contentFormat="z-a"`).
   - Tabla `DocumentParagraph`: párrafos enlazados a documentos.

**Descifrado (Fase 5.5)**: la clave se deriva de `SHA256(f"{lang}_{symbol}_{year}") XOR magic_32byte_constant`. La constante se descubrió en [`gokusander/jwpub-toolkit`](https://github.com/gokusander/jwpub-toolkit) (MIT) inspeccionando JW Library. Implementado en `jw_core.parsers.jwpub._compute_key_iv`.

API pública: `parse_jwpub_metadata()` (sin decryption) y `parse_jwpub()` (con decryption + paragraphs extraídos del XHTML).

## Fase 9 — Infraestructura

Módulos añadidos en Fase 9 que cualquier cliente HTTP puede opt-in:

| Término | Significado |
|---|---|
| **DiskCache** | Cache SQLite con TTL, WAL, lazy eviction. Bytes adentro, bytes afuera. Ver `jw_core.cache.DiskCache`. |
| **TokenBucket / Throttler** | Rate limit per-host con bucket clásico. Default: 2 req/s, burst 5. Ver `jw_core.throttle`. |
| **backoff_delay** | Exponential backoff con full jitter (estilo AWS). Para retry loops manuales. |
| **Telemetry** | Detector opt-in de drift de la API. Opt-in vía `JW_TELEMETRY_ENABLED=1`. Hashea SHAPE de respuestas (no contenido) y compara contra baseline persistente. |
| **JWTManager** | Holder async-safe del JWT para `b.jw-cdn.org`. Extraído de `CDNClient` en Fase 9. |
| **politely_get** | Wrapper interno (`jw_core.clients._polite`) que cablea throttler + cache + telemetry en cada GET. |
| **ClientSuite / build_clients** | Factory (`jw_core.clients.factory`) que arma los 6 clientes con infraestructura compartida. |
| **WeblangClient** | Cliente alterno (`jw_core.clients.weblang`) para `www.jw.org/{iso}/languages/`. Más campos por idioma que mediator. |

## Términos cross-reference / "cross-ref"

Watch Tower distingue:

- **Referencia cruzada inline** (`<a class="b">+</a>` dentro de un versículo): es solo un *marcador* que dice "este versículo tiene paralelos; abre el panel". El panel real se sirve en una URL aparte (`/bc/...`).
- **Panel de referencias cruzadas**: HTML separado con la lista de paralelos bíblicos para esa posición. Se obtiene con `WOLClient.get_cross_reference_panel(href)`.

Por eficiencia, los marcadores se extraen del HTML del capítulo pero los paneles solo se descargan cuando se piden explícitamente (`resolve_panel=True` en la herramienta MCP).
