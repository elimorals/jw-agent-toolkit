# Fases 65-76 — IA agéntica, multimodal, ML predictivo y voz: overview

> **Fecha**: 2026-06-11
> **Estado**: Familia de diseño aprobada (specs individuales pendientes de implementación)
> **Owner**: Elias
> **Tier**: 1 (kernel agéntico) + 2 (multimodal/ML) + 3 (voz)
> **Documento padre**: este overview
> **Predecesores conceptuales**:
> - Fase 34 (`audio-premium`) — TTS multi-provider + ASR
> - Fase 35 (`constrained-decoding`) — gramáticas + Pydantic
> - Fase 39 (`nli-runtime`) — fidelidad NLI con `FakeNLI`
> - Fase 41 (`plugin-sdk`) — 5 entry-points
> - Fase 43 (`agent-tracing`) — JSONL local-first
> - Fase 49 (`second-brain`) — GraphRAG + BrainDomain plugins
> - Fase 57 (`jw-meeting-media`) — presenter + multi-congregación
> - Fase 61 (`memoria-asistente`) — `MemoryStore` con 3 backends
> - Fase 62 (`historical-pdf-ingest`) — Atalayas escaneadas al RAG
> - Fase 64 (`asr-diarizacion`) — WhisperX + speakers

## Contexto

Tras Fase 64 el toolkit cubre 100% de [`VISION.md`](../../VISION.md) y tiene
1887+ tests passing. Las siguientes 9 fases atacan **necesidades reales
no cubiertas** identificadas en revisión 2026-06-11:

1. Los 12 agentes existentes son **silos** — no hay orquestación de
   alto nivel que cosa `workbook_helper → public_talk_outline →
   slides → tts` en un solo flujo "prepara mi domingo".
2. La **predicación** se entrena hoy solo con objeciones estáticas;
   no hay sparring interactivo voz-a-voz contra personas simuladas.
3. La **apologética** ranquea fuentes pero no expone el árbol de
   razonamiento ni lo verifica paso a paso con NLI Fase 39.
4. El **discurso del estudiante** se prepara con `student_part_helper`
   (50 counsel points) pero no hay autoevaluación del audio grabado.
5. **JW Broadcasting** se busca solo por transcripción; sin
   búsqueda visual frame-level.
6. La **desinformación visual** (memes / screenshots con citas falsas)
   no se verifica — `apocrypha_detector` solo lee texto pegado.
7. El **libro físico** queda fuera del toolkit (publicador mayor,
   recién interesado sin app, niño aprendiendo a leer).
8. La **evolución doctrinal** ("luz creciente") no se rastrea
   automáticamente entre décadas — útil para responder honestamente
   "antes decían X, ahora dicen Y".
9. El **TTS** es genérico — niños y ancianos preferirían oír la
   Biblia en voz familiar consentida.

Esta familia entrega esas 9 capacidades agrupadas en **4 capas
técnicas** que reusan al máximo lo construido en Fases 0-64.

## Tabla de fases

| Fase | Nombre                         | Capa | Esfuerzo | Reusa principal             | Tier |
|------|--------------------------------|------|----------|-----------------------------|------|
| 65   | `meta-orchestrator`            | A    | Bajo     | Todos los agentes F11-F64   | 1    |
| 66   | `conversation-sparring`        | A    | Medio    | F22, F39, F61, F34          | 1    |
| 67   | `doctrinal-reasoner`           | A    | Medio    | F35, F39, F43               | 1    |
| 68   | `talk-lab` (coach oratoria)    | B    | Medio    | F64, F39, F31, F26          | 2    |
| 69   | `broadcasting-visual-index`    | B    | Alto     | F49, F62, F53 polyglot      | 2    |
| 70   | `image-quote-verifier`         | B    | Bajo     | OCR, F39, RAG, apocrypha    | 2    |
| 71   | `book-camera`                  | B    | Medio    | OCR, F47 jw-core-js, TTS    | 2    |
| 72   | `doctrinal-drift`              | C    | Alto     | F49, F62, RAG híbrido       | 2    |
| 76   | `family-voice-clone`           | D    | Bajo     | F34, F43, F61               | 3    |

**Por qué F73-F75 saltados**: reservados para fases interreligiosas
del refactor `faith-core` documentado en
[`docs/conceptos/extrapolar-a-otras-religiones.md`](../../conceptos/extrapolar-a-otras-religiones.md).

