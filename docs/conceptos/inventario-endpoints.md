# Inventario de endpoints externos

> Cada endpoint que el toolkit consume, con método, autenticación, parámetros, formato de respuesta y ejemplos curl.

## Resumen

| Host | Endpoint | Auth | Cliente |
|---|---|---|---|
| `b.jw-cdn.org` | `/tokens/jworg.jwt` | — | `CDNClient._get_token` |
| `b.jw-cdn.org` | `/apis/search/results/{lang}/{filter}` | JWT Bearer | `CDNClient.search` |
| `b.jw-cdn.org` | `/apis/pub-media/GETPUBMEDIALINKS` | — | `PubMediaClient.get_publication` |
| `data.jw-api.org` | `/mediator/v1/languages/{lang}/web` | — | `MediatorClient.list_languages` |
| `data.jw-api.org` | `/mediator/finder` | — | `MediatorClient.find_item` |
| `wol.jw.org` | `/{iso}/wol/b/{res}/{lp}/{pub}/{book}/{ch}` | — | `WOLClient.get_bible_chapter` |
| `wol.jw.org` | `/{iso}/wol/d/{res}/{lp}/{docid}` | — | `WOLClient.fetch` / `TopicIndexClient.get_subject_page` |
| `wol.jw.org` | `/{iso}/wol/h/{res}/{lp}` | — | `WOLClient.get_today_homepage` |
| `wol.jw.org` | `/{iso}/wol/bc/{res}/{lp}/{doc}/{group}/{index}` | — | `WOLClient.get_cross_reference_panel` |

## 1. Token JWT

```
GET https://b.jw-cdn.org/tokens/jworg.jwt
```

Devuelve un JWT corto en texto plano. TTL: minutos (no documentado pero observado ~5-10 min). Se cachea en memoria; al recibir 401, se refresca y se reintenta.

```bash
curl -s https://b.jw-cdn.org/tokens/jworg.jwt
# eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpYXQ...
```

## 2. Búsqueda

```
GET https://b.jw-cdn.org/apis/search/results/{lang}/{filter}?q={query}
Headers:
  Authorization: Bearer {jwt}
  Accept: application/json; charset=utf-8
  Referer: https://www.jw.org/
```

- `{lang}` — código JW (`E`, `S`, `T`, ...).
- `{filter}` — uno de: `all`, `publications`, `videos`, `audio`, `bible`, `indexes`.
- `{query}` — texto urlencoded.

**Respuesta** (JSON):

```json
{
  "results": [
    {"type": "group", "title": "Publications", "results": [
      {
        "title": "Why Did Jesus Die?",
        "snippet": "...",
        "links": {"wol": "https://wol.jw.org/en/wol/d/r1/lp-e/2014365"},
        "subtype": "article"
      }
    ]},
    {"title": "...", "links": {...}}
  ]
}
```

El cliente aplana grupos vs items en `_flatten_search_results`. La API **no** soporta un parámetro `limit` server-side; truncamos en el cliente.

```bash
TOKEN=$(curl -s https://b.jw-cdn.org/tokens/jworg.jwt)
curl -s -H "Authorization: Bearer $TOKEN" \
  -H "Accept: application/json; charset=utf-8" \
  -H "Referer: https://www.jw.org/" \
  "https://b.jw-cdn.org/apis/search/results/E/all?q=peace"
```

## 3. Pub-media (`GETPUBMEDIALINKS`)

```
GET https://b.jw-cdn.org/apis/pub-media/GETPUBMEDIALINKS
    ?output=json
    &pub={code}
    &langwritten={jw_code}
    [&issue=yyyymm]
    [&booknum=1..66]
    [&fileformat=PDF|EPUB|JWPUB|MP3|RTF|BRL]
    [&alllangs=1]
```

**Respuesta** (JSON):

```json
{
  "pubName": "Bible Teach",
  "files": {
    "E": {
      "EPUB": [
        {
          "title": "What Does the Bible Really Teach?",
          "file": {"url": "https://...", "checksum": "..."},
          "filesize": 1234567,
          "mimetype": "application/epub+zip"
        }
      ],
      "PDF": [...]
    }
  }
}
```

```bash
curl -s "https://b.jw-cdn.org/apis/pub-media/GETPUBMEDIALINKS?output=json&pub=bh&langwritten=E&fileformat=EPUB"
```

## 4. Mediator: lista de idiomas

```
GET https://data.jw-api.org/mediator/v1/languages/{lang}/web
```

`{lang}` controla el idioma de los nombres devueltos (`E`, `S`, ...).

**Respuesta** (JSON):

```json
{
  "languages": [
    {
      "symbol": "E", "locale": "en", "name": "English",
      "vernacularName": "English", "direction": "ltr",
      "isSignLanguage": false, "hasWebContent": true
    }
  ]
}
```

