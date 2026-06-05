# Fase 66 — `mcp-jw-brain`: exponer `jw-brain` como tools MCP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans`. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Exponer las operaciones del `second-brain` (`status`, `query`, `lint`, `snapshot`, `compile`) como tools `@mcp.tool` en `packages/jw-mcp/src/jw_mcp/server.py`, permitiendo a Claude/Cursor/cualquier cliente MCP consultar el knowledge graph del `jw-brain` (con datos de F58) sin hablar directamente con DuckDB/Neo4j.

**Architecture:** No se crea servidor MCP independiente ni proxy. El precedente del repo (`server.py`, ~90 tools registradas con `@mcp.tool`) se extiende con 5-7 tools nuevas que envuelven funciones ya `async dict-returning` del módulo `jw_brain.server`. Tools resuelven el brain por `name` (param) y son no-op si no hay brain inicializado (degraded mode).

**Tech Stack:** Python 3.13 · `fastmcp` (ya en stack) · `jw-brain` (F49) — sin deps nuevas.

**Spec/origen brainstorm:** [`docs/conceptos/integraciones-priorizadas.md`](../../conceptos/integraciones-priorizadas.md) — recomendación brutal punto 7 (TIER S trivial, ~4h). El repo NO usa `neo4j-contrib/mcp-neo4j` upstream — el patrón se replica in-process porque jw-brain ya tiene la lógica.

**Depende de:** F49 (`jw-brain` core con `jw_brain.server` module). NO depende de F58 (bible-kg) ni F66 funciona sin él — el grafo vacío también responde queries (devuelve `[]`).

---

## File map

Modifica:
- `packages/jw-mcp/src/jw_mcp/server.py` — añadir 7 tools `@mcp.tool` con prefijo `second_brain_*`.
- `packages/jw-mcp/tests/test_protocol.py` — añadir las 7 tools al `_EXPECTED_TOOLS` set.
- `docs/referencia/jw-mcp.md` — sección "Fase 66 — second brain tools".
- `docs/ROADMAP.md` — entrada F66.
- `docs/superpowers/plans/2026-06-04-master-integracion-stars-plan.md` — marcar F66 ✅.

Crea:
- `packages/jw-mcp/tests/test_jw_brain_tools.py` — 5 tests específicos del nuevo wire-up.

NO se crea archivo nuevo en `jw-brain` — solo se reusan las funciones de `jw_brain.server` que ya existen desde F49.

---

## Decisiones clave de diseño (anti-placeholder)

### Por qué NO proxy a `mcp-neo4j` upstream
`neo4j-contrib/mcp-neo4j` (955★) es un MCP server **standalone** que se conecta a Neo4j vía Bolt. Para integrarlo en `jw-mcp` habría que añadir un **cliente MCP** (no existe en el toolkit) que reexponga tools de otro servidor. Costo: librería nueva + 200 LOC de plumbing. Beneficio: ninguno — `jw-brain` ya tiene la lógica para queries Cypher (cuando backend=neo4j) y para queries SQL (cuando backend=duckdb). Mejor expone directo.

### Resolver brain por nombre, no por path
Las tools reciben `brain: str | None = None` que se resuelve via el registry `~/.jw-brain/registry.toml` (precedente F49 `resolve_brain()`). Si no hay brain, las tools devuelven `{"error": "no brain configured"}` en vez de lanzar excepción — patrón consistente con el resto de tools MCP del repo.

### Async wrappers, no thread pools
`jw_brain.server.second_brain_*` ya son `async def` (verificado en exploración). Los wrappers son `@mcp.tool async def` que awaitan directo. No hace falta `asyncio.to_thread`.

### `query` tool: limitar peligro
El parámetro `mode` (`"auto"|"wiki"|"graph"|"vector"`) ya viene validado por `jw_brain.server.second_brain_query`. La tool MCP NO acepta SQL/Cypher crudo (read-only por diseño de jw-brain). Si un día se quiere exponer Cypher crudo, va detrás de `--allow-raw-queries` flag — fuera de scope F66.

### NO tocar `_EXPECTED_TOOLS` semilla F49
El precedente F49 ya registró tools `second_brain_*` (verificado en exploración: "second_brain_compile, second_brain_query, etc."). Si ya están, F66 es **no-op confirmador**: solo refresca tests y docs. Verificar en Task 1 antes de añadir wrappers.

---

### Task 1: Audit — qué tools `second_brain_*` ya existen en server.py

**Files:**
- Read (no modify): `packages/jw-mcp/src/jw_mcp/server.py`
- Read (no modify): `packages/jw-brain/src/jw_brain/server.py`

- [ ] **Step 1: Listar tools registradas hoy con prefijo `second_brain_`**

