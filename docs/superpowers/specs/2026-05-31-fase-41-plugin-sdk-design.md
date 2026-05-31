# Fase 41 — `plugin-sdk`: extension points sin forkear el monorepo

> **Fecha**: 2026-05-31
> **Estado**: Diseño aprobado (pendiente de implementación)
> **Owner**: Elias
> **Tier**: 2 (comunidad)
> **Depende de**: ninguna fase. Habilita Fase 42 (`scaffolding`).
> **Documento padre**: [`2026-05-31-fases-39-48-overview.md`](2026-05-31-fases-39-48-overview.md)

## Motivación

Hoy el toolkit es "lo de Elias". Para que sea **lo de la comunidad** hace falta una superficie que terceros puedan extender sin abrir un PR contra `jw-agent-toolkit/jw-agent-toolkit`. La barrera actual es alta: para añadir un agente nuevo, un parser de un formato exótico, un embedder dedicado o un VLM/Gen provider hace falta clonar el monorepo, conocer el layout de los 8 paquetes y mantener el fork.

Fase 41 cierra esa brecha: terceros publican su paquete Python en PyPI (o lo instalan local con `uv add ./mi-plugin`), declaran un **entry point** en su `pyproject.toml`, y el toolkit lo descubre automáticamente en runtime — agentes, parsers, embedders, VLMs y Gen providers.

Es la pieza con mayor palanca para adopción comunitaria: convierte cada hueco funcional ("me falta un parser para X formato local") en una contribución de **una librería externa** sin forking, sin proceso de review interno, sin coupling de versiones.

## Objetivos (en orden de prioridad)

1. **Discovery via PEP 621 entry points** sobre 5 extension points: agentes, parsers, embedders, VLM providers, Gen providers.
2. **Verificación de contrato** en load-time (signature, atributos, deps declaradas) con errores accionables.
3. **Resolución de conflictos** determinística (dos plugins registran el mismo nombre): política configurable + warning explícito.
4. **Evolución del contrato sin romper plugins existentes** — vía Protocols + optional attributes detectados por introspección.
5. **Opt-out de plugins no confiables** vía `JW_PLUGINS_DISABLED` + `JW_PLUGINS_ALLOW_LIST` (security boundary explícita).
6. **Integración transparente** con `default_agent_registry` (jw-eval), el MCP server (jw-mcp) y el CLI (jw-cli).

## No-objetivos (boundaries vinculantes)

- **No** sandboxing real del código del plugin. El plugin corre en el proceso del host con todos los privilegios — esto es **explícito y documentado**. Sandboxing requiere subprocesos/IPC, no entra en Fase 41 (queda en ROADMAP).
- **No** marketplace, ni package registry propio, ni reviews. Los plugins viven en PyPI o paths locales. Discovery se hace via `importlib.metadata.entry_points`.
- **No** hot-reload. Los plugins se descubren al startup. Cambios requieren reimportar.
- **No** plugins en otros lenguajes (JS, Go). Fase 47 abrirá la puerta JS para el subset mínimo de `jw-core`; el plugin SDK aquí es Python-only.
- **No** modifica los Protocols existentes. Fase 41 los **expone como contratos plugin** sin cambiarlos.

## Arquitectura

Nuevo módulo `packages/jw-core/src/jw_core/plugins/`. Razón de ubicarlo en `jw-core`: es la dependencia común de `jw-rag`, `jw-agents`, `jw-mcp`, `jw-cli`, `jw-eval`. Todos pueden importar el registry sin generar ciclos.

```
packages/jw-core/src/jw_core/plugins/
├── __init__.py            # API pública: get_plugins, verify_plugin
├── contracts.py           # 5 Protocols: AgentPlugin, ParserPlugin, EmbedderPlugin, VLMProviderPlugin, GenProviderPlugin
├── registry.py            # _discover() via importlib.metadata.entry_points
├── verify.py              # verify_plugin(name, group) — shape/deps/version check
├── errors.py              # PluginError, PluginConflictError, PluginVersionMismatch, PluginContractError
├── factory.py             # get_plugins(group) cached + clear_cache()
└── policy.py              # ConflictPolicy enum + ALLOW_LIST/DENY_LIST env handling
```

