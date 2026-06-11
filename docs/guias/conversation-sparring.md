---
title: "Sparring conversacional (Fase 66)"
description: "Simulador de interlocutor para predicación con 6 personas × 3 idiomas, memoria F61, NLI F39 opt-in, voice mode y persistencia SQLite cross-process."
date: "2026-06-11"
---

# Sparring conversacional (Fase 66)

> Entrena tu predicación contra un interlocutor simulado con memoria de
> sesión. 6 personas builtin (`catholic`, `evangelical`, `atheist`,
> `muslim`, `nominal`, `young_skeptic`). LLM-driven con guardrails
> (NLI F39 sobre los turnos del USUARIO, no del persona). Feedback
> post-sesión formativo, nunca punitivo.

## Quick start

```bash
# Listar personas builtin
jw spar personas

# Iniciar sesión
jw spar start --persona catholic --language es
# -> session started: spar-a1b2c3d4 (persona=catholic, lang=es)

# Enviar un turno
jw spar turn spar-a1b2c3d4 "Buenos días, ¿puedo hablar con usted?"

# Inspeccionar estado completo
jw spar show spar-a1b2c3d4

# Cerrar y obtener feedback
jw spar close spar-a1b2c3d4
```

## CLI

| Comando                    | Descripción                                |
|----------------------------|--------------------------------------------|
| `jw spar personas`         | Lista las 6 personas builtin               |
| `jw spar start -p X -l es` | Crea sesión, imprime `session_id`          |
| `jw spar turn <sid> "X"`   | Envía un turno y obtiene la respuesta JSON |
| `jw spar show <sid>`       | Dump JSON completo de la sesión            |
| `jw spar close <sid>`      | Cierra + calcula `score_summary`           |

## MCP

| Tool                   | Descripción                              |
|------------------------|------------------------------------------|
| `spar_list_personas`   | Lista las 6 personas                     |
| `spar_start`           | Crea sesión                              |
| `spar_turn`            | Turno y respuesta                        |
| `spar_close`           | Cierra + feedback                        |

## Variables de entorno

| Env                    | Default                | Efecto                                   |
|------------------------|------------------------|------------------------------------------|
| `JW_SPAR_LLM`          | `fake`                 | `anthropic`/`claude`/`ollama`/`fake`     |
| `JW_SPAR_MAX_TURNS`    | `20`                   | Cap de turnos por sesión                 |
| `JW_SPAR_PERSONA_DIR`  | builtin                | Path override para personas custom       |
| `JW_META_LLM`          | heredado de `JW_SPAR_LLM` cuando se setea explícito | F65 factory shim |

## Las 6 personas builtin

| Key             | Display name                  | Idioma | Tono       |
|-----------------|-------------------------------|--------|------------|
| `catholic`      | María (católica practicante)  | es     | warm       |
| `evangelical`   | Pastor Carlos (pentecostal)   | es     | guarded    |
| `atheist`       | Ana (atea analítica)          | es     | skeptical  |
| `muslim`        | Ahmed (musulmán sunita)       | es     | neutral    |
| `nominal`       | Roberto (cristiano nominal)   | es     | neutral    |
| `young_skeptic` | Luna (joven escéptica)        | es     | skeptical  |

Cada persona tiene 4-5 `core_beliefs` arquetípicos + 4-5 `typical_doubts`
+ perfil ampliado en `profile_md` que explica cómo evoluciona en la
conversación.

## Personas custom

Crea un directorio con archivos `.toml` que sigan el shape:

```toml
key = "atheist"           # debe coincidir con uno de los PersonaKey
display_name = "Mi Ana"
language = "es"
tone = "skeptical"
core_beliefs = ["..."]
typical_doubts = ["..."]
profile_md = """..."""
```

Y exporta `JW_SPAR_PERSONA_DIR=/ruta/al/dir`.

## Feedback engine

Al cerrar la sesión, cada turno del USUARIO recibe:

- **`citation_quality`**:
  - `strong`: cita `wol.jw.org` o un código de publicación (`w23.04`,
    `g23`, `bh`, `jt`, etc.).
  - `weak`: solo cita Bíblica (sin publicación).
  - `missing`: ni Biblia ni publicación.
- **`nli_verdict`** (opt-in con `JW_META_NLI=auto`): entails / neutral /
  contradicts / skipped. Usa el provider F39 default.
- **`suggested_phrasing`** cuando `citation_quality == missing` o cuando
  hay contradicción con la fuente esperada.

El `score_summary` agrega ratios:

```json
{
  "turns": 5,
  "citation_strong_ratio": 0.4,
  "citation_weak_ratio": 0.2,
  "citation_missing_ratio": 0.4,
  "nli_entails_ratio": 0.0,
  "nli_contradicts_ratio": 0.0
}
```

## Memoria por sesión (F61)

Cada `start_session` / `take_turn` / `close_session` mira a un
`MemoryStore` opcional. Si se pasa, los turnos del usuario se persisten
como `kind="question"` y los del persona como `kind="answer"`. La
preferencia inicial (`persona`+`language`) se guarda como
`kind="preference"`. El cierre emite un `kind="fact_recalled"`.

Útil para:
- Recuperar conversaciones entre procesos.
- Audit trail localizado de práctica.
- Pasar contexto al meta-orquestador F65 vía F61.

