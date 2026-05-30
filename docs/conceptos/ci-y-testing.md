# Conceptos: CI y testing

> Cómo está organizada la suite de pruebas, cómo funciona el sistema de cassettes para evitar tocar la red, y cómo GitHub Actions corre todo en cada PR.

## Estructura de la suite

```
packages/jw-core/tests/
├── conftest.py                       # Config compartida (cassette dir, vcr_config)
├── fixtures/                         # HTMLs reales descargados de jw.org
│   ├── nwtsty_john3.html             (195KB)
│   ├── wt_pub_index_trinity.html      (73KB)
│   ├── wt_pub_index_home.html
│   ├── wt_pub_index_alt_1204387.html
│   └── wt_research_guide.html
├── cassettes/                        # Auto-generado por pytest-recording
│   └── test_cassettes/*.yaml
├── test_reference_parser.py          # Parser de citas bíblicas
├── test_study_notes_parser.py        # Notas + cross-refs nwtsty
├── test_topic_index_parser.py        # Páginas de tema
├── test_topic_index_client.py        # Cliente de alto nivel
├── test_pub_media_unit.py            # GETPUBMEDIALINKS
├── test_epub_parser.py               # EPUB
├── test_jwpub_metadata.py            # JWPUB metadata + decryption
├── test_phase9_infra.py              # cache + throttle + telemetry
├── test_polite_get.py                # _polite.politely_get
└── test_cassettes.py                 # 4 endpoints críticos cassette-backed

packages/jw-cli/tests/test_cli_smoke.py
packages/jw-mcp/tests/test_server_smoke.py
packages/jw-rag/tests/test_rag.py
packages/jw-agents/tests/test_agents_unit.py
```

**Total**: 166 passing + 4 skipped (los skipped son los cassettes que aún no se han grabado en una máquina dada).

## Filosofía: tres tipos de prueba

### 1. Tests puros (la mayoría)

No tocan red ni disco. Pasan strings/HTML/dicts a parsers/utilities y validan output.

Ejemplos: `test_reference_parser.py`, `test_phase9_infra.py`, `test_polite_get.py`.

Rápidos, deterministas, ideales para TDD.

### 2. Tests con fixtures HTML

Cargan un archivo `.html` real previamente descargado en `tests/fixtures/`. Validan que los parsers extraigan correctamente la estructura observada en producción.

Ejemplos: `test_study_notes_parser.py` (usa `nwtsty_john3.html`), `test_topic_index_parser.py` (usa `wt_pub_index_trinity.html`).

Las fixtures se descargan vía los scripts `scripts/fetch_*.py` y se commitean. Cuando jw.org cambia el HTML, hay que regenerar el fixture y a veces ajustar el parser.

### 3. Tests cassette-backed (pytest-recording)

`pytest-recording` graba las respuestas HTTP reales en un YAML la primera vez, y las replaya en runs subsecuentes. Mantienen los tests **offline-capable** y **deterministas**, pero a la vez documentan la SHAPE real de los endpoints.

```python
@pytest.mark.vcr
async def test_mediator_languages_shape():
    client = MediatorClient()
    langs = await client.list_languages(in_language="E")
    assert len(langs) >= 50
```

Cassettes vivos en `tests/cassettes/test_cassettes/*.yaml`. Tamaño típico ~10-50 KB.

#### Grabarlos

Primera vez (o tras un cambio de API):

```bash
uv run pytest packages/jw-core/tests/test_cassettes.py --record-mode=rewrite
```

Re-graba todos los cassettes y los commitea. Los tests `@pytest.mark.skipif(not _cassette_present(...))` se saltan si el archivo no existe — por eso aparecen como **4 skipped** en la primera ejecución limpia.

#### Replayar (default)

```bash
uv run pytest packages/jw-core/tests/test_cassettes.py
```

`vcr_config.record_mode = "none"` fuerza modo replay-only. Cero red.

#### Sanitización