### Reglas duras de diseño

1. `jw_core.plugins` **no** importa de paquetes downstream (`jw_agents`, `jw_rag`, etc.). Los Protocols se definen estructuralmente con `typing.Protocol`, no por herencia.
2. Discovery es **lazy** y **cached** — `get_plugins(group)` corre una vez por proceso salvo `clear_cache()`.
3. Verificación falla **fail-soft** por default: un plugin malformado **no rompe el toolkit**, sólo se loguea como WARNING y se excluye del registry. Comportamiento configurable a fail-hard via `JW_PLUGINS_STRICT=1`.
4. Cero red, cero side-effects en import time del módulo plugin (el toolkit refuse cargarlo si su entry point tiene side-effects detectables).
5. Tests del registry no instalan paquetes reales — usan `importlib.metadata.EntryPoint(...)` construidos manualmente en fixtures.

## Las 5 extension points (entry-point groups)

Cada entry-point group corresponde a un Protocol estricto en `contracts.py`. El nombre del group se elige para coincidir con la nomenclatura del toolkit y evitar colisiones con otros proyectos (prefijo `jw_agent_toolkit.`).

### 1. `jw_agent_toolkit.agents`

```python
# contracts.py
from typing import Protocol, runtime_checkable, Any
from jw_agents.base import AgentResult  # re-export via TYPE_CHECKING

@runtime_checkable
class AgentPlugin(Protocol):
    """A pluggable agent.

    Implementations MUST be async callables accepting **kwargs and returning
    an AgentResult. The toolkit forwards GoldenCase.input as **kwargs.

    OPTIONAL attributes (detected via hasattr):
      - name: str         — overrides entry-point name if present
      - languages: list[str]  — ['en', 'es', 'pt'] for advertised language support
      - version: str      — semver of the plugin agent
    """

    __name__: str
    async def __call__(self, **kwargs: Any) -> AgentResult: ...
```

3rd party `pyproject.toml`:

```toml
[project.entry-points."jw_agent_toolkit.agents"]
translation_helper = "my_pkg.translation:translation_helper"
```

### 2. `jw_agent_toolkit.parsers`

```python
@runtime_checkable
class ParserPlugin(Protocol):
    """A pluggable document parser.

    Signature: (raw: bytes | str, *, source_url: str | None = None) -> ParsedDocument

    OPTIONAL attributes:
      - extensions: list[str]   — ['.pdf', '.epub'] for routing
      - mime_types: list[str]   — ['application/pdf'] for HTTP routing
    """

    def __call__(
        self,
        raw: bytes | str,
        *,
        source_url: str | None = None,
    ) -> "ParsedDocument": ...
```

### 3. `jw_agent_toolkit.embedders`

Extiende el `EmbedProvider` de Fase 33 (`packages/jw-rag/src/jw_rag/embed_providers/factory.py`). El plugin debe ofrecer `name`, `target`, `dim`, `is_available()`, `embed(texts)`. La verificación re-usa el `runtime_checkable` existente.

### 4. `jw_agent_toolkit.vlm_providers`

Extiende `VLMProvider` (Fase 13/jw-core/vision). Mismo patrón: el contrato ya existe; Fase 41 sólo lo expone como extension point.

### 5. `jw_agent_toolkit.gen_providers`

Extiende `GenerationProvider` (Fase 38/jw-gen).

## Discovery (`registry.py`)

```python
from importlib.metadata import entry_points
from functools import lru_cache

GROUPS = (
    "jw_agent_toolkit.agents",
    "jw_agent_toolkit.parsers",
    "jw_agent_toolkit.embedders",
    "jw_agent_toolkit.vlm_providers",
    "jw_agent_toolkit.gen_providers",
)

@lru_cache(maxsize=None)
def _discover(group: str) -> dict[str, EntryPointSpec]:
    """Return dict[name, spec] for the given group, post-policy filtering."""
    raw = entry_points(group=group)
    allow = _read_env_set("JW_PLUGINS_ALLOW_LIST")  # set[str] | None
    deny = _read_env_set("JW_PLUGINS_DENY_LIST")
    out: dict[str, EntryPointSpec] = {}
    for ep in raw:
        if allow is not None and ep.name not in allow:
            continue
        if deny and ep.name in deny:
            continue
        spec = EntryPointSpec.from_entry_point(ep, group=group)
        out = _apply_conflict_policy(out, spec)
    return out
```

