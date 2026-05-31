# Fase 42 — `scaffolding`: `create-jw-agent` + cookbook ejecutable

> **Fecha**: 2026-05-31
> **Estado**: Diseño aprobado (pendiente de implementación)
> **Owner**: Elias
> **Tier**: 2 (comunidad)
> **Depende de**: Fase 41 (`plugin-sdk`)
> **Documento padre**: [`2026-05-31-fases-39-48-overview.md`](2026-05-31-fases-39-48-overview.md)

## Motivación

Fase 41 abre los 5 extension points (agents, parsers, embedders, vlm_providers, gen_providers) vía entry points PEP 621. Pero el chasm de "entiendo la API en abstracto" a "tengo un repo Git verde con CI corriendo" sigue costando horas. La experiencia de las Fases 11-38 muestra que el bottleneck es:

1. Adivinar la estructura mínima de un `pyproject.toml` con entry point declarado.
2. Boilerplate de tests (fixtures, async, fakes determinísticos sin red).
3. CI mínimo que respete las reglas duras del toolkit (Python 3.13, ruff, sin red).
4. Saber qué API de `jw-core`/`jw-rag`/`jw-agents` invocar para cada tarea típica.

Fase 42 colapsa esos cuatro puntos a un solo comando + 12 recetas verificables. Objetivo concreto: **un colaborador externo publica su primer agente en PyPI en ≤ 10 minutos** (con CI verde y test que pasa).

## Objetivos

1. CLI `create-jw-agent <name> --type=... --lang=...` que genera proyecto listo-para-CI.
2. Cookbook de 12 recetas Markdown, cada una ≤ 60 líneas, todas auto-tested en CI.
3. Cada receta accesible vía URL canónica en el sitio Astro existente (Pagefind indexado).

## No-objetivos (boundaries vinculantes)

- **No** scaffold para paquetes "core" del monorepo (esos son `cookiecutter` interno de Elias, no público).
- **No** genera código LLM-backed por default (los providers son opt-in).
- **No** sustituye a Fase 41: el scaffolding produce el plugin; Fase 41 garantiza que el plugin **se descubre**.
- **No** publica a PyPI por el usuario (la receta "Publish your agent to PyPI" lo explica, pero no automatiza credenciales).
- **No** incluye templates JS/TS (Fase 47 es Python-only; mobile/extension es Fase 47/48).

## Decisión clave: ¿`create-jw-agent` ship en `jw-cli` o como paquete separado en PyPI?

Esta es la decisión más cara de revertir. Se evalúan las dos opciones:

### Opción A — Subcomando de `jw-cli` (`jw create-agent ...`)

**Pros**:
- Una sola dep (`pip install jw-cli`) y el usuario obtiene todo: CLI + scaffolder.
- Versionado acoplado: las plantillas siempre coinciden con la versión de los Protocols Fase 41.
- Cero infra adicional (publicación, badges, docs cross-repo).

**Contras**:
- `jw-cli` arrastra dependencias pesadas (asyncio HTTP clients, parsers, tikz para PDF export Fase 31). Un usuario que solo quiere scaffold instala 200 MB sin justificación.
- Patrón anti-idiomático en el ecosistema Python: `create-react-app`, `cookiecutter-django`, `cargo new`, `npm create vite` son **todos** ejecutables standalone, no subcomandos de un framework.
- Bootstrap circular: para crear un proyecto necesitas tener el monorepo instalado primero, lo cual asume que ya pasaste el setup que el scaffold debería minimizar.

### Opción B — Paquete separado `create-jw-agent` en PyPI

**Pros**:
- Idiomático: `uvx create-jw-agent my-thing` o `pipx run create-jw-agent` sin instalar nada permanente.
- Dependencias mínimas: solo `typer`, `jinja2`, `tomli-w`, `httpx` (opcional para chequeo de nombre PyPI). ~10 MB.
- Update independiente: arreglar un typo en una plantilla no requiere release de `jw-cli`.
- Marketing más limpio: badge `pip install create-jw-agent` legible en homepage.

**Contras**:
- Riesgo de drift de versiones: plantilla pinea `jw-core>=2.3.0` pero el monorepo está en `3.0.0` con breaking change en entry-point shape.
- Doble release pipeline (extra CI, otro paquete a mantener).
- Discovery: el usuario tiene que saber que existe; menos visible que un `jw --help` que lo enumere.

### Decisión: **Opción B con doble surface** (recomendada)

