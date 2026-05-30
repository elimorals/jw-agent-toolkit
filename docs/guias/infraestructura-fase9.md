# Guía: infraestructura Fase 9 (cache, throttle, telemetría, factory)

> Cómo activar el cache en disco, el rate-limiting por host, la detección de drift de la API y el ensamblado completo de clientes para producción.

## Por qué

En desarrollo casual, cada `WOLClient()` o `CDNClient()` se basta solo: golpea la API, devuelve resultados, cierra el socket. En producción quieres:

- **No reventar la API de jw.org** con ráfagas (rate limiting per-host).
- **No re-pagar la misma respuesta** repetidamente (cache TTL).
- **Saber cuándo jw.org cambia** la forma de sus respuestas (telemetría de drift).
- **Compartir conexiones HTTP** entre todos los clientes (factory).

La Fase 9 añade estos cuatro mecanismos como **piezas opcionales**: los clientes funcionan exactamente igual sin ellos. Cuando los pasas en el constructor, se activan transparentemente.

## La forma rápida: `build_clients()`

Para arrancar con todo cableado:

```python
from jw_core.clients.factory import build_clients

clients = build_clients(
    cache_path="~/.jw-agent-toolkit/cache.db",   # default
    enable_throttling=True,                       # default
    enable_cache=True,                            # default
    enable_telemetry=None,                        # None = lee JW_TELEMETRY_ENABLED
)

# Los seis clientes comparten throttler + cache + telemetry:
data = await clients.cdn.search("amor", language="S")
url, html = await clients.wol.get_bible_chapter(43, 3, language="es")
pub = await clients.pub_media.get_publication("bh", language="E", file_format="EPUB")
langs = await clients.weblang.list_languages(in_language_iso="es")
subjects = await clients.topic_index.search_subjects("Trinity")
medlangs = await clients.mediator.list_languages(in_language="E")

# Cierra todo en orden:
await clients.aclose()
```

`ClientSuite` (dataclass devuelto por `build_clients`) tiene los campos:
`cdn`, `wol`, `mediator`, `pub_media`, `topic_index`, `weblang`, `throttler`, `cache`.

## Pieza por pieza

### `DiskCache` — cache en disco con TTL

SQLite + WAL + lazy eviction. Bytes adentro / bytes afuera; el caller serializa.

```python
from jw_core.cache import DiskCache

with DiskCache("~/.jw-agent-toolkit/cache.db", default_ttl_seconds=3600) as cache:
    cache.set("clave", b"valor", ttl_seconds=600)     # 10 min específico
    val = cache.get("clave")                           # bytes | None
    cache.delete("clave")
    stats = cache.stats()                              # {"total": N, "live": N, "expired": N}
    cache.cleanup_expired()                            # rowcount eliminado
    cache.clear()                                      # purga total
```

**TTLs por endpoint (defaults internos)**:

| Endpoint | TTL |
|---|---|
| `mediator.list_languages` | 86400s (1 día) |
| `weblang.list_languages` | 86400s (1 día) |
| `pub_media.get_publication` | 86400s (1 día) |
| `cdn.search` | 900s (15 min) |
| `wol.fetch` | 3600s (1 hora) |

### `Throttler` + `TokenBucket` — rate limit per-host

Token bucket clásico con bloqueo asíncrono. Conservador para jw.org.

```python
from jw_core.throttle import Throttler, TokenBucket, backoff_delay

throttler = Throttler(default_rate=2.0, default_capacity=5.0)

# Sobreescribir un host específico (el factory limita CDN a 1 req/s):
throttler.set_limit("b.jw-cdn.org", rate_per_sec=1.0, capacity=3.0)

# Bloquea hasta tener token (uso típico — interno a politely_get):
await throttler.acquire("wol.jw.org", n=1.0)

# Para retry loops: backoff exponencial con full jitter (estilo AWS):
for attempt in range(5):
    try:
        return await op()
    except TransientError:
        await asyncio.sleep(backoff_delay(attempt, base=0.5, cap=30.0))
```

`TokenBucket` recibe `rate_per_sec` y `capacity`. Acquires `n` tokens; si no hay suficientes, calcula `wait = shortfall / rate` y duerme.

### `Telemetry` — detección de drift opt-in