`EntryPointSpec` es un dataclass con `name`, `group`, `module`, `attr`, `dist_name`, `dist_version`, `loaded` (lazy). Carga el objeto via `ep.load()` sólo cuando alguien llama `spec.resolve()`.

## Contrato de versiones

Cada plugin declara en su `pyproject.toml`:

```toml
[project]
dependencies = [
    "jw-agent-toolkit>=1.2,<2.0",  # rango aceptado
]
```

`verify.py` parsea esa restricción via `packaging.requirements` y la compara contra `jw_core.__version__`. Si el major del toolkit excede lo declarado, lanza `PluginVersionMismatch` y excluye el plugin (en modo fail-soft) o aborta (`JW_PLUGINS_STRICT=1`).

**Por qué basta el rango**: PEP 440 + `packaging` están en stdlib-adjacent. No reinventamos resolution. La regla "declarado `<2.0`, instalado 2.x → rechazado" es la SemVer estándar.

## Evolución del contrato (la pregunta dura)

**Problema**: si añadimos un nuevo campo opcional al Protocol `AgentPlugin` (ej. `cost_estimate(**kwargs) -> int`), ¿cómo no rompemos plugins viejos?

**Política**:

1. **Protocols son aditivos por contrato** — sólo se añaden métodos/atributos **opcionales**, nunca requeridos, dentro de una major.
2. La detección es vía `hasattr(plugin, "cost_estimate")`, **no** isinstance check. El plugin viejo que no tiene `cost_estimate` simplemente no participa de esa feature; el host degrada limpio.
3. Cualquier **nuevo método requerido** fuerza bump de major del toolkit. El registry rechaza plugins viejos automáticamente vía la regla de versión.
4. Documentamos la "**capability matrix**" en `docs/plugin-sdk/capabilities.md`: por cada versión del toolkit, qué Protocol attributes existen y cuáles son required vs optional.
5. `verify_plugin(name)` produce un reporte estructurado: `{required: ["__call__"], optional_supported: ["cost_estimate"], optional_missing: ["languages"]}` para que el plugin author sepa qué features puede activar.

Ejemplo concreto — añadir `languages: list[str]` opcional en v1.3:

```python
# contracts.py — siguen siendo válidos plugins v1.2
@runtime_checkable
class AgentPlugin(Protocol):
    __name__: str
    async def __call__(self, **kwargs: Any) -> AgentResult: ...
    # OPTIONAL (since 1.3): languages: list[str]

# uso defensivo en jw-eval/cli.py
def routes_for_language(plugin, lang: str) -> bool:
    declared = getattr(plugin, "languages", None)
    return declared is None or lang in declared
```

## Resolución de conflictos (la segunda pregunta dura)

**Problema**: dos plugins distintos registran un agente llamado `translation_helper`. ¿Quién gana?

**Política** (en `policy.py`):

```python
class ConflictPolicy(StrEnum):
    FIRST_WINS = "first_wins"   # primero descubierto se queda
    LAST_WINS = "last_wins"     # último descubierto sobrescribe
    NAMESPACED = "namespaced"   # default — emite ambos como dist_name:plugin_name
    REJECT = "reject"           # raise PluginConflictError
```

**Default**: `NAMESPACED`. Cuando hay colisión, los dos plugins quedan disponibles como `my-pkg:translation_helper` y `other-pkg:translation_helper`, y el nombre bare `translation_helper` **no** se resuelve — el caller debe ser explícito.

Configurable via `JW_PLUGINS_CONFLICT_POLICY=first_wins`. Siempre se loguea WARNING con el nombre, ambas distribuciones, y la política aplicada.

**Por qué NAMESPACED por default**: cero ambigüedad silenciosa. La política `FIRST_WINS` introduce orden de descubrimiento como variable opaca (qué paquete instaló primero `pip` afecta la respuesta del agente). NAMESPACED rompe explícitamente para forzar disambiguación.

## Seguridad (la tercera pregunta dura)

