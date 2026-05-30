# Guía: usar los clientes HTTP

> Patrones para usar `CDNClient`, `WOLClient`, `MediatorClient`, `PubMediaClient` y `TopicIndexClient` desde tu propio código.

## Patrón general

Todos los clientes son **async**. Todos aceptan opcionalmente un `httpx.AsyncClient` compartido. Todos exponen `aclose()` para limpieza.

```python
import asyncio
from jw_core.clients.cdn import CDNClient

async def main():
    cdn = CDNClient()
    try:
        data = await cdn.search("amor", language="S", limit=5)
        print(data)
    finally:
        await cdn.aclose()

asyncio.run(main())
```

## Cliente CDN (`b.jw-cdn.org`)

### Búsqueda

```python
from jw_core.clients.cdn import CDNClient, CDNError

cdn = CDNClient()
try:
    data = await cdn.search(
        "amor",
        filter_type="all",          # all | publications | videos | audio | bible | indexes
        language="S",               # código JW (E/S/T)
        limit=10,
    )
except CDNError as e:
    print(f"Búsqueda falló: {e}")
finally:
    await cdn.aclose()
```

Estructura típica de respuesta:

```python
{
    "results": [
        {"type": "group", "title": "Publications", "results": [
            {"title": "...", "snippet": "...",
             "links": {"wol": "https://wol.jw.org/..."}}
        ]},
        ...
    ]
}
```

Para aplanar grupos vs items:

```python
def flatten(data):
    out = []
    for r in data.get("results", []):
        if r.get("type") == "group":
            out.extend(r.get("results", []))
        else:
            out.append(r)
    return out
```

### Refresco automático del token JWT

El cliente cachea el token en `self._token` y lo refresca al recibir 401:

```python
# Primer search: pide token, lo cachea, hace request
await cdn.search("paz")

# Segundo search en la misma sesión: reusa el token cacheado
await cdn.search("amor")

# Si el token expira a medio camino → recibe 401 → refresca + reintenta una vez
```

## Cliente WOL (`wol.jw.org`)

### Capítulo bíblico

```python
from jw_core.clients.wol import WOLClient
from jw_core.parsers.article import parse_article

wol = WOLClient()
try:
    url, html = await wol.get_bible_chapter(
        book_num=43, chapter=3, language="es"
    )
    article = parse_article(html)
    print(article.title)
    print(article.paragraphs[0])
finally:
    await wol.aclose()
```

`publication` por defecto es `Language.default_bible` (`nwtsty` para inglés, `nwt` para español/portugués). Para forzar una edición:

```python
url, html = await wol.get_bible_chapter(43, 3, language="en", publication="nwt")
```

### Página del día (texto diario)

```python
from jw_core.parsers.daily_text import parse_daily_text

url, html = await wol.get_today_homepage(language="es")
daily = parse_daily_text(html)
if daily:
    print(daily.date)
    print(daily.scripture)
    print(daily.commentary)
```

### Fetch arbitrario

```python
html = await wol.fetch("https://wol.jw.org/es/wol/d/r4/lp-s/2024365")
# o con path relativo (se prepende https://wol.jw.org)
html = await wol.fetch("/es/wol/d/r4/lp-s/2024365")
```

### Panel de referencias cruzadas

```python
from jw_core.parsers.study_notes import parse_cross_references

url, html = await wol.get_bible_chapter(43, 3, language="en")
xrefs = parse_cross_references(html, book_num=43, chapter=3)
# Cada xref es un CrossReference con href apuntando al panel

for xref in xrefs:
    panel_url, panel_html = await wol.get_cross_reference_panel(xref.href)
    # parsear panel_html según necesites (ya no hay parser estándar aquí)
```

## Cliente Mediator (`data.jw-api.org/mediator`)

### Lista de idiomas

```python
from jw_core.clients.mediator import MediatorClient

med = MediatorClient()
try:
    langs = await med.list_languages(in_language="E")
    for lang in langs:
        print(f"{lang.code} ({lang.locale}): {lang.name} — {lang.vernacular}")
        if lang.is_sign_language:
            print("  [Lengua de señas]")
finally:
    await med.aclose()
```

### Resolver un código de contenido

```python
data = await med.find_item("pub-edj_x_VIDEO", language="E")
# Devuelve JSON crudo con URLs deliverable (video, audio, etc.)
```

## Cliente PubMedia (`GETPUBMEDIALINKS`)

### Inventariar archivos descargables

```python
from jw_core.clients.pub_media import PubMediaClient, PubMediaError

pub = PubMediaClient()
try:
    publication = await pub.get_publication(
        "bh",                       # pub code (Bible Teach)
        language="E",
        file_format="EPUB",         # opcional: filtra a un formato
    )
    print(publication.pub_name)
    for f in publication.files:
        print(f"  {f.filename} ({f.size_bytes} bytes) — {f.url}")
except PubMediaError as e:
    print(f"Error: {e}")
finally:
    await pub.aclose()
```