Se publica `create-jw-agent` como paquete standalone en PyPI **y** se expone `jw create-agent` como **thin wrapper** en `jw-cli` que invoca el binario standalone via `subprocess` si está disponible, con fallback a "instálalo con `uvx create-jw-agent`". El subcomando de `jw-cli` es solo discoverability — el código real vive en el paquete separado.

Mitigación al drift de versiones: la plantilla pinea **rangos compatibles** del Plugin SDK Fase 41 (`jw-core>=X.Y,<X+1.0`), nunca versiones exactas. CI del paquete `create-jw-agent` corre matrix contra los últimos 2 majors de `jw-core`.

## Arquitectura

### Paquete `create-jw-agent` (nuevo repo o subdirectorio publicable)

Vive en `packages/create-jw-agent/` dentro del monorepo. Publicado independientemente a PyPI. Distribuido como wheel pura (sin compilaciones nativas).

```
packages/create-jw-agent/
├── pyproject.toml
├── README.md
└── src/create_jw_agent/
    ├── __init__.py
    ├── cli.py              # Typer entrypoint
    ├── templates/
    │   ├── agent/          # type=agent
    │   │   ├── pyproject.toml.j2
    │   │   ├── src/{{name}}/__init__.py.j2
    │   │   ├── tests/test_{{name}}.py.j2
    │   │   ├── README.md.j2
    │   │   ├── Makefile.j2
    │   │   └── .github/workflows/ci.yml.j2
    │   ├── parser/         # type=parser
    │   ├── embedder/       # type=embedder
    │   ├── vlm/            # type=vlm
    │   └── gen/            # type=gen
    ├── render.py           # Jinja2 + filesystem ops
    ├── validate.py         # name compliance (PEP 503, no PyPI collision)
    └── lang/               # i18n de mensajes CLI
        ├── en.json
        ├── es.json
        └── pt.json
└── tests/
    ├── test_render.py
    ├── test_validate.py
    ├── test_cli.py
    └── golden/             # snapshot tests per type+lang combo
```

### Reglas duras de diseño

1. **Sin red en tests**. La validación de "nombre disponible en PyPI" es opt-in (`--check-pypi`), defaultea a `False`. Tests verifican el flag pero no hacen requests.
2. **i18n en/es/pt desde día 1** para mensajes CLI (errores, prompts interactivos, mensaje final). Default a `en`; auto-detect via `LANG`/`LC_ALL`; override con `--lang`.
3. **Identificadores Python siempre en inglés** (nombres de variables, funciones, módulos generados). Solo la prosa en strings/docstrings/README se traduce.
4. **Snapshot tests** sobre cada combinación (5 tipos × 3 idiomas = 15 snapshots) en `tests/golden/`. Cualquier cambio en una plantilla cambia el snapshot; el PR muestra el diff.
5. **Sin dependencias de `jw-core` en `create-jw-agent`**. Es un generator standalone. El proyecto generado sí depende de `jw-core`, pero el generator no.
6. **GPL-3.0** heredado (license en `pyproject.toml`).

### CLI surface

```
create-jw-agent NAME [OPTIONS]

Arguments:
  NAME                              Project name (kebab-case). Sin "jw-" prefix.

Options:
  --type [agent|parser|embedder|vlm|gen]   [default: agent]
  --lang [en|es|pt]                        [default: auto from $LANG]
  --output-dir PATH                        [default: ./NAME]
  --jw-core-version TEXT                   [default: ">=2.3,<3.0"]
  --license [GPL-3.0|MIT|Apache-2.0]       [default: GPL-3.0]
  --check-pypi / --no-check-pypi           [default: --no-check-pypi]
  --interactive / --no-interactive         [default: --interactive]
  --quiet                                  Suppress decorative output
  --version
  --help
```

### Output del scaffolder

Para `create-jw-agent my-translator --type=agent --lang=es`:

```
my-translator/
├── pyproject.toml                # con entry point [project.entry-points."jw_agent_toolkit.agents"]
├── README.md                     # prosa en español, código en inglés
├── Makefile                      # targets: install, test, lint, format, ci
├── .github/workflows/ci.yml      # Python 3.13, uv, ruff, pytest. NO red.
├── .gitignore                    # estándar Python + .venv, __pycache__, dist/, .ruff_cache
├── LICENSE                       # GPL-3.0 texto completo
├── src/my_translator/
│   ├── __init__.py               # export del callable
│   └── agent.py                  # stub: async def my_translator(**kwargs) -> AgentResult
└── tests/
    ├── __init__.py
    ├── conftest.py               # fixtures determinísticas (FakeWOLClient, etc.)
    └── test_my_translator.py     # 3 tests: smoke, contract, citations-present
```