Run: `cd /Users/elias/Documents/Trabajo/jw-agent-toolkit && grep -n "second_brain_" packages/jw-mcp/src/jw_mcp/server.py | head -40`
Expected output: lista de líneas, p.ej.:
```
1234:async def second_brain_compile(brain: str | None = None, ...) -> dict
1278:async def second_brain_query(question: str, ...) -> dict
```

- [ ] **Step 2: Listar funciones `second_brain_*` disponibles en jw-brain**

Run: `grep -n "^async def second_brain_" packages/jw-brain/src/jw_brain/server.py`
Expected: las funciones públicas (`second_brain_status`, `second_brain_compile`, `second_brain_query`, `second_brain_lint`, `second_brain_snapshot`, etc.).

- [ ] **Step 3: Calcular gap**

Generar mentalmente la lista `tools_to_add = (jw_brain functions) - (jw_mcp wrappers)`. Si el gap es vacío → marca F66 como "ya integrado" y salta a Task 5 (doc + commit). Si hay gap (típicamente 1-3 wrappers nuevos) → continúa Task 2.

- [ ] **Step 4: Documentar gap en commit message preparatorio**

Solo nota mental — no commit aún. Ejemplo de gap esperado:
- Falta `second_brain_status` (status del backend, stats nodos/edges)
- Falta `second_brain_lint` (corre F39 NLI cross-pub)
- Falta `second_brain_snapshot` (versionado declarativo del brain)

Si el gap es vacío, todos los siguientes tasks excepto Task 5 se saltan.

---

### Task 2: Añadir wrappers `@mcp.tool` faltantes

**Files:**
- Modify: `packages/jw-mcp/src/jw_mcp/server.py`

- [ ] **Step 1: Localizar la zona de tools jw-brain en `server.py`**

Buscar `# Second Brain` o las tools `second_brain_compile`/`second_brain_query` existentes. Añadir nuevas tools **junto a las existentes** (no en otra sección) para mantener cohesión.

- [ ] **Step 2: Añadir wrapper para `second_brain_status` (si falta)**

```python
@mcp.tool
async def second_brain_status(brain: str | None = None) -> dict[str, Any]:
    """Devuelve el estado del second-brain seleccionado: backend en uso,
    counts de nodos/edges/pendientes en raw/inbox, último snapshot.

    Args:
        brain: nombre del brain en el registry (~/.jw-brain/registry.toml).
            Si None usa el default ($JW_BRAIN_HOME o cwd).

    Returns:
        Dict con keys: `name`, `domain`, `backend`, `node_count`,
        `edge_count`, `pending_in_inbox`, `processed`, `last_snapshot`,
        o `{"error": "<reason>"}` si no hay brain configurado.
    """
    try:
        from jw_brain.server import second_brain_status as _impl
        return await _impl(brain=brain)
    except ImportError:
        return {"error": "jw-brain package not installed; run uv sync --all-packages"}
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}
```

- [ ] **Step 3: Añadir wrapper para `second_brain_lint` (si falta)**

```python
@mcp.tool
async def second_brain_lint(
    brain: str | None = None,
    *,
    rules: list[str] | None = None,
) -> dict[str, Any]:
    """Corre los linters del second-brain: orphan_pages, stale_chunks,
    missing_xrefs, contradiction_finder (F39 NLI). Devuelve findings
    agrupados por rule.

    Args:
        brain: nombre del brain.
        rules: subset de rules a correr; None corre todas.

    Returns:
        Dict con `total_findings`, `by_rule: {rule: [findings]}`.
    """
    try:
        from jw_brain.server import second_brain_lint as _impl
        return await _impl(brain=brain, rules=rules)
    except ImportError:
        return {"error": "jw-brain package not installed"}
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}
```

- [ ] **Step 4: Añadir wrapper para `second_brain_snapshot` (si falta)**

```python
@mcp.tool
async def second_brain_snapshot(
    brain: str | None = None,
    *,
    label: str | None = None,
) -> dict[str, Any]:
    """Crea un snapshot declarativo del brain (state actual de nodos/edges)
    en `<brain>/snapshots/<timestamp_or_label>.json`. Útil para diff entre
    versiones del KG y rollback.

    Args:
        brain: nombre del brain.
        label: si provee, usa label en el path; si None usa timestamp ISO.

    Returns:
        Dict con `snapshot_path`, `node_count`, `edge_count`.
    """
    try:
        from jw_brain.server import second_brain_snapshot as _impl
        return await _impl(brain=brain, label=label)
    except ImportError:
        return {"error": "jw-brain package not installed"}
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}
```

- [ ] **Step 5: Añadir wrapper para `second_brain_list` (si falta)**

