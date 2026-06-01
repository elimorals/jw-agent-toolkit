# Añadir verificación NLI a un agente existente

> **Tiempo estimado**: 3 minutos
> **Requisitos**: jw-agents con F39 (NLI runtime).
> **Slug URL**: `/cookbook/07-add-nli`

## ¿Qué construyes?

Envolver cualquier agente con el decorador `@fidelity_wrap` para que cada `Finding` se verifique contra su passage citado vía NLI antes de devolverse. Si la afirmación no se desprende del passage, el Finding queda marcado o filtrado.

## Código (copy-pasteable)

```python
# test
# Verify the decorator and FakeNLI are importable and the wrap is composable.
from jw_agents.fidelity_wrap import fidelity_wrap
from jw_core.fidelity.nli_providers.fakes import FakeNLI

# FakeNLI is pure-Python and always available — perfect for CI.
nli = FakeNLI()
assert nli.is_available()

# The decorator factory accepts a `provider` and returns a wrapper.
wrapped_factory = fidelity_wrap(min_score=0.5, on_fail="warn", provider=nli)
assert callable(wrapped_factory)
```

## Por qué funciona

`fidelity_wrap` es un decorador async-aware que:

1. Llama al agente normalmente.
2. Para cada `Finding`, extrae `claim` (del summary) y `premise` (del excerpt).
3. Invoca el `NLIProvider` configurado (`DeBERTa`, `Claude`, `Ollama`, `Fake`).
4. Añade `nli_verdict`/`nli_score` a metadata.
5. Según `on_fail`: `"warn"` deja pasar con log, `"reject"` lanza, `"off"` no hace nada.

## Variaciones

- `min_score=0.7` para umbral más estricto.
- Provider local: `FakeNLI` para tests, `DeBERTaV3MNLI` para producción CPU/MPS.
- Combinar con `provenance_check` (F40) para re-validar tras drift.

## Próximo paso

→ [08 — Publicar tu plugin a PyPI](08-publish-to-pypi.md)
