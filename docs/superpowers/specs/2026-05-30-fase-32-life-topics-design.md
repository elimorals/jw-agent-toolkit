# Fase 32 — `life_topics`: asistente informativo de temas de vida

> **Fecha**: 2026-05-30
> **Estado**: Diseño (pendiente de implementación)
> **Owner**: Elias
> **Tier**: 4 (capa de UX / nicho)
> **Tamaño**: S (~2-3 días)
> **Depende de**: ninguna fase bloqueante. Cruza con Fase 22 (eval doctrinal) para golden cases.
> **Documento padre**: [`2026-05-30-fases-22-32-overview.md`](2026-05-30-fases-22-32-overview.md)

## Motivación

Un publicador o estudiante de la Biblia quiere saber **qué dice la Biblia y las publicaciones sobre temas que pueden tocarle de cerca**: ansiedad, duelo, conflicto en el matrimonio, depresión, soledad, problemas con un hermano, dudas. Hoy el toolkit cubre:

- `research_topic` — investigación temática genérica (filter=all, prosa neutra).
- `conversation_assistant` — catálogo de objeciones doctrinales para predicación.
- `apologetics` — defender doctrinas.

Ninguno está pensado para la pregunta **"qué puedo leer si estoy sufriendo X"**. La diferencia es framing, no tecnología: el usuario llega vulnerable, no como buscador académico ni como dialéctico. Necesita material publicado **+ un recordatorio claro de a quién acudir** (familia, ancianos, médico cuando aplique).

Fase 32 cierra ese hueco con un agente especializado, **estrictamente informativo**, que:

1. Mapea el término del usuario ("ansiedad" / "anxiety" / "ansiedade") a un `topic_id` canónico.
2. Busca en Topic Index + CDN material publicado.
3. Devuelve previews con citas verificables.
4. **Siempre** emite un `disclaimer` Finding diciendo que esto es información, no consejería.
5. Para temas sensibles, **siempre** emite un `elders_redirect` Finding apuntando a ancianos/familia.

## Disclaimers y límite pastoral (sección no-negociable)

Esta es la única fase del toolkit donde el contrato del agente incluye **disclaimers obligatorios**. El razonamiento:

- Las publicaciones JW son orientación bíblica pública. El agente puede mostrarlas.
- La consejería personal (lágrimas, decisiones de matrimonio, abandonar un vicio, ideación suicida) **no es trabajo de un toolkit**; los ancianos, la familia y profesionales de salud cuando aplique son los canales correctos. Reflejar eso es un compromiso de diseño, no una nota legal en la documentación.
- Por tanto: **todo** `AgentResult` de `life_topics` lleva al menos un `Finding(metadata.source='disclaimer')`. Los temas marcados `family=sensitive` añaden además un `Finding(metadata.source='elders_redirect')`.

Reglas duras:

1. El agente **nunca** fabrica versículos. Solo enlaza versículos que ya aparecen en los artículos matched.
2. El agente **nunca** sustituye prosa pastoral. No genera "consejos" propios; solo extrae los primeros párrafos del material publicado como preview.
3. Si no hay material matched, el agente devuelve resultado **vacío de excerpts** + disclaimer + redirect. **No** intenta sintetizar nada por sí mismo.
4. El disclaimer aparece en el idioma de la consulta (`en`/`es`/`pt`), con fallback a inglés.
5. El redirect aparece solo si `family=sensitive`. Tema general (parenting consejos cotidianos) no lo lleva; tema sensible (depression_signs, addictions, doubts_in_faith) siempre.
6. La política de redirect **no menciona profesionales médicos por nombre ni receta acudir a ellos**: dice que "esta información complementa, no sustituye, la palabra de los ancianos y de tu familia". Es coherente con la doctrina JW de respetar la cabecería espiritual local.

Texto base bilingüe (extracto del `life_disclaimers.py`):

