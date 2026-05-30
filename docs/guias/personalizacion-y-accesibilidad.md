# Personalización, memoria y accesibilidad (Módulo 12)

> Cubre el ítem #12 de [VISION.md](../VISION.md): profile de usuario, memoria entre sesiones, tono ajustable, accesibilidad cognitiva y visual.

## Cuatro capas

| Archivo | Función |
|---|---|
| `jw_core/personalization/profile.py` | UserProfile + SQLite store por user_id |
| `jw_core/personalization/memory.py` | Append-log de memorias cross-session |
| `jw_core/personalization/tone.py` | Directivas para que el LLM ajuste tono |
| `jw_core/personalization/accessibility.py` | Easy-read + paletas alto contraste |

## Profile

```python
from jw_core.personalization import UserProfile, UserProfileStore

with UserProfileStore() as s:
    s.upsert(UserProfile(
        user_id="elias",
        language="es",
        congregation="Congregación Centro",
        assignments=["pioneer", "elder"],
        interests=["last_days", "youth"],
        tone="formal",
        tts_provider="edge",
    ))
    me = s.get("elias")
```

Campos:
- `language` — ISO code, se propaga a todos los agentes
- `congregation` — string libre, **nunca** sale del dispositivo
- `assignments` — roles (pioneer/elder/youth/...)
- `interests` — temas que pre-cargan investigación
- `tone` — `formal | casual | easy_read`
- `tts_provider` — override para Módulo 3
- `rag_root` — override para el RAG store

Default DB: `~/.jw-agent-toolkit/profile.db` (override `JW_PROFILE_DB`).

## Memoria

```python
from jw_core.personalization import MemoryEntry, save_memory_for_user, load_memory_for_user

save_memory_for_user("elias", MemoryEntry(kind="open_question", text="¿Qué significa el 'huésped y residente temporario'?"))
save_memory_for_user("elias", MemoryEntry(kind="topic", text="Trinity", metadata={"last_url": "https://wol.jw.org/..."}))

# En siguiente sesión: el LLM puede inyectar esto al system prompt.
recent = load_memory_for_user("elias", limit=10, kinds=["open_question", "topic"])
for m in recent:
    print(m.kind, "—", m.text)
```

`kind` recomendado: `topic | verse_ref | open_question | last_revisit | free_note`. El append-log es local y rotará por cuotas de uso (próxima Fase) cuando crezca.

## Tono ajustable

`adjust_tone(text, target_tone="casual", language="es")` retorna una **directiva** que el LLM consumidor (Claude/Ollama) usa para reescribir, mientras el toolkit garantiza que las URLs y citas se preserven verbatim:

```python
from jw_core.personalization import adjust_tone, TONE_TEMPLATES

directive = adjust_tone(
    "Tras analizar... según wol.jw.org/x...",
    target_tone="easy_read",
    language="es",
)
# Pasar al LLM:
# system: directive
# user: <pregunta original>
```

## Accesibilidad

**Easy-read** — heurística sin LLM:
```python
from jw_core.personalization import easy_read

text = "Sin embargo, debemos demostrar amor en cada acción."
out = easy_read(text, language="es")
# "pero, debemos mostrar amor en cada acción."
```

Reglas:
- Sustituye conectores complejos (`sin embargo` → `pero`, `demostrar` → `mostrar`).
- Trocea oraciones de >21 palabras en chunks de 15.
- Para alta fidelidad combinar con `adjust_tone(..., target_tone="easy_read")`.

**Paletas alto contraste:**

```python
from jw_core.personalization import high_contrast_palette

palette = high_contrast_palette("yellow_on_blue")
# {"background": "#001D3D", "foreground": "#FFD60A", ...}
```

Tres temas (`dark`, `light`, `yellow_on_blue`). Todos diseñados con ratio de contraste ≥7:1 (WCAG AAA).

`increase_legibility(text)` añade espacios irrompibles tras conectivos cortos para reducir líneas huérfanas en lectores móviles/ePub.

## Tests

12 tests en `packages/jw-core/tests/test_personalization_module.py`:

- Profile: `is_minor` por assignment 'youth', roundtrip, fallback a default.
- Memoria: append + recent ordering descendente, filter por kind, clear per-user.
- Tono: templates localizados, directiva preserva texto original.
- Easy-read: chunking de oraciones largas, swap de palabras complejas en español.
- Paletas: 6 keys exactas, fallback a `dark` para tema desconocido.

```bash
uv run pytest packages/jw-core/tests/test_personalization_module.py -v
```

## Cómo integrar en agentes existentes

Patrón recomendado para cualquier agente que devuelve prosa-friendly:

```python
async def my_agent(question: str, *, user_id: str = "default"):
    profile = UserProfileStore().get(user_id)
    history = load_memory_for_user(user_id, kinds=["topic"], limit=5)

    # Llamar al toolkit como siempre (idioma del profile).
    result = await apologetics(question, language=profile.language.upper())

    # Capturar evento de memoria para próxima sesión.
    save_memory_for_user(user_id, MemoryEntry(kind="topic", text=question))

    # Devolver con directiva de tono — el LLM consumidor la aplica.
    result.metadata["tone_directive"] = adjust_tone("...", target_tone=profile.tone, language=profile.language)
    return result
```

## Pendiente

- UI para editar profile (web/Tauri).
- Multi-perfil real con auth en el REST API.
- Memoria sintetizada vía LLM (compactar el log cuando crece) — apoyado en Módulo 11 (Ollama).
