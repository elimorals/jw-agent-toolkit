# Asistente de ministerio (Módulo 2 — Fase 12)

> Cierra el ítem #2 de [VISION.md](../VISION.md): "Asistente de conversaciones / objeciones con respuestas + citas verificables". Cubre cinco superficies — objeciones, presentaciones por audiencia, búsqueda inversa de citas, tracker local de revisitas, y plan de próxima visita.

## Componentes

| Capa | Archivo | Qué hace |
|---|---|---|
| Datos | `jw_core/data/objections.py` | Catálogo de objeciones (es/en/pt) con keywords + anchors (topic_index + scripture) |
| Agente | `jw_agents/conversation_assistant.py` | Empareja texto con catálogo y cosecha topics + versículos |
| Agente | `jw_agents/presentation_builder.py` | Scaffold de presentación por audiencia (católico, evangélico, ateo, musulmán, joven, en duelo) |
| Agente | `jw_agents/reverse_citation_lookup.py` | "¿De qué publicación es esta cita?" — overlap de bigramas |
| Agente | `jw_agents/revisit_tracker.py` | Tracker SQLite **local-only** de revisitas (`~/.jw-agent-toolkit/ministry.db`) |
| MCP | `jw_mcp/server.py` | 8 tools nuevas: `conversation_assistant`, `list_known_objections`, `presentation_builder`, `list_audiences`, `reverse_citation_lookup`, `revisit_upsert`, `revisit_list`, `revisit_due`, `revisit_plan`, `revisit_delete` |
| CLI | `jw_cli/commands/ministry.py` | `jw ministry objections / answer / audiences / present / quote / revisit ...` |

## Catálogo de objeciones

9 entradas en la primera ola (Trinidad, infierno, alma inmortal, cruz, sangre, contradicciones, sufrimiento, últimos días, 1914). Cada una expone:

- `key` canónico
- `labels` (en/es/pt) — etiquetas humanas
- `keywords` por idioma — usado por `find_objection` con scoring multiidioma
- `topic_anchors` — los temas a consultar en el Índice de Publicaciones (autoritativo)
- `scripture_anchors` — versículos que siempre aplican
- `category` — `doctrine`, `bible_reliability`, `philosophical`

**Importante:** el catálogo **no incluye prosa**. Las respuestas las compone el agente desde el topic_index + versículos, así la doctrina vigente siempre proviene de jw.org. Cuando JW actualiza un punto, el agente lo refleja al siguiente fetch — sin desfase.

## Flujo `conversation_assistant`

```
texto del interlocutor
       │
       ▼
find_objection() ──► no match ──► warning + free apologetics
       │
       ▼
para cada topic_anchor:
   topic_index.search_subjects → get_subject_page → emit subheadings
       │
       ▼
para cada scripture_anchor:
   wol.get_bible_chapter → get_verse + study notes
       │
       ▼
AgentResult con findings ordenados por autoridad
```

## Audiencias soportadas en `presentation_builder`

| key | Tono especial | Anchors típicos |
|---|---|---|
| `catholic` | Respeta la tradición; nunca ataca "la Iglesia" | God's Name, Jesus, Prayer |
| `evangelical` | Autoridad de la Biblia es campo común | Kingdom, Trinity, Hell |
| `atheist` | No pide asumir Dios; arranca con diseño | Creation, Suffering, Bible Prophecy |
| `muslim` | Monoteísmo, respeto a profetas | God's Name, Jesus, Resurrection |
| `young` | Identidad y futuro | Youth, Anxiety, Future |
| `struggling_grief` | Pérdida y esperanza | Resurrection, Death, Comfort |

Cada perfil expone `opening_questions`, `common_ground`, `suggested_topics`, `suggested_scriptures`, `tone_notes` — todos localizados.

## Tracker de revisitas

**Privacidad por diseño:**
- SQLite local en `~/.jw-agent-toolkit/ministry.db` (override con `JW_MINISTRY_DB`).
- Cero llamadas de red. Cero telemetría.
- VISION.md prohíbe trackers de hermanos sin opt-in — este existe para las propias notas del publicador.

**Operaciones:**
- `upsert(Revisit)` — crea o actualiza por `interest_id`
- `get(interest_id)` / `list_all(language=...)` / `due(on_or_before=...)`
- `search(query)` — fuzzy en `notes`, `name_alias`, `last_topic`
- `delete(interest_id)`

