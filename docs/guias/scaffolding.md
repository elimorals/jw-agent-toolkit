# Guía: scaffold de un plugin con `create-jw-agent`

> Crear un plugin nuevo del ecosistema jw-agent-toolkit en **menos de 10 minutos**, con todo cableado: entry-points de la Fase 41, CI listo, tests deterministas, README y Makefile.

## ¿Cuándo usar esto?

Si vas a publicar un paquete que **extiende** jw-agent-toolkit (un nuevo agente, parser, embedder, modelo VLM o generador), `create-jw-agent` te da el scaffolding completo. No es para empezar un proyecto nuevo desde cero ni para forkear el monorepo.

El proyecto generado:

- Declara los entry-points correctos para que `jw plugins list` lo detecte.
- Compila con `hatchling` (mismo backend que el monorepo).
- Incluye un workflow de GitHub Actions verde desde el primer commit.
- Tiene tests con `pytest` que verifican el contrato del Protocol que implementas.
- Soporta i18n en `en/es/pt` para los mensajes iniciales del CLI.

## Instalación

Tres opciones, de menor a mayor compromiso:

```bash
# Opción A: ejecutar una sola vez sin instalar (uv)
uvx create-jw-agent my-plugin

# Opción B: instalar global aislado (recomendado para uso recurrente)
pipx install create-jw-agent
create-jw-agent my-plugin

# Opción C: invocar desde el monorepo (sin publicar a PyPI)
uv run create-jw-agent my-plugin
```

> Si ya tienes el monorepo clonado y `jw-cli` instalado, también funciona:
>
> ```bash
> jw create-agent my-plugin
> ```
>
> Es un thin-wrapper que delega en el binario `create-jw-agent` y devuelve un hint claro de instalación si no lo encuentra.

## Uso básico

```bash
create-jw-agent my-apologetics-helper --type=agent --lang=es
```

Esto genera:

```
my-apologetics-helper/
├── pyproject.toml             # entry-point: jw_agent_toolkit.agents
├── src/my_apologetics_helper/
│   ├── __init__.py
│   └── agent.py               # implementa AgentProtocol (F41)
├── tests/
│   └── test_my_apologetics_helper.py
├── .github/workflows/ci.yml   # ruff + pytest + uv sync
├── .gitignore
├── Makefile                   # `make test`, `make lint`, `make build`
└── README.md
```

## Tipos disponibles

| `--type=`  | Entry-point group              | Protocol implementado | Casos de uso típicos |
|------------|--------------------------------|-----------------------|----------------------|
| `agent`    | `jw_agent_toolkit.agents`      | `AgentProtocol`       | Nuevo agente de razonamiento JW |
| `parser`   | `jw_agent_toolkit.parsers`     | `ParserProtocol`      | Parsear un tipo de documento de jw.org no soportado |
| `embedder` | `jw_agent_toolkit.embedders`   | `EmbedderProtocol`    | Embedding model wrapper (sentence-transformers, OpenAI, etc.) |
| `vlm`      | `jw_agent_toolkit.vlms`        | `VLMProtocol`         | Vision-language model para procesar imágenes de publicaciones |
| `gen`      | `jw_agent_toolkit.generators`  | `GeneratorProtocol`   | LLM generator local (llama.cpp, vLLM, etc.) |

## Validación de nombre

El scaffolder rechaza nombres incompatibles con PEP 503 / PyPI:

- Mayúsculas (`MyPlugin`) → `case`
- Espacios o símbolos (`with space`, `my_plugin`) → `invalid-shape`
- Empieza por dígito (`123foo`) → `invalid-shape`
- Prefijo reservado (`jw-anything`) → `reserved-prefix` (los `jw-*` son paquetes core)
- Coincide con un nombre reservado (`jw-core`, `jw-cli`, etc.) → `reserved-name`

El check opcional `--check-pypi` consulta el índice antes de generar para evitar colisión con un nombre ya publicado:

```bash
create-jw-agent my-plugin --check-pypi
# → ERROR if my-plugin already exists on PyPI
```

(Requiere instalar el extra: `pipx install 'create-jw-agent[pypi-check]'`.)

## i18n del CLI

El idioma de los mensajes se auto-detecta de `$LC_ALL` / `$LANG`:

```bash
LANG=es_ES.UTF-8 create-jw-agent demo
# → "Plugin 'demo' creado en …"

LANG=pt_BR.UTF-8 create-jw-agent demo
# → "Plugin 'demo' criado em …"

create-jw-agent demo --lang=en
# → "Plugin 'demo' created at …"
```

Hay 3 catálogos (`en`, `es`, `pt`) garantizados a tener las **mismas claves** vía test de paridad.

## ¿Qué hago después de generar?

```bash
cd my-apologetics-helper
uv sync                  # instala deps (jw-core, pytest, ruff)
make test                # tests pasan (verde desde el primer commit)
git init && git add .
git commit -m "feat: initial scaffold from create-jw-agent"
git push                 # CI pasa en GitHub Actions
```

A partir de aquí: implementa la lógica real en `src/<module>/<type>.py`, sigue extendiendo los tests, y publica a PyPI cuando estés listo (`make build && uv publish`).

## Verificar que tu plugin se descubre

Una vez instalado tu plugin junto al monorepo o en un entorno con `jw-cli`:

```bash
uv pip install -e ./my-apologetics-helper
jw plugins list --json
# → debería incluir tu plugin con su entry-point group
```

Si no aparece, ve al [authoring guide del Plugin SDK](../plugin-sdk/authoring.md) — explica cómo debuggear el descubrimiento por `importlib.metadata.entry_points()`.

## Variaciones

- **Plugin privado interno**: genera con `--license=Proprietary` (los públicos van con `Apache-2.0` por defecto).
- **Sin GitHub Actions**: borra `.github/workflows/ci.yml` después de generar; el resto es independiente del CI.
- **Multi-plugin en un mismo repo**: corre `create-jw-agent` varias veces apuntando a subdirectorios distintos (`--output-dir=packages/foo`).

## Recursos relacionados

- [docs/cookbook/01-…](../cookbook/01-resolver-cita.md) — recetas ejecutables que validan APIs públicas.
- [docs/plugin-sdk/authoring.md](../plugin-sdk/authoring.md) — guía exhaustiva del SDK de plugins (Fase 41).
- [docs/guias/construir-un-agente.md](construir-un-agente.md) — diseño conceptual de un agente, antes de scaffold.
