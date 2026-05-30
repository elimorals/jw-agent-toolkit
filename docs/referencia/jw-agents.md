# Referencia: jw-agents

> Documentación exhaustiva de los agentes procedurales: contrato base + pipeline detallado de cada uno.

## Estructura del paquete

```
jw_agents/
├── __init__.py             # Re-exporta AgentResult, Citation, Finding + los 4 agentes
├── base.py                 # Dataclasses: AgentResult, Finding, Citation
├── verse_explainer.py
├── research_topic.py
├── meeting_helper.py
└── apologetics.py
```

---

## API base (`jw_agents.base`)

### `class Citation` (dataclass)

Puntero verificable a una fuente.

| Campo | Tipo | Default | Descripción |
|---|---|---|---|
| `url` | `str` | — | URL de wol.jw.org (o cualquier fuente verificable) |
| `title` | `str` | `""` | Título legible |
| `kind` | `str` | `""` | `"verse"` / `"article"` / `"daily_text"` / `"chapter"` / `"study_note"` / `"cross_ref"` / `"topic_subject"` / `"topic_subheading"` / `"topic_candidate"` / `"rag_chunk"` |
| `metadata` | `dict` | `{}` | Contexto libre |

### `class Finding` (dataclass)

Una unidad de información devuelta por un agente.

| Campo | Tipo | Default | Descripción |
|---|---|---|---|
| `summary` | `str` | — | Texto corto que orienta al LLM sobre qué es este finding |
| `citation` | `Citation` | — | Fuente verificable |
| `excerpt` | `str` | `""` | Texto verbatim sobre el que se basa el finding |
| `metadata` | `dict` | `{}` | Convención: incluir `source` para ranking por autoridad |

### `class AgentResult` (dataclass)

Envelope estándar de la salida de todo agente.

| Campo | Tipo | Default | Descripción |
|---|---|---|---|
| `query` | `str` | — | Entrada original |
| `agent_name` | `str` | — | Nombre del agente (`"verse_explainer"`, etc.) |
| `findings` | `list[Finding]` | `[]` | Evidencias ordenadas |
| `warnings` | `list[str]` | `[]` | Advertencias no fatales |
| `metadata` | `dict` | `{}` | Contexto del run |

**`to_dict() -> dict`** — serialización JSON-ready (usado por las herramientas MCP).

---

## Agente `verse_explainer`

```python
async def verse_explainer(
    text: str,
    *,
    language: str = "en",
    wol: WOLClient | None = None,
    max_paragraphs: int = 5,
    include_study_notes: bool = True,
    include_cross_refs: bool = True,
) -> AgentResult
```

### Pipeline

1. `parse_reference(text)` → si None: warning + return.
2. `WOLClient.get_bible_chapter(book_num, chapter, language)`.
3. `parse_article(html)` → metadata `chapter_title`.
4. `parse_verses(html, ...)`.
5. Si `ref.has_verse`: filtra target verses → un `Finding(kind="verse")` por versículo objetivo. Si no: primeros N párrafos.
6. Si `include_study_notes`: `parse_study_notes` filtrado al rango → `Finding(kind="study_note")` por nota.
7. Si `include_cross_refs`: `parse_cross_references` filtrado → hasta 10 `Finding(kind="cross_ref")`.

### Salida típica

```json
{
  "query": "Juan 3:16",
  "agent_name": "verse_explainer",
  "metadata": {
    "book_num": 43,
    "book_canonical": "John",
    "chapter": 3,
    "verse_start": 16,
    "verse_end": null,
    "detected_language": "es",
    "canonical_url": "https://wol.jw.org/...",
    "chapter_title": "John 3"
  },
  "findings": [
    {"summary": "John 3:16", "excerpt": "Porque tanto amó Dios...",
     "citation": {"url": "...", "kind": "verse", ...},
     "metadata": {"kind": "target_verse"}},
    {"summary": "Study note: world", "excerpt": "...",
     "citation": {"url": "...", "kind": "study_note", ...},
     "metadata": {"kind": "study_note", "verse": 16}},
    ...
  ]
}
```

---

## Agente `research_topic`

```python
async def research_topic(
    topic: str,
    *,
    language: str = "E",
    top_n: int = 5,
    fetch_top_k: int = 3,
    max_excerpts_per_article: int = 3,
    cdn: CDNClient | None = None,
    wol: WOLClient | None = None,
) -> AgentResult
```

### Pipeline

1. `CDNClient.search(topic, filter_type="all", language, limit=top_n)`.
2. `_flatten_search(data, limit=top_n)` → items aplanados (groups expandidos).
3. Para cada item con URL WOL, fetch + `parse_article`.
4. Por cada artículo: primeros `max_excerpts_per_article` párrafos → `Finding(kind="article")`.
5. Parar al alcanzar `fetch_top_k` artículos fetcheados.