**Realidad**: el plugin corre en nuestro proceso con todos los privilegios. Puede leer secretos del entorno, escribir archivos, hacer red. Esto **no se puede mitigar** sin sandboxing real (subprocesos/wasmtime/seccomp), que excede el alcance.

**Lo que SÍ ofrecemos**:

1. **Documentación explícita** en `docs/plugin-sdk/security.md`: "Instalar un plugin = ejecutar código arbitrario. Verifica la fuente."
2. **`JW_PLUGINS_DISABLED=1`** — desactiva descubrimiento completo. Útil para entornos auditados / CI público.
3. **`JW_PLUGINS_ALLOW_LIST="trusted_a,trusted_b"`** — sólo carga estos nombres. Default permisivo, pero si está seteado se vuelve estricto.
4. **`JW_PLUGINS_DENY_LIST`** — bloquea nombres específicos (post-incident response).
5. **Trazabilidad**: `verify_plugin` emite en su reporte `dist_name`, `dist_version`, `dist_url` (PyPI URL si aplica). Auditable.
6. **No auto-instalamos**. El toolkit nunca corre `pip install` por su cuenta. Los plugins llegan via `uv add` explícito del usuario.

**Lo que NO ofrecemos** (y queda documentado):
- Bloqueo de red por plugin.
- Bloqueo de FS por plugin.
- Sandboxing de imports.

Postura: el modelo de confianza es **el mismo que `pip install`**. Cualquier package Python instalable puede hacer cualquier cosa. Plugins no son la excepción; sólo son más visibles porque se descubren automáticamente.

## API pública

```python
# jw_core/plugins/__init__.py
from .factory import get_plugins, clear_plugin_cache
from .verify import verify_plugin
from .errors import (
    PluginError,
    PluginConflictError,
    PluginVersionMismatch,
    PluginContractError,
)

__all__ = [
    "get_plugins",
    "clear_plugin_cache",
    "verify_plugin",
    "PluginError",
    "PluginConflictError",
    "PluginVersionMismatch",
    "PluginContractError",
]
```

```python
# uso desde jw_eval/cli.py
from jw_core.plugins import get_plugins
from jw_eval.cli import _make_sync_wrapper

def default_agent_registry() -> dict[str, Callable[[dict[str, Any]], Any]]:
    registry: dict[str, Callable[..., Any]] = {
        # Hardcoded (legacy)
        "apologetics": _make_sync_wrapper(apologetics),
        # ... resto de los hardcoded
    }
    # Merge con plugins descubiertos. Política: hardcoded gana sobre plugin
    # con el mismo nombre (compat). Plugin nuevo NO sobrescribe core.
    for name, spec in get_plugins("jw_agent_toolkit.agents").items():
        if name in registry:
            continue  # core wins; plugin queda accesible como dist:name vía namespaced policy
        registry[name] = _make_sync_wrapper(spec.resolve())
    return registry
```

## Integración con surfaces existentes

### jw-eval

`default_agent_registry()` reemplazado por la versión merge (arriba). Golden cases pueden referenciar `agent: my-pkg:translation_helper` igual que un agente core.

### jw-mcp

`packages/jw-mcp/src/jw_mcp/server.py` itera los 5 groups en `register_tools()`. Cada plugin agente genera una tool MCP con nombre `agent.<plugin_name>` y schema derivado de la signature (introspectada via `inspect.signature`).

### jw-cli

`jw plugins list` — muestra los 5 groups con nombre, dist, versión, estado (loaded/error).
`jw plugins verify <name>` — corre `verify_plugin` y emite reporte humano.
`jw plugins disable <name>` — escribe en `~/.jw-agent-toolkit/plugins.toml` para deny-list persistente.

### jw-rag

`jw_rag.embed_providers.factory._instantiate_registry()` deja de ser hardcoded — itera `get_plugins("jw_agent_toolkit.embedders")` y los suma a los providers core. Cero cambio para usuarios que no instalan plugins.

## Test strategy

### Fixture package

`packages/jw-core/tests/fixtures/plugin_sample/`:

```
plugin_sample/
├── pyproject.toml         # declara entry points en los 5 groups
├── src/plugin_sample/
│   ├── __init__.py
│   ├── agent.py           # async agent stub que devuelve AgentResult vacío
│   ├── parser.py          # parser stub
│   ├── embedder.py        # embedder fake
│   ├── vlm.py             # VLM fake
│   └── gen.py             # Gen provider fake
```

`tests/test_plugins_discovery.py` instala este paquete en un venv temporal (`uv venv .tox/plugin_test && uv pip install -e ./fixtures/plugin_sample`), luego corre `get_plugins(group)` y verifica que aparece.

**Sin red**: el venv es local, el paquete es local, no se baja nada de PyPI.

### Tests del registry sin instalar paquetes

Para los happy paths del registry usamos `importlib.metadata.EntryPoint(...)` directamente + monkey-patch de `importlib.metadata.entry_points`:

```python
def test_discovery_picks_up_registered_agent(monkeypatch):
    fake_ep = EntryPoint(
        name="my_agent",
        value="tests.fakes.agent_module:my_agent_callable",
        group="jw_agent_toolkit.agents",
    )
    monkeypatch.setattr(
        "importlib.metadata.entry_points",
        lambda group=None: [fake_ep] if group == "jw_agent_toolkit.agents" else [],
    )
    clear_plugin_cache()
    plugins = get_plugins("jw_agent_toolkit.agents")
    assert "my_agent" in plugins
```

### Tests de conflicto, version, contract

- `test_conflict_namespaced_default`
- `test_conflict_first_wins_via_env`
- `test_version_mismatch_raises_in_strict`
- `test_version_mismatch_logs_in_soft`
- `test_contract_violation_missing_call`
- `test_allow_list_filters`
- `test_deny_list_filters`
- `test_disabled_returns_empty`

Cobertura objetivo: ≥95% del módulo `jw_core.plugins`.

## Modelos (Pydantic / dataclasses)

```python
# jw_core/plugins/contracts.py
@dataclass(frozen=True)
class EntryPointSpec:
    name: str
    group: str
    module: str
    attr: str
    dist_name: str
    dist_version: str
    namespaced_name: str  # "{dist_name}:{name}"

    def resolve(self) -> Any:
        """Lazy-load the entry point target. Cached at the EntryPoint level."""
        ...

@dataclass(frozen=True)
class VerifyReport:
    name: str
    group: str
    ok: bool
    required_present: list[str]
    required_missing: list[str]
    optional_present: list[str]
    optional_missing: list[str]
    version_constraint: str | None
    version_satisfied: bool
    errors: list[str]
```

## Variables de entorno (resumen)

| Variable | Default | Efecto |
|---|---|---|
| `JW_PLUGINS_DISABLED` | unset | Si `=1`, `get_plugins` siempre devuelve `{}` |
| `JW_PLUGINS_STRICT` | unset | Si `=1`, errores de verificación abortan; default loguea WARNING |
| `JW_PLUGINS_ALLOW_LIST` | unset | CSV de nombres permitidos; si se setea, todo lo demás se filtra |
| `JW_PLUGINS_DENY_LIST` | unset | CSV de nombres bloqueados |
| `JW_PLUGINS_CONFLICT_POLICY` | `namespaced` | `first_wins` \| `last_wins` \| `namespaced` \| `reject` |

## CI integration

Nuevo job offline en `.github/workflows/ci.yml`:

```yaml
plugin-sdk:
  needs: test
  steps:
    - run: uv pip install -e packages/jw-core/tests/fixtures/plugin_sample
    - run: uv run python -m pytest packages/jw-core/tests/test_plugins_*.py -v
    - run: uv run jw plugins list --json | jq '.["jw_agent_toolkit.agents"] | length > 0'
```

Sin red. El fixture se instala desde path local.

## Métricas de éxito de la fase

- ✅ Fixture package se descubre por los 5 groups en CI offline.
- ✅ `verify_plugin` produce reporte estructurado para los 5 groups del fixture.
- ✅ Conflict detection con default `namespaced` produce ambos plugins con prefijo de dist.
- ✅ `JW_PLUGINS_DISABLED=1` desactiva discovery 100%.
- ✅ `JW_PLUGINS_ALLOW_LIST` filtra correctamente.
- ✅ Plugin que declara `jw-agent-toolkit>=99.0` se rechaza con `PluginVersionMismatch`.
- ✅ `default_agent_registry` merge no rompe los golden cases existentes de jw-eval.
- ✅ `jw plugins list/verify/disable` funcionan end-to-end.
- ✅ Documentado en `docs/plugin-sdk/{overview,security,capabilities,authoring}.md` (en/es/pt).

