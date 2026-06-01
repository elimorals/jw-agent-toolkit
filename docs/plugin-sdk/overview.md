# Plugin SDK (Fase 41)

> Extension points sin forkear el monorepo. Terceros publican paquetes en PyPI que el toolkit descubre automáticamente.

## Mecanismo

PEP 621 entry points. Tu plugin declara en su `pyproject.toml`:

```toml
[project.entry-points."jw_agent_toolkit.agents"]
translation_helper = "my_pkg.translation:translation_helper"
```

El toolkit lo descubre vía `importlib.metadata.entry_points` al startup. Cero modificación del toolkit, cero PR.

## 5 extension points

| Group | Para extender | Protocol |
|---|---|---|
| `jw_agent_toolkit.agents` | Agentes nuevos | `AgentPlugin` (async callable) |
| `jw_agent_toolkit.parsers` | Parsers de formatos | `ParserPlugin` |
| `jw_agent_toolkit.embedders` | Embedders custom | `EmbedderPlugin` |
| `jw_agent_toolkit.vlm_providers` | VLMs | `VLMProviderPlugin` |
| `jw_agent_toolkit.gen_providers` | Generación | `GenProviderPlugin` |

## API

```python
from jw_core.plugins import (
    get_plugins,        # descubre plugins de un group
    verify_plugin,      # check contract + version
    clear_plugin_cache, # reset cache (tests)
    PluginError,
    PluginConflictError,
    PluginContractError,
    PluginVersionMismatch,
)
```

## CLI

```bash
jw plugins list                          # ver todos los plugins instalados
jw plugins list --json                   # output JSON
jw plugins verify <name>                 # check contract + version
jw plugins disable <name>                # deny-list persistente
```

## Variables de entorno

| Variable | Default | Efecto |
|---|---|---|
| `JW_PLUGINS_DISABLED` | unset | `=1` → `get_plugins` devuelve `{}` |
| `JW_PLUGINS_STRICT` | unset | `=1` → errores de verificación abortan |
| `JW_PLUGINS_ALLOW_LIST` | unset | CSV de nombres permitidos |
| `JW_PLUGINS_DENY_LIST` | unset | CSV de nombres bloqueados |
| `JW_PLUGINS_CONFLICT_POLICY` | `namespaced` | `first_wins`/`last_wins`/`namespaced`/`reject` |

## Ver también

- [Security](security.md) — modelo de confianza y mitigaciones.
- [Capabilities matrix](capabilities.md) — qué Protocol attributes existen por versión.
- [Authoring](authoring.md) — guía paso a paso para crear un plugin.