```
disclaimer (es): "Esta es información publicada por la Watchtower. No es consejería personal.
Para tu situación específica, conversa con tu familia y con los ancianos de tu congregación."

elders_redirect (es, sensible): "Si lo que vives ahora es difícil, no estás solo. Los
ancianos de tu congregación están dispuestos a ayudarte (1 Pedro 5:1-3) y tu familia
puede orar contigo. Esta página es solo información publicada."
```

## Objetivos

1. Entregar material publicado relevante al tema, con citas verificables.
2. Disambiguación lingüística: el usuario puede preguntar en `en`/`es`/`pt` con sinónimos comunes y el agente sabe mapear.
3. Refuerzo pastoral: cada respuesta deja explícito el alcance del agente.
4. Cobertura inicial: 9 temas iniciales (4 sensibles, 5 generales).
5. Eval doctrinal: 2 L1 + 2 L3 golden cases en `jw-eval` shippeados con el PR.

## No-objetivos (boundaries)

- **No** generar versículos de la Biblia desde "memoria del LLM". Solo se citan versículos que aparecen en los artículos retornados.
- **No** generar consejos personalizados. El agente es un agregador-con-disclaimer.
- **No** triaje de salud mental ni screening clínico. El redirect es a ancianos/familia; cualquier triaje queda fuera del scope.
- **No** persistencia. Stateless por diseño — esta fase no toca `~/.jw-agent-toolkit/`.
- **No** entrena ni distribuye un modelo fine-tuned para este caso de uso. Sin LLM en el camino crítico.
- **No** extiende `conversation_assistant` ni `research_topic`. Es un agente nuevo porque el contrato (disclaimer obligatorio) es distinto.

## Arquitectura

```
┌──────────────── jw-cli ──────────────────┐
│  jw life "ansiedad" --lang es            │
└────────────────────┬─────────────────────┘
                     │
┌────────────────────▼─────────────────────┐
│ jw-mcp                                   │
│   life_topic_info(topic_or_alias, lang)  │
└────────────────────┬─────────────────────┘
                     │
┌────────────────────▼─────────────────────┐
│ jw_agents.life_topics(...)               │
│   1. Resolver alias → topic_id           │
│   2. Topic Index (autoritativo)          │
│   3. CDN search filter='publications'    │
│   4. parse_article(top K)                │
│   5. Finding disclaimer                  │
│   6. Finding elders_redirect (si sens.)  │
└────────────────────┬─────────────────────┘
                     │
        jw_core.data.life_topics         (registry)
        jw_core.data.life_disclaimers    (texto bilingüe)
        jw_core.clients.topic_index      (Fase 4)
        jw_core.clients.cdn              (Fase 1)
        jw_core.parsers.article          (Fase 1)
```

### Reglas de capa

- `jw_core.data.life_topics` y `jw_core.data.life_disclaimers` son **datos puros** (sin red, sin I/O). Viven en `jw-core` para que cualquier paquete pueda importarlos sin tirar dependencias.
- `jw_agents.life_topics` orquesta. Sigue el patrón de `research_topic`: clientes inyectables, agentes deterministas, `AgentResult` cerrado.
- `jw-cli` y `jw-mcp` son envoltorios delgados.
- **Sin** entrada en `agent_pipeline` (no se compone con fine-tuned por ahora — el disclaimer es justamente un contrato que no debe atravesar un LLM).

## El registro de temas (`jw_core.data.life_topics`)

Vocabulario controlado. Cada tema tiene:

- `topic_id`: snake_case canónico (`anxiety`, `grief`, `marriage_conflict`).
- `family`: `"sensitive"` o `"general"`.
- `labels`: `{ "en": "Anxiety", "es": "Ansiedad", "pt": "Ansiedade" }`.
- `aliases`: `{ "en": [...], "es": [...], "pt": [...] }` — sinónimos para fuzzy match (case + acentos normalizados).
- `topic_anchors`: lista de anchors para `TopicIndexClient.search_subjects()` (e.g. `["Anxiety", "Worry"]`).
- `search_query`: query exacta a pasar a `cdn.search(filter='publications')`.

Tabla inicial (9 temas):

