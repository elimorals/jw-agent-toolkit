# Plugin SDK — Authoring a Plugin

## 1. Crear el paquete

```bash
mkdir my-jw-plugin && cd my-jw-plugin
mkdir -p src/my_jw_plugin
touch src/my_jw_plugin/__init__.py
```

## 2. `pyproject.toml`

```toml
[project]
name = "my-jw-plugin"
version = "0.1.0"
description = "My custom agent for jw-agent-toolkit"
requires-python = ">=3.13"
dependencies = [
    "jw-agent-toolkit>=1.0,<2.0",  # rango aceptado por tu plugin
]

[project.entry-points."jw_agent_toolkit.agents"]
my_agent = "my_jw_plugin.agent:my_agent"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/my_jw_plugin"]
```

## 3. Implementar el agente

```python
# src/my_jw_plugin/agent.py
from typing import Any


async def my_agent(**kwargs: Any) -> dict[str, Any]:
    """My custom agent — returns AgentResult-shaped dict."""

    return {
        "findings": [],
        "warnings": [],
        "metadata": {"agent": "my_agent"},
    }


# Optional attributes (capability matrix — detected via hasattr)
my_agent.languages = ["en", "es"]
my_agent.version = "0.1.0"
```

## 4. Instalar local y verificar

```bash
uv pip install -e .
jw plugins list
jw plugins verify my_agent
```

## 5. Publicar (opcional)

```bash
uv build
twine upload dist/*
```

## 6. Otros groups

Cambia el group en `entry-points`:

```toml
[project.entry-points."jw_agent_toolkit.parsers"]
my_parser = "my_jw_plugin.parser:my_parser"

[project.entry-points."jw_agent_toolkit.embedders"]
my_emb = "my_jw_plugin.embedder:MyEmbedder"

[project.entry-points."jw_agent_toolkit.vlm_providers"]
my_vlm = "my_jw_plugin.vlm:MyVLM"

[project.entry-points."jw_agent_toolkit.gen_providers"]
my_gen = "my_jw_plugin.gen:MyGen"
```

Cada uno tiene su Protocol — ver [Capabilities matrix](capabilities.md).

## 7. Ejemplo fixture canónico

`packages/jw-core/tests/fixtures/plugin_sample/` en el repo del toolkit es un plugin completo con los 5 groups. Cópialo como template:

```bash
gh repo clone eliascipre/jw-agent-toolkit
cp -r jw-agent-toolkit/packages/jw-core/tests/fixtures/plugin_sample my-jw-plugin
cd my-jw-plugin && edit src/...
```
