# Master Plan — Integración de stars seleccionadas (F57-F66)

> **No es plan ejecutable.** Es el documento maestro que coordina los 6 sub-planes de integración derivados del análisis de stars (jun 2026). Cada sub-plan vive en su propio archivo y es ejecutable de forma independiente con `superpowers:executing-plans` o `superpowers:subagent-driven-development`.

**Goal:** Integrar 7 piezas externas seleccionadas tras filtrado JW-first (5 reales + 2 hallazgos JW-específicos), respetando la decisión arquitectónica del proyecto: *"LLM no en camino crítico; agentes procedurales; local-first; API keys son opt-in"*.

**Origen del scope:** [`docs/conceptos/integraciones-priorizadas.md`](../../conceptos/integraciones-priorizadas.md) (análisis 2026-06-04 sobre 2675 stars de las cuentas `eliascipre` y `elimorals`).

**Spec/origen brainstorm:** conversación 2026-06-04 con el autor, 4 iteraciones de filtrado hasta criterio brutal "¿aporta valor a procesar contenido JW real?".

---

## Fases incluidas

| Fase | Slug | Origen externo | Mode | Riesgo | LOC est. |
|---|---|---|---|---|---|
| **F57** | `jw-meeting-media` | `sircharlo/meeting-media-manager` (207★) | Port + nueva ventana Tauri | Medio | ~2500 |
| **F58** | `bible-knowledge-graph` | NO se porta upstream — versión **propia JW** desde Insight + NWT | Construcción JW-pura | Medio | ~1800 |
| **F61** | `letta-memory-adapter` | `letta-ai/letta` (23k★) | Adapter opt-in en `jw-agents/memory/` | Bajo | ~600 |
| **F62** | `marker-markitdown-loaders` | `datalab-to/marker` (36k★) + `microsoft/markitdown` (144k★) | Adapter en `jw-rag/loaders/` | Bajo | ~800 |
| **F64** | `whisperx-asr` | `m-bain/whisperX` (22k★) | Nuevo `ASRProvider` en `jw_core.audio.asr_providers` | Bajo | ~500 |
| **F66** | `mcp-jw-brain` | `neo4j-contrib/mcp-neo4j` (955★) como referencia | Tools `@mcp.tool` en `jw_mcp/server.py` envolviendo `jw_brain.server` | Trivial | ~300 |

Total estimado: ~6500 LOC nuevas + ~250 tests nuevos.

---

## Orden recomendado de ejecución

Dependencias mutuas son débiles. Orden propuesto por **valor entregado por unidad de esfuerzo**:

1. **F66** (trivial, 4h) — gana exposición MCP del `jw-brain` ya existente. Cero riesgo.
2. **F58** (~3-4 semanas) — entrega el KG bíblico que enriquece todas las queries de `jw-brain`. Habilita F66 con datos reales.
3. **F62** (~1 semana) — adapters de OCR para extender corpus historico.
4. **F64** (~1 semana) — diarización de discursos/asambleas para alimentar `jw-rag`.
5. **F61** (~1 semana) — memoria conversacional para `conversation_assistant` y futuro asistente de estudio.
6. **F57** (~4-6 semanas) — la más compleja por la ventana Tauri y el descubrimiento dinámico de programa semanal de jw.org.

> **Hito sugerido tras F58 + F66**: release `v0.7.0` (todo el cluster grafo/MCP termina cohesivo). F62/F64/F61/F57 pueden ir en `v0.8.0` por trimestre.

---

## Decisiones globales (NO repetir en cada sub-plan)

Cada sub-plan asume y respeta:

### Convenciones del repo
- **Python 3.13**, `uv workspace`, hatchling, `ruff` (line-length 120, `quote-style="double"`), `mypy strict` (no bloquea CI), `pytest-asyncio` (auto mode), `pytest-recording` para cassettes.
- **Naming de commits**: `<type>(<scope>): F##[.#] <descripción>` con `plus` en lugar de `+` para concatenar (precedente en `git log`).
- **Tests pattern**: cada package tiene `tests/` con `conftest.py` propio. Fixtures HTML en `tests/fixtures/`. Asyncio sin decorador.
- **CI bloqueante**: solo `ruff lint` + `ruff format --check` + `pytest`. Mypy y bandit `continue-on-error`.

### Patrón `extras_require` granular
Cada integración pesada NUEVA va detrás de un extra explícito en el `pyproject.toml` del paquete dueño. NO inflar la instalación base. Convención de naming de extras:
- F58: `bible-kg = ["lxml>=5.0"]` (opcional, parsea Insight más rápido)
- F61: `memory-letta = ["letta-client>=0.x"]`
- F62: `pdf-marker = ["marker-pdf>=x"]`, `doc-markitdown = ["markitdown[all]>=x"]`
- F64: `asr-whisperx = ["whisperx>=x"]`
- F66: sin extra nuevo (solo wraps tools existentes)

### Patrón "LLM no en camino crítico"
- Loaders de F58 son **procedurales/deterministas** (parser de Insight HTML → upserts directos). El `LLMExtractor` de `jw-brain` se reserva para corpus narrativo (Atalayas), no para datos canónicos bíblicos.
- F61 (letta) va como `MemoryStore` Protocol con backend `letta` cargado on-demand y backend `FakeMemoryStore` por defecto. Sin letta instalado el toolkit funciona idéntico.
- F62 (marker/markitdown) NO usan VLM remoto en path crítico — modo local CPU por defecto, GPU opcional.