## Agrupación por capa técnica

### Capa A — Agéntica / orquestación (F65-F67)

Eleva la arquitectura procedural existente a un nivel meta: orquestar
agentes, simular interlocutores, exponer razonamiento auditable.

```
F65 meta_orchestrator                  ─┐
F66 conversation_sparring               │  Capa A: agéntica
F67 doctrinal_reasoner (CoT verificable)─┘
                │
                ▼
        ┌──────────────────────────────┐
        │  Agentes F11-F64 existentes  │
        │  (verse_explainer,           │
        │   apologetics,               │
        │   workbook_helper, ...)      │
        └──────────────────────────────┘
```

### Capa B — Multimodal / visión profunda (F68-F71)

Añade percepción audio-visual real al toolkit: prosodia + VLM + CLIP +
cámara en vivo. Reutiliza al máximo F36 `vlm-ocr` y F37 `colpali-visual`.

```
F68 talk_lab          (audio prosodia)
F69 broadcasting_vidx (frames + CLIP)
F70 image_quote_verif (memes + OCR)
F71 book_camera       (cámara live)
```

### Capa C — ML clásico / predictivo (F72)

Modelos analíticos no-LLM sobre el corpus diacrónico de publicaciones JW.

```
F72 doctrinal_drift   (embeddings temporales + DBSCAN)
```

### Capa D — Voz / accesibilidad (F76)

Workflow guiado de fine-tuning de voz familiar consentida.

```
F76 family_voice_clone (F5-TTS / XTTSv2)
```

## Diagrama de dependencias entre fases

```
                        ┌─────────────────────────────────┐
                        │  Agentes y módulos F11-F64      │
                        └────────────────┬────────────────┘
                                         │
                  ┌──────────────────────┼──────────────────────┐
                  │                      │                      │
                  ▼                      ▼                      ▼
              ┌───────┐             ┌─────────┐            ┌─────────┐
              │  F65  │             │   F66   │            │   F67   │
              │ meta  │             │ sparring│            │ reasoner│
              └───┬───┘             └────┬────┘            └────┬────┘
                  │                      │                      │
                  └──────────────────────┴──────────────────────┘
                                         │
                                         ▼ (todos los agentes pueden ser
                                            llamados desde meta-orchestrator)

  Capa B — multimodal (independientes entre sí, comparten F36/F37):
  ┌──────┐   ┌──────┐   ┌──────┐   ┌──────┐
  │ F68  │   │ F69  │   │ F70  │   │ F71  │
  │ talk │   │broad-│   │image-│   │ book-│
  │ lab  │   │cast  │   │quote │   │camera│
  └──────┘   └──────┘   └──────┘   └──────┘

  Capa C:                       Capa D:
  ┌──────┐                      ┌──────┐
  │ F72  │                      │ F76  │
  │drift │                      │voice │
  └──────┘                      └──────┘
```

**Sin ciclos**. F65 puede llamar a F66, F67, F68, F69, F70, F71, F72 y
F76 como tools opcionales, pero no al revés.

## Decisiones arquitectónicas comunes

Estas decisiones se aplican a TODAS las fases de esta familia para
mantener consistencia con las 64 fases previas:

### D1 — Local-first sin telemetría externa por defecto

Todas las fases respetan [`docs/guias/privacidad-local-first.md`](../../guias/privacidad-local-first.md).
Los modelos pesados (VLM, CLIP, F5-TTS, embeddings temporales) corren
en CPU/GPU local o en API opt-in con `JW_*_PROVIDER` env. Ningún audio,
imagen o nota personal sale del disco sin consentimiento explícito.

### D2 — Reutilizar el Plugin SDK Fase 41

Cuando una fase añade un componente intercambiable (LLM provider,
VLM provider, embedder temporal, voice cloning backend), va por
entry-points existentes:

- `jw_agent_toolkit.gen_providers` para LLMs nuevos.
- `jw_agent_toolkit.vlm_providers` para VLMs (F69, F70, F71).
- `jw_agent_toolkit.embedders` para embeddings temporales (F72).
- `jw_agent_toolkit.agents` para los nuevos agentes (F65, F66, F67, F68).

No se inventan entry-points nuevos en esta familia.

### D3 — NLI Fase 39 como guardrail por defecto

