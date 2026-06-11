# Fase 66 — `conversation-sparring`: simulador de interlocutor para predicación

> **Fecha**: 2026-06-11
> **Estado**: Diseño aprobado (pendiente de implementación)
> **Owner**: Elias
> **Tier**: 1 (kernel agéntico)
> **Capa**: A — Agéntica
> **Depende de**: F12 `conversation_assistant`, F39 `nli-runtime`, F61 `memoria-asistente`, F34 `audio-premium` (TTS+ASR), F43 `agent-tracing`
> **Documento padre**: [`2026-06-11-fases-65-76-overview.md`](2026-06-11-fases-65-76-overview.md)
> **Predecesor conceptual**: F12 `conversation_assistant` + catálogo `objections` (objeciones estáticas, sin memoria de turno)

## Motivación

`conversation_assistant` (Fase 12) cataloga 9 objeciones estándar
× 3 idiomas. Útil como referencia. Pero **no entrena predicación
real**:

- No recuerda turnos previos.
- No reacciona a tu respuesta.
- No simula tono / persistencia / dudas reales del interlocutor.
- No te puntúa contra fuentes JW al final.

Un publicador que quiere mejorar en territorio difícil necesita
**sparring**: un interlocutor simulado con personalidad, memoria de
sesión, dudas que persisten si no las resuelves, y feedback post-sesión.

## Objetivos

1. **6 personas simuladas** con personalidad consistente:
   `catholic`, `evangelical`, `atheist`, `muslim`, `nominal`,
   `young_skeptic`.
2. **Memoria por sesión** (F61 `MemoryStore`): el interlocutor
   recuerda qué versículos citaste, qué objeciones ya resolviste,
   qué tono usaste.
3. **Feedback post-sesión** con NLI F39: lista de tus respuestas
   verificadas contra fuentes JW + sugerencias del agente
   `apologetics`.
4. **Voice mode** opt-in: ASR captura tu turno hablado, TTS reproduce
   el del interlocutor (reusa F34).
5. **Determinista bajo `JW_SPAR_LLM=fake`** con conversaciones
   pregrabadas para tests.

## No-objetivos (boundaries vinculantes)

- **No** caricaturiza personas reales o grupos religiosos. Cada
  persona simulada es un arquetipo informado por sus textos
  públicos, no un retrato de un individuo.
- **No** prepara argumentos ofensivos contra otras religiones —
  solo defensivos contra objeciones hipotéticas hacia TJ.
- **No** persiste el contenido de sesiones en cloud. Default
  SQLite local cifrado con `JW_MEMORY_KEY` (F61).
- **No** evalúa al usuario con un "score" punitivo. El feedback es
  formativo (qué reforzar), no comparativo.
- **No** sustituye al ministerio real. El CLI rotula explícitamente
  "PRÁCTICA — esto NO es una visita real".

## Decisión clave: ¿LLM-driven persona vs persona scriptada?

### Opción A — Persona puramente scriptada (state machine)

Diálogos pregrabados con árbol de respuestas por objeción.

**Pros**: 100% predecible, sin coste LLM.
**Contras**: rígido, fácil de "romper" como usuario, valor de entrenamiento bajo.

### Opción B — LLM con system prompt + guardrails

Cada persona = system prompt + lista de "creencias core" + lista de
"dudas que tiene" + tono. LLM responde con esa coherencia. F39 NLI
valida que las afirmaciones del USUARIO (no del interlocutor) coinciden
con fuentes JW.

**Pros**: realista, escalable, soporta improvisación del usuario.
**Contras**: requiere LLM real para ser útil; coste por token.

### Decisión: **Opción B** (LLM + guardrails)

Justificación:
1. El valor de sparring está en lo impredecible.
2. F39 NLI ya provee el guardrail de fidelidad doctrinal.
3. `FakeLLMProvider` con respuestas hardcodeadas mantiene tests
   deterministas sin sacrificar el modelo de producción.
4. El coste se controla con `JW_SPAR_MAX_TURNS=20` cap.

## Arquitectura