### Patrón privacy-first (F61)
F61 reusa el patrón ya validado por `RevisitStore` (`packages/jw-agents/src/jw_agents/revisit_tracker.py:75`) y `StudentProgress` (`packages/jw-agents/src/jw_agents/study_progress.py`):
- Sqlite en `~/.jw-agent-toolkit/<feature>.db`
- Opt-in Fernet via env var (`JW_MEMORY_KEY` para F61)
- Consent `y/N` cuando aplica
- NO subir nada a la nube por default

### Licencias y atribución
Verificadas para todas las TIER S:
- **Marker** Apache-2.0 ✓ commercial-safe
- **Markitdown** MIT ✓ commercial-safe
- **WhisperX** BSD-4-Clause — atención si redistribuyes binarios; usar como dep
- **Letta** Apache-2.0 ✓ commercial-safe
- **mcp-neo4j** Apache-2.0 ✓ (no se redistribuye, solo se usa como referencia de patrón)
- **F58 (KG propio)**: no hay terceros — datos derivados del Insight on the Scriptures (publicación oficial JW de Watch Tower Bible and Tract Society). Atribución obligatoria en `docs/conceptos/bible-knowledge-graph.md`: *"datos derivados de la Versión Watch Tower de la Biblia (NWT/NWTsty) y de Estudio Perspicaz de las Escrituras (Insight on the Scriptures), © Watch Tower Bible and Tract Society of Pennsylvania."* y aclarar que el toolkit NO redistribuye el texto, solo los metadatos que el usuario genera localmente a partir de su propio JWPUB/EPUB descargado de jw.org.

---

## Cruces entre fases (qué desbloquea qué)

```
F58 (Bible KG) ──┬──> F66 (expose jw-brain via MCP)  ── datos reales para consultas Cypher
                 └──> F61 (memoria conversacional)   ── contexto bíblico para recall

F62 (marker/markitdown) ──> F58 (loader puede leer PDFs históricos del Insight pre-EPUB)
                       ──> F61 (jw-rag se extiende a docs Office compartidos)

F64 (whisperX) ──> F61 (transcribir notas de voz dictadas)
              ──> F57 (transcribir comentarios de la reunión en vivo)

F57 (jw-meeting-media) ──> usa F20 (linkify), F51 (organized-app), F53 (omnilingual-ASR)
```

Si se sigue el orden recomendado arriba, **ningún sub-plan tiene un bloqueante real** sobre otro (cada uno define `Fake*` backend para tests).

---

## Sub-planes (links)

- [F58 — Bible Knowledge Graph JW-puro](./2026-06-04-fase-58-bible-knowledge-graph-plan.md) ✅ redactado (12 tasks, ~25 tests)
- [F66 — `jw-brain` expuesto vía MCP](./2026-06-04-fase-66-mcp-jw-brain-plan.md) ✅ redactado (5 tasks, ~5 tests)
- [F62 — `marker` + `markitdown` loaders](./2026-06-04-fase-62-marker-markitdown-plan.md) ✅ redactado (8 tasks, ~9 tests)
- [F64 — `whisperX` ASR provider](./2026-06-04-fase-64-whisperx-asr-plan.md) ✅ redactado (6 tasks, ~10 tests)
- [F61 — Letta memory adapter opt-in](./2026-06-04-fase-61-letta-memory-plan.md) ✅ redactado (7 tasks, ~23 tests)
- [F57 — `jw-meeting-media` subpkg (clean-room)](./2026-06-04-fase-57-jw-meeting-media-plan.md) ✅ redactado (13 tasks, ~40 tests)

Cuando todos estén redactados, este documento listará cada uno como ✅ y describirá brevemente lo que entrega.

---

## Lo que NO está en este master plan

Para mantener foco brutal (ver `docs/conceptos/integraciones-priorizadas.md` — "Re-evaluación honesta"):

- ❌ LiteLLM gateway, MeloTTS, LightRAG, kuzu, mlx-vlm, PaddleOCR, olmocr, langfuse, theographic-upstream-port, LlamaFactory, Composio, context7, mlx-audio: descartados por duplicación, contradicción local-first, o falta de valor JW real.
- ❌ langchain/autogen/crewAI/smolagents en core: rompen la arquitectura "agentes procedurales determinísticos".
- ❌ Frameworks de RL, diffusion, sign-language: scope creep masivo, fuera de v0.8.

Si algún día se reconsidera, abrir nuevo análisis (`docs/conceptos/integraciones-priorizadas.md` v2026-12).

---

## Cómo usar este master plan

1. Lee este doc para entender el panorama completo y las decisiones globales.
2. Pickea el sub-plan a ejecutar.
3. En el sub-plan, sigue `superpowers:subagent-driven-development` (recomendado) o `superpowers:executing-plans`.
4. Cada sub-plan es **standalone**: sus tests pasan y entrega valor por sí solo, aunque los demás aún no estén integrados.
5. Cuando completes una fase, actualiza el estado en la tabla de "Sub-planes" arriba **y** en `docs/ROADMAP.md`.

---

## Estado de redacción de los planes

| Sub-plan | Redactado | Ejecutado | PR |
|---|---|---|---|
| F58 — bible-knowledge-graph | ✅ 2026-06-04 | ✅ 2026-06-05 | — |
| F66 — mcp-jw-brain | ✅ 2026-06-04 | ✅ 2026-06-04 | — |
| F62 — marker-markitdown | ✅ 2026-06-04 | ⬜ | — |
| F64 — whisperx-asr | ✅ 2026-06-04 | ⬜ | — |
| F61 — letta-memory | ✅ 2026-06-04 | ⬜ | — |
| F57 — jw-meeting-media | ✅ 2026-06-04 | ⬜ | — |

**Total**: 6 planes, ~51 tasks bite-sized, ~112 tests nuevos esperados.
