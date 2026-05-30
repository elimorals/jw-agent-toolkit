# Guía: conectar el MCP a Claude Desktop

> Paso a paso para que Claude Desktop hable con `jw-mcp` y troubleshooting de los errores más comunes.

## Pre-requisitos

- macOS, Linux o Windows con Claude Desktop instalado.
- `uv` instalado y en el PATH. (Verifica con `which uv`.)
- El monorepo clonado y `uv sync --all-packages` ejecutado.

## Paso 1: localizar `claude_desktop_config.json`

| OS | Ruta |
|---|---|
| macOS | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| Windows | `%APPDATA%\Claude\claude_desktop_config.json` |
| Linux | `~/.config/Claude/claude_desktop_config.json` |

Si el archivo no existe, créalo con `{}`:

```bash
mkdir -p ~/Library/Application\ Support/Claude
echo '{}' > ~/Library/Application\ Support/Claude/claude_desktop_config.json
```

## Paso 2: añadir el servidor

Edita el archivo para que contenga:

```json
{
  "mcpServers": {
    "jw": {
      "command": "uv",
      "args": [
        "--directory",
        "/Users/elias/Documents/Trabajo/jw-agent-toolkit",
        "run",
        "jw-mcp"
      ]
    }
  }
}
```

Sustituye `/Users/elias/Documents/Trabajo/jw-agent-toolkit` por la **ruta absoluta** de tu clon.

Si ya tenías otros servidores configurados, añade `"jw": {...}` dentro de `mcpServers` sin borrar lo demás.

## Paso 3: variables de entorno opcionales

Para apuntar el store RAG, el cache en disco y la telemetría a rutas personalizadas:

```json
{
  "mcpServers": {
    "jw": {
      "command": "uv",
      "args": ["--directory", "/path/to/jw-agent-toolkit", "run", "jw-mcp"],
      "env": {
        "JW_RAG_STORE_PATH": "/Users/elias/jw-rag-store",
        "JW_CACHE_PATH": "/Users/elias/.cache/jw/cache.db",
        "JW_TELEMETRY_ENABLED": "1",
        "JW_TELEMETRY_PATH": "/Users/elias/.cache/jw/telemetry.json"
      }
    }
  }
}
```

| Variable | Default | Para qué |
|---|---|---|
| `JW_RAG_STORE_PATH` | `~/.jw-agent-toolkit/rag/` | Path del store RAG (donde se persisten chunks + vectors) |
| `JW_CACHE_PATH` | `~/.jw-agent-toolkit/cache.db` | Path del DiskCache SQLite leído por `get_cache_stats` |
| `JW_TELEMETRY_ENABLED` | (no set) | `1`/`true`/`yes` activa el detector de drift de la API |
| `JW_TELEMETRY_PATH` | `~/.jw-agent-toolkit/telemetry.json` | Path del JSON con baselines + eventos de drift |

> **Importante**: el servidor MCP por defecto **no arranca con cache wired** (cada handler crea su cliente lazy sin throttler/cache/telemetry). Esto mantiene el arranque rápido. `get_cache_stats` solo refleja un cache standalone que otro proceso pudo dejar en `JW_CACHE_PATH` (típicamente vía `factory.build_clients()` en scripts propios). Si quieres caching dentro del MCP, edita `_get_wol()`/`_get_cdn()`/etc. en `packages/jw-mcp/src/jw_mcp/server.py` para inyectar los deps.

## Paso 4: reiniciar Claude Desktop

Cierra completamente la app (⌘Q en macOS) y vuelve a abrirla. Si solo cierras la ventana, Claude no relee la config.

## Paso 5: verificar conexión

En cualquier conversación, Claude debería tener acceso a las herramientas del servidor `jw`. Para confirmar:

> "¿Qué herramientas MCP tienes disponibles?"

Deberías ver las 24 herramientas (`resolve_reference`, `get_chapter`, `get_daily_text`, ...).

O directamente prueba:

> "Resuelve la cita Juan 3:16 en español"

## Troubleshooting

### "Server jw failed to start" / no aparecen las herramientas

**Causa más común**: `uv` no está en el PATH que ve Claude Desktop. Claude no hereda tu PATH de shell; usa un PATH mínimo.

