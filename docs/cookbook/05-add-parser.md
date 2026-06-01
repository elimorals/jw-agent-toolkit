# Añadir un parser custom como plugin

> **Tiempo estimado**: 5 minutos
> **Requisitos**: jw-core (plugin SDK F41).
> **Slug URL**: `/cookbook/05-add-parser`

## ¿Qué construyes?

Un parser para tu formato local (ej. `.opdx` de Onyx Boox, o un export propietario) registrado como plugin externo. El toolkit lo descubre vía `jw_agent_toolkit.parsers` sin que tengas que tocar el monorepo.

## Código (copy-pasteable)

```python
# test
# Define a parser following the ParserPlugin Protocol:
def opdx_parser(raw: bytes | str, *, source_url: str | None = None) -> dict:
    """Parser stub. Returns a ParsedDocument-shaped dict."""
    text = raw.decode("utf-8") if isinstance(raw, bytes) else raw
    return {
        "text": text,
        "source_url": source_url,
        "metadata": {"parser": "opdx", "format": "Onyx Boox export"},
    }

# Optional plugin attributes (capability matrix).
opdx_parser.extensions = [".opdx"]
opdx_parser.mime_types = ["application/x-opdx"]

# Verify the Protocol is satisfied:
from jw_core.plugins.contracts import ParserPlugin
assert isinstance(opdx_parser, ParserPlugin)

# Verify behavior:
result = opdx_parser("hello", source_url="file:///x.opdx")
assert result["text"] == "hello"
assert result["metadata"]["parser"] == "opdx"
```

## Por qué funciona

`ParserPlugin` es un `Protocol` estructural (PEP 544): no necesitas heredar de nada. Cualquier callable con la firma correcta lo satisface. `isinstance(..., ParserPlugin)` chequea la forma en runtime.

Para que el toolkit lo descubra, declaras el entry-point en tu `pyproject.toml`:

```toml
[project.entry-points."jw_agent_toolkit.parsers"]
opdx = "my_pkg.parser:opdx_parser"
```

## Variaciones

- Devuelve `chunks: list[str]` además de `text` para que el RAG ingest pueda saltarse el chunking propio.
- Atributo opcional `version: str` para que `verify_plugin` lo reporte.

## Próximo paso

→ [06 — Embedder custom](06-custom-embedder.md)