### Estructura del agent stub generado (type=agent)

```python
# src/my_translator/agent.py
from jw_core.models import AgentResult, Finding, Citation

async def my_translator(
    *,
    question: str,
    language: str = "en",
    **kwargs,
) -> AgentResult:
    """Stub agent. Replace this with real logic.

    See docs/cookbook for recipes that show how to call jw-core APIs.
    """
    finding = Finding(
        source="stub",
        text=f"TODO: implement logic for {question!r}",
        citation=Citation(
            url="https://wol.jw.org/",
            title="Placeholder",
            metadata={},
        ),
    )
    return AgentResult(findings=[finding], metadata={"agent": "my_translator"})
```

### Tests generados (3 mínimos, todos deterministas, todos sin red)

```python
# tests/test_my_translator.py
import pytest
from my_translator.agent import my_translator

@pytest.mark.asyncio
async def test_smoke():
    result = await my_translator(question="Trinity", language="en")
    assert result.findings, "agent must return at least one finding"

@pytest.mark.asyncio
async def test_contract_shape():
    result = await my_translator(question="x", language="en")
    for finding in result.findings:
        assert finding.source
        assert finding.text
        assert finding.citation
        assert finding.citation.url.startswith("https://")

@pytest.mark.asyncio
async def test_citations_present():
    result = await my_translator(question="x", language="en")
    assert all(f.citation for f in result.findings)
```

### CI generado (`.github/workflows/ci.yml`)

```yaml
name: ci
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
      - run: uv python install 3.13
      - run: uv sync
      - run: uv run ruff check .
      - run: uv run ruff format --check .
      - run: uv run pytest -v
```

Cero secrets requeridos. Cero red. El proyecto generado pasa CI en su primer commit.

## Cookbook (`docs/cookbook/`)

### Estructura

```
docs/cookbook/
├── README.md                      # índice navegable + tabla
├── _common/
│   ├── conftest.py                # fixtures compartidas para tests de recetas
│   └── fakes.py                   # FakeWOLClient, FakeEmbedder reutilizables
├── 01-resolve-bible-reference.md
├── 02-search-and-synthesize.md
├── 03-telegram-bot.md
├── 04-finetune-llama-3.md
├── 05-add-parser.md
├── 06-custom-embedder.md
├── 07-add-nli.md
├── 08-publish-to-pypi.md
├── 09-trace-agent-run.md
├── 10-calibrate-golden-case.md
├── 11-browser-extension.md
├── 12-capacitor-app.md
└── tests/
    └── test_cookbook.py           # parsea cada .md, extrae bloques ```python ... ``` con marcador `# test`, los ejecuta
```

### Convención de receta

Cada receta sigue exactamente este formato (forzado por linter de cookbook):

```markdown
# {{Título de la receta}}

> **Tiempo estimado**: N minutos
> **Requisitos**: lista de extras opcionales (ej. `[local-embeddings]`)
> **Slug URL**: `/cookbook/{{slug}}` (deeplink Astro + Pagefind)

## ¿Qué construyes?

Frase única (≤2 líneas) explicando la salida.

## Código (copy-pasteable)

```python
# test
# Bloque ejecutable. Marcador `# test` en primera línea lo registra para pytest.
...
```

## Por qué funciona

≤3 párrafos explicando la decisión clave.

## Variaciones

3-5 bullets con tweaks comunes.

## Próximo paso

Link a la siguiente receta o a una guía relacionada.
```

Reglas duras:

- **≤60 líneas de código** por receta (línea estricta enforced por linter).
- **Bloques con `# test` en primera línea** los recoge `pytest --collect-from-markdown` (plugin nuevo `pytest-cookbook`).
- **Fakes en `_common/`** evitan red en CI.
- **Prosa en español; identificadores en inglés**.
- **3 idiomas**: cada receta tiene su versión `01-resolve-bible-reference.md` (es default), `01-resolve-bible-reference.en.md`, `01-resolve-bible-reference.pt.md`. Astro genera 3 URLs.

### Las 12 recetas obligatorias