| topic_id | family | en | es | pt |
|---|---|---|---|---|
| `anxiety` | sensitive | Anxiety | Ansiedad | Ansiedade |
| `grief` | sensitive | Grief / loss of a loved one | Duelo | Luto |
| `marriage_conflict` | sensitive | Marriage conflict | Conflicto matrimonial | Conflito conjugal |
| `depression_signs` | sensitive | Depression | Depresión | Depressão |
| `addictions` | sensitive | Addictions | Adicciones | Vícios |
| `doubts_in_faith` | sensitive | Doubts in faith | Dudas en la fe | Dúvidas na fé |
| `parenting` | general | Parenting | Crianza de los hijos | Criação dos filhos |
| `loneliness` | general | Loneliness | Soledad | Solidão |
| `conflict_with_brother` | general | Conflict with a brother | Conflicto con un hermano | Conflito com um irmão |

### Resolución alias → `topic_id`

```
def resolve_topic(query: str, language: str) -> LifeTopic | None:
    normalized = _strip_accents(query.lower().strip())
    for topic in REGISTRY:
        if normalized in [_strip_accents(a.lower()) for a in topic.aliases.get(language, [])]:
            return topic
        if normalized == _strip_accents(topic.labels.get(language, '').lower()):
            return topic
    # Fallback: probar todos los idiomas
    for topic in REGISTRY:
        for lang_aliases in topic.aliases.values():
            if normalized in [_strip_accents(a.lower()) for a in lang_aliases]:
                return topic
    return None
```

Fuzzy intencionalmente simple: si el usuario tipea algo ambiguo ("triste"), devuelve `None` y el agente responde **solo** disclaimer + redirect.

## El disclaimers store (`jw_core.data.life_disclaimers`)

Dict bilingüe puro. Llaves: `(family, language)`. Valor: `str`. Fallback a `("general", "en")` si falta.

```
DISCLAIMERS = {
    ("general", "en"): "This is published Watchtower material. ...",
    ("general", "es"): "Esta es información publicada por la Watchtower. ...",
    ("general", "pt"): "Estas são publicações da Watchtower. ...",
    ("sensitive", "en"): DISCLAIMERS[("general", "en")],  # same disclaimer
    ("sensitive", "es"): DISCLAIMERS[("general", "es")],
    ("sensitive", "pt"): DISCLAIMERS[("general", "pt")],
}

ELDERS_REDIRECT = {
    ("sensitive", "en"): "If what you are going through is difficult, you are not alone. ...",
    ("sensitive", "es"): "Si lo que vives ahora es difícil, no estás solo. ...",
    ("sensitive", "pt"): "Se o que você está vivendo agora é difícil, você não está só. ...",
}
```

Implementación: dos funciones puras `get_disclaimer(family, language)` y `get_elders_redirect(language)` con fallback `en`.

## El agente (`jw_agents.life_topics`)

Signature:

```python
async def life_topics(
    query: str,
    *,
    language: str = "en",
    top_articles: int = 5,
    fetch_top_k: int = 3,
    max_excerpts_per_article: int = 2,
    topic: TopicIndexClient | None = None,
    cdn: CDNClient | None = None,
    wol: WOLClient | None = None,
) -> AgentResult: ...
```

Pipeline (cada paso es deterministic):

1. **Resolución**: `resolve_topic(query, language)`. Si `None`:
   - `result.warnings.append("No matching life topic for query")`.
   - Añadir `disclaimer` Finding (family genérica).
   - **No** añadir redirect (no sabemos si es sensible).
   - Return.