```
                   ┌─────────────────────────────────┐
                   │ CLI: jw spar --persona catholic │
                   │ MCP: spar_start / spar_turn     │
                   └────────────┬────────────────────┘
                                │
                                ▼
                   ┌─────────────────────────────────┐
                   │ SparSession                     │
                   │  - persona: Persona             │
                   │  - memory: MemoryStore (F61)    │
                   │  - turn_count: int              │
                   │  - resolved_objections: set     │
                   └────────────┬────────────────────┘
                                │
                ┌───────────────┼────────────────────┐
                ▼               ▼                    ▼
       ┌──────────────┐ ┌──────────────┐  ┌─────────────────┐
       │ User turn    │ │ Persona LLM  │  │ Feedback engine │
       │ (text/voice) │ │ (constrained │  │ (NLI F39 sobre  │
       │              │ │  F35 JSON)   │  │  user turns)    │
       └──────────────┘ └──────────────┘  └─────────────────┘
                                │
                                ▼
                   PersonaTurnResponse(reply, hidden_doubts, score)
```

## Contratos de tipos

```python
# packages/jw-agents/src/jw_agents/spar/models.py

from pydantic import BaseModel, Field
from typing import Literal

PersonaKey = Literal[
    "catholic", "evangelical", "atheist",
    "muslim", "nominal", "young_skeptic"
]

class Persona(BaseModel):
    key: PersonaKey
    display_name: str            # "María (católica practicante)"
    language: Literal["en", "es", "pt"]
    core_beliefs: list[str]      # 5-10 creencias arquetípicas
    typical_doubts: list[str]    # 5-10 objeciones que naturalmente plantea
    tone: Literal["warm", "neutral", "skeptical", "guarded"]
    profile_path: str            # ruta al MD con perfil completo

class UserTurn(BaseModel):
    text: str
    voice_audio_path: str | None = None
    turn_index: int

class PersonaTurnResponse(BaseModel):
    reply: str
    hidden_doubts: list[str] = []   # dudas internas no expresadas aún
    references_cited: list[str] = [] # versículos / fuentes que MENCIONÓ el interlocutor
    needs_followup: bool = False    # señala si la duda persiste

class TurnFeedback(BaseModel):
    user_turn_index: int
    nli_verdict: Literal["entails", "neutral", "contradicts", "skipped"]
    nli_score: float | None = None
    citation_quality: Literal["strong", "weak", "missing"]
    suggested_source: str | None = None  # wol.jw.org URL
    suggested_phrasing: str | None = None

class SparSession(BaseModel):
    session_id: str
    persona: Persona
    language: Literal["en", "es", "pt"]
    started_at: str
    user_turns: list[UserTurn] = []
    persona_turns: list[PersonaTurnResponse] = []
    feedback: list[TurnFeedback] = []
    resolved_objections: list[str] = []
    closed: bool = False
    score_summary: dict[str, float] | None = None
```

## API pública

```python
# packages/jw-agents/src/jw_agents/spar/__init__.py

from jw_agents.spar.session import SparSession, start_session, take_turn, close_session
from jw_agents.spar.personas import (
    list_personas,
    get_persona,
    PersonaKey,
    Persona,
)
from jw_agents.spar.feedback import score_session, TurnFeedback
from jw_agents.spar.models import UserTurn, PersonaTurnResponse

__all__ = [
    "SparSession",
    "Persona",
    "PersonaKey",
    "UserTurn",
    "PersonaTurnResponse",
    "TurnFeedback",
    "start_session",
    "take_turn",
    "close_session",
    "score_session",
    "list_personas",
    "get_persona",
]
```

## CLI

```bash
# Listar personas
jw spar personas

# Iniciar sesión texto
jw spar start --persona catholic --language es

# Continuar turn (en el flujo interactivo)
jw spar turn <session_id> "Buenos días, ¿puedo hablar con usted del Reino?"

# Voice mode (opt-in)
jw spar start --persona evangelical --voice --tts-provider edge

# Cerrar + obtener feedback
jw spar close <session_id>

# Inspeccionar transcripción + feedback de sesión cerrada
jw spar show <session_id>
```