## 5. Mediator: finder

```
GET https://data.jw-api.org/mediator/finder?lang={code}&item={key}
```

Resuelve un código de contenido (p.ej. `pub-edj_x_VIDEO`) a sus URLs deliverable. Útil para encadenar con `GETPUBMEDIALINKS` o para descubrir streams.

## 6. WOL: capítulo bíblico

```
GET https://wol.jw.org/{iso}/wol/b/{res}/{lp}/{pub}/{book_num}/{chapter}
```

| Variable | Significado | Cómo se obtiene |
|---|---|---|
| `{iso}` | Código ISO 639-1 | `Language.iso` |
| `{res}` | Versión del bundle WOL | `Language.wol_resource` (`r1` en, `r4` es, `r5` pt) |
| `{lp}` | lp-tag | `Language.lp_tag` (`lp-e`, `lp-s`, `lp-t`) |
| `{pub}` | Código de publicación bíblica | `Language.default_bible` (`nwtsty` o `nwt`) |
| `{book_num}` | 1..66 | Estándar JW (1 = Génesis, 66 = Apocalipsis) |
| `{chapter}` | número de capítulo | — |

Ejemplo: `https://wol.jw.org/es/wol/b/r4/lp-s/nwt/43/3` (Juan 3 en español).

Ancla opcional `#study=discover&v={book}:{ch}:{verse}` posiciona en el versículo.

Devuelve HTML server-side rendered. Lo parseamos con BeautifulSoup en `parsers.article`, `parsers.verse`, `parsers.study_notes`, `parsers.cross_references` según la información que se busque.

## 7. WOL: documento / artículo / tema

```
GET https://wol.jw.org/{iso}/wol/d/{res}/{lp}/{docid}
```

`{docid}` es el WOL document id (entero). Se usa tanto para artículos individuales (revistas, libros) como para páginas de tema del Índice de Publicaciones.

## 8. WOL: homepage del idioma (texto diario)

```
GET https://wol.jw.org/{iso}/wol/h/{res}/{lp}
```

La página del día contiene el texto diario en `<div class="todayItem">` (o `.dailyText`, varía). Parseado por `parsers.daily_text`.

## 9. WOL: panel de referencias cruzadas

```
GET https://wol.jw.org/{iso}/wol/bc/{res}/{lp}/{doc_id}/{group}/{index}
```

El `href` del marcador inline `+` en un versículo apunta a uno de estos paneles. La descarga es **lazy**: el toolkit solo lo trae cuando se pide explícitamente con `resolve_panel=True` en la herramienta MCP `get_cross_references`.

## Formato JWPUB (offline)

```
{file}.jwpub  =  ZIP
                 ├── manifest.json
                 └── contents       ← otro ZIP
                                    ├── {symbol}_{lang}.db   ← SQLite
                                    └── images/*
```

La tabla `Document` del SQLite tiene una columna `Content` cifrada (AES-CBC sobre zlib, contentFormat `"z-a"` en el manifest). La derivación de clave **no es pública**. Por eso `parsers.jwpub.parse_jwpub_metadata` expone solo metadata estructural y `decrypted_text_available=False`.

Para texto completo offline, usar **EPUB**: descargar con `download_publication(pub_code, format='EPUB', ...)` y procesar con `parsers.epub.parse_epub`.

## Headers que usamos

- **`User-Agent`**: `WOLClient` envía `jw-agent-toolkit/0.1 (+research)` para ser identificable.
- **`Accept-Language`**: `WOLClient` envía `en,es;q=0.9` por defecto.
- **`Authorization`**: solo en la búsqueda CDN (`Bearer {jwt}`).
- **`Accept: application/json; charset=utf-8`** y **`Referer: https://www.jw.org/`**: requeridos por la API de búsqueda CDN; sin ellos devuelve 403.

## Comportamiento ante errores

| Código | Significado típico | Manejo |
|---|---|---|
| `401` | JWT expirado (búsqueda CDN) | Refresca token y reintenta una vez |
| `404` | Publicación inexistente, capítulo fuera de rango, idioma no soportado | Eleva `PubMediaError` / `WOLError` con mensaje |
| `5xx` | Error temporal del servidor | Eleva la excepción correspondiente, sin retry automático (Fase 9 añadirá backoff) |

## Notas sobre rate limiting

Hoy **no aplicamos rate limiting** desde el cliente. WOL y CDN aceptan ráfagas razonables (decenas de requests por minuto) sin bloquear. Si vas a hacer ingest masivo (cientos de capítulos), considera meter sleeps entre llamadas hasta que la Fase 9 añada rate limiting + backoff exponencial.