```python
@mcp.tool
async def second_brain_list() -> dict[str, Any]:
    """Lista los brains registrados en `~/.jw-brain/registry.toml`.

    Returns:
        Dict con `brains: [{name, path, domain, default}]`.
    """
    try:
        from jw_brain.server import second_brain_list as _impl
        return await _impl()
    except ImportError:
        return {"error": "jw-brain package not installed"}
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}
```

- [ ] **Step 6: Smoke import**

Run: `uv run python -c "from jw_mcp.server import mcp; print([t.name for t in mcp.list_tools() if 'second_brain' in t.name])"`
Expected: lista incluye todas las tools `second_brain_*`.

- [ ] **Step 7: Commit**

```bash
git add packages/jw-mcp/src/jw_mcp/server.py
git commit -m "feat(jw-mcp): F66.2 add second_brain_status status lint snapshot list tools"
```

---

### Task 3: Tests del protocolo MCP — `_EXPECTED_TOOLS`

**Files:**
- Modify: `packages/jw-mcp/tests/test_protocol.py`

- [ ] **Step 1: Localizar `_EXPECTED_TOOLS`**

Run: `grep -n "_EXPECTED_TOOLS" packages/jw-mcp/tests/test_protocol.py`
Expected: línea donde se define el set/list de tools esperadas.

- [ ] **Step 2: Añadir las 4 nuevas tools**

Editar el set/lista agregando:
```python
    "second_brain_status",
    "second_brain_lint",
    "second_brain_snapshot",
    "second_brain_list",
```
(en orden alfabético si el set lo está, o al final del bloque second_brain_*).

- [ ] **Step 3: Run test, expect PASS**

Run: `uv run pytest packages/jw-mcp/tests/test_protocol.py -v`
Expected: tests del protocolo siguen pasando (no regresión); las nuevas tools aparecen.

- [ ] **Step 4: Commit**

```bash
git add packages/jw-mcp/tests/test_protocol.py
git commit -m "test(jw-mcp): F66.3 register 4 second_brain tools in protocol expected set"
```

---

### Task 4: Test E2E con DuckDB temp brain

**Files:**
- Create: `packages/jw-mcp/tests/test_jw_brain_tools.py`

- [ ] **Step 1: Test que crea un brain temp y verifica que las tools responden**

```python
# packages/jw-mcp/tests/test_jw_brain_tools.py
"""F66 — verifica que las tools second_brain_* del MCP server
responden correctamente sobre un brain DuckDB inicializado en tmp_path."""
from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture()
def temp_brain(tmp_path, monkeypatch) -> Path:
    """Inicializa un brain TJ vacío en tmp_path y lo registra como default."""
    monkeypatch.setenv("JW_BRAIN_HOME", str(tmp_path))
    from jw_brain.cli import app as brain_cli
    from typer.testing import CliRunner

    runner = CliRunner()
    result = runner.invoke(
        brain_cli,
        ["init", "--domain", "tj", "--brain", "test", "--vault", str(tmp_path / "vault")],
    )
    assert result.exit_code == 0, result.stdout
    return tmp_path


@pytest.mark.asyncio
async def test_second_brain_status_responds(temp_brain):
    from jw_mcp.server import second_brain_status

    result = await second_brain_status.fn(brain="test")
    assert "error" not in result, result
    assert result["name"] == "test"
    assert result["domain"] == "tj"
    assert result["node_count"] == 0


@pytest.mark.asyncio
async def test_second_brain_list_includes_test_brain(temp_brain):
    from jw_mcp.server import second_brain_list

    result = await second_brain_list.fn()
    assert "error" not in result, result
    names = {b["name"] for b in result["brains"]}
    assert "test" in names


@pytest.mark.asyncio
async def test_second_brain_status_unknown_brain_returns_error():
    from jw_mcp.server import second_brain_status

    result = await second_brain_status.fn(brain="does_not_exist_xyz_404")
    assert "error" in result


@pytest.mark.asyncio
async def test_second_brain_query_empty_brain_returns_empty(temp_brain):
    from jw_mcp.server import second_brain_query

    result = await second_brain_query.fn(question="¿quién es Abraham?", brain="test")
    # Empty brain → 0 hits, NO error
    assert "error" not in result
    assert result.get("hits", []) == [] or result.get("count", 0) == 0


@pytest.mark.asyncio
async def test_second_brain_snapshot_creates_file(temp_brain):
    from jw_mcp.server import second_brain_snapshot

    result = await second_brain_snapshot.fn(brain="test", label="test_snapshot")
    assert "error" not in result, result
    assert "snapshot_path" in result
    assert Path(result["snapshot_path"]).exists()
```

> **Nota**: `second_brain_query.fn` y similar — fastmcp wrappea las funciones como objetos `Tool`. Para llamar directo en test, accedemos `.fn` que es la función subyacente. Si la API del fastmcp del repo usa otra forma (`_func`, `__call__`), adaptar.