| # | Slug | Cubre | Test verifica |
|---|---|---|---|
| 01 | `resolve-bible-reference` | `parse_reference` + `wol_url` | parse devuelve `BibleRef("John", 3, 16)` |
| 02 | `search-and-synthesize` | `search_topic_index` + Claude API (mockeado) | mock devuelve findings con citations |
| 03 | `telegram-bot` | REST API Fase 20 + python-telegram-bot | bot procesa mensaje sin red real |
| 04 | `finetune-llama-3` | `jw-finetune` recipe + JWPUB local | preset `synth_provider=None` extrae Q&A |
| 05 | `add-parser` | Plugin SDK Fase 41 + `ParsedDocument` | parser bytes→doc respeta Protocol |
| 06 | `custom-embedder` | `Embedder` Protocol + numpy stub | embed() devuelve shape (N, d) |
| 07 | `add-nli` | `fidelity_wrap` Fase 39 + agent existente | wrap añade `nli_verdict` a metadata |
| 08 | `publish-to-pypi` | `uv build` + `uv publish` + trusted publishing | check de pyproject válido |
| 09 | `trace-agent-run` | `AgentTracer` Fase 43 | JSON trace tiene los 4 campos del schema |
| 10 | `calibrate-golden-case` | YAML L1/L2/L3 + `jw eval` Fase 22 | `Suite.load_case()` valida shape |
| 11 | `browser-extension` | Manifest v3 + REST API Fase 48 | manifest.json valida con jsonschema |
| 12 | `capacitor-app` | `@jw-agent-toolkit/core` JS Fase 47 | npm package.json valida (sin install) |

Las recetas 11 y 12 declaran su requisito de Fase 47/48 en frontmatter; el linter las marca `skip-if-fase-not-ready` y CI no las falla hasta entonces. Cuando 47/48 mergeen, se quita el skip.

### Plugin `pytest-cookbook`

Nuevo paquete interno `tools/pytest-cookbook/` (no se publica). Implementa `pytest --collect-from-markdown=docs/cookbook/`:

1. Glob de `.md`.
2. Regex extracción de bloques ` ```python ` con `# test` en primera línea.
3. Cada bloque se compila a un test function nombrado `test_{recipe_slug}_block_{n}`.
4. Se ejecutan en process aislado con `_common/conftest.py` cargado.
5. Failure incluye link al `.md` y número de bloque.

CI corre `pytest --collect-from-markdown=docs/cookbook/ -v` como job separado `cookbook-tests`. Bloquea merge si falla.

## Integración con el sitio Astro

`website/src/content.config.ts` ya tiene `glob({ pattern: "**/*.md", base: "../docs" })`. Las recetas en `docs/cookbook/` se indexan automáticamente. Para cada receta:

- URL: `/docs/cookbook/01-resolve-bible-reference`
- Pagefind indexa título, frase "¿Qué construyes?", código, prosa.
- Botón "Copy" en cada bloque (componente Astro existente).
- Badge "Tested in CI" si la receta tiene bloque `# test` (auto-detectado al build).

Nueva ruta especial `/cookbook/<slug>` shortcut que redirige a `/docs/cookbook/<slug>` (alias amigable para compartir).

## Integración con `jw-cli`

Nuevo subcomando wrapper:

```python
# packages/jw-cli/src/jw_cli/commands/create_agent.py
@app.command(name="create-agent")
def create_agent_wrapper(...):
    """Thin wrapper that delegates to create-jw-agent."""
    try:
        subprocess.run(["create-jw-agent", *sys.argv[2:]], check=True)
    except FileNotFoundError:
        rich.print("[yellow]Install with: uvx create-jw-agent[/]")
        raise typer.Exit(1)
```

## Tests del propio paquete `create-jw-agent`

- `test_render.py`: cada (type, lang) combo genera output que matchea snapshot en `tests/golden/`.
- `test_validate.py`: rechaza nombres inválidos (`MyProject`, `jw-core`, `123start`, `with space`).
- `test_cli.py`: invocación end-to-end vía `typer.testing.CliRunner`; genera en `tmp_path`; verifica que el proyecto resultante pasa `uv sync && uv run pytest`.
- `test_no_network.py`: monkeypatch `httpx.get` para fallar; verifica que sin `--check-pypi` no se llama.

Total estimado: ~25 tests para el paquete, ~12 tests para el cookbook (1 por receta).

## Métricas de éxito de la fase