Otros parámetros útiles:

- `bible_book=43` — para libros bíblicos (0 = toda la Biblia, 1-66 = libro específico).
- `issue=202401` — para revistas, formato yyyymm.
- `all_languages=True` — devuelve todas las variantes de idioma.

### Descargar a disco con streaming

```python
from pathlib import Path

publication = await pub.get_publication("bh", language="E", file_format="EPUB")
for f in publication.files:
    dest = Path("./descargas") / f.filename
    saved_path = await pub.download(f, dest)
    print(f"Guardado: {saved_path}")
```

`download` hace streaming con chunks de 64KB, así que es seguro para archivos grandes (Biblia entera en EPUB ≈ 25MB).

## Cliente TopicIndex (Índice de Publicaciones Watch Tower)

### Buscar temas

```python
from jw_core.clients.topic_index import TopicIndexClient, TopicIndexError

topic = TopicIndexClient()
try:
    results = await topic.search_subjects(
        "Trinity",                  # query
        language="E",               # código JW
        limit=10,
        rerank_by_title_match=True, # default True
    )
    for r in results:
        print(f"[{r['score']:.0f}] {r['title']} — docid={r['docid']}")
        print(f"        {r['snippet']}")
except TopicIndexError as e:
    print(f"Error: {e}")
finally:
    await topic.aclose()
```

`rerank_by_title_match` ordena los resultados por proximidad título → query (100 match exacto, 80 startswith-word, 60 whole-word, 40 substring, 20 token, 0 nada).

### Fetchar una página de tema

```python
subject = await topic.get_subject_page("1200275936", language="en")
print(f"{subject.title} — {subject.total_citations} citas en {len(subject.subheadings)} subtítulos")
print(f"Style: {subject.style}")  # "trinity" o "article_title"
print(f"See also: {subject.see_also}")

for sh in subject.subheadings[:5]:
    indent = "" if sh.is_top_level else "  "
    print(f"{indent}{sh.heading} ({len(sh.citations)} citas)")
    for cite in sh.citations[:3]:
        print(f"{indent}  • [{cite.kind}] {cite.text}")
        if cite.url:
            print(f"{indent}    → {cite.url}")
```

### Reutilizar conexiones con TopicIndex

`TopicIndexClient` internamente crea un `CDNClient` + un `WOLClient`. Si ya tienes esos, pásaselos para no duplicar el pool:

```python
import httpx

shared_http = httpx.AsyncClient()
cdn = CDNClient(http=shared_http)
wol = WOLClient(http=shared_http)
topic = TopicIndexClient(cdn=cdn, wol=wol)

# ... usar topic ...

# Cerrar TODO:
await topic.aclose()   # no cierra cdn ni wol (no los posee)
await cdn.aclose()      # no cierra shared_http
await wol.aclose()      # no cierra shared_http
await shared_http.aclose()
```

## Compartir httpx entre clientes

Patrón limpio para apps que usan múltiples clientes:

```python
import httpx
from contextlib import asynccontextmanager

@asynccontextmanager
async def jw_clients():
    """Cliente compartido + todos los wrappers, gestionados como context manager."""
    http = httpx.AsyncClient(timeout=30.0, follow_redirects=True)
    cdn = CDNClient(http=http)
    wol = WOLClient(http=http)
    pub = PubMediaClient(http=http)
    med = MediatorClient(http=http)
    topic = TopicIndexClient(cdn=cdn, wol=wol)
    try:
        yield {"cdn": cdn, "wol": wol, "pub": pub, "med": med, "topic": topic}
    finally:
        await cdn.aclose()
        await wol.aclose()
        await pub.aclose()
        await med.aclose()
        await topic.aclose()
        await http.aclose()


async def main():
    async with jw_clients() as c:
        data = await c["cdn"].search("amor")
        url, html = await c["wol"].get_bible_chapter(43, 3, language="es")
        # ...
```

## Manejo de errores

Cada cliente tiene su propia excepción base:

| Cliente | Excepción |
|---|---|
| `CDNClient` | `CDNError` |
| `WOLClient` | `WOLError` |
| `MediatorClient` | `MediatorError` |
| `PubMediaClient` | `PubMediaError` |
| `TopicIndexClient` | `TopicIndexError` |

Todas heredan de `RuntimeError`. Atrápalas selectivamente:

```python
try:
    publication = await pub.get_publication("nonexistent", language="E")
except PubMediaError as e:
    # Probablemente 404
    print(f"Publicación no encontrada: {e}")
except Exception as e:
    # Cualquier otra cosa
    print(f"Error inesperado: {e}")
```

Las herramientas MCP atrapan estas excepciones internamente y devuelven `{"error": "..."}` en lugar de propagarlas.

## Ver también

- [`docs/conceptos/inventario-endpoints.md`](../conceptos/inventario-endpoints.md) — cada endpoint con curl
- [`docs/referencia/jw-core.md`](../referencia/jw-core.md) — referencia exhaustiva de cada cliente
