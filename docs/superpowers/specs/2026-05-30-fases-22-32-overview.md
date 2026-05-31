# Plan maestro Fases 22-32 — 11 features para cerrar el ecosistema de discipulado

> **Fecha**: 2026-05-30
> **Estado**: Índice de planificación. Cada fase tiene (o tendrá) su propio spec hijo.
> **Owner**: Elias
> **Documentos hijos**: `2026-05-30-fase-22-*.md` … `2026-05-30-fase-32-*.md`

## Contexto

Las Fases 0-21 ya entregaron 13/13 de [VISION.md](../../VISION.md) más JW Library y Obsidian (551 tests verdes, ~60 herramientas MCP, 12 agentes). Quedan 11 huecos identificados que cierran el bucle de discipulado activo y la infraestructura de confianza. Este documento los organiza en **Tiers** (no fases lineales obligatorias — pueden paralelizarse dentro del mismo tier).

## Principios duros que TODAS las fases respetan

Heredados del proyecto y no negociables:

1. **Sin LLM en el camino crítico** — parsers, agentes y stores deterministas. El LLM sintetiza prosa fuera del toolkit.
2. **Citas verificables siempre** — cada `Finding` lleva `metadata['source']` y URL canónica de wol.jw.org.
3. **Local-first** — toda persistencia personal en `~/.jw-agent-toolkit/`, SQLite cifrable.
4. **Sin red en tests** — fixtures + cassettes; tests CPU-only.
5. **Multilenguaje desde el día 1** — `en`/`es`/`pt` mínimo con fallback elegante.
6. **No sustituir la palabra de los ancianos** — los agentes orientan/informan, no aconsejan pastoralmente.
7. **No tracker de hermanos sin opt-in** — datos personales (revisitas, estudiantes) son local-only.

## Tier 1 — Infraestructura de confianza

**Por qué primero**: cada feature posterior aumenta el riesgo de alucinación doctrinal y de link-rot si no hay medición. Construir estos dos antes convierte "confío en mí" en métrica auditable.

### Fase 22 — Eval doctrinal regresión (#9)

- **Qué**: paquete `jw-eval` con suite de Golden Q&A calificadas automáticamente contra citas wol.jw.org. Métrica de regresión por cada cambio de prompt/modelo/RAG.
- **Reutiliza**: `fact_checker` (4 veredictos), `jw_core.clients.wol`, CI workflow (Fase 10).
- **Entregable**: 50+ Q&A doradas, runner `pytest -m eval`, dashboard de score, alarmas en CI.
- **Spec hijo**: `2026-05-30-fase-22-eval-doctrinal.md`

### Fase 23 — Citation integrity validator (#10)

- **Qué**: módulo `jw_core.citations.validator` que verifica que cada URL wol que produce un agente resuelve y que el docId↔pub_code sigue mapeando.
- **Reutiliza**: `meps_catalog` (Fase 19), `telemetry` (Fase 9, contraparte input).
- **Entregable**: validador batch + tool MCP `validate_citations`, integrado al smoke test de cada agente.
- **Spec hijo**: `2026-05-30-fase-23-citation-validator.md`

## Tier 2 — Alto valor recurrente

### Fase 24 — Conductor "Disfruta de la vida para siempre" (#1)

- **Qué**: agente `study_conductor` + store local `study_progress`. Lifecycle del libro de estudio actual: preparar cada lección, anticipar preguntas del estudiante, sugerir versículos de apoyo, registrar lecciones completadas y metas (asistencia, dejar un vicio, bautismo).
- **Reutiliza**: `revisit_tracker` (patrón store), `kids_resources`, `personal_notes`, parser EPUB/JWPUB para extraer las lecciones del libro `lff` cuando esté disponible.
- **Entregable**: agente + store cifrable (Fase 11) + tool MCP + guía.
- **Spec hijo**: `2026-05-30-fase-24-study-conductor.md`

### Fase 25 — Monitor de novedades jw.org (#5)

- **Qué**: agente periódico `whats_new` que detecta publicaciones nuevas, videos JW Broadcasting y programa mensual; entrega digest por semana/mes.
- **Reutiliza**: `pub_media`, `mediator`, `broadcasting`, `weblang`, telemetría drift (input).
- **Entregable**: scheduler local opcional + reporte markdown + tool MCP `news_digest`.
- **Spec hijo**: `2026-05-30-fase-25-news-monitor.md`

## Tier 3 — Especializado pero único

### Fase 26 — Asistente de partes del estudiante V&M (#2)

- **Qué**: agente `student_part_helper`. Tipos: lectura de la Biblia, empezar conversaciones, revisita, demostración de estudio bíblico. Cada uno con su guión pedagógico y enganche al **punto de oratoria del mes**.
- **Reutiliza**: `workbook_helper` (comentarios), `public_talk_outline`, `conversation_assistant`.
- **Entregable**: agente con 4 tipos de asignación + outline por tipo + tool MCP.
- **Spec hijo**: `2026-05-30-fase-26-student-parts.md`

### Fase 27 — Informe mensual de precursor (#3)

- **Qué**: módulo `jw_core.ministry.field_report` agregador horas + cursos + revisitas. Solo precursores (regulares/auxiliares) — para publicadores el informe es solo participación.
- **Reutiliza**: `revisit_tracker` (Fase 12), `personal_notes`, cifrado (Fase 11).
- **Entregable**: CLI `jw report --month`, export PDF/CSV, tool MCP.
- **Spec hijo**: `2026-05-30-fase-27-pioneer-report.md`

### Fase 28 — Concordancia exacta NWT + publicaciones (#7)

