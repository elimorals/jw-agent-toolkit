# create-jw-agent

Scaffolder for jw-agent-toolkit plugins.

```bash
uvx create-jw-agent my-translator --type=agent --lang=es
cd my-translator && uv sync && uv run pytest
```

Generates a Python package with:

- `pyproject.toml` declaring the right entry-point for Fase 41 (`jw_agent_toolkit.{agents,parsers,embedders,vlm_providers,gen_providers}`).
- A stub callable that satisfies the corresponding Protocol.
- 3 deterministic tests (smoke, contract, citations-present) that pass without network.
- A `.github/workflows/ci.yml` that runs ruff + pytest on Python 3.13.
- Prose in en/es/pt; Python identifiers always in English.

## Scope

This tool is part of `jw-agent-toolkit`, which is exclusively for Jehovah's Witnesses publications. The plugin SDK (Fase 41) exists so the JW community can extend the toolkit without forking the monorepo. This scaffolder makes that fast.

## License

GPL-3.0-only (inherited from jw-agent-toolkit).
