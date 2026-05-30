# Inventario de endpoints externos

> Cada endpoint que el toolkit consume, con método, autenticación, parámetros, formato de respuesta y ejemplos curl.

## Resumen

| Host | Endpoint | Auth | Cliente | TTL cache |
|---|---|---|---|---|
| `b.jw-cdn.org` | `/tokens/jworg.jwt` | — | `auth.JWTManager.get_token` | (memoria) |
| `b.jw-cdn.org` | `/apis/search/results/{lang}/{filter}` | JWT Bearer | `CDNClient.search` | 900s |
| `b.jw-cdn.org` | `/apis/pub-media/GETPUBMEDIALINKS` | — | `PubMediaClient.get_publication` | 86400s |
| `data.jw-api.org` | `/mediator/v1/languages/{lang}/web` | — | `MediatorClient.list_languages` | 86400s |
| `data.jw-api.org` | `/mediator/finder` | — | `MediatorClient.find_item` | (sin TTL específico) |
| `www.jw.org` | `/{iso}/languages/` | — | `WeblangClient.list_languages` | 86400s |
| `wol.jw.org` | `/{iso}/wol/b/{res}/{lp}/{pub}/{book}/{ch}` | — | `WOLClient.get_bible_chapter` | 3600s |
| `wol.jw.org` | `/{iso}/wol/d/{res}/{lp}/{docid}` | — | `WOLClient.fetch` · `get_document_by_id` · `TopicIndexClient.get_subject_page` | 3600s |
| `wol.jw.org` | `/{iso}/wol/dt/{res}/{lp}/{YYYY}/{M}/{D}` | — | `WOLClient.get_daily_text_by_date` | 3600s |
| `wol.jw.org` | `/{iso}/wol/h/{res}/{lp}` | — | `WOLClient.get_today_homepage` | 3600s |
| `wol.jw.org` | `/{iso}/wol/publication/{res}/{lp}/{pub}[/{n}]` | — | `WOLClient.get_publication_page` | 3600s |
| `wol.jw.org` | `/{iso}/wol/bc/{res}/{lp}/{doc}/{group}/{index}` | — | `WOLClient.get_cross_reference_panel` | 3600s |

> TTL aplicado solo cuando el cliente está wired con `DiskCache` (ver [`docs/guias/infraestructura-fase9.md`](../guias/infraestructura-fase9.md)). Sin cache, cada GET va a la red.

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

## 5b. www.jw.org: lista alterna de idiomas

```
GET https://www.jw.org/{iso}/languages/
```

`{iso}` es el código ISO de la lengua de display (`en`, `es`, ...). Devuelve un JSON con `{"languages": [...]}`. Cada entrada tiene más campos que el endpoint mediator: `vernacularName`, `script`, `direction`, `isSignLanguage`, `altSpellings` (variantes ortográficas).

Útil cuando necesitas el script o variantes alternativas. Actualizado con menor frecuencia que el mediator (más estable, mejor cacheable: TTL 1 día).

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

## 8. WOL: homepage del idioma (texto diario de hoy)

```
GET https://wol.jw.org/{iso}/wol/h/{res}/{lp}
```

La página del día contiene el texto diario en `<div class="todayItem">` (o `.dailyText`, varía). Parseado por `parsers.daily_text`.

## 8b. WOL: texto diario por fecha específica (Fase 10)

```
GET https://wol.jw.org/{iso}/wol/dt/{res}/{lp}/{YYYY}/{M}/{D}
```

Patrón date-based para textos diarios pasados (típicamente varios años hacia atrás). Mismo parser. Útil para reconstruir histórico o pre-fetchar la semana próxima.

Ejemplo: `https://wol.jw.org/es/wol/dt/r4/lp-s/2025/12/25`.

## 8c. WOL: publication landing / TOC (Fase 10)

```
GET https://wol.jw.org/{iso}/wol/publication/{res}/{lp}/{pub}[/{number}]
```

Página landing de cualquier publicación. Para Bibles (`pub="nwtsty"`), `number=book_num` abre la TOC del libro. Para revistas, `number=issue` (yyyymm). Para libros, `number=chapter`. Sin `number`, devuelve el índice general de la publicación.

Útil para descubrir la estructura jerárquica de una publicación antes de profundizar.

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

La tabla `Document` del SQLite tiene una columna `Content` cifrada (AES-128-CBC sobre zlib, `contentFormat="z-a"` en el manifest). **Desde Fase 5.5 se decrypta** usando la derivación descubierta por [`gokusander/jwpub-toolkit`](https://github.com/gokusander/jwpub-toolkit) (MIT):

```
pub_string = f"{meps_language_index}_{symbol}_{year}"   (+ "_{issue}" si non-zero)
material   = SHA256(pub_string) XOR _XOR_KEY            (constante 32-byte fija)
key = material[:16]    # AES-128 key
iv  = material[16:32]  # CBC IV
plaintext = zlib_inflate(AES-128-CBC-decrypt(content_blob, key, iv))
```

Implementación en `jw_core.parsers.jwpub._compute_key_iv`. Tests en `test_jwpub_metadata.py` con vectores conocidos (Trinity brochure).

API pública:
- `parse_jwpub_metadata(path)` — barato, sin decrypt.
- `parse_jwpub(path)` — decrypt + `text` + `paragraphs` por documento.
- `ingest_jwpub(store, path)` — pipeline completo a RAG.

EPUB sigue siendo válido como alternativa (estándar abierto, mismo material moderno, sin necesidad de la clave derivada).

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

Desde **Fase 9** existe `jw_core.throttle.Throttler` con token bucket per-host:

- Default: 2 req/s, burst 5.
- En `factory.build_clients()` el CDN se baja a 1 req/s, burst 3 (es el más chatty).
- El throttler es **opt-in**: los clientes funcionan sin él. Para activar, pasa `throttler=` en el constructor o usa `build_clients()`.

`jw_core.throttle.backoff_delay(attempt)` ofrece backoff exponencial con full jitter (estilo AWS) para retry loops. Ver [`docs/guias/infraestructura-fase9.md`](../guias/infraestructura-fase9.md).