## Arquitectura

```
        jw spar / MCP tools
                │
                ▼
   ┌─────────────────────────┐
   │  start_session(persona) │── MemoryStore F61 (opt)
   │  -> SparSession         │
   └──────────┬──────────────┘
              │
              ▼
   ┌─────────────────────────┐
   │  take_turn(sid, text)   │
   │   - append UserTurn     │
   │   - simulate_persona_turn
   │     - Jinja2 prompt     │
   │     - LLM acomplete     │
   │     - JSON parse        │
   │   - append PersonaTurn  │
   └──────────┬──────────────┘
              │
              ▼ (repeat up to JW_SPAR_MAX_TURNS)
              │
   ┌─────────────────────────┐
   │  close_session(sid)     │
   │   - score_session       │
   │     - citation_quality  │
   │     - NLI F39 (opt)     │
   │     - score_summary     │
   └─────────────────────────┘
```

## Disclaimer ético

El CLI marca explícitamente en `jw spar start`:

```
PRACTICA - esto NO es una visita real. Sin guardado remoto.
```

Las personas son arquetipos para entrenamiento, NO retratos de
individuos reales. Si una persona dice algo que parece estereotipado,
el feedback engine debe corregirlo del lado del USUARIO con
`suggested_phrasing`, no del lado del persona.

## Voice mode (F66 post-MVP)

`jw spar voice-turn <sid>` enlaza ASR F34 + LLM persona + TTS F34 en una
sola llamada:

```bash
jw spar voice-turn spar-a1b2c3d4 \
  --audio-in user_turn.wav \
  --audio-out persona_reply.wav \
  --asr-model base \
  --tts-provider edge
```

El audio del usuario se transcribe localmente con Whisper, se manda al
LLM persona, y la respuesta se sintetiza con TTS al `--audio-out`. El
audio nunca sale del disco; el LLM recibe solo la transcripción
textual. Si las deps F34 (faster-whisper / Kokoro / edge-tts) no están
instaladas, el comando emite `VoiceModeError` con exit code 1.

Inyección para tests: `take_voice_turn(..., transcribe_fn=, synthesize_fn=)`.

## Markdown export del transcript (F66 post-MVP)

```bash
# Solo transcript .md (no JSON en stdout)
jw spar show spar-a1b2c3d4 --export transcript.md

# Al cerrar: imprime JSON + escribe MD
jw spar close spar-a1b2c3d4 --export transcript.md
```

El MD incluye persona, turnos, feedback, score_summary y el disclaimer
"PRÁCTICA - esto NO es una visita real".

## Multi-idioma: variantes por persona (F66 post-MVP)

Cada persona puede tener variantes por idioma usando el sufijo
`_<lang>` en el nombre del archivo TOML:

```
personas/
  catholic.toml          # default (es)
  catholic_en.toml       # variant en
  catholic_pt.toml       # variant pt
```

Resolución:
- `get_persona("catholic")` → `catholic.toml` (es default)
- `get_persona("catholic", language="en")` → `catholic_en.toml`
- `get_persona("catholic", language="fr")` → fallback a `catholic.toml`

Los **6 personas builtin tienen variantes completas en es/en/pt** (18
TOMLs en total).

## Tool `spar.session` en meta-orchestrator F65 (post-MVP)

Registrado en `jw_agents.meta.builtin_tools` como adapter que envuelve
`start_session` + N `take_turn` + `close_session` + `score_session` en
una sola llamada. Permite al meta-orchestrator componer un plan como:

```json
{"steps": [
  {"id": "step-1", "tool": "spar.session",
   "args": {"persona": "atheist", "language": "es",
            "user_turns": ["Hola", "Como dice w23.04..."]}}
]}
```

## Golden conversations (F66 post-MVP)

`packages/jw-agents/tests/spar/fixtures/conversations/*.jsonl` registra
escenarios de regresión que corren contra `FakeSparLLM` determinista.
Cada línea declara persona + turns + assertions sobre la respuesta y
el citation_quality esperado. Cambiar el fake o las personas hace
visible el cambio en el diff del test.

## Estado actual

- 6 personas builtin con **variantes completas es/en/pt** (18 TOMLs).
- Simulator con `FakeSparLLM` determinista (detección por display_name
  con word-boundary regex).
- Reuso F65 `llm_factory` cuando `JW_SPAR_LLM!=fake`.
- F61 MemoryStore wire-up opt-in.
- Feedback engine con citation_quality + NLI F39 opt-in.
- CLI `jw spar {personas,start,turn,show,close,voice-turn}`.
- MCP: 4 tools nuevas.
- Voice mode F34: ASR + TTS via `take_voice_turn`.
- Markdown export del transcript.
- Tool `spar.session` registrada en F65 meta-orchestrator.
- Golden conversations de regresión.
- **56 tests passing** (models 7 + personas 4 + multilang 7 + simulator 4 +
  session 9 + feedback 7 + voice 2 + export 3 + golden 4 + meta 2 +
  CLI 4 + MCP 3).

## Pendiente (futuro)

- Persistencia de session.sqlite cross-process (hoy solo memoria).
- Persona moderation suite: review humano periódico de los TOMLs para
  evitar drift hacia estereotipos.