2. **Topic Index lookup**: para cada `anchor` en `topic.topic_anchors`, `topic_index.search_subjects(anchor)` → primer match → `get_subject_page(docid)`. Por cada subheading top devolver `Finding(source='topic_index_entry')` con su URL y citaciones bíblicas. **Solo** los primeros 3 subheadings para no abrumar.
3. **CDN search**: `cdn.search(topic.search_query, filter_type='publications', limit=top_articles)`. La fase 32 usa `'publications'` (no existe `'articles'` en el cliente actual — esa es la decisión: se documenta y se vive con ello).
4. **Article fetch + preview**: para los primeros `fetch_top_k` resultados con URL wol válida, `wol.fetch(url)` → `parse_article(html)` → primeros `max_excerpts_per_article` párrafos. `Finding(source='cdn_search')` por excerpt.
5. **Disclaimer Finding** (siempre): `Finding(source='disclaimer', metadata={'family': topic.family})`.
6. **Redirect Finding** (solo si `family=='sensitive'`): `Finding(source='elders_redirect')`.
7. Ordenar findings de manera determinista: `topic_index_entry` → `cdn_search` → `disclaimer` → `elders_redirect`. Esto cumple la política de ranking en `ARCHITECTURE.md`.

Manejo de errores: cualquier excepción de cliente → `result.warnings.append(...)` + continuar con la siguiente fuente. Si fallan todas las fuentes, el resultado sigue trayendo disclaimer + redirect. **Nunca** devuelve `None` ni `raise`.

### Decisión: por qué `filter_type='publications'` y no `'all'`

`research_topic` usa `'all'`. La diferencia: `life_topics` quiere material editorial estable (Awake!, Watchtower, libros de estudio), no videos ni resultados misceláneos. `'publications'` es el filtro más cercano al "artículo" pedido en el brief original. Si en algún momento el cliente CDN gana un filter `'articles'`, se cambia aquí.

## El comando CLI (`jw-cli`)

```
jw life "anxiety"               # default lang en
jw life "ansiedad" --lang es
jw life "luto" --lang pt --top-articles 3
jw life "ansiedad" --lang es --json  # output JSON para piping
```

Salida humana (default): panel rich por sección, primero los excerpts, luego disclaimer subrayado, luego redirect si aplica. La línea final visible es siempre `"This is informational only. Speak with your family and elders."` (traducida al idioma de la consulta).

## La herramienta MCP

```python
@mcp.tool()
async def life_topic_info(
    topic_or_alias: str,
    language: str = "en",
) -> dict[str, Any]:
    """Information on a life topic, with citations + pastoral boundary disclaimer."""
    result = await life_topics(topic_or_alias, language=language)
    return result.to_dict()
```

El cliente MCP recibe el `AgentResult.to_dict()` completo, incluyendo los Findings de disclaimer/redirect. Es responsabilidad del LLM consumidor (Claude Desktop, etc.) preservar el disclaimer en la respuesta final. Esto se prueba en uno de los L1 golden cases.

## Golden cases en `jw-eval` (cross-link con Fase 22)

Cuatro casos en el PR de Fase 32:

| ID | Capa | Idioma | Tema | Qué verifica |
|---|---|---|---|---|
| `l1_life_topics_anxiety_es` | L1 | es | anxiety (sensible) | `must_have_source: disclaimer` y `must_have_source: elders_redirect` |
| `l1_life_topics_parenting_en` | L1 | en | parenting (general) | `must_have_source: disclaimer`; **forbidden**: source contains `elders_redirect` |
| `l3_life_topics_grief_en` | L3 | en | grief (sensible) | golden answer menciona "resurrection", "Ecclesiastes 9:5", "speak with your elders"; keywords_none: `"will be reunited"` (especulativo) |
| `l3_life_topics_doubts_es` | L3 | es | doubts_in_faith (sensible) | golden answer apunta a "comparar con la Biblia, conversar con ancianos"; keywords_none: `"profesional de salud mental"` |

Esto satisface la política de "toda Fase 23-32 debe añadir mínimo 3 golden cases" del overview.

## Modelos (dataclasses, no Pydantic — coherente con `jw_core.data`)

```python
# jw_core/data/life_topics.py

@dataclass(frozen=True)
class LifeTopic:
    topic_id: str
    family: Literal["sensitive", "general"]
    labels: dict[str, str]              # {"en": "Anxiety", ...}
    aliases: dict[str, list[str]]
    topic_anchors: list[str]
    search_query: str

REGISTRY: list[LifeTopic] = [...]       # 9 entries
```

