# Memoria persistente del asistente (Fase 61)

> Permite al `conversation_assistant` (y futuros agentes) recordar
> discusiones doctrinales pasadas, preferencias del usuario y objeciones
> ya tratadas — sin perder contexto entre sesiones.

## Backends disponibles

| Backend | Local-first | Setup | Caso de uso |
|---|---|---|---|
| `fake` (default) | ✓ in-memory | nada | tests, ejecuciones one-shot |
| `sqlite` (recomendado) | ✓ archivo local | nada (auto-create) | uso personal continuo |
| `letta` (opt-in) | ✗ requiere server | docker + agent UI | multi-device sync, memoria jerárquica |

Elige con env var: `export JW_MEMORY_BACKEND=sqlite`.

## SqliteMemoryStore + cifrado opcional

Default: archivo `~/.jw-agent-toolkit/memory.db` (plaintext).

Para cifrar TODO content con Fernet:

```bash
# Generar key una sola vez:
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# → guardarla EN tu password manager (vault, 1Password)

export JW_MEMORY_KEY="<la-key-generada>"
```

**ATENCIÓN**: si pierdes la key, los records cifrados son irrecuperables.
El toolkit NO escribe la key a disco ni la sincroniza.

## Letta backend

Para memoria jerárquica + multi-device sync:

```bash
# 1. Levantar Letta server (Docker)
docker run -p 8283:8283 letta/letta:latest

# 2. Crear agente en Letta UI (http://localhost:8283)
#    Copiar el agent_id

# 3. Setup env vars
export JW_MEMORY_BACKEND=letta
export LETTA_BASE_URL=http://localhost:8283
export LETTA_AGENT_ID=<agent-id-de-letta-ui>
export LETTA_TOKEN=<opcional si auth activo>

# 4. Instalar dep
uv add 'jw-agents[memory-letta]'
```

## Uso desde Python

```python
from jw_agents.memory import build_memory_store
from jw_agents.conversation_assistant import conversation_assistant

memory = build_memory_store()  # respeta JW_MEMORY_BACKEND
result = await conversation_assistant(
    "¿Por qué los TJ no aceptan transfusiones?",
    language="S",
    session_id="conversation-2026-06-04",
    memory=memory,
)
```

## Uso desde MCP / Claude

```
@jw-agent-toolkit memory_record
  session_id: conversation-2026-06-04
  kind: preference
  content: El usuario prefiere explicaciones cortas con 2-3 citas máximo

@jw-agent-toolkit memory_recall
  session_id: conversation-2026-06-04
  query: transfusiones
```

## Auto-recap de sesiones previas (F61.8)

Al iniciar una nueva sesión, el agente `recap_previous_session` genera un
resumen procedural (sin LLM en el camino crítico) de las sesiones previas
del usuario. Útil para preguntar "¿continuamos con la sesión de ayer?".

```python
from jw_agents import recap_previous_session
from jw_agents.memory import build_memory_store

memory = build_memory_store()
result = await recap_previous_session(
    memory=memory,
    current_session_id="conversation-2026-06-05",
    limit=5,                   # hasta 5 sesiones previas
    max_excerpts_per_kind=3,   # 3 excerpts por kind
)
for finding in result.findings:
    print(finding.summary)
    print(finding.metadata["excerpts_by_kind"])
```

Vía MCP:

```
@jw-agent-toolkit recap_previous_session
  current_session_id: conversation-2026-06-05
  limit: 5
```

El output es un `AgentResult` con un `Finding` por sesión previa (ordenadas
por timestamp desc) — cada `Finding` lleva `summary`, `excerpt` y
`metadata.excerpts_by_kind` para que un LLM downstream pueda generar
narrativa rica si lo desea.

## Privacy first

- TODO el storage es local (sqlite) por default.
- El cifrado Fernet es **opt-in** (env var) — no en path crítico.
- `forget(session_id)` borra **inmediatamente**, sin papelera ni sync.
- El toolkit NO sube records a la nube en ningún backend (Letta opcionalmente
  los expone vía API, pero esa decisión queda en el usuario).
- `JW_MEMORY_DB` apunta a archivo local; el usuario puede backupearlo
  manualmente (recomendado: junto con sus notas Obsidian del F20).