Errores por artículo se añaden a `warnings` y continúa.

### Metadata

- `language`
- `search_hits`: número de items aplanados antes de fetchar.

---

## Agente `meeting_helper`

```python
async def meeting_helper(
    input_text: str,
    *,
    language: str = "en",
    max_paragraphs: int = 8,
    wol: WOLClient | None = None,
) -> AgentResult
```

### Pipeline

1. Si `input_text` empieza por `"http"`: `WOLClient.fetch(url)`.
2. Si no: `parse_reference(input_text)` → si None: warning + return. Si sí: `get_bible_chapter(...)`. Anota `metadata.resolved_reference`.
3. `parse_article(html)` → primeros `max_paragraphs` párrafos → `Finding(kind="article")`.
4. Cada Finding lleva `metadata.suggest_comment` (`""` / `"good for an early brief comment"` / `"rich content — pick one sentence to highlight"`).
5. `metadata.cross_references` = primeros 15 cross-refs del artículo.
6. `metadata.prep_prompts` = lista fija de 4 preguntas heurísticas.

---

## Agente `apologetics`

```python
async def apologetics(
    question: str,
    *,
    language: str = "E",
    rag_store: object | None = None,
    rag_top_k: int = 5,
    web_top_k: int = 3,
    topic_top_k: int = 1,
    topic_subheadings_limit: int = 8,
    use_topic_index: bool = True,
    cdn: CDNClient | None = None,
    wol: WOLClient | None = None,
    topic: TopicIndexClient | None = None,
) -> AgentResult
```

### Pipeline (4 fases)

**0. Topic Index** (si `use_topic_index=True`):
- `topic.search_subjects(question, limit=topic_top_k)`.
- Para cada subject con `docid`: `get_subject_page(docid)`.
- 1 `Finding(kind="topic_subject", source="topic_index")` anchor + `topic_subheadings_limit` `Finding(kind="topic_subheading", source="topic_index_entry")` por subject.
- Subjects sin docid → `Finding(kind="topic_candidate", source="topic_index_candidate")`.

**1. Bible refs explícitas en la pregunta**:
- `parse_all_references(question)`.
- Por cada ref: `Finding(kind="verse", source="question_refs")` anchor.
- Si tiene versículo: fetch capítulo, extraer `Verse` → `Finding(source="verse_text")`; `parse_study_notes` + `study_notes_for_verse` → `Finding(source="study_note")`.

**2. Búsqueda CDN + artículos**:
- `CDNClient.search(question, filter_type="all", limit=web_top_k * 2)`.
- `_flatten_search(data, limit=web_top_k)` → top-K items.
- Por cada item con WOL URL: fetch + `parse_article` → `Finding(kind="article", source="cdn_search")` con primer párrafo.

**3. RAG (opcional)**:
- Si `rag_store is not None` y tiene `hybrid_search`: ejecuta búsqueda híbrida → `Finding(source="rag")` por hit con `metadata.rrf_score`.

### Política de autoridad (convención para el LLM)

```
topic_index > topic_index_entry > question_refs
> verse_text > study_note > cdn_search > rag
```

El LLM llamante sintetiza usando `findings[i].metadata.source` para priorizar.

### Helpers utilizados

- `_iso_for(jw_or_iso)` — `"E"` → `"en"`, `"S"` → `"es"`, `"T"` → `"pt"`, otros pasan tal cual lowercased.
- `_flatten_search`, `_wol_url_from` — importados de `research_topic`.

---

## Pattern matching de fuentes (sample)

Si quieres rankear findings desde tu propio código:

```python
SOURCE_PRIORITY = {
    "topic_index": 7,
    "topic_index_entry": 6,
    "question_refs": 5,
    "verse_text": 4,
    "study_note": 3,
    "cdn_search": 2,
    "rag": 1,
    "topic_index_candidate": 0,
}

def rank(finding):
    return SOURCE_PRIORITY.get(finding.metadata.get("source", ""), 0)

ranked = sorted(result.findings, key=rank, reverse=True)
```

---

## Anti-patrones

- **No** invocar un LLM dentro del agente. La síntesis va en el cliente Claude.
- **No** levantar excepciones — usar `warnings.append()` y devolver el `AgentResult` parcial.
- **No** omitir `citation.url`. Todo el toolkit existe para producir citas verificables.
- **No** crear `WOLClient`/`CDNClient` cuando recibes uno por parámetro.

---

## Ver también

- [`docs/guias/construir-un-agente.md`](../guias/construir-un-agente.md) — guía para escribir un agente nuevo
- [`docs/conceptos/flujos-end-to-end.md`](../conceptos/flujos-end-to-end.md) — diagramas detallados