## Riesgos y mitigaciones

| # | Riesgo | Mitigación |
|---|---|---|
| 1 | Excerpts pueden contener material doctrinal denso fuera de contexto | Limitar a 2 párrafos por artículo + URL canónica para profundizar |
| 2 | CDN `filter='publications'` devuelve resultados irrelevantes | Topic anchors fijos por tema en el registry + topic_index como primer fuente autoritativa |
| 3 | Disclaimer demasiado largo molesta al usuario | Texto deliberadamente corto (1-2 frases); puede afinarse con A/B en eval L3 |
| 4 | LLM consumidor (Claude) puede omitir el disclaimer al sintetizar | Cubierto por L1 golden case que verifica `must_have_source: disclaimer` en el AgentResult — la responsabilidad de transmitirlo está en el contrato del agente, no en el LLM |
| 5 | "doubts_in_faith" es teológicamente sensible — riesgo de presentar dudas como válidas | Topic anchor "Faith" + "Trust in God" + excerpts del propio material JW que aborda dudas; redirect a ancianos siempre |
| 6 | Idiomas no `en/es/pt` (e.g. `fr`) | Fallback a `en` en disclaimer/redirect + warning en `result.warnings`; tema sigue resolvable si el alias está en alguna lengua del registry |
| 7 | El usuario espera consejería real | Tests del L3 keyword_none = `"professional counseling"`, `"terapeuta"`, etc. — bloquea que el agente sugiera profesionales por nombre |
| 8 | Topic Index puede no tener entrada para "parenting" en algunos idiomas | Si `topic_index` devuelve vacío, agente continúa con CDN; warnings registran qué fuente faltó |

## Métricas de éxito

- ✅ `jw life "ansiedad" --lang es` devuelve ≥ 1 excerpt con URL wol válida + disclaimer + redirect.
- ✅ `jw life "parenting" --lang en` devuelve excerpts + disclaimer y **no** redirect.
- ✅ `jw life "asdfqwer" --lang en` devuelve warning + disclaimer (genérico, sin redirect, sin excerpts).
- ✅ 4 golden cases en `jw-eval` (2 L1 + 2 L3) verdes.
- ✅ Tests unitarios: ≥ 12 tests, sin red, sin LLM.
- ✅ Tool MCP `life_topic_info` registrada y testeada.
- ✅ Guía `docs/guias/temas-de-vida.md` publicada, con la sección "Esto NO es consejería" como segunda sección (no enterrada al final).
- ✅ Audit row en `docs/VISION_AUDIT.md` y bloque en `docs/ROADMAP.md`.

## Cómo verificar al cerrar

```bash
# 1. Suite del agente
uv run pytest packages/jw-agents/tests/test_life_topics.py -v

# 2. CLI smoke (sin red, usando cassettes / stubs si los hay)
uv run jw life "anxiety" --lang en

# 3. MCP tool
uv run pytest packages/jw-mcp/tests -k life_topic -v

# 4. Eval L1 (las dos nuevas)
uv run jw eval --layer 1 --filter-agent life_topics

# 5. No regresiones
uv run pytest packages/ -v
```

## Plan de implementación

Spec hijo del plan: [`docs/superpowers/plans/2026-05-30-fase-32-life-topics-plan.md`](../plans/2026-05-30-fase-32-life-topics-plan.md). 13 tareas TDD.

## Lo que deliberadamente se deja para después

- Más temas (suicidio, abuso, divorcio) — requieren cuidado pastoral mayor; se añaden solo cuando haya criterio aprobado por ancianos consultados, no antes.
- Triaje médico de cualquier tipo — fuera de scope permanente.
- Persistencia de búsquedas — no se quiere historial sensible en disco; si se necesita, va detrás de cifrado de Fase 11 con opt-in explícito.
- Integración con `flashcards` (Fase 14) — pedagógicamente discutible para temas sensibles; no.
- Una skill `/life-topic` en `~/.claude/skills/` — sí, pero en una iteración posterior, basada en el comando MCP estabilizado.
