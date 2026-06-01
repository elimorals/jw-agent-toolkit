# Embedder custom como plugin

> **Tiempo estimado**: 5 minutos
> **Requisitos**: jw-core + numpy.
> **Slug URL**: `/cookbook/06-custom-embedder`

## ¿Qué construyes?

Un embedder propio (modelo fine-tuned sobre el corpus JW, o uno especializado en español/portugués) registrado como plugin que el RAG descubre y usa.

## Código (copy-pasteable)

```python
# test
import numpy as np

class JwBibleEmbedder:
    """Stub embedder. Replace with real model call."""
    name = "jw-bible-emb"
    target = "cpu"
    dim = 8

    def is_available(self) -> bool:
        return True

    def embed(self, texts: list[str]) -> np.ndarray:
        # Stub: returns zero vectors. Real implementation would call your model.
        return np.zeros((len(texts), self.dim), dtype=np.float32)

# Verify Protocol:
from jw_core.plugins.contracts import EmbedderPlugin
emb = JwBibleEmbedder()
assert isinstance(emb, EmbedderPlugin)

# Verify shape:
vecs = emb.embed(["Juan 3:16", "Eclesiastés 9:5"])
assert vecs.shape == (2, 8)
```

## Por qué funciona

El `Embedder` Protocol (`name`, `target`, `dim`, `is_available()`, `embed()`) es el mismo que usan los embedders core (`BGEM3Provider`, `CohereEmbedV3Provider`, etc.). Tu plugin se mezcla con ellos en `_instantiate_registry()` sin distinción.

Entry-point:

```toml
[project.entry-points."jw_agent_toolkit.embedders"]
jw_bible_emb = "my_pkg.embedder:JwBibleEmbedder"
```

## Variaciones

- `target="mlx"` para Apple Silicon.
- `target="gpu"` para CUDA — el RAG lo prioriza cuando hay hardware.
- Atributo opcional `max_tokens: int` para truncation.

## Próximo paso

→ [07 — Añadir NLI a tu agente](07-add-nli.md)
