# Inicio rápido

## Instalación

```bash
cd jw-agent-toolkit
uv sync --all-packages
```

> **macOS bajo `~/Documents` o `~/Desktop`:** macOS marca automáticamente `.venv/` como `UF_HIDDEN`, lo que rompe los imports editables con `ModuleNotFoundError` silencioso aunque `uv pip show` diga que el paquete está instalado. Antes del primer `uv sync`, ejecuta:
>
> ```bash
> uv venv venv --python 3.13
> ln -s venv .venv
> uv sync --all-packages
> ```
>
> Explicación completa, causa raíz y verificación en [`docs/guias/setup-macos.md`](docs/guias/setup-macos.md).

## Probar el parser

```python
from jw_core import parse_reference

ref = parse_reference("Juan 3:16")
print(ref.display())              # "John 3:16"
print(ref.wol_url(lang="es"))     # https://wol.jw.org/es/wol/b/r4/lp-s/nwt/43/3#study=discover&v=43:3:16
```

## Ejecutar el servidor MCP

```bash
uv run jw-mcp
```

El servidor habla MCP sobre stdio. Conéctalo a Claude Desktop:

**macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`

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

Tras reiniciar Claude Desktop verás disponibles **29 herramientas**:

Núcleo (Fase 1): `resolve_reference`, `get_chapter`, `get_daily_text` (acepta `date` opcional), `search_content`, `get_article`.
Media (Fase 2): `list_languages`, `list_publication_files`, `download_publication`, `get_publication_toc`, `list_weblang_languages`.
Notas (Fase 3): `get_verse`, `get_study_notes`, `get_cross_references`, `compare_translations`.
Temas (Fase 4): `search_topic_index`, `get_topic_articles`.
EPUB (Fase 5): `extract_epub_text`, `ingest_epub`.
JWPUB (Fase 5 / 5.5): `inspect_jwpub_metadata`, `extract_jwpub_text`, `ingest_jwpub`.
RAG (Fase 6): `semantic_search`, `ingest_bible_chapter`, `ingest_search_topk`.
Agentes (Fase 7): `research_topic`, `verse_explainer`, `meeting_helper`, `apologetics`.
Infraestructura (Fase 9): `get_cache_stats`.

Variables de entorno opcionales en `claude_desktop_config.json` (sección `env`):

- `JW_RAG_STORE_PATH` — path del store RAG (default `~/.jw-agent-toolkit/rag`).
- `JW_CACHE_PATH` — path del DiskCache SQLite (default `~/.jw-agent-toolkit/cache.db`).
- `JW_TELEMETRY_ENABLED=1` — activa el detector de drift de la API.
- `JW_TELEMETRY_PATH` — path del JSON de telemetría (default `~/.jw-agent-toolkit/telemetry.json`).

## Ejecutar las pruebas

```bash
uv run pytest packages/ -v
```

Esperado: **166 passing + 4 skipped**. Los skipped son tests cassette-backed que necesitan `--record-mode=rewrite` la primera vez (corren sin red en las siguientes pasadas).

Para re-grabar los cassettes contra la API actual de jw.org:

```bash
uv run pytest packages/jw-core/tests/test_cassettes.py --record-mode=rewrite
```

## Probar las herramientas desde Python

```python
import asyncio
from jw_core.clients.cdn import CDNClient
from jw_core.clients.wol import WOLClient

async def main():
    cdn = CDNClient()
    data = await cdn.search("amor", filter_type="bible", language="S", limit=3)
    print(data)
    await cdn.aclose()

    wol = WOLClient()
    url, html = await wol.get_bible_chapter(43, 3, language="es")
    print(url, "->", len(html), "bytes")
    await wol.aclose()

asyncio.run(main())
```

## Próximos pasos

- Lee [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) para entender la arquitectura por capas.
- Explora [docs/guias/](docs/guias/) si vas a construir agentes, extender el parser o indexar con RAG.
- Mira [docs/referencia/](docs/referencia/) para la documentación exhaustiva de la API pública de cada paquete.