```python
from jw_core.telemetry import Telemetry, get_telemetry

# Vía singleton (respeta variables de entorno):
tel = get_telemetry()      # enabled solo si JW_TELEMETRY_ENABLED=1

# O instanciar directamente para tests:
tel = Telemetry(path="/tmp/tel.json")

# Cada respuesta JSON pasa por record(endpoint_id, json_obj):
drift = tel.record("cdn.search", {"results": [...]})
# Primer call: aprende baseline, devuelve False
# Calls subsecuentes con misma SHAPE: devuelve False
# Call con shape distinto (nueva clave, tipo cambiado): devuelve True + warning

# Inspeccionar:
report = tel.report()
# {"enabled": True, "path": "...", "baselines": {...}, "drift_events": [...]}
```

Activar globalmente:

```bash
export JW_TELEMETRY_ENABLED=1
export JW_TELEMETRY_PATH=/tmp/jw-telemetry.json   # opcional
```

**Fingerprint**: `_shape_hash` calcula un hash de la **estructura** (claves de dicts, tipos de scalars, longitudes y muestra de los primeros 3 elementos de listas). Misma estructura → mismo hash, independientemente de los valores. Una nueva clave o tipo distinto cambia el hash.

### `JWTManager` — token JWT extraído

Antes vivía dentro de `CDNClient`. Ahora es reusable y async-safe (con `asyncio.Lock` para evitar dos refresh en paralelo).

```python
from jw_core.auth import JWTManager
import httpx

http = httpx.AsyncClient()
auth = JWTManager(http)

token = await auth.get_token()                     # cachea en memoria
headers = await auth.authorized_headers()          # {Authorization, Accept, Referer}
auth.invalidate()                                  # tras un 401
```

`CDNClient` lo crea internamente si no se pasa uno propio.

## Wirearlo en clientes individuales

Cada cliente acepta `throttler`, `cache`, `telemetry` opcionales:

```python
from jw_core.throttle import Throttler
from jw_core.cache import DiskCache
from jw_core.telemetry import Telemetry
from jw_core.clients.cdn import CDNClient
from jw_core.clients.wol import WOLClient

throttler = Throttler()
cache = DiskCache("/tmp/jw-cache.db")
tel = Telemetry()

cdn = CDNClient(throttler=throttler, cache=cache, telemetry=tel)
wol = WOLClient(throttler=throttler, cache=cache, telemetry=tel)
# ... etc
```

Verás métodos `cache_stats()` en cada cliente para inspeccionar el estado del cache compartido.

## `politely_get` — el wrapper interno

Todo GET de cualquier cliente pasa por `clients._polite.politely_get`. Hace:

1. **Cache check**: si hay `cache` y hay `cache_key` (compuesto por URL + sorted params), devuelve la respuesta sintética.
2. **Throttle**: si hay `throttler`, `await throttler.acquire(host)`.
3. **Request**: `http.get(url, params, headers)`.
4. **Cache set**: si status 200 y hay cache, guarda el body con TTL.
5. **Telemetry record**: si hay `telemetry` y `record_json_shape=True` y status 200 con content-type JSON, registra el fingerprint bajo `endpoint_id`.

Para usarlo directamente (raro — normalmente vía clientes):

```python
from jw_core.clients._polite import politely_get
import httpx

async with httpx.AsyncClient() as http:
    resp = await politely_get(
        http, "https://api.test/x",
        params={"q": "x"},
        throttler=throttler, cache=cache, telemetry=tel,
        endpoint_id="api.test.x", record_json_shape=True,
        cache_ttl_seconds=600,
    )
```

## Cuándo NO usar Fase 9

- **Scripts ad-hoc, exploración manual**: el overhead de configurar todo no se justifica para 10 requests.
- **Tests unitarios**: usa los clientes "desnudos" para no contaminar con estado persistente.
- **Sesiones MCP cortas**: el servidor por defecto NO arranca con cache wired (cada handler crea su cliente lazy sin infraestructura). Esto mantiene el arranque rápido. La herramienta `get_cache_stats` mira el cache **standalone** en `JW_CACHE_PATH` si existe.

## Ver también

- [`docs/conceptos/inventario-endpoints.md`](../conceptos/inventario-endpoints.md) — TTLs y endpoints
- [`docs/referencia/jw-core.md`](../referencia/jw-core.md) — referencia exhaustiva de cada clase
- [`docs/conceptos/decisiones-de-diseno.md`](../conceptos/decisiones-de-diseno.md) — por qué opt-in, por qué token bucket per-host
