# Fase 72 — `doctrinal-drift`: analizador de evolución diacrónica de doctrinas

> **Fecha**: 2026-06-11
> **Estado**: Diseño aprobado (pendiente de implementación)
> **Owner**: Elias
> **Tier**: 2 (ML clásico)
> **Capa**: C — ML clásico / predictivo
> **Depende de**: F49 `second-brain` (GraphRAG), F62 `historical-pdf-ingest`, F33 `embed-rerank` (embeddings reales), F39 `nli-runtime`, RAG híbrido
> **Documento padre**: [`2026-06-11-fases-65-76-overview.md`](2026-06-11-fases-65-76-overview.md)
> **Predecesor conceptual**: F49 Second Brain (multi-era pero no analiza drift)

## Motivación

Las publicaciones de los Testigos de Jehová refinan entendimiento
doctrinal con el tiempo, consistente con el principio "la luz brilla
cada vez más" (Prov 4:18). Ejemplos documentados:

- "Generación que no pasará" (Mateo 24:34) — interpretación refinada
  varias veces entre 1925 y 2010.
- "Esclavo fiel y discreto" — definición precisada en 2013.
- "Babilonia la Grande" — concepto desarrollado a lo largo de
  décadas.
- "Príncipes" (Salmo 45:16) — re-clasificación posterior.

Hoy estos cambios solo se rastrean leyendo Atalayas década por
década manualmente.

Es útil para:
- **Estudio personal** — entender el desarrollo doctrinal.
- **Apologética honesta** — responder "antes decían X, ahora dicen
  Y" con citas verificables a ambas eras.
- **Investigación académica** — religious studies on adventist /
  millenarianism trajectories.

## Objetivos

1. CLI `jw drift "alma"` produce `DoctrinalDrift` que muestra cómo
   la enseñanza sobre un concepto evolucionó por décadas.
2. **Embeddings temporales**: cada chunk del corpus se embedea con
   su `(text, era)` para detectar shifts.
3. **Clustering DBSCAN** sobre embeddings por tema → identifica
   "core meaning" estables vs aspectos refinados.
4. **Output con citas verificables** a publicaciones de cada era +
   nota explicativa Prov 4:18.
5. Salida estructurada: timeline + diff por era + sumario en prosa.
6. Determinista bajo `JW_DRIFT_LLM=fake`.

## No-objetivos (boundaries vinculantes)

- **No** caracteriza cambios como "error" o "corrección". El framing
  es siempre **refinamiento** o **mayor claridad**, con cita a
  Prov 4:18.
- **No** se usa contra TJ. El output presenta la evolución; no
  emite veredicto.
- **No** detecta cambios doctrinales no fundamentados — requiere
  ≥3 publicaciones por era para reportar drift.
- **No** entrena un clasificador propio. Es análisis no-supervisado.
- **No** afirma intenciones humanas detrás del refinamiento — solo
  reporta el cambio observable en el corpus público.

## Decisión clave: ¿modelo de embeddings temporal-aware vs estático?

### Opción A — Embeddings estáticos (BGE-M3 / Voyage-3)

Cada chunk se embedea sin tag de era. La era se mete en metadata.

**Pros**: simple, modelos ya integrados en F33.
**Contras**: la similitud puede mezclar "núcleo estable" con "modo
de explicación de la era".

### Opción B — Embeddings temporal-aware (concat era tag al text)

`text_for_embedding = f"[era={decade}] {text}"`.

**Pros**: el modelo aprende a separar era + concepto.
**Contras**: requiere fine-tune para que funcione bien — sin
fine-tune, el tag puede ser ruido.

### Opción C — Doble embedding: estático + delta-cluster

Embedea estático (concepto) y luego clusteriza por (concepto,
era). El delta entre cluster centers entre eras = drift.

**Pros**: usa modelos existentes (F33) + análisis no-supervisado.
**Contras**: requiere ≥1000 chunks por tema para clusters estables.

### Decisión: **Opción C** (doble embedding + delta-cluster)

Justificación:
1. Reusa F33 embeddings reales sin re-entrenar.
2. DBSCAN no-supervisado es robusto a número de chunks variable.
3. Si el corpus es chico, falla con error claro en vez de inventar
   drift.

## Arquitectura

