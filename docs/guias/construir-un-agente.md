# Guía: construir un agente

> Cómo escribir un nuevo agente procedural sobre `jw-core` siguiendo las convenciones de `jw-agents`.

## Filosofía recordatoria

Los agentes en `jw-agents` **no invocan LLMs**. Son orquestadores procedurales que componen parsers + clientes + RAG en pipelines deterministas y producen `AgentResult` estructurado. El LLM llamante (Claude Desktop, etc.) lee `findings` y sintetiza la respuesta usando los `excerpt` como evidencia y `citation.url` como cita verificable.

Ventajas:
- Tests rápidos sin mockear LLMs.
- Reproducibles.
- Cero coste de tokens.
- Componibles desde tu propia lógica LLM.

## Plantilla de un nuevo agente

Crea `packages/jw-agents/src/jw_agents/mi_agente.py`:

```python
"""mi_agente — descripción de una línea.

Entrada: ...
Pasos:
  1. ...
  2. ...
Salida: AgentResult con N findings ordenados por X.
"""

from __future__ import annotations

from jw_core.clients.wol import WOLClient
from jw_core.parsers.article import parse_article
from jw_core.parsers.reference import parse_reference

from jw_agents.base import AgentResult, Citation, Finding


async def mi_agente(
    entrada: str,
    *,
    language: str = "en",
    wol: WOLClient | None = None,
    # ... otros parámetros con defaults razonables
) -> AgentResult:
    """Docstring imperativo: '<verbo>' + qué hace."""
    result = AgentResult(query=entrada, agent_name="mi_agente")
    result.metadata["language"] = language

    # Paso 1: parsear / preparar
    ref = parse_reference(entrada)
    if ref is None:
        result.warnings.append(f"No se detectó cita bíblica en {entrada!r}")
        return result

    # Paso 2: fetch HTTP (con gestión de "propiedad" del cliente)
    owned = wol is None
    if wol is None:
        wol = WOLClient()
    try:
        url, html = await wol.get_bible_chapter(
            ref.book_num, ref.chapter, language=language
        )
    finally:
        if owned:
            await wol.aclose()

    # Paso 3: parsear el HTML
    article = parse_article(html)
    result.metadata["chapter_title"] = article.title

    # Paso 4: construir findings
    for i, paragraph in enumerate(article.paragraphs[:5]):
        result.findings.append(Finding(
            summary=f"Párrafo {i + 1}",
            excerpt=paragraph,
            citation=Citation(
                url=url,
                title=article.title,
                kind="chapter",
                metadata={"paragraph_index": i + 1},
            ),
            metadata={"source": "chapter_paragraph"},
        ))

    return result
```

## Reglas que TODOS los agentes siguen

### 1. Devolver `AgentResult` siempre

Incluso ante error. Usa `result.warnings.append(...)` y `return result`. **Nunca** levantes excepciones desde el agente — el llamante (MCP server, código de usuario) las atraparía y perdería el resto del trabajo.

```python
# MAL
if ref is None:
    raise ValueError("...")

# BIEN
if ref is None:
    result.warnings.append(f"No se detectó cita bíblica en {entrada!r}")
    return result
```

### 2. Cada `Finding` lleva una `Citation` verificable

```python
Finding(
    summary="...",         # texto corto para el LLM (no es la respuesta final)
    excerpt="...",         # evidencia verbatim (puede estar vacío para findings tipo "marker")
    citation=Citation(
        url="https://wol.jw.org/...",   # OBLIGATORIO
        title="...",
        kind="verse" | "article" | "study_note" | "cross_ref" | "topic_subject" | "topic_subheading",
        metadata={...},
    ),
    metadata={"source": "...", ...},   # OBLIGATORIO si quieres que el LLM rankee por autoridad
)
```

### 3. Usar `metadata["source"]` para ranking por autoridad

El agente `apologetics` estableció la convención:

```
topic_index             > Mayor autoridad
topic_index_entry       > Subtítulos del índice temático
question_refs           > Citas explícitas en la pregunta
verse_text              > Texto del versículo enriquecido
study_note              > Notas de estudio nwtsty
cdn_search              > Resultados de búsqueda CDN
rag                     > Corpus local RAG
```

Tu agente puede definir nuevos valores, pero documéntalos para que el LLM (o tu prompt) pueda priorizarlos.

### 4. Aceptar clientes inyectados, gestionar "propiedad"

```python
owned = wol is None
if wol is None:
    wol = WOLClient()
try:
    # ... usar wol ...
finally:
    if owned:
        await wol.aclose()
```

Si el llamante (típicamente el MCP server) pasa un cliente compartido, no lo cierres. Si tú lo creaste, ciérralo.

