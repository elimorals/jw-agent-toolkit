# Calibrar un golden case para `jw eval`

> **Tiempo estimado**: 10 minutos
> **Requisitos**: jw-eval (F22).
> **Slug URL**: `/cookbook/10-calibrate-golden-case`

## ¿Qué construyes?

Crear un YAML L1/L2/L3 que el harness de Fase 22 (`jw eval`) usa para detectar regresiones doctrinales antes de cada merge.

## Código (copy-pasteable)

```python
# test
# Validate that a representative golden case YAML loads correctly.
import yaml

golden_yaml = """
id: t-001-trinity
layer: l1
agent: apologetics
input:
  question: "¿Es bíblica la doctrina de la Trinidad?"
  language: es
expected:
  must_cite:
    - "https://wol.jw.org/es/wol/d/r4/lp-s/1102004110"
  forbidden_claims:
    - "Trinity is biblical"
"""

case = yaml.safe_load(golden_yaml)
assert case["layer"] == "l1"
assert case["agent"] == "apologetics"
assert "must_cite" in case["expected"]
```

## Por qué funciona

Tres capas:

- **L1**: ¿cita correcta? (URL canónica en `must_cite`).
- **L2**: ¿passage existe? (cassette HTTP comparado con snapshot).
- **L3**: ¿síntesis correcta? (NLI embeddings, threshold 0.78).

Cada layer aísla un tipo de regresión, así sabes exactamente qué se rompió.

## Variaciones

- `forbidden_claims` para asegurar que el agente NO afirma cosas erróneas.
- `metric: ndcg10` para queries de recall (cf. F45).
- `agent_filter: --filter-agent=apologetics` para correr solo un agente.

## Próximo paso

→ [11 — Browser extension WOL](11-browser-extension.md)