```
              query: "alma" / "generation" / "harvest"
                       │
                       ▼
          ┌─────────────────────────────┐
          │ 1. Sub-corpus extraction    │
          │    F49 GraphRAG: filtra     │
          │    todos los chunks con     │
          │    keyword + neighbors      │
          └────────────┬────────────────┘
                       │
                       ▼
          ┌─────────────────────────────┐
          │ 2. Era partitioning         │
          │    chunks → {era: list}     │
          │    eras: 1900s, 1910s, ...  │
          └────────────┬────────────────┘
                       │
                       ▼
          ┌─────────────────────────────┐
          │ 3. Embed all chunks (F33)   │
          │    BGE-M3 / Voyage real     │
          └────────────┬────────────────┘
                       │
                       ▼
          ┌─────────────────────────────┐
          │ 4. DBSCAN cluster per era   │
          │    → era_clusters[era] = [] │
          │    representative chunk     │
          │    per cluster              │
          └────────────┬────────────────┘
                       │
                       ▼
          ┌─────────────────────────────┐
          │ 5. Cluster alignment        │
          │    pair clusters across     │
          │    eras by cosine of centers│
          └────────────┬────────────────┘
                       │
                       ▼
          ┌─────────────────────────────┐
          │ 6. Drift events             │
          │    pair (era_a, era_b) with │
          │    delta > threshold        │
          │    → DriftEvent with cita   │
          └────────────┬────────────────┘
                       │
                       ▼
          ┌─────────────────────────────┐
          │ 7. LLM synth                │
          │    sumario por era + nota   │
          │    Prov 4:18                │
          └─────────────────────────────┘
```

## Contratos de tipos

```python
# packages/jw-core/src/jw_core/drift/models.py

from pydantic import BaseModel, Field
from typing import Literal

Era = Literal[
    "1900s", "1910s", "1920s", "1930s", "1940s", "1950s",
    "1960s", "1970s", "1980s", "1990s", "2000s", "2010s", "2020s",
]

class Citation(BaseModel):
    text: str
    wol_url: str | None = None
    pub_code: str
    year: int

class EraSnapshot(BaseModel):
    era: Era
    chunk_count: int
    representative_chunks: list[str]   # 2-3 chunks típicos
    representative_citations: list[Citation]
    cluster_count: int
    cluster_center_embedding_id: int   # índice en .npy local

class DriftEvent(BaseModel):
    from_era: Era
    to_era: Era
    cosine_delta: float                # distance between cluster centers
    significance: Literal["minor", "moderate", "major"]
    summary_change: str                # 1-2 sentences
    from_citation: Citation
    to_citation: Citation
    nli_verdict: Literal["entails", "neutral", "contradicts", "skipped"] = "skipped"

class DoctrinalDrift(BaseModel):
    query: str
    language: Literal["en", "es", "pt"]
    era_snapshots: list[EraSnapshot]
    drift_events: list[DriftEvent]
    summary_prose: str = ""
    explanatory_note: str              # ALWAYS includes Prov 4:18
    insufficient_data: bool = False
    eras_skipped_low_data: list[Era] = []
```

## API pública

```python
# packages/jw-core/src/jw_core/drift/__init__.py

from jw_core.drift.analyzer import analyze_doctrinal_drift
from jw_core.drift.models import (
    DoctrinalDrift,
    DriftEvent,
    EraSnapshot,
    Era,
    Citation,
)

__all__ = [
    "analyze_doctrinal_drift",
    "DoctrinalDrift",
    "DriftEvent",
    "EraSnapshot",
    "Era",
    "Citation",
]
```

## CLI

```bash
# Análisis básico
jw drift "alma"

# Limitar eras
jw drift "generation" --from 1920s --to 2020s

# Forzar idioma
jw drift "esperança" --language pt

# Exportar reporte
jw drift "soul" --export drift_soul.md
```

## MCP tools

- `analyze_doctrinal_drift(query, language="es", from_era=None, to_era=None) → DoctrinalDrift`

## Reuso de F49 Second Brain

El sub-corpus extraction en paso 1 reusa el GraphRAG de F49:

```python
from jw_core.brain import second_brain

def extract_drift_subcorpus(query: str, language: str) -> list[BrainChunk]:
    # Query expansion via GraphRAG
    expanded = second_brain.expand_query(query, language=language)
    chunks = second_brain.retrieve(
        query=expanded,
        top_k=500,                  # mucho más alto que default
        include_neighbors=True,     # 2-hop neighbors en grafo
        filters={"is_jw_pub": True},
    )
    return chunks
```

## Nota explicativa "luz creciente"

`packages/jw-core/src/jw_core/drift/explanatory_notes.py`:

