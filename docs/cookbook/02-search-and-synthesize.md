# Buscar un tema y sintetizar resultados

> **Tiempo estimado**: 5 minutos
> **Requisitos**: jw-core. Para LLM real, configurar provider (ver `docs/guias/`).
> **Slug URL**: `/cookbook/02-search-and-synthesize`

## ¿Qué construyes?

Buscar un tema en jw.org (vía `CDNClient`) y devolver findings con citation. Aquí se usa un cliente fake para mantener el test offline; en producción se sustituye por `CDNClient()` real.

## Código (copy-pasteable)

```python
# test
import asyncio
import sys
from pathlib import Path

# Add cookbook fakes to path (CI helper).
sys.path.insert(0, str(Path(__file__).parent / "_common"))
from fakes import FakeCDNClient

cdn = FakeCDNClient(canned=[
    {"title": "Trinity?", "url": "https://wol.jw.org/...", "snippet": "..."}
])

async def search_topic(query: str):
    response = await cdn.search(query, limit=3)
    findings = []
    for result in response["results"]:
        findings.append({
            "text": result["snippet"],
            "citation": {"url": result["url"], "title": result["title"]},
        })
    return findings

results = asyncio.run(search_topic("¿Existe la Trinidad?"))
assert len(results) == 1
assert "wol.jw.org" in results[0]["citation"]["url"]
```

## Por qué funciona

El patrón "search → mapear a Finding con citation" es la columna vertebral de los agentes en `jw-agents`. Hacerlo offline-first con un fake es lo que permite que CI sea verde sin red. Para producción, sustituyes `FakeCDNClient` por `from jw_core.clients.cdn import CDNClient`.

## Variaciones

- Combinar con `parse_reference` (receta 01) para detectar versículos dentro de los snippets.
- Pasar `filter_type="article"` para limitar a artículos.
- Cachear resultados con `jw-core` cache helpers.

## Próximo paso

→ [03 — Telegram bot](03-telegram-bot.md)