`conftest.py` strippea headers identificantes para que los cassettes sean reproducibles entre máquinas:

```python
"filter_headers": ["authorization", "cookie", "user-agent", "x-client-id"]
```

#### Qué endpoints cubre

Solo los 4 más críticos:

- `mediator.list_languages` — registro JW de idiomas
- `weblang.list_languages` — registro alterno
- `cdn.search` — búsqueda autenticada
- `pub_media.get_publication` — catálogo de archivos

Los demás endpoints están cubiertos por unit tests con fixtures HTML.

## GitHub Actions CI

Archivo: `.github/workflows/ci.yml`.

### Triggers

- `push` a `main` o `master`.
- `pull_request` a `main` o `master`.
- `workflow_dispatch` (botón manual en la UI de Actions).

### Concurrency

```yaml
concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true
```

Cancela runs viejos del mismo PR cuando llega un push nuevo. Ahorra minutos de Actions.

### Job `test`

Runner: `ubuntu-latest`. Matrix: Python 3.13.

Pasos:

1. **Checkout** (`actions/checkout@v4`).
2. **Install uv** (`astral-sh/setup-uv@v3`) con cache habilitado vía `uv.lock`.
3. **Python install** (`uv python install 3.13`).
4. **Deps** (`uv sync --all-packages`).
5. **Ruff lint** (`uv run ruff check packages/`).
6. **Ruff format check** (`uv run ruff format --check packages/`).
7. **Mypy** strict en `jw-core` y `jw-mcp` (`continue-on-error: true` — sabemos que FastMCP tiene falsos positivos).
8. **Pytest** (`uv run pytest packages/ -v --tb=short`).
9. **Build wheels smoke**: `for pkg in packages/*; do uv build --wheel; done`.

### Job `security`

Corre **después** de `test` (`needs: test`):

```bash
uv run --with bandit bandit -r packages/*/src -ll
```

Scan estático de seguridad. `continue-on-error` también — los hallazgos son informativos.

## Ejecutar local antes de PR

```bash
# Linting
uv run ruff check packages/
uv run ruff format --check packages/

# Tipos
uv run mypy packages/jw-core/src packages/jw-mcp/src

# Tests completos
uv run pytest packages/ -v

# Solo un paquete
uv run pytest packages/jw-core -v

# Solo un test
uv run pytest packages/jw-core/tests/test_reference_parser.py::test_simple_match -v
```

## Cómo añadir un test cassette nuevo

1. Añade un test `@pytest.mark.vcr` en `test_cassettes.py`:

```python
@pytest.mark.vcr
@pytest.mark.skipif(
    not _cassette_present("test_my_new_endpoint"),
    reason="No cassette; run with --record-mode=rewrite once.",
)
async def test_my_new_endpoint() -> None:
    client = SomeClient()
    data = await client.method(...)
    assert ...
```

2. Grábalo:

```bash
uv run pytest packages/jw-core/tests/test_cassettes.py::test_my_new_endpoint --record-mode=rewrite
```

3. Verifica que el YAML resultante es razonable (~10-50 KB; sin tokens ni headers identificantes — `conftest.py` ya los filtra).

4. Commit el `.yaml` con el código.

## Cómo regrabar todos los cassettes

Útil cuando un endpoint cambió su shape (y el test ya no pasa):

```bash
uv run pytest packages/jw-core/tests/test_cassettes.py --record-mode=rewrite
git diff packages/jw-core/tests/cassettes/
```

Revisa el diff — un cambio mínimo (key añadida) suele ser inofensivo; un cambio grande puede indicar que la API rompió algo.

## Ver también

- [`docs/guias/scripts-de-exploracion.md`](../guias/scripts-de-exploracion.md) — para los scripts que generan fixtures
- [`docs/guias/infraestructura-fase9.md`](../guias/infraestructura-fase9.md) — para entender qué hacen los módulos que `test_phase9_infra.py` cubre
