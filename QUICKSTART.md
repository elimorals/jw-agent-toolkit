# Inicio rápido

## Instalación

```bash
cd jw-agent-toolkit
uv sync --all-packages

# Aviso para macOS: la carpeta ~/Documents sincronizada con iCloud
# a veces asigna el flag UF_HIDDEN a los archivos que uv crea en .venv/.
# Python 3.13+ ignora los archivos .pth ocultos, lo que rompe silenciosamente
# los imports editables de jw-core / jw-mcp. Ejecuta esto una vez después
# de cada `uv sync` hasta que uv lance una corrección:
chflags nohidden .venv/lib/python3.13/site-packages/*.pth 2>/dev/null || true
```

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

Tras reiniciar Claude Desktop verás disponibles 24 herramientas:

Núcleo (Fase 1): `resolve_reference`, `get_chapter`, `get_daily_text`, `search_content`, `get_article`.
Media (Fase 2): `list_languages`, `list_publication_files`, `download_publication`.
Notas (Fase 3): `get_verse`, `get_study_notes`, `get_cross_references`, `compare_translations`.
Temas (Fase 4): `search_topic_index`, `get_topic_articles`.
EPUB/JWPUB (Fase 5): `extract_epub_text`, `inspect_jwpub_metadata`, `ingest_epub`.
RAG (Fase 6): `semantic_search`, `ingest_bible_chapter`, `ingest_search_topk`.
Agentes (Fase 7): `research_topic`, `verse_explainer`, `meeting_helper`, `apologetics`.

## Ejecutar las pruebas

```bash
uv run pytest packages/ -v
```

Esperado: 44 passing (núcleo de Fase 1) + las pruebas adicionales de las
fases 2-7 (citas, notas de estudio, índice temático, RAG y agentes).

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