```python
EXPLANATORY_NOTE_ES = """
Los Testigos de Jehová consideran que la comprensión doctrinal se
refina con el tiempo, en armonía con Proverbios 4:18: "Pero la senda
de los justos es como la luz brillante que va aumentando hasta que el
día queda firmemente establecido". Los cambios reportados aquí
reflejan ese refinamiento, no contradicciones. Cada cita enlaza a
wol.jw.org para verificación directa.
"""

EXPLANATORY_NOTE_EN = """
Jehovah's Witnesses understand that doctrinal understanding is
refined over time, in harmony with Proverbs 4:18: "But the path of
the righteous is like the bright morning light that grows brighter
and brighter until full daylight." The changes reported here reflect
that refinement, not contradictions. Each citation links to
wol.jw.org for direct verification.
"""

EXPLANATORY_NOTE_PT = """..."""
```

Esta nota va SIEMPRE en el output, antes del summary_prose.

## Significance scoring

```python
def classify_significance(cosine_delta: float, chunk_counts: tuple[int, int]) -> str:
    a, b = chunk_counts
    if min(a, b) < 5:
        return "minor"      # not enough signal
    if cosine_delta < 0.05:
        return "minor"
    if cosine_delta < 0.15:
        return "moderate"
    return "major"
```

## Plan de pruebas

| Caso                                                          | Tipo        |
|---------------------------------------------------------------|-------------|
| `Era` Literal acepta solo valores válidos                     | Unit        |
| `DriftEvent` Pydantic rechaza cosine_delta > 1                | Unit        |
| Sub-corpus extraction usa F49                                 | Integration |
| Era partitioning agrupa por año correctamente                 | Unit        |
| DBSCAN over fake embeddings produce N clusters                | Unit        |
| Cluster alignment empareja centers por cosine                 | Unit        |
| Significance classifier: 0.20 delta + 10/10 chunks → major    | Unit        |
| Insufficient data flag se setea con <3 eras                   | Unit        |
| Explanatory note SIEMPRE presente en output                   | Unit        |
| FakeLLM produce summary_prose válido                          | Unit        |
| MCP serializa DoctrinalDrift                                  | Integration |
| Golden: 5 queries doctrinales con drift conocido              | E2E         |

## Golden set

`tests/drift/fixtures/golden/`:
- `query_alma_es.json` — drift esperado entre 1900s y 2020s
- `query_generation_en.json` — drift esperado en interpretación Mat 24:34
- `query_faithful_slave_en.json` — refinamiento 2013
- `query_harvest_en.json` — drift modesto
- `query_no_drift_en.json` — control negativo (Gen 1:1) — sin drift

Cada uno con `expected_summary_keywords` y `expected_min_drift_events`.

## Riesgos / mitigaciones

| Riesgo                                                  | Mitigación                                          |
|---------------------------------------------------------|-----------------------------------------------------|
| LLM enmarca cambio como "error" en lugar de refinamiento| Prompt explícito + explanatory note hard-coded      |
| Falsos drift por OCR malo en corpus histórico F62       | Min chunk count threshold + warning si OCR conf <0.7|
| Output ofensivo para hermanos                           | Tono neutral, framing Prov 4:18, no "antes vs ahora"|
| Output útil para ex-TJ críticos                         | Imposible evitar; mitigación: tono académico        |
| Embeddings drift entre upgrades de modelo               | meta.json + reindex automático                      |
| Costo computacional sobre corpus completo               | Sub-corpus extraction primero limita scope          |
| Hallazgo "drift" sin significancia estadística          | Min sample size + DBSCAN robust epsilon             |

## Métricas de éxito

- **Recall sobre drifts documentados**: ≥3/5 drifts conocidos del
  golden son detectados correctamente.
- **Precisión**: <20% de false drifts en query control negativo
  (Gen 1:1, "amor", "fe" — conceptos estables).
- **Tono**: 100% de outputs incluyen explanatory note Prov 4:18.

## Wire-up

- CLI: `packages/jw-cli/src/jw_cli/commands/drift.py` — `jw drift "..."`.
- MCP: 1 tool nueva.
- F62 historical-pdf-ingest: precondición — corpus histórico
  completo en RAG.
- F33 embeddings: reusa provider real (BGE-M3 / Voyage / Cohere).
- F49 Second Brain: query expansion + 2-hop neighbors.

## Guía resultante

`docs/guias/doctrinal-drift.md` — quick start, framing Prov 4:18,
interpretación de significance levels, dataset histórico (F62),
ejemplos académicos.