### 5. Usar dataclasses, no dicts

Toda la API entre agentes y consumidores es vía las dataclasses `AgentResult`, `Finding`, `Citation`. El método `result.to_dict()` produce el shape JSON-ready para serializar.

## Patrones avanzados

### Combinar múltiples fuentes (estilo `apologetics`)

```python
# Paso 0: Índice temático (autoridad máxima)
subjects = await topic.search_subjects(query, language=language, limit=1)
for s in subjects:
    if s["docid"]:
        subject = await topic.get_subject_page(s["docid"], language=iso)
        result.findings.append(Finding(
            summary=f"Topic index: {subject.title}",
            excerpt=f"{subject.total_citations} citas en {len(subject.subheadings)} subtítulos",
            citation=Citation(url=subject.source_url, kind="topic_subject"),
            metadata={"source": "topic_index"},
        ))

# Paso 1: Bible refs explícitas
for ref in parse_all_references(query):
    # ... ver apologetics.py ...

# Paso 2: Búsqueda CDN
data = await cdn.search(query, ...)
for item in items:
    # ... ver apologetics.py ...

# Paso 3: RAG opcional
if rag_store and not rag_store.is_empty:
    hits = rag_store.hybrid_search(query, top_k=rag_top_k)
    # ... ver apologetics.py ...
```

### Propagación de errores no fatales

Si un sub-paso falla, regístralo en `warnings` y continúa:

```python
try:
    html = await wol.fetch(url)
except Exception as e:
    result.warnings.append(f"Fetch falló para {url}: {e}")
    continue   # sigue con el siguiente item
```

### Limitar el coste de fetch

```python
async def mi_agente(
    query: str,
    *,
    top_n: int = 5,           # cuántos resultados de búsqueda considerar
    fetch_top_k: int = 3,     # cuántos efectivamente descargar
    max_excerpts: int = 3,    # cuántos extractos por artículo
    ...
):
    items = items[:top_n]
    fetched = 0
    for item in items:
        if fetched >= fetch_top_k:
            break
        # ... fetch ...
        for p in article.paragraphs[:max_excerpts]:
            # ...
        fetched += 1
```

## Exponerlo como herramienta MCP

En `packages/jw-mcp/src/jw_mcp/server.py`:

```python
from jw_agents import mi_agente as mi_agente_fn

@mcp.tool
async def mi_agente(
    entrada: str,
    language: str = "en",
) -> dict[str, Any]:
    """Una sola línea descriptiva. Args y Returns documentados.

    Args:
        entrada: ...
        language: ISO code (en/es/pt).
    """
    result = await mi_agente_fn(
        entrada, language=language,
        wol=_get_wol(),
    )
    return result.to_dict()
```

Y en `packages/jw-agents/src/jw_agents/__init__.py`:

```python
from jw_agents.mi_agente import mi_agente

__all__ = [
    ...,
    "mi_agente",
]
```

## Tests

En `packages/jw-agents/tests/test_mi_agente.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock

from jw_agents.mi_agente import mi_agente


@pytest.mark.asyncio
async def test_basic():
    wol = MagicMock()
    wol.get_bible_chapter = AsyncMock(
        return_value=("https://...", "<html>...</html>")
    )

    result = await mi_agente("Juan 3:16", language="es", wol=wol)

    assert result.query == "Juan 3:16"
    assert result.agent_name == "mi_agente"
    assert len(result.findings) > 0
    assert all(f.citation.url.startswith("http") for f in result.findings)
```

Para tests con HTML real, usa fixtures en `packages/jw-core/tests/fixtures/` (los hay para John 3 nwtsty, Trinity subject, etc.).

## Anti-patrones

### No incluyas LLMs

Si tu agente quiere invocar un LLM, en realidad lo que quieres es **devolver datos estructurados** y dejar que el cliente Claude haga la llamada. Si necesitas embeddings, usa el `Embedder` protocol vía `VectorStore`.

### No hagas el agente síncrono

Todos los agentes son `async def`. Permite que el MCP server los ejecute en su loop sin bloquear.

### No olvides `metadata["source"]` y `citation.url`

Sin `source`, el LLM no puede rankear por autoridad. Sin `citation.url`, no puede citar la fuente — y todo el toolkit existe para producir citas verificables.

## Ver también

- [`docs/referencia/jw-agents.md`](../referencia/jw-agents.md) — referencia exhaustiva de cada agente existente
- [`docs/conceptos/flujos-end-to-end.md`](../conceptos/flujos-end-to-end.md) — diagramas de `verse_explainer` y `apologetics`