**`plan_next_visit`:** genera intro + warmup question + topic anchor en el idioma del interés.

## Búsqueda inversa de citas

`reverse_citation_lookup(quote)`:
1. Normaliza el texto (quita puntuación, lowercase).
2. Toma los primeros 10 tokens como query CDN, filter='publications'.
3. Por cada resultado fetcha y calcula overlap de bigramas.
4. Filtra por `min_confidence` (0.0-1.0).

**Best practice:** funciona mejor con 8-30 palabras textuales. Bajo `min_confidence=0.4` deberías ver pocos falsos positivos.

## Uso

### CLI

```bash
# Catálogo
jw ministry objections --lang en

# Responder a una objeción
jw ministry answer "¿Por qué no creen en la Trinidad?" --lang S

# Audiencias y presentaciones
jw ministry audiences --lang es
jw ministry present catholic --lang S

# Búsqueda inversa
jw ministry quote "el reino de Dios es un gobierno celestial"

# Revisitas (todo local)
jw ministry revisit add john1 --name "John" --topic "Trinity" --next 2026-06-04
jw ministry revisit list
jw ministry revisit due 2026-06-30
jw ministry revisit plan john1 --lang en
jw ministry revisit delete john1
```

### MCP

Desde Claude Desktop:

```
> usa conversation_assistant con text="¿Por qué no usan la cruz?"
> usa presentation_builder con audience="atheist"
> usa revisit_upsert con interest_id="alex1" name_alias="Alex" next_visit_iso="2026-07-15"
```

### Como librería

```python
import asyncio
from jw_agents import (
    Revisit, RevisitStore, conversation_assistant,
    presentation_builder, reverse_citation_lookup, plan_next_visit,
)

# Objeciones
result = asyncio.run(conversation_assistant("Doesn't the soul live forever?", language="E"))
for f in result.findings:
    print(f.summary, "→", f.citation.url)

# Tracker local
with RevisitStore() as store:
    store.upsert(Revisit(interest_id="alex", name_alias="Alex", last_topic="Hell"))
    print(plan_next_visit(store.get("alex"), language="en"))
```

## Diseño / decisiones clave

1. **El catálogo no carga prosa.** Si encodificáramos respuestas, se desactualizarían cada vez que JW publica nuevo material. Los anchors apuntan al topic_index — siempre vigente.
2. **Localización end-to-end.** Todas las etiquetas, plantillas de comentarios y prompts de warmup están en es/en/pt. Falta crecer a fr/de/it (Fase 16 / Módulo 8).
3. **Audience profile como datos.** Agregar una audiencia es añadir un `AudienceProfile` al diccionario `PROFILES` — sin tocar lógica.
4. **Reverse lookup local-friendly.** El bigram overlap evita llamar a un LLM; corre en CPU con poquísima memoria.

## Tests

20+ tests en `packages/jw-agents/tests/test_ministry_module.py`:

- Cobertura del catálogo (todas las objeciones core presentes y con anchors).
- Matching multiidioma (en/es/pt + fallback a en).
- Helpers de búsqueda inversa (`_normalize`, `_bigram_overlap`) con casos límite.
- SQLite store: upsert idempotente, filtro por `due`, search, delete con retorno booleano.
- `presentation_builder` offline (sin red) para todas las audiencias.

```bash
uv run pytest packages/jw-agents/tests/test_ministry_module.py -v
```

## Cómo extender

| Quiero... | Hago... |
|---|---|
| Agregar una objeción nueva | Apendear a `CATALOG` en `objections.py` |
| Agregar un perfil de audiencia | Apendear a `PROFILES` en `presentation_builder.py` |
| Añadir idioma | Añadir entradas a los diccionarios `labels` / `keywords` / templates |
| Cifrar el tracker | Settear `JW_MINISTRY_KEY` y wrappear `RevisitStore` con un EncryptedColumn helper |

## Pendiente (para Fase 12 completa)

- Audio/voz de las respuestas (lo cubre Módulo 3).
- Sync end-to-end-encryption multi-dispositivo (Módulo 11).
- Modelo Ollama local opcional para sintetizar las respuestas sin Claude (Módulo 11).
