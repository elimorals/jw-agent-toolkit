# Plugin SDK — Capability Matrix

## Protocols por versión

### `AgentPlugin` (group `jw_agent_toolkit.agents`)

| Attribute | Required | Since | Notes |
|---|---|---|---|
| `__name__: str` | ✅ | v1.0 | Callables tienen esto for free |
| `__call__(**kwargs)` | ✅ | v1.0 | Debe ser async |
| `languages: list[str]` | optional | v1.0 | `['en', 'es', 'pt']` |
| `version: str` | optional | v1.0 | semver del plugin |
| `cost_estimate(**kwargs) -> int` | optional | v1.3 (futuro) | Tokens/llamadas esperadas |

### `ParserPlugin` (group `jw_agent_toolkit.parsers`)

| Attribute | Required | Since | Notes |
|---|---|---|---|
| `__call__(raw, *, source_url=None)` | ✅ | v1.0 | Returns ParsedDocument-like |
| `extensions: list[str]` | optional | v1.0 | `['.pdf', '.epub']` |
| `mime_types: list[str]` | optional | v1.0 | `['application/pdf']` |

### `EmbedderPlugin` (group `jw_agent_toolkit.embedders`)

| Attribute | Required | Since | Notes |
|---|---|---|---|
| `name: str` | ✅ | v1.0 | Único per plugin |
| `target: str` | ✅ | v1.0 | `'cpu'` / `'gpu'` / `'mlx'` |
| `dim: int` | ✅ | v1.0 | Dimensión del vector |
| `is_available() -> bool` | ✅ | v1.0 | Health check |
| `embed(texts) -> array` | ✅ | v1.0 | Batch embedding |
| `max_tokens: int` | optional | v1.0 | Para truncation |

### `VLMProviderPlugin` (group `jw_agent_toolkit.vlm_providers`)

| Attribute | Required | Since | Notes |
|---|---|---|---|
| `name: str` | ✅ | v1.0 | |
| `is_available()` | ✅ | v1.0 | |
| `describe(image_bytes, *, language="en")` | ✅ | v1.0 | |
| `languages: list[str]` | optional | v1.0 | |

### `GenProviderPlugin` (group `jw_agent_toolkit.gen_providers`)

| Attribute | Required | Since | Notes |
|---|---|---|---|
| `name: str` | ✅ | v1.0 | |
| `is_available()` | ✅ | v1.0 | |
| `generate(prompt, *, max_tokens=128)` | ✅ | v1.0 | |
| `max_tokens: int` | optional | v1.0 | |
| `supports_streaming: bool` | optional | v1.0 | |

## Política de evolución

1. **Protocols son aditivos por contrato** — solo se añaden métodos/atributos **opcionales** dentro de una major.
2. La detección es vía `hasattr(plugin, "X")`, no isinstance check.
3. Cualquier nuevo método **requerido** fuerza bump de major. El registry rechaza plugins viejos vía version constraint.
4. `verify_plugin` reporta `required_present` / `required_missing` / `optional_present` / `optional_missing` para que el plugin author sepa qué features puede activar.