- [ ] **Step 2: Run, expect PASS**

Run: `uv run pytest packages/jw-mcp/tests/test_jw_brain_tools.py -v`
Expected: 5 passed.

- [ ] **Step 3: Commit**

```bash
git add packages/jw-mcp/tests/test_jw_brain_tools.py
git commit -m "test(jw-mcp): F66.4 e2e tests second_brain tools over temp DuckDB brain"
```

---

### Task 5: Doc + ROADMAP + master plan update

**Files:**
- Modify: `docs/referencia/jw-mcp.md`
- Modify: `docs/ROADMAP.md`
- Modify: `docs/superpowers/plans/2026-06-04-master-integracion-stars-plan.md`

- [ ] **Step 1: Añadir sección en `docs/referencia/jw-mcp.md`**

Localizar la tabla "Superficie de herramientas MCP" o sección equivalente. Añadir bloque:

```markdown
## Fase 66 — Second Brain tools

Las siguientes tools exponen el knowledge graph del `jw-brain` (F49+F58) a
clientes MCP (Claude Desktop, Cursor, etc.). Todas resuelven el brain por
nombre via el registry `~/.jw-brain/registry.toml`.

| Tool | Inputs | Returns |
|---|---|---|
| `second_brain_status` | `brain?: str` | stats del brain (counts, backend, último snapshot) |
| `second_brain_list` | — | lista brains registrados |
| `second_brain_query` | `question: str`, `mode?: "auto"\|"wiki"\|"graph"\|"vector"`, `brain?: str` | hits con `source_url`/`canonical_id`/`snippet` |
| `second_brain_compile` | `brain?: str`, `dry_run?: bool`, `language?: str` | counts de nodos/edges procesados |
| `second_brain_lint` | `brain?: str`, `rules?: list[str]` | findings agrupados por rule |
| `second_brain_snapshot` | `brain?: str`, `label?: str` | path del snapshot + counts |

Modo "degraded": si `jw-brain` no está instalado o no hay brain configurado,
las tools devuelven `{"error": "..."}` (no lanzan excepción) — consistencia
con el resto del MCP server.
```

- [ ] **Step 2: Añadir entrada en `docs/ROADMAP.md`**

```markdown
## Fase 66 — second brain expuesto vía MCP ✅

- ✅ Tools `@mcp.tool` para `second_brain_status/list/compile/query/lint/snapshot` en `jw_mcp/server.py`.
- ✅ Modo "degraded" cuando `jw-brain` no está instalado o no hay brain en registry.
- ✅ Tests E2E sobre temp DuckDB brain (`test_jw_brain_tools.py`).
- ✅ Doc actualizada en `docs/referencia/jw-mcp.md`.
- ⬜ Tool `second_brain_export` para exportar el grafo completo a un JSON portable (sprint siguiente).
```

- [ ] **Step 3: Marcar F66 ✅ en master plan**

Editar la tabla "Estado de redacción de los planes" en `docs/superpowers/plans/2026-06-04-master-integracion-stars-plan.md`:
```markdown
| F66 | ✅ 2026-06-04 | ⬜ | — |
```

- [ ] **Step 4: Commit**

```bash
git add docs/referencia/jw-mcp.md docs/ROADMAP.md docs/superpowers/plans/2026-06-04-master-integracion-stars-plan.md
git commit -m "docs(F66): document second_brain MCP tools plus ROADMAP entry"
```

---

## Tests resumen

```bash
uv run pytest packages/jw-mcp/tests/test_protocol.py \
              packages/jw-mcp/tests/test_jw_brain_tools.py \
              -v --tb=short
```
Esperado: tests previos siguen verde + 5 nuevos passed.

Smoke total `jw-mcp`:
```bash
uv run pytest packages/jw-mcp/tests/ -v --tb=short
```

---

## Self-review checklist

- ✅ **Cobertura de spec**: las 7 ops del `second-brain` se exponen como tools. Modo degraded cubierto. Brain registry respetado.
- ✅ **No placeholders**: cada Step tiene código real. Donde falta una API del repo (`mcp.list_tools()`, `Tool.fn`) se indica explícitamente "adapta a lo que fastmcp del repo expone".
- ✅ **Consistencia de tipos**: todas las tools devuelven `dict[str, Any]` siguiendo precedente del resto del server.py. Param `brain: str | None` consistente.
- ⚠️ **Posible gap**: Task 1 puede revelar que TODAS las tools ya existen (F49 las metió). En ese caso, Tasks 2-3 se reducen a verificación y solo Tasks 4-5 corren. Esto es deseable — significa que F66 es virtualmente "instant complete".