- **Qué**: índice FTS5 sobre corpus ya descifrado (NWT + JWPUB) con búsqueda literal de palabra/frase. Determinista, complementa el RAG semántico.
- **Reutiliza**: chunker, `jw_core.parsers.jwpub` (descifrado), `personal_notes` (FTS5 ya en uso).
- **Entregable**: tool MCP `exact_concordance`, CLI `jw grep`, índice incremental.
- **Spec hijo**: `2026-05-30-fase-28-concordance.md`

## Tier 4 — Capas de UX / nicho

### Fase 29 — Compositor de carta / teléfono / carrito (#4)

- **Qué**: agente `letter_composer` con plantillas para predicación por carta, guion telefónico, y conversación de carrito (cart witnessing). Personalizable por territorio.
- **Reutiliza**: `presentation_builder` (6 audiencias), `conversation_assistant`, `topic_index`.
- **Spec hijo**: `2026-05-30-fase-29-letter-composer.md`

### Fase 30 — Compañero de cánticos del Reino (#8)

- **Qué**: módulo `jw_core.songs` con metadata (número, tema, textos en que se basa). Sin letra (copyright). Integración con `workbook_helper` para mostrar el cántico de cada reunión.
- **Reutiliza**: scraper workbook (Fase 11), `weblang`, `topic_index`.
- **Spec hijo**: `2026-05-30-fase-30-kingdom-songs.md`

### Fase 31 — Exportador hoja de estudio PDF/DOCX/Anki (#11)

- **Qué**: convertir `AgentResult` con findings → entregable imprimible (PDF/DOCX) o mazo Anki para repaso espaciado.
- **Reutiliza**: skills `pdf`/`docx`/`pptx`, `flashcards` SM-2 (Fase 14), bridge Obsidian (Fase 20).
- **Spec hijo**: `2026-05-30-fase-31-exporter.md`

### Fase 32 — Asistente informativo de temas de vida (#6)

- **Qué**: agente `life_topics` enfocado en "qué dice la Biblia sobre ansiedad/duelo/matrimonio". Framing: orientación con citas, **no** consejería pastoral.
- **Reutiliza**: `research_topic`, `topic_index`, `conversation_assistant` (catálogo de objeciones — patrón).
- **Spec hijo**: `2026-05-30-fase-32-life-topics.md`

## Diagrama de dependencias

```
                          ┌────────────────────────────────┐
                          │  Tier 1 (build primero)        │
                          │  • Fase 22 (eval doctrinal)    │
                          │  • Fase 23 (citation validator)│
                          └────────────┬───────────────────┘
                                       │ (todas las fases posteriores
                                       │  se miden con Fase 22)
                                       ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  Tier 2 — paralelizable                                                  │
│  • Fase 24 (conductor estudio) ── usa store cifrado (Fase 11)            │
│  • Fase 25 (news monitor)      ── usa pub_media/mediator/broadcasting    │
└────────────────────────────────────┬─────────────────────────────────────┘
                                     │
                                     ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  Tier 3 — paralelizable, depende parcialmente de Tier 2                  │
│  • Fase 26 (student parts)    ── usa workbook_helper                     │
│  • Fase 27 (pioneer report)   ── usa revisit_tracker                     │
│  • Fase 28 (concordance)      ── usa parsers JWPUB                       │
└────────────────────────────────────┬─────────────────────────────────────┘
                                     │
                                     ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  Tier 4 — capa final                                                     │
│  • Fase 29 (letter composer)                                             │
│  • Fase 30 (kingdom songs)    ── depende Fase 30 para integrar en Fase 24│
│  • Fase 31 (exporter)         ── escribe sobre cualquier AgentResult    │
│  • Fase 32 (life topics)                                                 │
└──────────────────────────────────────────────────────────────────────────┘
```

## Estimación y secuencia recomendada

| Tier | Fase | Tamaño | Bloqueantes |
|---|---|---|---|
| 1 | 22 — eval doctrinal | M (~5-7d) | — |
| 1 | 23 — citation validator | S (~2-3d) | — |
| 2 | 24 — study conductor | L (~7-10d) | Fase 22 (para medir) |
| 2 | 25 — news monitor | M (~4-5d) | — |
| 3 | 26 — student parts | M (~4-5d) | — |
| 3 | 27 — pioneer report | S (~2-3d) | — |
| 3 | 28 — concordance | S (~2-3d) | — |
| 4 | 29 — letter composer | M (~3-4d) | — |
| 4 | 30 — kingdom songs | S (~2d) | — |
| 4 | 31 — exporter | M (~3-4d) | — |
| 4 | 32 — life topics | S (~2-3d) | Fase 32 solapa parcial con #6 |

**Total estimado**: ~40-55 días de trabajo si secuencial; ~25-35 con paralelización tier-interna.

## Política de ramificación

Cada Fase X tiene:
- Spec en `docs/superpowers/specs/2026-05-30-fase-X-<slug>-design.md`.
- Plan de implementación en `docs/superpowers/plans/2026-05-30-fase-X-<slug>-plan.md`.
- Branch `feature/fase-X-<slug>`.
- PR independiente con audit 1:1 contra la sección de VISION.md correspondiente (donde aplique).

## Lo que NO está en este plan

Conscientemente fuera de scope (riesgo legal / política JW / fuera del foco):

- Cualquier feature comunitaria que recolecte datos sin opt-in.
- Directorio de hermanos/asignaciones de congregación.
- Almacenamiento centralizado de notas personales sin E2E.
- Sustitución de la consejería de los ancianos.
- Distribución de letra de cánticos (copyright).
- Distribución de pesos de modelos fine-tuned (cubierto en `jw-finetune` — local-only).

## Siguiente paso

Brainstorming detallado de **Fase 22 — Eval doctrinal regresión** (Tier 1, sin bloqueantes, protege todo lo demás). Salida: spec hija aprobada por el usuario antes de tocar código.