**Fix**: usar la ruta absoluta a `uv`:

```bash
which uv
# /Users/elias/.local/bin/uv   ← ejemplo
```

```json
{
  "mcpServers": {
    "jw": {
      "command": "/Users/elias/.local/bin/uv",
      "args": ["--directory", "/path/to/jw-agent-toolkit", "run", "jw-mcp"]
    }
  }
}
```

### "ModuleNotFoundError: No module named 'jw_core'" en los logs del MCP

**Causa típica en macOS bajo `~/Documents`**: macOS marca `.venv/` con el flag `UF_HIDDEN` automáticamente cuando vive bajo una carpeta indexada por Spotlight, y CPython 3.8+ filtra los `.pth` ocultos. El resultado es que los imports editables de `jw-core`/`jw-mcp` fallan en silencio.

**Fix permanente**: usa `venv/` físico con symlink `.venv → venv`. Receta y causa raíz en [`docs/guias/setup-macos.md`](setup-macos.md).

### "Address already in use" o "Server connection lost"

El MCP no usa puertos — habla por stdio. Si ves errores de conexión, suele ser por:

- El proceso anterior de Claude Desktop no terminó limpiamente. **Fix**: matar procesos `uv` colgados (`pkill -f jw-mcp`) y reabrir Claude.
- Multiple instancias de Claude Desktop. **Fix**: solo una.

### "RAG store load failed" en logs

El store RAG arranca empty si no encuentra `meta.json` en la ruta configurada. No es un error fatal — la primera vez es normal. Si quieres confirmarlo:

```bash
ls -la ~/.jw-agent-toolkit/rag/
# Si no existe, lo crea en el primer ingest_*
```

### "JWPUB Content is encrypted" — sí, está documentado

`inspect_jwpub_metadata` siempre devuelve `decrypted_text_available: false`. Es esperado: el contenido cifrado AES del JWPUB no es decodificable sin la derivación de clave (no pública). Para texto offline usa EPUB con `extract_epub_text` o `ingest_epub`.

### El servidor arranca pero las llamadas a herramientas dan 401/403

Para las herramientas que hablan con la CDN de búsqueda:

- 401: token JWT expirado. El cliente refresca y reintenta una vez — si vuelve 401, hay algo raro con el endpoint del token. Verifica `curl -sI https://b.jw-cdn.org/tokens/jworg.jwt`.
- 403: headers incorrectos. El cliente envía `Authorization`, `Accept` y `Referer` — si modificaste el código y rompiste uno, devolvería 403.

### Las URLs de wol.jw.org dan 404 en español/portugués

Verifica que `Language.wol_resource` y `Language.default_bible` están al día. Si JW reorganizó el bundle de recursos (raro), el `r4` (es) puede haberse vuelto `r5`. Actualiza `_REGISTRY` en `jw_core/languages.py`.

## Logs

El MCP server hace logging al stderr:

```python
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
```

Claude Desktop captura stderr y lo muestra en su panel de MCP servers. Para ver más detalle, cambia `level=logging.INFO` por `level=logging.DEBUG` en `packages/jw-mcp/src/jw_mcp/server.py`.

## Ejecutar fuera de Claude Desktop

Para probar el servidor manualmente:

```bash
cd /path/to/jw-agent-toolkit
uv run jw-mcp
```

El proceso se queda esperando en stdio. Para hablarle, necesitas un cliente MCP. Las opciones más simples:

- **Claude Code CLI** — si lo tienes instalado, lee la misma config.
- **`mcp-cli`** ([github](https://github.com/modelcontextprotocol/inspector)) — herramienta oficial de debugging.

## Comandos útiles después de cambios

Si modificas el código del MCP server, Claude Desktop tiene que reiniciarlo:

1. Cierra completamente Claude Desktop (⌘Q).
2. Vuelve a abrirlo.

No hay hot reload — el server se respawnea al inicio de cada sesión de Claude.

## Ver también

- [`docs/referencia/jw-mcp.md`](../referencia/jw-mcp.md) — contratos completos de cada herramienta MCP
- [`packages/jw-mcp/README.md`](../../packages/jw-mcp/README.md) — vista general del paquete