## Riesgos y mitigaciones

| # | Riesgo | Mitigación |
|---|---|---|
| 1 | Plugin malicioso roba secretos | Documentado en `security.md`; `ALLOW_LIST` para entornos sensibles; `DISABLED=1` para CI público |
| 2 | Plugin rompe el toolkit al cargar | Fail-soft default + `STRICT=1` opt-in para devs; verify_plugin antes de incluir en registry |
| 3 | Conflictos silenciosos entre plugins comunitarios | NAMESPACED por default — la ambigüedad explota explícita |
| 4 | Evolución del Protocol rompe plugins viejos | Política additive-only + capability matrix + version constraint |
| 5 | `lru_cache` no se limpia entre tests | `clear_plugin_cache()` en `conftest.py` autouse fixture |
| 6 | Discovery lento en startup con muchos plugins | `_discover` es lazy y cached; el costo se paga 1x por proceso |
| 7 | Fakes y reales con mismo nombre en `embedders` group | Reusamos la convención `fake-*` de Fase 33 dentro del propio plugin name |
| 8 | El usuario instala 2 plugins que declaran rangos incompatibles entre sí | No es nuestro problema; PEP resolution lo bloquea en `uv pip install` |

## Cómo verificar al cerrar

```bash
# 1. Instalar
uv sync --all-packages

# 2. Instalar el fixture como plugin externo
uv pip install -e packages/jw-core/tests/fixtures/plugin_sample

# 3. Verificar discovery
uv run jw plugins list
uv run jw plugins verify plugin_sample_agent

# 4. Correr suite de tests del módulo plugins
.venv/bin/python -m pytest packages/jw-core/tests/test_plugins_*.py -v

# 5. Verificar que jw-eval ve el plugin
uv run jw eval --layer 1 --filter agent=plugin_sample_agent

# 6. Verificar opt-out
JW_PLUGINS_DISABLED=1 uv run jw plugins list   # devuelve groups vacíos
```

## Pendientes explícitos (post-Fase 41)

- Sandboxing real via subprocess + IPC (ROADMAP, no urgente).
- Marketplace web sobre PyPI (no es responsabilidad del toolkit; basta `pip search jw-agent-toolkit-plugin-*`).
- Hot-reload de plugins en dev mode (nice-to-have).
- Plugins JS — depende de Fase 47 (port TS).

## Plan de implementación (alto nivel)

Spec hijo: `docs/superpowers/plans/2026-05-31-fase-41-plugin-sdk-plan.md` (a escribir tras aprobar este spec).

Pasos cronológicos:

1. Scaffold `jw_core/plugins/` con `errors.py` + `contracts.py` (Protocols sin lógica).
2. `policy.py` + `EntryPointSpec` + tests unitarios de policy.
3. `registry.py` con `_discover()` + cache + tests con `monkeypatch` de `entry_points`.
4. `verify.py` + `VerifyReport` + tests sobre fixture inline.
5. `factory.py` con `get_plugins` + `clear_plugin_cache` + tests.
6. Fixture package `tests/fixtures/plugin_sample/` con `pyproject.toml` + 5 stubs.
7. Test e2e: instalar fixture en venv temporal, verificar discovery, conflict, version.
8. Integrar en `jw-eval/cli.py::default_agent_registry`.
9. Integrar en `jw-rag/embed_providers/factory.py::_instantiate_registry`.
10. Integrar en `jw-mcp/server.py::register_tools`.
11. CLI: `jw plugins {list,verify,disable}`.
12. CI job `plugin-sdk` + script de smoke test.
13. Docs en/es/pt: `docs/plugin-sdk/{overview,security,capabilities,authoring}.md`.
14. Audit 1:1 en `docs/VISION_AUDIT.md`.

Cada paso con su PR + tests + sin regresiones en los 1984 tests existentes.
