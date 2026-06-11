---
title: "Análisis de drift doctrinal (Fase 72)"
description: "Embeddings temporales + DBSCAN cosine + cluster alignment + significance. La nota Prov 4:18 trilingüe SIEMPRE va inyectada. Wire-up F49 Second Brain + SVG timeline."
date: "2026-06-11"
---

# Análisis de drift doctrinal (Fase 72)

> Rastrea cómo la comprensión doctrinal **se refina** ("la luz brilla
> cada vez más" - Proverbios 4:18) usando embeddings temporales +
> DBSCAN-style clustering. Cada output incluye OBLIGATORIAMENTE una
> nota explicativa que enmarca los cambios como refinamiento, NO
> contradicción.

## Quick start

```bash
# Listar las décadas reconocidas
jw drift eras

# Imprimir la nota Prov 4:18 (es/en/pt)
jw drift note -l es

# Analizar un corpus local (JSONL con text/year/embedding)
jw drift analyze "alma" --chunks /tmp/alma.jsonl -l es
```

## Formato del JSONL

Una línea por chunk; cada chunk:

```json
{"text": "el alma del hombre...", "year": 1985, "embedding": [0.12, -0.34, ...]}
```

Los embeddings se normalizan automáticamente. El año determina la era
por `(year // 10) * 10`. Las eras soportadas son `1900s` a `2020s`.

## CLI

| Comando             | Descripción                              |
|---------------------|------------------------------------------|
| `jw drift analyze`  | Ejecuta el analizador sobre JSONL local  |
| `jw drift note`     | Imprime la nota Prov 4:18 por idioma     |
| `jw drift eras`     | Lista las décadas reconocidas            |

### Flags de `analyze`

| Flag                       | Default | Efecto                                       |
|----------------------------|---------|----------------------------------------------|
| `--chunks`                 | —       | Path al JSONL (obligatorio)                  |
| `--language` / `-l`        | `es`    | Idioma del resumen y nota explicativa        |
| `--min-chunks-per-era`     | `3`     | Mínimo de chunks para que una era cuente     |
| `--min-delta`              | `0.05`  | Cosine delta mínimo para emitir evento       |

## MCP

| Tool              | Descripción                              |
|-------------------|------------------------------------------|
| `drift_analyze`   | Devuelve `DoctrinalDrift` dict           |

## Arquitectura

```
   list[Chunk(text, year, embedding)]
              │
              ▼
   ┌──────────────────────────┐
   │ partition_by_era         │ - (year // 10) * 10
   │  -> {Era: [Chunk,...]}   │ - drops out-of-range
   └────────────┬─────────────┘
                │
                ▼
   ┌──────────────────────────┐
   │ dbscan_cluster por era   │ - cosine distance
   │  epsilon, min_samples    │ - numpy puro
   │  -> ClusterResult        │
   └────────────┬─────────────┘
                │
                ▼
   ┌──────────────────────────┐
   │ detect_drift_events      │ - cluster center alignment
   │  significance: minor/    │   por par consecutivo
   │   moderate/major         │ - skip si delta < threshold
   └────────────┬─────────────┘
                │
                ▼
   ┌──────────────────────────┐
   │ DoctrinalDrift           │
   │  - era_snapshots         │
   │  - drift_events          │
   │  - summary_prose         │
   │  - **explanatory_note    │
   │    (Prov 4:18 SIEMPRE)** │
   └──────────────────────────┘
```

## Significance bands

```
min(chunk_count_from, chunk_count_to) < 5    -> minor (low signal)
delta < 0.05                                 -> minor
0.05 <= delta < 0.15                          -> moderate
delta >= 0.15                                 -> major
```

## La nota Prov 4:18 (obligatoria)

`explanatory_note` se inyecta SIEMPRE en cada reporte, en el idioma
solicitado. Su rol es enmarcar éticamente el output: los TJ consideran
que la comprensión doctrinal se refina con el tiempo, NO que las
publicaciones del pasado contradicen al presente. Cualquier consumidor
del JSON debe presentar la nota visible junto a `drift_events`.

## Integración en F65 meta-orchestrator

Registrada como tool `drift.analyze`. El planner F65 puede componer:

```json
{"steps": [
  {"id": "s1", "tool": "drift.analyze",
   "args": {"query": "alma", "chunks_path": "/tmp/alma.jsonl"}}
]}
```

## Dependencias

| Feature        | Dep         | Fallback                       |
|----------------|-------------|--------------------------------|
| Clustering     | numpy       | requerido                       |
| Real embeddings| F33 provider| el caller los genera y persiste |

El analizador es **embedding-agnóstico**: cualquier provider (BGE-M3,
Voyage, Cohere, OpenAI) sirve mientras los vectores estén normalizados.

## Privacidad

- Los embeddings vivien en disco del usuario (JSONL).
- Sin telemetría externa.
- El analyzer no descarga corpus — el caller alimenta `chunks_path`.

## Estado actual

- 5 tasks TDD. **31 tests passing** (6 models + 6 cluster + 7
  drift_detect + 5 engine + 3 CLI + 1 MCP + 2 meta + 1 protocol delta).
- Pipeline puro numpy (sin sklearn).
- DBSCAN-style cosine clustering con epsilon configurable.
- Nota Prov 4:18 trilingüe (es/en/pt) SIEMPRE inyectada.
- 3 niveles de significance (minor/moderate/major) con muestreo cap.
- CLI `jw drift {analyze,note,eras}` + MCP tool.
- Meta tool `drift.analyze` en F65.

## Pendiente (futuro)

- Wire-up automático con F49 Second Brain para que el caller no tenga
  que materializar JSONLs manualmente.
- F33 embedder default builtin para generar el JSONL desde un
  `query + corpus` interactivo.
- Comparación cluster-vs-cluster pairwise (no solo consecutiva).
- Visualización SVG del drift timeline para exportar a `docs/`.