## MCP tools

- `spar_list_personas() → list[Persona]`
- `spar_start(persona, language, congregation=None) → SparSession`
- `spar_turn(session_id, text) → PersonaTurnResponse`
- `spar_close(session_id) → SparSession` (incluye `score_summary`)

## Provider abstraction

| Env                  | Default     | Efecto                              |
|----------------------|-------------|-------------------------------------|
| `JW_SPAR_LLM`        | `fake`      | `claude`/`openai`/`ollama`/`fake`   |
| `JW_SPAR_MAX_TURNS`  | `20`        | Cap turns por sesión                |
| `JW_SPAR_NLI`        | `fake`      | Hereda F39 si está wired            |
| `JW_SPAR_VOICE`      | `off`       | `on` habilita ASR/TTS de F34        |
| `JW_SPAR_PERSONA_DIR`| —           | Path a personas custom (override)   |

`FakeLLMProvider` para sparring devuelve diálogos hardcodeados por
`(persona, turn_index)` desde `tests/spar/fixtures/conversations/`.

## Definición de las 6 personas

Cada persona vive en `packages/jw-agents/src/jw_agents/spar/personas/`
como un MD con front-matter Pydantic-loadable.

Estructura mínima:

```markdown
---
key: catholic
display_name: María (católica practicante)
language: es
tone: warm
core_beliefs:
  - "El papa es el sucesor legítimo de Pedro"
  - "La Virgen María intercede ante Dios"
  - "El alma es inmortal e inmediatamente va al cielo o al purgatorio"
typical_doubts:
  - "¿Por qué no celebráis la Navidad si Jesús también la celebraba?"
  - "Si Cristo es Dios, ¿por qué no oran a él?"
  - "¿De dónde sacáis que solo 144.000 van al cielo?"
---

# Perfil

María tiene 52 años, asiste a misa los domingos, criada en familia
católica tradicional. No es teóloga; sus creencias vienen de la
catequesis infantil y de lo que el párroco predica. Cuando un TJ
visita, abre la puerta con cordialidad pero mantiene distancia: no
quiere "cambiar de religión". Su tono es cálido pero defensivo si
percibe ataque a "su fe de toda la vida".

# Cómo evoluciona en la conversación

- Si el publicador es respetuoso y usa Biblia (no su propia
  traducción), María baja la guardia.
- Si el publicador critica al papa directamente, María se cierra.
- Las dudas se resuelven solo cuando el publicador cita Biblia + un
  argumento histórico/lógico, no solo Biblia.
```

Las 6 personas: 3 cristianas (catholic, evangelical, nominal) + atheist
+ muslim + young_skeptic (joven sin religión heredada pero curioso).

## Prompt del persona LLM

```jinja
{# packages/jw-agents/src/jw_agents/spar/prompts/persona_es.j2 #}
Eres {{ persona.display_name }}.

Creencias centrales (mantén coherencia):
{% for b in persona.core_beliefs %}- {{ b }}
{% endfor %}

Dudas típicas (plantea naturalmente si vienen al caso):
{% for d in persona.typical_doubts %}- {{ d }}
{% endfor %}

Tono: {{ persona.tone }}.

Historia de la conversación:
{% for t in turns %}
Visitante: {{ t.user }}
{{ persona.display_name }}: {{ t.persona }}
{% endfor %}

Visitante acaba de decir: "{{ current_user_turn }}"

Responde como {{ persona.display_name }}. Tu respuesta debe ser:
- Coherente con tus creencias.
- Apropiada al tono.
- Si el visitante no resolvió una duda que ya planteaste, recuérdaselo.
- Si planteó algo doctrinalmente débil para los TJ, no lo digas con
  esas palabras — simplemente continúa siendo escéptico.

Devuelve JSON estricto:
{
  "reply": "...",
  "hidden_doubts": ["..."],
  "references_cited": [],
  "needs_followup": true | false
}
```

Constrained con GBNF F35.

## Feedback engine

Tras cierre de sesión:

1. Para cada `UserTurn`, ejecuta NLI F39 contra el corpus RAG
   (Biblia + Atalayas oficiales):
   - Claim = la afirmación del usuario.
   - Premise = el chunk RAG top-1 que el agente `apologetics`
     habría usado para esa pregunta.
   - Verdict = entails / neutral / contradicts.
2. Mide `citation_quality`:
   - `strong` si el usuario citó wol.jw.org URL o pub code.
   - `weak` si solo citó Biblia sin pub.
   - `missing` si no citó nada y la afirmación lo requería.
3. Si `entails`, devuelve la URL real como `suggested_source`.
4. Si `contradicts` o `weak`, llama al agente `apologetics` con el
   turno como query y propone `suggested_phrasing` con cita real.

## Plan de pruebas

| Caso                                                       | Tipo        |
|------------------------------------------------------------|-------------|
| `Persona` carga desde MD con front-matter                  | Unit        |
| `list_personas()` devuelve 6                               | Unit        |
| Personas custom dir override                               | Unit        |
| `start_session` crea entrada en MemoryStore F61            | Integration |
| `take_turn` con FakeLLM devuelve `PersonaTurnResponse`     | Unit        |
| Sesión respeta max_turns                                   | Unit        |
| `close_session` invoca feedback engine                     | Integration |
| Feedback con NLI=entails marca `citation_quality=strong`   | Unit        |
| Feedback con NLI=contradicts sugiere phrasing nuevo        | Unit        |
| Voice mode wire-up F34 (mock ASR + TTS)                    | Integration |
| Sesión multi-turno preserva `resolved_objections`          | Unit        |
| CLI `jw spar start` produce session_id                     | E2E         |
| MCP `spar_turn` valida session_id                          | Integration |
| Constrained F35: persona JSON siempre parseable            | Property    |

## Conversaciones golden (test fixtures)

`tests/spar/fixtures/conversations/`:
- `catholic_friendly_es.jsonl` — 8 turnos, resolución limpia.
- `evangelical_defensive_en.jsonl` — 6 turnos, dudas persistentes.
- `atheist_hostile_es.jsonl` — 4 turnos, cierre temprano.
- `muslim_curious_es.jsonl` — 10 turnos, profundización.

Cada uno con (`turn_index, user_text, expected_persona_reply,
expected_feedback`).

## Riesgos / mitigaciones

| Riesgo                                                    | Mitigación                                       |
|-----------------------------------------------------------|--------------------------------------------------|
| Persona muestra estereotipo ofensivo                      | Review humano del MD de cada persona + advertencia legal en CLI; opción "report persona" para feedback |
| Usuario abusa del sparring contra personas reales         | CLI marca claramente "PRÁCTICA — NO es visita real"; logging local de uso |
| Persona "gana" demasiado y desanima al usuario            | Feedback siempre formativo, nunca punitivo; sugiere `apologetics` |
| Voice mode lag perceptible                                | Streaming ASR + streaming TTS; cap 200ms latency |
| Persona dice algo doctrinalmente falso sobre TJ           | NLI F39 valida turnos del USUARIO, no del interlocutor; persona es libre de ser incorrecta como un interlocutor real |
| LLM costoso si sesiones largas                            | `JW_SPAR_MAX_TURNS=20` + reporte tokens en `close_session` |

## Métricas de éxito

- **Personas creíbles**: ≥4/5 evaluadores humanos las clasifican como
  "razonables" sobre 20 turnos cada una.
- **Feedback útil**: ≥80% de turnos con `contradicts` reciben
  `suggested_phrasing` no-trivial.
- **Adopción**: usuarios activos hacen ≥1 sesión por semana en mes 2.

## Wire-up

- CLI: `packages/jw-cli/src/jw_cli/commands/spar.py` — `jw spar {start,turn,close,show,personas}`.
- MCP: `packages/jw-mcp/src/jw_mcp/server.py` — 4 tools nuevas.
- Memoria F61: namespace `spar:session:{session_id}`.
- Audio F34: `--voice` activa providers default.

## Guía resultante

`docs/guias/conversation-sparring.md` — quick start, las 6 personas,
voice mode, interpretación de feedback.