- ✅ `uvx create-jw-agent demo --type=agent` produce proyecto que pasa `uv run pytest` en el primer commit.
- ✅ Las 12 recetas existen con bloque `# test`; CI ejecuta los 12 y todos pasan offline.
- ✅ Sitio Astro expone las 12 recetas en `/docs/cookbook/*` + alias `/cookbook/*`; Pagefind las indexa.
- ✅ `jw create-agent --help` muestra el wrapper y delega correctamente al binario standalone.
- ✅ Tiempo de "clone repo de receta 01 + correr test" ≤ 2 min en macOS limpio.
- ✅ Tiempo medido end-to-end de "primer agente custom publicable" ≤ 10 min.

## Riesgos y mitigaciones

| # | Riesgo | Mitigación |
|---|---|---|
| 1 | Plantillas divergen del Protocol Fase 41 | Matrix CI corre `create-jw-agent` + `jw-core` última versión y verifica que el proyecto generado pasa `verify_plugin()` de Fase 41 |
| 2 | Recetas pudren con cambios de API | `cookbook-tests` job bloqueante en CI; cualquier API breaking change rompe el job antes del merge |
| 3 | Usuarios eligen nombre que choca en PyPI | `--check-pypi` opt-in con warning amigable; doc explica el flag |
| 4 | Wrapper `jw create-agent` se descoordina | El wrapper es <20 LOC y solo hace `subprocess`; sin lógica propia |
| 5 | Snapshot tests muy frágiles | Snapshot diff legible; PR muestra el cambio; auto-update con `pytest --snapshot-update` |
| 6 | Receta `04-finetune-llama-3` requiere GPU/MLX | Marker `# test slow` + skip en CI público; corre en nightly self-hosted runner cuando exista |
| 7 | Receta `11`/`12` bloqueada por Fase 47/48 | Frontmatter `requires-fase: 48`; linter las marca skip; CI no las falla |
| 8 | Drift entre `create-jw-agent` PyPI y monorepo | Release del scaffolder se hace **después** de release de `jw-core`; CHANGELOG cross-link obligatorio |

## Pendientes explícitos (post-Fase 42)

- Template para web UI / dashboard sobre traces (espera Fase 43 + decisión de stack).
- Template multi-package monorepo (cookiecutter-jw-monorepo) — fuera de scope; cuando aparezca un caso real.
- Auto-PR a `jw-agent-toolkit-plugins-list` (catálogo curado de plugins) — Fase futura T2.
- Plantilla específica de Sign Language tooling — espera Fase de visión propia.

## Cómo verificar al cerrar

```bash
# 1. Tests del scaffolder
uv run --package create-jw-agent pytest

# 2. Tests del cookbook
uv run pytest --collect-from-markdown=docs/cookbook/ -v

# 3. End-to-end: genera proyecto y mira que su CI pase localmente
uvx create-jw-agent demo --type=agent --lang=en --no-interactive
cd demo
uv sync && uv run ruff check . && uv run pytest

# 4. Tiempo total (debe ser < 10 min en máquina limpia)
time bash -c '
  uvx create-jw-agent timer-test --type=agent --no-interactive
  cd timer-test
  uv sync --quiet
  uv run pytest -q
'
```

## Plan de implementación (alto nivel)

Spec hijo: `docs/superpowers/plans/2026-05-31-fase-42-scaffolding-plan.md` (a escribir tras aprobar este spec).

Pasos cronológicos:

1. Scaffold de `packages/create-jw-agent/` (pyproject, estructura, README).
2. `render.py` + `validate.py` con tests unitarios.
3. Plantillas tipo `agent` (en/es/pt) + golden snapshots.
4. Plantillas tipos `parser`, `embedder`, `vlm`, `gen` + snapshots.
5. CLI Typer + i18n + tests E2E con `CliRunner`.
6. Wrapper `jw create-agent` en `jw-cli`.
7. Plugin `pytest-cookbook` en `tools/`.
8. Recetas 01-10 (las que no dependen de Fase 47/48).
9. Recetas 11-12 con marker skip-until-fase.
10. Integración Astro (verifica que `/cookbook/*` resuelve + Pagefind indexa).
11. Job `cookbook-tests` en CI del monorepo.
12. Pipeline de release: GitHub Action que publica `create-jw-agent` a PyPI via trusted publishing en tag `create-jw-agent-vX.Y.Z`.
13. Guía en `docs/guias/scaffolding.md` + audit 1:1 en `docs/VISION_AUDIT.md`.

Cada paso con su PR + tests + sin regresiones en los 1984 tests existentes ni en los Protocols Fase 41.
