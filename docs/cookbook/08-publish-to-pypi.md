# Publicar tu plugin a PyPI

> **Tiempo estimado**: 10 minutos
> **Requisitos**: cuenta PyPI + GitHub Actions trusted publishing.
> **Slug URL**: `/cookbook/08-publish-to-pypi`

## ¿Qué construyes?

Pipeline de release que publica tu plugin a PyPI automáticamente cuando empujas un tag `vX.Y.Z`, sin secrets en el repo (vía OIDC trusted publishing).

## Código (copy-pasteable)

```python
# test
# Validate that the generated pyproject.toml of a scaffolded plugin
# satisfies the minimum requirements for `uv build`.
import importlib
spec = importlib.util.find_spec("create_jw_agent")
assert spec is not None

# A valid pyproject must declare: name, version, requires-python, build-system.
# We verify the agent template here as the canonical reference.
from pathlib import Path

# Get a fresh tmp project rendered from the agent template.
import tempfile
from create_jw_agent.render import RenderContext, render_template

with tempfile.TemporaryDirectory() as tmp:
    out = Path(tmp) / "demo-plugin"
    ctx = RenderContext.build(name="demo-plugin", type="agent", lang="en")
    render_template(template_type="agent", output_dir=out, ctx=ctx)

    pyproject = (out / "pyproject.toml").read_text(encoding="utf-8")
    assert 'name = "demo-plugin"' in pyproject
    assert "build-system" in pyproject
    assert "requires-python" in pyproject
```

## Por qué funciona

`create-jw-agent` genera un `pyproject.toml` que ya es publishable con `uv build && uv publish`. Para PyPI sin secrets, configura trusted publishing siguiendo la guía oficial:

1. En PyPI: crea el proyecto pendiente (pending publisher) con tu repo de GitHub.
2. En tu repo: añade `.github/workflows/publish.yml` con `id-token: write`.
3. Push tag `v0.1.0` → CI corre `uv build` + `uv publish --trusted-publishing always`.

## Variaciones

- TestPyPI primero (`--publish-url https://test.pypi.org/legacy/`) para verificar.
- `uv version --bump patch` automatiza el bump pre-tag.
- Doble release: PyPI + GitHub Releases con notas auto-generadas.

## Próximo paso

→ [09 — Trace de la ejecución del agente](09-trace-agent-run.md)
