# Eval doctrinal (`jw-eval`)

> Fase 22 — suite de regresión doctrinal. Spec en `docs/superpowers/specs/2026-05-30-fase-22-eval-doctrinal-design.md`.

## Para qué sirve

Mide en cada commit (y nightly) que los agentes del toolkit no introduzcan regresión doctrinal silenciosa. Tres capas independientes:

| Capa | Qué mide | Cuándo corre | Bloquea CI |
|---|---|---|---|
| L1 estructural | shape de `AgentResult` esperada | siempre | sí |
| L2 citas | URLs resuelven + texto sustenta cita | siempre (snapshot) + weekly (live) | sí (snapshot); no (live) |
| L3 semántico | respuesta agente ≈ respuesta dorada | nightly | no |

## Usar localmente

```bash
# L1 + L2 (offline, rápido)
uv run jw eval --layer 1,2

# L2 live contra wol.jw.org real
uv run jw eval --layer 2 --live

# L1+L2+L3 con LLM judge Ollama (default)
JW_EVAL_LLM=ollama uv run jw eval --layer 1,2,3

# Solo Claude judge (requiere ANTHROPIC_API_KEY)
JW_EVAL_LLM=claude uv run jw eval --layer 3

# Salida a archivo
uv run jw eval --layer 1,2 --report md --out eval-report.md
```

## Añadir un nuevo caso dorado

1. Decide la capa: estructural / citas / semántico.
2. Crea YAML en `packages/jw-eval/fixtures/golden_qa/{l1,l2,l3}/<descriptive_name>.yaml`.
3. Si es L2, ejecuta `uv run python packages/jw-eval/scripts/build_eval_snapshots.py` para añadir el snapshot.
4. Commitea YAML + snapshot.
5. CI corre `jw eval` automáticamente.

## Política para fases nuevas

Toda Fase 23-32 debe añadir mínimo 3 casos dorados (uno por capa cuando aplique) al PR. CI verifica cobertura mínima.

## Troubleshooting

| Síntoma | Diagnóstico | Fix |
|---|---|---|
| L2 reporta `skip` | snapshot missing | `build_eval_snapshots.py` |
| L3 falla constantemente score=0 | embedder no instalado | `uv pip install -e packages/jw-eval[embeddings]` |
| L3 escala a LLM y no responde | Ollama no corre | `ollama serve` + `ollama pull llama3.1:8b` |
| L2 live abre muchos issues | wol cambió HTML | revisa snapshots + Fase 23 (auto-refresh) |