Toda salida que cite fuentes JW pasa por `@fidelity_wrap` (F39) en
modo `warn` por defecto. F67 reasoner lo eleva a `reject` explícitamente.
F70 image-quote-verifier lo usa para emitir el veredicto.

### D4 — Tracing Fase 43 obligatorio

Cada nuevo agente emite traza JSONL con cada decisión interna
(`kept/dropped/warn/step`). Habilitable por flag `--trace` y CLI
`jw trace view`. Útil para auditar razonamiento (F67) y diagnosticar
fallos en orquestaciones complejas (F65).

### D5 — Constrained decoding Fase 35 para JSON estricto

Outputs estructurados (árbol de pruebas de F67, score timeline de F68,
verdict de F70, diff de F72) van por gramáticas GBNF + Pydantic.
Garantiza que cualquier LLM consumidor recibe JSON parseable sin
post-procesamiento.

### D6 — Polyglot Python F53 para dependencias pesadas

Modelos VLM (Llava-1.6, Qwen-VL-7B) y F5-TTS requieren torch+cuda
con cadencias de soporte distintas. Cada fase con dependencia ML
opcional se aísla en venv dedicado vía subprocess JSON (patrón ya
usado por F53 Omnilingual ASR).

### D7 — Memoria F61 para sesiones multi-turno

F65, F66 y F67 persisten estado de sesión vía `MemoryStore` Protocol
(SQLite default, Fernet opt-in con `JW_MEMORY_KEY`, Letta opt-in
multi-device).

### D8 — Multi-congregación F57.16 respetada

F65 meta-orchestrator y F68 talk-lab aceptan `congregation: str | None`
y resuelven contra `~/.jw-agent-toolkit/meetings/congregations.toml`.

## Motivación común

Estas 9 fases comparten **3 motivaciones de fondo**:

### M1 — Reducir fricción del usuario final

Hoy un publicador debe llamar 4-6 herramientas separadas para preparar
una reunión. F65 colapsa ese flujo a un solo comando `jw plan-sunday`.
F71 + F76 traen a usuarios que no tienen relación con el ecosistema
tecnológico (mayores, niños, recién interesados).

### M2 — Convertir el toolkit en superficie defendible

Coach de oratoria (F68), reasoner CoT (F67), drift doctrinal (F72)
no existen en ningún otro proyecto del ecosistema TJ open-source.
Son **diferenciadores únicos** que justifican la inversión hecha.

### M3 — Defensa contra desinformación creciente

Memes con citas falsas, screenshots descontextualizados, deepfakes
de hermanos. F70 (image-quote-verifier) y F66 (sparring con personas
simuladas) son tooling defensivo, no ofensivo: nadie ataca, todos se
preparan mejor.

## No-objetivos (boundaries vinculantes)

Las 9 fases comparten estos límites:

- **No** sustituyen la consejería pastoral de ancianos. Ya documentado
  para TJ en [`docs/guias/temas-de-vida.md`](../../guias/temas-de-vida.md)
  (F32); el patrón aplica especialmente a F66 (sparring) y F67
  (reasoner).
- **No** entrenan modelos sobre datos privados del usuario sin
  consentimiento explícito (F76 voice cloning ya tiene `consent.txt`
  desde F34; F68 talk-lab grabaciones de usuario nunca salen del
  disco).
- **No** indexan ni redistribuyen contenido propietario fuera de
  fair-use técnico (F69 broadcasting solo guarda timestamps + deep
  links, nunca frames cacheados).
- **No** introducen nuevas dependencias en `jw-core`. Toda dependencia
  ML pesada va por extras `[talk-lab]`, `[visual-search]`,
  `[voice-clone]`, etc.
- **No** rompen la suite existente. Cada PR cierra con `1887 + N tests
  passing`.

## Estrategia de roll-out

### Fase 0 — Validación (mes 1)

Solo F65 meta-orchestrator. Demuestra el patrón de orquestación sobre
los 12 agentes existentes. Sin modelo nuevo. Si F65 no genera tracción
medible (uso recurrente del comando `jw plan-sunday`), se cuestionan
las fases B+C+D.

### Fase 1 — Capa A completa (mes 2)

F66 + F67. La capa agéntica queda cerrada antes de tocar multimodal
(que requiere modelos pesados).

### Fase 2 — Multimodal alta-confianza (mes 3-4)

F68 (talk-lab) + F70 (image-quote-verifier). Ambos reutilizan modelos
ya integrados (F64 WhisperX, OCR Tesseract). Son quick wins que
desbloquean ROI antes de invertir en VLM nuevos.

### Fase 3 — Multimodal investigación (mes 5-6)

F69 (broadcasting frame-level) + F71 (book-camera). Requieren VLM
nuevos integrados via Plugin SDK F41. Riesgo medio.

### Fase 4 — ML clásico + voz (mes 7-8)

F72 (doctrinal-drift) + F76 (voice-clone). Cierre de la familia.
F72 requiere ingest histórico (F62) maduro. F76 requiere F34
audio-premium maduro.

## Métricas de éxito por capa

| Capa | Métrica primaria                                        | Umbral mínimo |
|------|---------------------------------------------------------|---------------|
| A    | Uso recurrente de `jw plan-sunday` en >50% sábados      | tracking opt-in via F25 news monitor pattern |
| A    | F67 reasoner: >85% de árboles aceptados por NLI=entails | golden set 30 preguntas multi-paso |
| B    | F68: correlación >0.7 con autoevaluación humana en 20 grabaciones | golden con anotación de 50 counsel points |
| B    | F70: precisión >90% en golden de 50 memes (25 reales + 25 falsos) | dataset cerrado |
| C    | F72: detección de ≥15 drifts confirmados en 50 años de Atalayas | 5 drifts anotados manualmente como ground truth |
| D    | F76: MOS >3.5 en evaluación familiar (3-5 evaluadores) | escala 1-5 |

## Riesgos comunes y mitigaciones

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|--------------|---------|------------|
| LLM API se vuelve caro al usar F65 frecuentemente | Media | Alto | Default Ollama local; tracing F43 reporta tokens. |
| F66 personas simuladas caricaturizan o ofenden | Media | Alto | Guardrail explícito: prompts pasan por NLI F39 antes de mostrar; CLI `--persona` requiere `--i-understand-this-is-roleplay`. |
| F67 reasoner alucina paso intermedio | Alta | Alto | Cada paso del árbol verificado con NLI F39 modo `reject`; si falla, se trunca y reporta. |
| F69 VLM consume disco (frames) | Alta | Medio | Solo timestamps + caption en disco; nunca el frame. |
| F70 falsos positivos contra ex-TJ legítimos | Baja | Alto | Veredicto siempre incluye `confidence` + texto original; el LLM consumidor decide presentación. |
| F72 drift mal-interpretado | Media | Alto | Output siempre con `wol_url` a ambas eras + nota explicativa Prov 4:18. |
| F76 voice-clone abuso | Baja | Muy alto | `consent.txt` obligatorio + audit trail F43 + license check siempre `personal_family_only`. |

## Especificaciones individuales

Cada fase tiene su propio design doc:

- [`fase-65-meta-orchestrator-design.md`](2026-06-11-fase-65-meta-orchestrator-design.md)
- [`fase-66-conversation-sparring-design.md`](2026-06-11-fase-66-conversation-sparring-design.md)
- [`fase-67-doctrinal-reasoner-design.md`](2026-06-11-fase-67-doctrinal-reasoner-design.md)
- [`fase-68-talk-lab-design.md`](2026-06-11-fase-68-talk-lab-design.md)
- [`fase-69-broadcasting-visual-index-design.md`](2026-06-11-fase-69-broadcasting-visual-index-design.md)
- [`fase-70-image-quote-verifier-design.md`](2026-06-11-fase-70-image-quote-verifier-design.md)
- [`fase-71-book-camera-design.md`](2026-06-11-fase-71-book-camera-design.md)
- [`fase-72-doctrinal-drift-design.md`](2026-06-11-fase-72-doctrinal-drift-design.md)
- [`fase-76-family-voice-clone-design.md`](2026-06-11-fase-76-family-voice-clone-design.md)

Planes implementacionales completos (TDD task-by-task) para las dos
fases prioritarias:

- [`../plans/2026-06-11-fase-65-meta-orchestrator-plan.md`](../plans/2026-06-11-fase-65-meta-orchestrator-plan.md)
- [`../plans/2026-06-11-fase-68-talk-lab-plan.md`](../plans/2026-06-11-fase-68-talk-lab-plan.md)

Los planes para F66, F67, F69-F72, F76 se redactarán al iniciar
implementación de cada una (decisión de no pre-cargar 9 planes
de 3000+ líneas que pueden quedar obsoletos por aprendizajes de F65
y F68).
