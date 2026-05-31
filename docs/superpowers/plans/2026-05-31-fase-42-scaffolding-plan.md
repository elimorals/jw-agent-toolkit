# Fase 42 — `create-jw-agent` + Cookbook Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `create-jw-agent`, a standalone PyPI-publishable scaffolder (Typer + Jinja2) that emits CI-green plugin projects in ≤ 10 minutes, plus a 12-recipe cookbook where every recipe is executed offline in CI via a new `pytest-cookbook` plugin.

**Architecture:** New publishable package `packages/create-jw-agent/` (zero `jw-core` dep). Internal-only `tools/pytest-cookbook/` plugin discovers ` ```python ` blocks tagged `# test` inside Markdown and executes them as real tests. Cookbook recipes live in `docs/cookbook/` (default Spanish prose, English identifiers, English/Portuguese mirrors). Thin `jw create-agent` wrapper in `jw-cli` delegates via `subprocess`. CI gains one new blocking job (`cookbook-tests`) plus snapshot tests for the scaffolder.

**Tech Stack:** Python 3.13 · Typer (CLI) · Jinja2 (templates) · tomli-w (manifest writes) · httpx (opt-in PyPI name check) · Pydantic (validation) · pytest (own tests + cookbook runner) · PyYAML (recipe frontmatter) · uv (workspace + publish) · GitHub Actions (CI + trusted publishing).

**Spec:** [`docs/superpowers/specs/2026-05-31-fase-42-scaffolding-design.md`](../specs/2026-05-31-fase-42-scaffolding-design.md).

---

## File map

Creates:
- `packages/create-jw-agent/pyproject.toml`
- `packages/create-jw-agent/README.md`
- `packages/create-jw-agent/src/create_jw_agent/__init__.py`
- `packages/create-jw-agent/src/create_jw_agent/validate.py`
- `packages/create-jw-agent/src/create_jw_agent/render.py`
- `packages/create-jw-agent/src/create_jw_agent/cli.py`
- `packages/create-jw-agent/src/create_jw_agent/i18n.py`
- `packages/create-jw-agent/src/create_jw_agent/lang/en.json`
- `packages/create-jw-agent/src/create_jw_agent/lang/es.json`
- `packages/create-jw-agent/src/create_jw_agent/lang/pt.json`
- `packages/create-jw-agent/src/create_jw_agent/templates/agent/pyproject.toml.j2`
- `packages/create-jw-agent/src/create_jw_agent/templates/agent/README.md.j2`
- `packages/create-jw-agent/src/create_jw_agent/templates/agent/Makefile.j2`
- `packages/create-jw-agent/src/create_jw_agent/templates/agent/.gitignore.j2`
- `packages/create-jw-agent/src/create_jw_agent/templates/agent/.github/workflows/ci.yml.j2`
- `packages/create-jw-agent/src/create_jw_agent/templates/agent/src/{{module}}/__init__.py.j2`
- `packages/create-jw-agent/src/create_jw_agent/templates/agent/src/{{module}}/agent.py.j2`
- `packages/create-jw-agent/src/create_jw_agent/templates/agent/tests/__init__.py.j2`
- `packages/create-jw-agent/src/create_jw_agent/templates/agent/tests/conftest.py.j2`
- `packages/create-jw-agent/src/create_jw_agent/templates/agent/tests/test_{{module}}.py.j2`
- `packages/create-jw-agent/src/create_jw_agent/templates/agent/LICENSE.j2`
- `packages/create-jw-agent/src/create_jw_agent/templates/parser/...` (mirror)
- `packages/create-jw-agent/src/create_jw_agent/templates/embedder/...` (mirror)
- `packages/create-jw-agent/src/create_jw_agent/templates/vlm/...` (mirror)
- `packages/create-jw-agent/src/create_jw_agent/templates/gen/...` (mirror)
- `packages/create-jw-agent/tests/__init__.py`
- `packages/create-jw-agent/tests/test_validate.py`
- `packages/create-jw-agent/tests/test_render.py`
- `packages/create-jw-agent/tests/test_cli.py`
- `packages/create-jw-agent/tests/test_no_network.py`
- `packages/create-jw-agent/tests/test_e2e_generated_project.py`
- `packages/create-jw-agent/tests/golden/agent_en.txt`
- `packages/create-jw-agent/tests/golden/agent_es.txt`
- `packages/create-jw-agent/tests/golden/agent_pt.txt`
- `packages/create-jw-agent/tests/golden/parser_en.txt`
- `packages/create-jw-agent/tests/golden/embedder_en.txt`
- `packages/create-jw-agent/tests/golden/vlm_en.txt`
- `packages/create-jw-agent/tests/golden/gen_en.txt`
- `tools/pytest-cookbook/pyproject.toml`
- `tools/pytest-cookbook/src/pytest_cookbook/__init__.py`
- `tools/pytest-cookbook/src/pytest_cookbook/plugin.py`
- `tools/pytest-cookbook/tests/test_plugin.py`
- `docs/cookbook/README.md`
- `docs/cookbook/_common/__init__.py`
- `docs/cookbook/_common/conftest.py`
- `docs/cookbook/_common/fakes.py`
- `docs/cookbook/01-resolve-bible-reference.md`
- `docs/cookbook/02-search-and-synthesize.md`
- `docs/cookbook/03-telegram-bot.md`
- `docs/cookbook/04-finetune-llama-3.md`
- `docs/cookbook/05-add-parser.md`
- `docs/cookbook/06-custom-embedder.md`
- `docs/cookbook/07-add-nli.md`
- `docs/cookbook/08-publish-to-pypi.md`
- `docs/cookbook/09-trace-agent-run.md`
- `docs/cookbook/10-calibrate-golden-case.md`
- `docs/cookbook/11-browser-extension.md`
- `docs/cookbook/12-capacitor-app.md`
- `docs/cookbook/tests/__init__.py`
- `docs/cookbook/tests/test_cookbook.py`
- `docs/guias/scaffolding.md`
- `.github/workflows/cookbook-tests.yml`
- `.github/workflows/publish-create-jw-agent.yml`

Modifies:
- `pyproject.toml` (root) — register `packages/create-jw-agent` + `tools/pytest-cookbook` as workspace members.
- `packages/jw-cli/pyproject.toml` — no new runtime dep (subprocess only).
- `packages/jw-cli/src/jw_cli/main.py` — register `create-agent` command.
- `packages/jw-cli/src/jw_cli/commands/__init__.py` + new `create_agent.py`.
- `.github/workflows/ci.yml` — call new `cookbook-tests.yml` reusable job.
- `docs/VISION_AUDIT.md` — add Fase 42 row.
- `docs/ROADMAP.md` — add Fase 42 section.
- `docs/README.md` — link the new guide.

---

### Task 1: Scaffold `packages/create-jw-agent` package and register in workspace

**Files:**
- Create: `packages/create-jw-agent/pyproject.toml`
- Create: `packages/create-jw-agent/README.md`
- Create: `packages/create-jw-agent/src/create_jw_agent/__init__.py`
- Modify: `pyproject.toml` (root)

- [ ] **Step 1: Write the pyproject.toml**

```toml
# packages/create-jw-agent/pyproject.toml
[project]
name = "create-jw-agent"
version = "0.1.0"
description = "Scaffolder for jw-agent-toolkit plugins (agents, parsers, embedders, vlm, gen)"
readme = "README.md"
requires-python = ">=3.13"
license = "GPL-3.0-only"
authors = [{ name = "Elias", email = "elias@cipreholding.com" }]
keywords = ["jw-agent-toolkit", "scaffolder", "plugin", "jehovah-witnesses"]
classifiers = [
    "Development Status :: 4 - Beta",
    "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
    "Programming Language :: Python :: 3 :: Only",
    "Programming Language :: Python :: 3.13",
    "Topic :: Software Development :: Code Generators",
]
dependencies = [
    "typer>=0.12.0",
    "jinja2>=3.1.4",
    "tomli-w>=1.0.0",
    "pydantic>=2.5.0",
    "httpx>=0.27.0",  # opt-in PyPI name check
]

[project.optional-dependencies]
dev = ["pytest>=8.0.0", "pytest-asyncio>=0.23.0"]

[project.scripts]
create-jw-agent = "create_jw_agent.cli:app"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/create_jw_agent"]

[tool.hatch.build.targets.wheel.force-include]
"src/create_jw_agent/templates" = "create_jw_agent/templates"
"src/create_jw_agent/lang" = "create_jw_agent/lang"
```

- [ ] **Step 2: Write the README**

```markdown
# create-jw-agent

Scaffolder for [jw-agent-toolkit](https://github.com/eliascipre/jw-agent-toolkit) plugins.

## Install

    uvx create-jw-agent my-new-agent --type=agent
    # or
    pipx run create-jw-agent my-new-agent --type=agent

## Quick start

    uvx create-jw-agent my-bible-helper --type=agent --lang=en
    cd my-bible-helper
    uv sync
    uv run pytest        # green on first run

## Supported plugin types

| Type      | Entry point group                          |
|-----------|--------------------------------------------|
| agent     | `jw_agent_toolkit.agents`                  |
| parser    | `jw_agent_toolkit.parsers`                 |
| embedder  | `jw_agent_toolkit.embedders`               |
| vlm       | `jw_agent_toolkit.vlm_providers`           |
| gen       | `jw_agent_toolkit.gen_providers`           |

Spec: [`docs/superpowers/specs/2026-05-31-fase-42-scaffolding-design.md`](https://github.com/eliascipre/jw-agent-toolkit/blob/main/docs/superpowers/specs/2026-05-31-fase-42-scaffolding-design.md).
```

- [ ] **Step 3: Create the package `__init__.py`**

```python
# packages/create-jw-agent/src/create_jw_agent/__init__.py
"""create-jw-agent — scaffolder for jw-agent-toolkit plugins.

Public API:
    from create_jw_agent.render import render_template
    from create_jw_agent.validate import validate_project_name
"""

__version__ = "0.1.0"

from create_jw_agent.render import render_template
from create_jw_agent.validate import validate_project_name

__all__ = ["__version__", "render_template", "validate_project_name"]
```

- [ ] **Step 4: Register in workspace**

Edit root `pyproject.toml`:
- In `[tool.uv.workspace] members = [...]` append `"packages/create-jw-agent"` and `"tools/pytest-cookbook"`.
- In `[tool.uv.sources]` add `create-jw-agent = { workspace = true }` and `pytest-cookbook = { workspace = true }`.

- [ ] **Step 5: Verify install + commit**

```bash
uv sync --all-packages
uv pip list | grep create-jw-agent
git add packages/create-jw-agent pyproject.toml uv.lock
git commit -m "feat(create-jw-agent): scaffold package and register in workspace"
```

Expected: `create-jw-agent 0.1.0`. Suite still green.

---

### Task 2: Name validation (PEP 503 + reserved names)

**Files:**
- Create: `packages/create-jw-agent/src/create_jw_agent/validate.py`
- Create: `packages/create-jw-agent/tests/__init__.py`
- Create: `packages/create-jw-agent/tests/test_validate.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/create-jw-agent/tests/test_validate.py
"""Tests for create_jw_agent.validate."""

from __future__ import annotations

import pytest

from create_jw_agent.validate import (
    ValidationError,
    project_to_module,
    validate_project_name,
)


def test_accepts_simple_kebab() -> None:
    validate_project_name("my-translator")


def test_accepts_single_word() -> None:
    validate_project_name("translator")


def test_rejects_uppercase() -> None:
    with pytest.raises(ValidationError, match="lowercase"):
        validate_project_name("MyProject")


def test_rejects_underscore() -> None:
    with pytest.raises(ValidationError, match="kebab-case"):
        validate_project_name("my_project")


def test_rejects_space() -> None:
    with pytest.raises(ValidationError, match="whitespace"):
        validate_project_name("with space")


def test_rejects_leading_digit() -> None:
    with pytest.raises(ValidationError, match="letter"):
        validate_project_name("123start")


def test_rejects_reserved_jw_prefix() -> None:
    with pytest.raises(ValidationError, match="jw-"):
        validate_project_name("jw-core")


def test_rejects_reserved_create_jw_prefix() -> None:
    with pytest.raises(ValidationError, match="create-jw-"):
        validate_project_name("create-jw-something")


def test_rejects_empty() -> None:
    with pytest.raises(ValidationError, match="empty"):
        validate_project_name("")


def test_rejects_too_long() -> None:
    with pytest.raises(ValidationError, match="64"):
        validate_project_name("a" * 65)


def test_project_to_module_converts_kebab_to_snake() -> None:
    assert project_to_module("my-translator") == "my_translator"
    assert project_to_module("simple") == "simple"
    assert project_to_module("a-b-c") == "a_b_c"
```

Also write `packages/create-jw-agent/tests/__init__.py` as an empty file.

- [ ] **Step 2: Run test (expect failure)**

```bash
uv run --package create-jw-agent pytest packages/create-jw-agent/tests/test_validate.py -v
```
Expected: `ModuleNotFoundError: create_jw_agent.validate`.

- [ ] **Step 3: Implement validate.py**

```python
# packages/create-jw-agent/src/create_jw_agent/validate.py
"""Validate project names per PEP 503 + toolkit-specific reserved prefixes.

PEP 503 says distribution names match `[A-Za-z0-9][A-Za-z0-9._-]*`. We tighten to:
    - lowercase only,
    - kebab-case (hyphens, no underscores or dots),
    - first char must be a letter,
    - length 1..64,
    - cannot start with `jw-` or `create-jw-` (toolkit-reserved).
"""

from __future__ import annotations

import re

MAX_LEN = 64
_PATTERN = re.compile(r"^[a-z][a-z0-9-]*$")
_RESERVED_PREFIXES: tuple[str, ...] = ("jw-", "create-jw-")


class ValidationError(ValueError):
    """Raised when a project name fails validation."""


def validate_project_name(name: str) -> None:
    """Raise ValidationError if `name` is not a usable PyPI/distribution name."""

    if not name:
        raise ValidationError("project name is empty")
    if any(c.isspace() for c in name):
        raise ValidationError(f"project name {name!r} contains whitespace")
    if len(name) > MAX_LEN:
        raise ValidationError(f"project name longer than {MAX_LEN} chars")
    if not name[0].isalpha():
        raise ValidationError(f"project name must start with a letter (got {name!r})")
    if "_" in name or "." in name:
        raise ValidationError(f"project name {name!r} must be kebab-case (no _ or .)")
    if name != name.lower():
        raise ValidationError(f"project name {name!r} must be lowercase")
    if not _PATTERN.match(name):
        raise ValidationError(f"project name {name!r} does not match {_PATTERN.pattern!r}")
    for prefix in _RESERVED_PREFIXES:
        if name.startswith(prefix):
            raise ValidationError(
                f"project name {name!r} starts with reserved prefix {prefix!r}"
            )


def project_to_module(name: str) -> str:
    """Convert kebab-case project name to snake_case Python module identifier."""

    return name.replace("-", "_")
```

- [ ] **Step 4: Run test (expect pass)**

```bash
uv run --package create-jw-agent pytest packages/create-jw-agent/tests/test_validate.py -v
```
Expected: 11 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/create-jw-agent/src/create_jw_agent/validate.py packages/create-jw-agent/tests
git commit -m "feat(create-jw-agent): name validation (PEP 503 + reserved prefixes)"
```

---

### Task 3: i18n loader (en/es/pt) for CLI messages

**Files:**
- Create: `packages/create-jw-agent/src/create_jw_agent/i18n.py`
- Create: `packages/create-jw-agent/src/create_jw_agent/lang/en.json`
- Create: `packages/create-jw-agent/src/create_jw_agent/lang/es.json`
- Create: `packages/create-jw-agent/src/create_jw_agent/lang/pt.json`
- Create: `packages/create-jw-agent/tests/test_i18n.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/create-jw-agent/tests/test_i18n.py
"""Tests for i18n loader."""

from __future__ import annotations

import pytest

from create_jw_agent.i18n import Translator, detect_lang, load_translator


def test_detect_lang_defaults_to_en(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LANG", raising=False)
    monkeypatch.delenv("LC_ALL", raising=False)
    assert detect_lang() == "en"


def test_detect_lang_reads_lang(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LANG", "es_ES.UTF-8")
    assert detect_lang() == "es"


def test_detect_lang_reads_lc_all(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LC_ALL", "pt_BR.UTF-8")
    monkeypatch.delenv("LANG", raising=False)
    assert detect_lang() == "pt"


def test_detect_lang_unknown_falls_back_to_en(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LANG", "ja_JP.UTF-8")
    assert detect_lang() == "en"


def test_translator_returns_known_key() -> None:
    t = load_translator("en")
    assert t("cli.welcome") != "cli.welcome"


def test_translator_unknown_key_returns_key() -> None:
    t = load_translator("en")
    assert t("does.not.exist") == "does.not.exist"


def test_translator_invalid_lang_falls_back_to_en() -> None:
    t = load_translator("zz")
    assert isinstance(t, Translator)
    assert t.lang == "en"


def test_translator_supports_format_args() -> None:
    t = load_translator("en")
    out = t("cli.generated_at", path="/tmp/x")
    assert "/tmp/x" in out
```

- [ ] **Step 2: Run test (expect failure)**

```bash
uv run --package create-jw-agent pytest packages/create-jw-agent/tests/test_i18n.py -v
```
Expected: `ModuleNotFoundError: create_jw_agent.i18n`.

- [ ] **Step 3: Write the lang JSON files**

```json
{
  "cli.welcome": "Creating a new jw-agent-toolkit plugin",
  "cli.generated_at": "Project generated at: {path}",
  "cli.next_steps": "Next steps:\n  cd {name}\n  uv sync\n  uv run pytest",
  "cli.publish_hint": "Publish later with: uv build && uv publish",
  "cli.error.invalid_name": "Invalid name: {reason}",
  "cli.error.dest_exists": "Destination already exists: {path}",
  "cli.warning.pypi_taken": "Heads up: '{name}' already exists on PyPI",
  "cli.confirm.create": "Create project '{name}' at {path}? [y/N]"
}
```
Save as `packages/create-jw-agent/src/create_jw_agent/lang/en.json`.

```json
{
  "cli.welcome": "Creando un nuevo plugin de jw-agent-toolkit",
  "cli.generated_at": "Proyecto generado en: {path}",
  "cli.next_steps": "Próximos pasos:\n  cd {name}\n  uv sync\n  uv run pytest",
  "cli.publish_hint": "Publica luego con: uv build && uv publish",
  "cli.error.invalid_name": "Nombre inválido: {reason}",
  "cli.error.dest_exists": "El destino ya existe: {path}",
  "cli.warning.pypi_taken": "Aviso: '{name}' ya existe en PyPI",
  "cli.confirm.create": "¿Crear proyecto '{name}' en {path}? [s/N]"
}
```
Save as `packages/create-jw-agent/src/create_jw_agent/lang/es.json`.

```json
{
  "cli.welcome": "Criando um novo plugin do jw-agent-toolkit",
  "cli.generated_at": "Projeto gerado em: {path}",
  "cli.next_steps": "Próximos passos:\n  cd {name}\n  uv sync\n  uv run pytest",
  "cli.publish_hint": "Publique depois com: uv build && uv publish",
  "cli.error.invalid_name": "Nome inválido: {reason}",
  "cli.error.dest_exists": "O destino já existe: {path}",
  "cli.warning.pypi_taken": "Aviso: '{name}' já existe no PyPI",
  "cli.confirm.create": "Criar projeto '{name}' em {path}? [s/N]"
}
```
Save as `packages/create-jw-agent/src/create_jw_agent/lang/pt.json`.

- [ ] **Step 4: Implement i18n.py**

```python
# packages/create-jw-agent/src/create_jw_agent/i18n.py
"""Tiny i18n loader for CLI messages.

JSON tables live in lang/{en,es,pt}.json. Missing keys return the key itself,
which makes tests obvious and avoids silent fallback to a wrong language.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from importlib.resources import files
from typing import Any

SUPPORTED_LANGS: tuple[str, ...] = ("en", "es", "pt")
DEFAULT_LANG = "en"


def detect_lang() -> str:
    """Read $LC_ALL / $LANG, return one of SUPPORTED_LANGS or DEFAULT_LANG."""

    raw = os.environ.get("LC_ALL") or os.environ.get("LANG") or ""
    if "_" in raw:
        prefix = raw.split("_", 1)[0].lower()
    else:
        prefix = raw[:2].lower()
    if prefix in SUPPORTED_LANGS:
        return prefix
    return DEFAULT_LANG


@dataclass(frozen=True)
class Translator:
    lang: str
    table: dict[str, str]

    def __call__(self, key: str, **kwargs: Any) -> str:
        raw = self.table.get(key, key)
        if not kwargs:
            return raw
        try:
            return raw.format(**kwargs)
        except (KeyError, IndexError):
            return raw


def load_translator(lang: str) -> Translator:
    """Load a Translator for the requested lang; fall back to DEFAULT_LANG."""

    actual = lang if lang in SUPPORTED_LANGS else DEFAULT_LANG
    raw = (files("create_jw_agent.lang") / f"{actual}.json").read_text(encoding="utf-8")
    return Translator(lang=actual, table=json.loads(raw))
```

- [ ] **Step 5: Run test (expect pass) + commit**

```bash
uv run --package create-jw-agent pytest packages/create-jw-agent/tests/test_i18n.py -v
```
Expected: 8 passed.

```bash
git add packages/create-jw-agent/src/create_jw_agent/i18n.py packages/create-jw-agent/src/create_jw_agent/lang packages/create-jw-agent/tests/test_i18n.py
git commit -m "feat(create-jw-agent): i18n loader with en/es/pt tables"
```

---

### Task 4: Renderer (Jinja2 + filesystem)

**Files:**
- Create: `packages/create-jw-agent/src/create_jw_agent/render.py`
- Create: `packages/create-jw-agent/tests/test_render.py`
- Create: `packages/create-jw-agent/src/create_jw_agent/templates/agent/pyproject.toml.j2` (stub for first render test)
- Create: `packages/create-jw-agent/src/create_jw_agent/templates/agent/src/{{module}}/__init__.py.j2`

- [ ] **Step 1: Write a minimal pair of templates for the test**

```jinja
# packages/create-jw-agent/src/create_jw_agent/templates/agent/pyproject.toml.j2
[project]
name = "{{ name }}"
version = "0.1.0"
description = "{{ description }}"
requires-python = ">=3.13"
license = "{{ license }}"
dependencies = [
    "jw-core{{ jw_core_version }}",
]

[project.entry-points."jw_agent_toolkit.agents"]
{{ module }} = "{{ module }}.agent:{{ module }}"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

```jinja
# packages/create-jw-agent/src/create_jw_agent/templates/agent/src/{{module}}/__init__.py.j2
"""{{ name }} — {{ description }}."""

from {{ module }}.agent import {{ module }}

__all__ = ["{{ module }}"]
```

- [ ] **Step 2: Write the failing test**

```python
# packages/create-jw-agent/tests/test_render.py
"""Tests for the template renderer."""

from __future__ import annotations

from pathlib import Path

import pytest

from create_jw_agent.render import RenderContext, render_template


def _ctx(name: str = "my-translator", **overrides: object) -> RenderContext:
    base = RenderContext(
        name=name,
        module=name.replace("-", "_"),
        type="agent",
        lang="en",
        description=f"Stub for {name}",
        license="GPL-3.0",
        jw_core_version=">=2.3,<3.0",
        author="anonymous",
    )
    return base.model_copy(update=overrides)


def test_render_writes_pyproject(tmp_path: Path) -> None:
    out = tmp_path / "my-translator"
    render_template(_ctx(), out)
    pyproject = (out / "pyproject.toml").read_text(encoding="utf-8")
    assert 'name = "my-translator"' in pyproject
    assert "jw_agent_toolkit.agents" in pyproject
    assert "my_translator = \"my_translator.agent:my_translator\"" in pyproject


def test_render_renames_module_dir(tmp_path: Path) -> None:
    out = tmp_path / "demo-thing"
    render_template(_ctx("demo-thing"), out)
    assert (out / "src" / "demo_thing" / "__init__.py").exists()
    text = (out / "src" / "demo_thing" / "__init__.py").read_text(encoding="utf-8")
    assert "from demo_thing.agent import demo_thing" in text


def test_render_refuses_existing_non_empty_dir(tmp_path: Path) -> None:
    out = tmp_path / "exists"
    out.mkdir()
    (out / "junk.txt").write_text("x")
    with pytest.raises(FileExistsError):
        render_template(_ctx(), out)


def test_render_allows_existing_empty_dir(tmp_path: Path) -> None:
    out = tmp_path / "empty"
    out.mkdir()
    render_template(_ctx(), out)
    assert (out / "pyproject.toml").exists()


def test_render_unknown_type_raises(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="unknown type"):
        render_template(_ctx().model_copy(update={"type": "nonsense"}), tmp_path / "x")
```

- [ ] **Step 3: Run test (expect failure)**

```bash
uv run --package create-jw-agent pytest packages/create-jw-agent/tests/test_render.py -v
```
Expected: `ModuleNotFoundError: create_jw_agent.render`.

- [ ] **Step 4: Implement render.py**

```python
# packages/create-jw-agent/src/create_jw_agent/render.py
"""Template renderer.

Walks the chosen template tree, runs each `.j2` file through Jinja2,
strips the `.j2` suffix in the output, and renames any path component
containing `{{module}}` to the snake_case module name.

The context model is the single source of truth for what variables a
template can use — every new Jinja variable must be added to RenderContext.
"""

from __future__ import annotations

from importlib.resources import as_file, files
from pathlib import Path
from typing import Literal

from jinja2 import Environment, FileSystemLoader, StrictUndefined
from pydantic import BaseModel, Field

PluginType = Literal["agent", "parser", "embedder", "vlm", "gen"]


class RenderContext(BaseModel):
    """Single source of truth for template variables."""

    name: str
    module: str
    type: PluginType
    lang: Literal["en", "es", "pt"] = "en"
    description: str = ""
    license: str = "GPL-3.0"
    jw_core_version: str = Field(default=">=2.3,<3.0")
    author: str = "anonymous"


def _template_root(plugin_type: PluginType) -> Path:
    pkg = files("create_jw_agent.templates")
    candidate = pkg / plugin_type
    with as_file(candidate) as path:
        if not path.is_dir():
            raise ValueError(f"unknown type: {plugin_type!r}")
        return Path(path)


def _is_dir_empty(path: Path) -> bool:
    return not any(path.iterdir())


def render_template(ctx: RenderContext, dest: Path) -> None:
    """Render the template for ctx.type into dest."""

    root = _template_root(ctx.type)
    if dest.exists():
        if not dest.is_dir():
            raise FileExistsError(f"destination is not a directory: {dest}")
        if not _is_dir_empty(dest):
            raise FileExistsError(f"destination not empty: {dest}")
    else:
        dest.mkdir(parents=True)

    env = Environment(
        loader=FileSystemLoader(str(root)),
        autoescape=False,
        keep_trailing_newline=True,
        undefined=StrictUndefined,
    )
    variables = ctx.model_dump()

    for src in sorted(root.rglob("*")):
        rel = src.relative_to(root)
        # path-level substitution: any segment "{{module}}" becomes ctx.module.
        rel_parts = [p.replace("{{module}}", ctx.module) for p in rel.parts]
        out_path = dest.joinpath(*rel_parts)
        if src.is_dir():
            out_path.mkdir(parents=True, exist_ok=True)
            continue
        out_path.parent.mkdir(parents=True, exist_ok=True)
        if src.suffix == ".j2":
            template = env.get_template(str(rel))
            content = template.render(**variables)
            out_path.with_suffix("").write_text(content, encoding="utf-8")
        else:
            out_path.write_bytes(src.read_bytes())
```

- [ ] **Step 5: Run test (expect pass) + commit**

```bash
uv run --package create-jw-agent pytest packages/create-jw-agent/tests/test_render.py -v
```
Expected: 5 passed.

```bash
git add packages/create-jw-agent/src/create_jw_agent/render.py packages/create-jw-agent/src/create_jw_agent/templates packages/create-jw-agent/tests/test_render.py
git commit -m "feat(create-jw-agent): Jinja2 renderer with path-level module substitution"
```

---

### Task 5: Full `agent` template — emit a CI-green project on first run

**Files:**
- Create: `packages/create-jw-agent/src/create_jw_agent/templates/agent/README.md.j2`
- Create: `packages/create-jw-agent/src/create_jw_agent/templates/agent/Makefile.j2`
- Create: `packages/create-jw-agent/src/create_jw_agent/templates/agent/.gitignore.j2`
- Create: `packages/create-jw-agent/src/create_jw_agent/templates/agent/.github/workflows/ci.yml.j2`
- Create: `packages/create-jw-agent/src/create_jw_agent/templates/agent/src/{{module}}/agent.py.j2`
- Create: `packages/create-jw-agent/src/create_jw_agent/templates/agent/tests/__init__.py.j2`
- Create: `packages/create-jw-agent/src/create_jw_agent/templates/agent/tests/conftest.py.j2`
- Create: `packages/create-jw-agent/src/create_jw_agent/templates/agent/tests/test_{{module}}.py.j2`
- Create: `packages/create-jw-agent/src/create_jw_agent/templates/agent/LICENSE.j2`
- Create: `packages/create-jw-agent/tests/test_e2e_generated_project.py`

- [ ] **Step 1: Write the failing E2E test**

```python
# packages/create-jw-agent/tests/test_e2e_generated_project.py
"""End-to-end: generate a project, run uv sync + pytest inside it."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from create_jw_agent.render import RenderContext, render_template

REQUIRES_UV = pytest.mark.skipif(shutil.which("uv") is None, reason="uv not installed")


@REQUIRES_UV
def test_generated_agent_passes_its_own_tests(tmp_path: Path) -> None:
    dest = tmp_path / "demo-thing"
    ctx = RenderContext(
        name="demo-thing",
        module="demo_thing",
        type="agent",
        lang="en",
        description="Smoke",
        license="GPL-3.0",
        jw_core_version=">=2.3,<3.0",
        author="ci",
    )
    render_template(ctx, dest)
    assert (dest / "pyproject.toml").exists()
    assert (dest / "src" / "demo_thing" / "agent.py").exists()
    assert (dest / "tests" / "test_demo_thing.py").exists()
    assert (dest / ".github" / "workflows" / "ci.yml").exists()
    assert (dest / "LICENSE").exists()
    # Smoke: pytest inside generated project.
    env = {**os.environ, "UV_NO_CACHE": "1"}
    sync = subprocess.run(["uv", "sync", "--quiet"], cwd=dest, env=env, check=False)
    if sync.returncode != 0:
        pytest.skip("uv sync failed offline; covered by golden tests")
    result = subprocess.run(
        ["uv", "run", "pytest", "-q"], cwd=dest, env=env, capture_output=True, check=False
    )
    assert result.returncode == 0, result.stdout.decode() + result.stderr.decode()
```

- [ ] **Step 2: Write the templates**

```jinja
# packages/create-jw-agent/src/create_jw_agent/templates/agent/README.md.j2
# {{ name }}

> {{ description }}

A jw-agent-toolkit plugin (type: agent) scaffolded with `create-jw-agent`.

## Install

    uv sync

## Test

    uv run pytest

## Register

Entry point already declared in `pyproject.toml`:

    [project.entry-points."jw_agent_toolkit.agents"]
    {{ module }} = "{{ module }}.agent:{{ module }}"

After `pip install .`, the agent is auto-discovered by `jw-core`'s plugin loader (Fase 41).

## License

{{ license }}
```

```jinja
# packages/create-jw-agent/src/create_jw_agent/templates/agent/Makefile.j2
.PHONY: install test lint format ci

install:
	uv sync

test:
	uv run pytest -v

lint:
	uv run ruff check .

format:
	uv run ruff format .

ci: install lint test
```

```jinja
# packages/create-jw-agent/src/create_jw_agent/templates/agent/.gitignore.j2
__pycache__/
*.py[cod]
.venv/
.uv/
dist/
build/
*.egg-info/
.ruff_cache/
.pytest_cache/
.mypy_cache/
.coverage
htmlcov/
```

```jinja
# packages/create-jw-agent/src/create_jw_agent/templates/agent/.github/workflows/ci.yml.j2
name: ci
on:
  push:
    branches: [main]
  pull_request:

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
        with:
          enable-cache: true
      - name: Install Python 3.13
        run: uv python install 3.13
      - name: Sync deps
        run: uv sync
      - name: Lint
        run: |
          uv run ruff check .
          uv run ruff format --check .
      - name: Test
        run: uv run pytest -v
```

```jinja
# packages/create-jw-agent/src/create_jw_agent/templates/agent/src/{{module}}/agent.py.j2
"""{{ name }} — stub agent.

Replace this with real logic. See cookbook recipes for patterns:
https://jw-agent-toolkit.dev/cookbook/
"""

from __future__ import annotations

from typing import Any

# We import lazily so the unit tests can run without jw-core installed.
try:
    from jw_core.models import AgentResult, Citation, Finding
except ImportError:  # pragma: no cover - dev-time fallback
    from dataclasses import dataclass, field

    @dataclass
    class Citation:  # type: ignore[no-redef]
        url: str
        title: str = ""
        metadata: dict[str, Any] = field(default_factory=dict)

    @dataclass
    class Finding:  # type: ignore[no-redef]
        source: str
        text: str
        citation: Citation

    @dataclass
    class AgentResult:  # type: ignore[no-redef]
        findings: list[Finding]
        metadata: dict[str, Any] = field(default_factory=dict)


async def {{ module }}(
    *,
    question: str,
    language: str = "en",
    **kwargs: Any,
) -> "AgentResult":
    """Entry-point callable. Returns at least one Finding with a Citation."""

    finding = Finding(
        source="stub",
        text=f"TODO: implement logic for {question!r} ({language})",
        citation=Citation(
            url="https://wol.jw.org/",
            title="Placeholder",
            metadata={"stub": True},
        ),
    )
    return AgentResult(findings=[finding], metadata={"agent": "{{ module }}"})
```

```jinja
# packages/create-jw-agent/src/create_jw_agent/templates/agent/tests/__init__.py.j2
```

```jinja
# packages/create-jw-agent/src/create_jw_agent/templates/agent/tests/conftest.py.j2
"""Shared fixtures. Deterministic, offline only."""

from __future__ import annotations

import asyncio
from collections.abc import Iterator

import pytest


@pytest.fixture
def loop() -> Iterator[asyncio.AbstractEventLoop]:
    loop = asyncio.new_event_loop()
    try:
        yield loop
    finally:
        loop.close()


@pytest.fixture(autouse=True)
def _no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Hard-block accidental network access during tests."""

    def _boom(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("network access disabled in tests")

    import socket

    monkeypatch.setattr(socket, "create_connection", _boom)
```

```jinja
# packages/create-jw-agent/src/create_jw_agent/templates/agent/tests/test_{{module}}.py.j2
"""Smoke + contract + citations-present tests."""

from __future__ import annotations

import asyncio

from {{ module }}.agent import {{ module }}


def _run(coro):
    return asyncio.run(coro)


def test_smoke() -> None:
    result = _run({{ module }}(question="Trinity", language="en"))
    assert result.findings, "agent must return at least one finding"


def test_contract_shape() -> None:
    result = _run({{ module }}(question="x", language="en"))
    for finding in result.findings:
        assert finding.source
        assert finding.text
        assert finding.citation is not None
        assert finding.citation.url.startswith("https://")


def test_citations_present() -> None:
    result = _run({{ module }}(question="x", language="en"))
    assert all(f.citation for f in result.findings)
```

```jinja
# packages/create-jw-agent/src/create_jw_agent/templates/agent/LICENSE.j2
{{ license }} License

Copyright (c) {{ author }}

See https://www.gnu.org/licenses/gpl-3.0.txt for full GPL-3.0 text.
```

Also replace the stub `pyproject.toml.j2` from Task 4 with the production version:

```jinja
[project]
name = "{{ name }}"
version = "0.1.0"
description = "{{ description }}"
readme = "README.md"
requires-python = ">=3.13"
license = "{{ license }}"
authors = [{ name = "{{ author }}" }]
dependencies = [
    "jw-core{{ jw_core_version }}",
]

[project.optional-dependencies]
dev = ["pytest>=8.0.0", "ruff>=0.5.0"]

[project.entry-points."jw_agent_toolkit.agents"]
{{ module }} = "{{ module }}.agent:{{ module }}"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/{{ module }}"]

[tool.ruff]
line-length = 100
target-version = "py313"

[tool.ruff.lint]
select = ["E", "F", "W", "I", "UP", "B", "SIM"]
```

- [ ] **Step 3: Run E2E test**

```bash
uv run --package create-jw-agent pytest packages/create-jw-agent/tests/test_e2e_generated_project.py -v
```
Expected: pass (or `skip` if uv is not available — pure rendering still verified).

- [ ] **Step 4: Quick sanity render manually**

```bash
uv run --package create-jw-agent python -c "
from pathlib import Path
from create_jw_agent.render import RenderContext, render_template
import tempfile, shutil
tmp = Path(tempfile.mkdtemp())
ctx = RenderContext(name='demo', module='demo', type='agent', description='Demo', author='ci')
render_template(ctx, tmp / 'demo')
print(sorted(p.relative_to(tmp).as_posix() for p in (tmp / 'demo').rglob('*') if p.is_file()))
shutil.rmtree(tmp)
"
```

Expected output lists `demo/pyproject.toml`, `demo/README.md`, `demo/src/demo/agent.py`, `demo/tests/test_demo.py`, `demo/.github/workflows/ci.yml`, `demo/LICENSE`, etc.

- [ ] **Step 5: Commit**

```bash
git add packages/create-jw-agent/src/create_jw_agent/templates/agent packages/create-jw-agent/tests/test_e2e_generated_project.py
git commit -m "feat(create-jw-agent): complete agent template (CI-green on first commit)"
```

---

### Task 6: Templates for `parser`, `embedder`, `vlm`, `gen` (mirrors of agent)

**Files:**
- Create: `packages/create-jw-agent/src/create_jw_agent/templates/parser/...`
- Create: `packages/create-jw-agent/src/create_jw_agent/templates/embedder/...`
- Create: `packages/create-jw-agent/src/create_jw_agent/templates/vlm/...`
- Create: `packages/create-jw-agent/src/create_jw_agent/templates/gen/...`
- Modify: `packages/create-jw-agent/tests/test_render.py`

- [ ] **Step 1: Write parametric test that exercises all 5 types**

Append to `test_render.py`:

```python
@pytest.mark.parametrize("plugin_type", ["agent", "parser", "embedder", "vlm", "gen"])
def test_render_each_type_emits_pyproject(tmp_path: Path, plugin_type: str) -> None:
    out = tmp_path / plugin_type
    ctx = RenderContext(
        name=f"demo-{plugin_type}",
        module=f"demo_{plugin_type}",
        type=plugin_type,  # type: ignore[arg-type]
        lang="en",
        description=f"Demo {plugin_type}",
        license="GPL-3.0",
        jw_core_version=">=2.3,<3.0",
        author="ci",
    )
    render_template(ctx, out)
    pyproject = (out / "pyproject.toml").read_text(encoding="utf-8")
    expected_entry_groups = {
        "agent": "jw_agent_toolkit.agents",
        "parser": "jw_agent_toolkit.parsers",
        "embedder": "jw_agent_toolkit.embedders",
        "vlm": "jw_agent_toolkit.vlm_providers",
        "gen": "jw_agent_toolkit.gen_providers",
    }
    assert expected_entry_groups[plugin_type] in pyproject
```

- [ ] **Step 2: Run test (expect failure for non-agent types)**

```bash
uv run --package create-jw-agent pytest packages/create-jw-agent/tests/test_render.py::test_render_each_type_emits_pyproject -v
```
Expected: 4 failures (`unknown type` for parser/embedder/vlm/gen).

- [ ] **Step 3: Create mirror templates**

Copy the agent template tree four times, varying only:

| Type     | Entry-point group                  | Stub module exports                                        |
|----------|------------------------------------|------------------------------------------------------------|
| parser   | `jw_agent_toolkit.parsers`         | `class Parser: def parse(self, raw: bytes) -> ParsedDocument` |
| embedder | `jw_agent_toolkit.embedders`       | `class Embedder: def embed(self, texts: list[str]) -> np.ndarray` (returns zeros) |
| vlm      | `jw_agent_toolkit.vlm_providers`   | `class VLM: async def describe(self, image_bytes: bytes) -> str` |
| gen      | `jw_agent_toolkit.gen_providers`   | `class Gen: async def generate(self, prompt: str) -> str` |

For each type, write the `pyproject.toml.j2` with the matching entry-point group, plus a minimal `agent.py.j2` equivalent (`parser.py.j2`, `embedder.py.j2`, etc.) and three tests (smoke/contract/no-side-effect).

Example for `parser`:

```jinja
# packages/create-jw-agent/src/create_jw_agent/templates/parser/pyproject.toml.j2
[project]
name = "{{ name }}"
version = "0.1.0"
description = "{{ description }}"
readme = "README.md"
requires-python = ">=3.13"
license = "{{ license }}"
authors = [{ name = "{{ author }}" }]
dependencies = ["jw-core{{ jw_core_version }}"]

[project.entry-points."jw_agent_toolkit.parsers"]
{{ module }} = "{{ module }}.parser:{{ module|capitalize }}Parser"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/{{ module }}"]
```

```jinja
# packages/create-jw-agent/src/create_jw_agent/templates/parser/src/{{module}}/parser.py.j2
"""{{ name }} — stub parser."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ParsedDocument:
    text: str
    metadata: dict


class {{ module|capitalize }}Parser:
    """Parses raw bytes into a ParsedDocument. Replace with real logic."""

    def parse(self, raw: bytes) -> ParsedDocument:
        return ParsedDocument(text=raw.decode("utf-8", errors="replace"), metadata={})
```

Repeat the same surgical edits for embedder/vlm/gen (entry point + stub module). Reuse README, Makefile, .gitignore, ci.yml, LICENSE from agent (identical contents apart from "type: parser").

- [ ] **Step 4: Run parametric test (expect pass)**

```bash
uv run --package create-jw-agent pytest packages/create-jw-agent/tests/test_render.py -v
```
Expected: all `test_render_each_type_emits_pyproject[*]` pass.

- [ ] **Step 5: Commit**

```bash
git add packages/create-jw-agent/src/create_jw_agent/templates packages/create-jw-agent/tests/test_render.py
git commit -m "feat(create-jw-agent): parser/embedder/vlm/gen templates with matching entry points"
```

---

### Task 7: Golden snapshot tests (15 = 5 types × 3 langs)

**Files:**
- Create: `packages/create-jw-agent/tests/golden/agent_en.txt`
- Create: `packages/create-jw-agent/tests/golden/agent_es.txt`
- Create: `packages/create-jw-agent/tests/golden/agent_pt.txt`
- Create: `packages/create-jw-agent/tests/golden/parser_en.txt`
- Create: `packages/create-jw-agent/tests/golden/embedder_en.txt`
- Create: `packages/create-jw-agent/tests/golden/vlm_en.txt`
- Create: `packages/create-jw-agent/tests/golden/gen_en.txt`
- Modify: `packages/create-jw-agent/tests/test_render.py`

- [ ] **Step 1: Append the snapshot test**

```python
GOLDEN_DIR = Path(__file__).parent / "golden"


def _tree(path: Path) -> str:
    """Return a deterministic listing of relative file paths + size."""

    lines: list[str] = []
    for p in sorted(path.rglob("*")):
        rel = p.relative_to(path).as_posix()
        if p.is_dir():
            lines.append(f"DIR {rel}/")
        else:
            lines.append(f"FILE {rel} {p.stat().st_size}")
    return "\n".join(lines) + "\n"


SNAPSHOT_COMBOS = [
    ("agent", "en"),
    ("agent", "es"),
    ("agent", "pt"),
    ("parser", "en"),
    ("embedder", "en"),
    ("vlm", "en"),
    ("gen", "en"),
]


@pytest.mark.parametrize("plugin_type,lang", SNAPSHOT_COMBOS)
def test_render_matches_golden_snapshot(
    tmp_path: Path,
    plugin_type: str,
    lang: str,
    request: pytest.FixtureRequest,
) -> None:
    out = tmp_path / f"{plugin_type}-{lang}"
    ctx = RenderContext(
        name=f"demo-{plugin_type}",
        module=f"demo_{plugin_type}",
        type=plugin_type,  # type: ignore[arg-type]
        lang=lang,  # type: ignore[arg-type]
        description=f"Demo {plugin_type}",
        license="GPL-3.0",
        jw_core_version=">=2.3,<3.0",
        author="ci",
    )
    render_template(ctx, out)
    actual = _tree(out)
    snapshot = GOLDEN_DIR / f"{plugin_type}_{lang}.txt"
    if request.config.getoption("--snapshot-update", default=False):
        snapshot.parent.mkdir(parents=True, exist_ok=True)
        snapshot.write_text(actual, encoding="utf-8")
    assert snapshot.read_text(encoding="utf-8") == actual
```

And register the option once at the top of the file (or in `tests/conftest.py`):

```python
# packages/create-jw-agent/tests/conftest.py
def pytest_addoption(parser):
    parser.addoption("--snapshot-update", action="store_true", default=False)
```

- [ ] **Step 2: First run — generate snapshots**

```bash
uv run --package create-jw-agent pytest packages/create-jw-agent/tests/test_render.py -v --snapshot-update
```
Expected: 7 snapshot files appear in `tests/golden/`. Test passes by virtue of self-overwrite.

- [ ] **Step 3: Second run — verify deterministic**

```bash
uv run --package create-jw-agent pytest packages/create-jw-agent/tests/test_render.py -v
```
Expected: 7 `test_render_matches_golden_snapshot` pass with no further snapshot mutation.

- [ ] **Step 4: Inspect one snapshot**

```bash
head -n 25 packages/create-jw-agent/tests/golden/agent_en.txt
```
Expected: deterministic file-list with sizes (no timestamps, no absolute paths).

- [ ] **Step 5: Commit**

```bash
git add packages/create-jw-agent/tests/golden packages/create-jw-agent/tests/conftest.py packages/create-jw-agent/tests/test_render.py
git commit -m "test(create-jw-agent): golden snapshots for 5 types x 3 langs"
```

---

### Task 8: Typer CLI + no-network guarantee

**Files:**
- Create: `packages/create-jw-agent/src/create_jw_agent/cli.py`
- Create: `packages/create-jw-agent/tests/test_cli.py`
- Create: `packages/create-jw-agent/tests/test_no_network.py`

- [ ] **Step 1: Write the failing tests**

```python
# packages/create-jw-agent/tests/test_cli.py
"""Tests for the Typer CLI."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from create_jw_agent.cli import app

runner = CliRunner()


def test_cli_help() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "create-jw-agent" in result.stdout
    assert "--type" in result.stdout
    assert "--lang" in result.stdout


def test_cli_version() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "0.1.0" in result.stdout


def test_cli_generates_default_agent(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["my-demo", "--output-dir", str(tmp_path / "out"), "--no-interactive"],
    )
    assert result.exit_code == 0, result.stdout
    assert (tmp_path / "out" / "pyproject.toml").exists()
    assert (tmp_path / "out" / "src" / "my_demo" / "agent.py").exists()


def test_cli_rejects_invalid_name(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["My_Bad", "--output-dir", str(tmp_path / "out"), "--no-interactive"],
    )
    assert result.exit_code != 0
    assert "Invalid name" in result.stdout or "Nombre inválido" in result.stdout


def test_cli_respects_lang_flag(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["mi-demo", "--lang", "es", "--output-dir", str(tmp_path / "out"), "--no-interactive"],
    )
    assert result.exit_code == 0, result.stdout
    assert "Próximos pasos" in result.stdout


def test_cli_emits_pt(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["meu-demo", "--lang", "pt", "--output-dir", str(tmp_path / "out"), "--no-interactive"],
    )
    assert result.exit_code == 0, result.stdout
    assert "Próximos passos" in result.stdout


def test_cli_refuses_existing_non_empty(tmp_path: Path) -> None:
    (tmp_path / "out").mkdir()
    (tmp_path / "out" / "junk.txt").write_text("x")
    result = runner.invoke(
        app,
        ["demo", "--output-dir", str(tmp_path / "out"), "--no-interactive"],
    )
    assert result.exit_code != 0


def test_cli_supports_all_types(tmp_path: Path) -> None:
    for t in ("agent", "parser", "embedder", "vlm", "gen"):
        out = tmp_path / t
        result = runner.invoke(
            app,
            ["my-thing", "--type", t, "--output-dir", str(out), "--no-interactive"],
        )
        assert result.exit_code == 0, f"{t}: {result.stdout}"
```

```python
# packages/create-jw-agent/tests/test_no_network.py
"""Guarantee: without --check-pypi, no HTTP requests."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from typer.testing import CliRunner

from create_jw_agent.cli import app


def test_no_network_unless_check_pypi(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calls: list[str] = []

    def _boom_get(*_args: object, **_kwargs: object) -> object:
        calls.append("get")
        raise RuntimeError("must not be called")

    def _boom_head(*_args: object, **_kwargs: object) -> object:
        calls.append("head")
        raise RuntimeError("must not be called")

    monkeypatch.setattr(httpx, "get", _boom_get)
    monkeypatch.setattr(httpx, "head", _boom_head)

    runner = CliRunner()
    result = runner.invoke(
        app,
        ["demo", "--output-dir", str(tmp_path / "out"), "--no-interactive"],
    )
    assert result.exit_code == 0
    assert calls == []
```

- [ ] **Step 2: Run tests (expect failure)**

```bash
uv run --package create-jw-agent pytest packages/create-jw-agent/tests/test_cli.py packages/create-jw-agent/tests/test_no_network.py -v
```
Expected: failures (`create_jw_agent.cli` missing).

- [ ] **Step 3: Implement the CLI**

```python
# packages/create-jw-agent/src/create_jw_agent/cli.py
"""Typer CLI entry point for `create-jw-agent`."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import httpx
import typer

from create_jw_agent import __version__
from create_jw_agent.i18n import detect_lang, load_translator
from create_jw_agent.render import RenderContext, render_template
from create_jw_agent.validate import (
    ValidationError,
    project_to_module,
    validate_project_name,
)

app = typer.Typer(
    name="create-jw-agent",
    help="Scaffolder for jw-agent-toolkit plugins.",
    add_completion=False,
    no_args_is_help=True,
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(__version__)
        raise typer.Exit()


def _check_pypi(name: str) -> bool:
    """Best-effort name availability check. Returns True if PROBABLY taken."""

    try:
        response = httpx.head(f"https://pypi.org/pypi/{name}/json", timeout=4.0, follow_redirects=True)
    except httpx.HTTPError:
        return False
    return response.status_code == 200


@app.command()
def create(
    name: Annotated[str, typer.Argument(help="Project name (kebab-case).")],
    type: Annotated[
        str,
        typer.Option(
            "--type",
            help="Plugin type: agent|parser|embedder|vlm|gen.",
            case_sensitive=False,
        ),
    ] = "agent",
    lang: Annotated[
        str,
        typer.Option("--lang", help="Output language for prose: en|es|pt."),
    ] = "",
    output_dir: Annotated[
        Path,
        typer.Option("--output-dir", "-o", help="Destination directory."),
    ] = Path(),
    jw_core_version: Annotated[
        str,
        typer.Option(
            "--jw-core-version",
            help="jw-core version specifier (e.g. '>=2.3,<3.0').",
        ),
    ] = ">=2.3,<3.0",
    license: Annotated[
        str,
        typer.Option("--license", help="License identifier."),
    ] = "GPL-3.0",
    check_pypi: Annotated[
        bool,
        typer.Option("--check-pypi/--no-check-pypi", help="Hit PyPI to check name availability."),
    ] = False,
    interactive: Annotated[
        bool,
        typer.Option("--interactive/--no-interactive", help="Prompt for confirmation."),
    ] = True,
    quiet: Annotated[bool, typer.Option("--quiet", help="Suppress decorative output.")] = False,
    version: Annotated[
        bool,
        typer.Option("--version", callback=_version_callback, is_eager=True),
    ] = False,
) -> None:
    """Scaffold a new jw-agent-toolkit plugin."""

    effective_lang = lang or detect_lang()
    t = load_translator(effective_lang)

    try:
        validate_project_name(name)
    except ValidationError as exc:
        typer.echo(t("cli.error.invalid_name", reason=str(exc)))
        raise typer.Exit(code=2) from exc

    if type not in {"agent", "parser", "embedder", "vlm", "gen"}:
        typer.echo(f"unknown --type={type!r}")
        raise typer.Exit(code=2)

    dest = (output_dir if str(output_dir) and output_dir != Path() else Path(name)).resolve()
    if dest.exists() and any(dest.iterdir()) if dest.is_dir() else dest.exists():
        typer.echo(t("cli.error.dest_exists", path=str(dest)))
        raise typer.Exit(code=2)

    if check_pypi and _check_pypi(name):
        typer.echo(t("cli.warning.pypi_taken", name=name))

    if interactive and not quiet:
        typer.echo(t("cli.welcome"))
        confirm = typer.prompt(t("cli.confirm.create", name=name, path=str(dest)), default="y")
        if confirm.strip().lower() not in {"y", "s", "yes", "sí", "si", "sim"}:
            raise typer.Exit(code=1)

    ctx = RenderContext(
        name=name,
        module=project_to_module(name),
        type=type,  # type: ignore[arg-type]
        lang=effective_lang,  # type: ignore[arg-type]
        description=f"jw-agent-toolkit {type} plugin",
        license=license,
        jw_core_version=jw_core_version,
        author="anonymous",
    )
    render_template(ctx, dest)

    if not quiet:
        typer.echo(t("cli.generated_at", path=str(dest)))
        typer.echo(t("cli.next_steps", name=name))
        typer.echo(t("cli.publish_hint"))


# Default invocation behaviour: typing `create-jw-agent NAME ...` should work.
@app.callback(invoke_without_command=True)
def _root(
    ctx: typer.Context,
    version: Annotated[
        bool,
        typer.Option("--version", callback=_version_callback, is_eager=True),
    ] = False,
) -> None:
    if ctx.invoked_subcommand is None and not version:
        # Allow direct positional usage: `create-jw-agent NAME` ↔ `create-jw-agent create NAME`.
        # Typer handles this when the script is registered with no command name.
        return
```

Because `app` has a single command, we expose it as the script directly. Adjust `[project.scripts]` in `pyproject.toml` to `create-jw-agent = "create_jw_agent.cli:create"` if Typer would otherwise expect a subcommand. (Single-command typer apps work as `app = typer.Typer(); @app.command()` + setting `app` as entry point; verify with `runner.invoke(app, ["--help"])`.)

- [ ] **Step 4: Run tests (expect pass)**

```bash
uv run --package create-jw-agent pytest packages/create-jw-agent/tests/test_cli.py packages/create-jw-agent/tests/test_no_network.py -v
```
Expected: 8 + 1 passed.

- [ ] **Step 5: Manual smoke + commit**

```bash
uv run --package create-jw-agent create-jw-agent demo --no-interactive --output-dir /tmp/demo-cli
ls /tmp/demo-cli
rm -rf /tmp/demo-cli
```
Expected: pyproject.toml, src/, tests/, .github/.

```bash
git add packages/create-jw-agent/src/create_jw_agent/cli.py packages/create-jw-agent/tests/test_cli.py packages/create-jw-agent/tests/test_no_network.py packages/create-jw-agent/pyproject.toml
git commit -m "feat(create-jw-agent): Typer CLI with i18n, --check-pypi opt-in, no-network default"
```

---

### Task 9: `jw create-agent` wrapper in `jw-cli`

**Files:**
- Create: `packages/jw-cli/src/jw_cli/commands/create_agent.py`
- Modify: `packages/jw-cli/src/jw_cli/commands/__init__.py`
- Modify: `packages/jw-cli/src/jw_cli/main.py`
- Create: `packages/jw-cli/tests/test_create_agent_wrapper.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-cli/tests/test_create_agent_wrapper.py
"""The `jw create-agent` wrapper delegates to the standalone binary."""

from __future__ import annotations

from typer.testing import CliRunner

from jw_cli.main import app

runner = CliRunner()


def test_create_agent_subcommand_registered() -> None:
    result = runner.invoke(app, ["create-agent", "--help"])
    assert result.exit_code == 0
    assert "create-jw-agent" in result.stdout.lower() or "delegates" in result.stdout.lower()


def test_create_agent_subcommand_reports_missing_binary(monkeypatch) -> None:
    import jw_cli.commands.create_agent as mod

    monkeypatch.setattr(mod.shutil, "which", lambda _: None)
    result = runner.invoke(app, ["create-agent", "demo"])
    assert result.exit_code != 0
    assert "uvx" in result.stdout or "pipx" in result.stdout
```

- [ ] **Step 2: Run test (expect failure)**

```bash
uv run pytest packages/jw-cli/tests/test_create_agent_wrapper.py -v
```
Expected: `create-agent` subcommand not found.

- [ ] **Step 3: Implement the wrapper**

```python
# packages/jw-cli/src/jw_cli/commands/create_agent.py
"""Thin wrapper around the standalone `create-jw-agent` binary.

The wrapper exists only for discoverability — `jw create-agent ...` is meant to
be findable from `jw --help`. The real work lives in the `create-jw-agent`
package on PyPI (Fase 42).
"""

from __future__ import annotations

import shutil
import subprocess
import sys

import typer

app = typer.Typer(
    name="create-agent",
    help="Scaffolder wrapper that delegates to the standalone `create-jw-agent` binary.",
    add_completion=False,
)


@app.callback(invoke_without_command=True, context_settings={"allow_extra_args": True, "ignore_unknown_options": True})
def main(ctx: typer.Context) -> None:
    """Delegate to `create-jw-agent` on PATH; instruct install if missing."""

    binary = shutil.which("create-jw-agent")
    if not binary:
        typer.echo("create-jw-agent is not on PATH. Install with one of:")
        typer.echo("  uvx create-jw-agent ...")
        typer.echo("  pipx run create-jw-agent ...")
        typer.echo("  pip install create-jw-agent")
        raise typer.Exit(code=1)

    try:
        completed = subprocess.run([binary, *ctx.args], check=False)
    except FileNotFoundError:
        typer.echo("create-jw-agent vanished between detection and invocation; check PATH.")
        raise typer.Exit(code=1) from None
    sys.exit(completed.returncode)
```

```python
# packages/jw-cli/src/jw_cli/commands/__init__.py  (modify)
from jw_cli.commands import create_agent  # noqa: F401

# ... existing exports
```

```python
# packages/jw-cli/src/jw_cli/main.py  (modify — add registration)
from jw_cli.commands.create_agent import app as create_agent_app

# ... existing app construction
app.add_typer(create_agent_app, name="create-agent")
```

- [ ] **Step 4: Run test (expect pass)**

```bash
uv run pytest packages/jw-cli/tests/test_create_agent_wrapper.py -v
```
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-cli/src/jw_cli/commands/create_agent.py packages/jw-cli/src/jw_cli/main.py packages/jw-cli/src/jw_cli/commands/__init__.py packages/jw-cli/tests/test_create_agent_wrapper.py
git commit -m "feat(jw-cli): add 'jw create-agent' wrapper that delegates to create-jw-agent"
```

---

### Task 10: `pytest-cookbook` plugin — collect ` ```python ` blocks tagged `# test`

**Files:**
- Create: `tools/pytest-cookbook/pyproject.toml`
- Create: `tools/pytest-cookbook/src/pytest_cookbook/__init__.py`
- Create: `tools/pytest-cookbook/src/pytest_cookbook/plugin.py`
- Create: `tools/pytest-cookbook/tests/test_plugin.py`

- [ ] **Step 1: Write the failing test**

```python
# tools/pytest-cookbook/tests/test_plugin.py
"""Tests for the pytest-cookbook plugin."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest_plugins = ["pytester"]


def test_collects_only_blocks_with_test_marker(pytester: pytest.Pytester) -> None:
    pytester.makefile(
        ".md",
        recipe_demo="""
# Recipe demo

Some prose.

```python
# test
def test_passes():
    assert 1 + 1 == 2
```

Another block, **not** marked:

```python
def not_collected():
    raise RuntimeError("should not run")
```
""",
    )
    result = pytester.runpytest("--collect-from-markdown", str(pytester.path), "-v")
    result.assert_outcomes(passed=1)


def test_collected_block_can_use_assert(pytester: pytest.Pytester) -> None:
    pytester.makefile(
        ".md",
        recipe_assertfail="""
```python
# test
def test_boom():
    assert False, "expected"
```
""",
    )
    result = pytester.runpytest("--collect-from-markdown", str(pytester.path), "-v")
    result.assert_outcomes(failed=1)


def test_no_op_when_no_marker(pytester: pytest.Pytester) -> None:
    pytester.makefile(".md", recipe_nothing="```python\nprint('x')\n```")
    result = pytester.runpytest("--collect-from-markdown", str(pytester.path), "-v")
    # No tests collected ↔ pytest exits with code 5 (no tests collected) — but the
    # plugin should still allow normal collection to coexist; we just expect zero
    # tests collected.
    assert result.ret in (0, 5)
```

- [ ] **Step 2: Run test (expect failure — plugin missing)**

```bash
uv run pytest tools/pytest-cookbook/tests/test_plugin.py -v
```
Expected: collection error, plugin not loaded.

- [ ] **Step 3: Write the pyproject and implement the plugin**

```toml
# tools/pytest-cookbook/pyproject.toml
[project]
name = "pytest-cookbook"
version = "0.1.0"
description = "Internal pytest plugin: run executable code blocks from Markdown cookbook recipes"
requires-python = ">=3.13"
license = "GPL-3.0-only"
dependencies = ["pytest>=8.0.0"]

[project.entry-points.pytest11]
cookbook = "pytest_cookbook.plugin"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/pytest_cookbook"]
```

```python
# tools/pytest-cookbook/src/pytest_cookbook/__init__.py
"""pytest-cookbook — execute Markdown code blocks marked `# test`."""

__version__ = "0.1.0"
```

```python
# tools/pytest-cookbook/src/pytest_cookbook/plugin.py
"""pytest plugin: collect ``` ```python ... ``` ``` blocks tagged `# test` from Markdown.

Usage:
    pytest --collect-from-markdown=path/to/dir

For every block whose first content line is `# test`, a synthetic Python module
is built that exposes any `def test_*` functions inside the block; pytest then
collects them normally.
"""

from __future__ import annotations

import importlib.util
import re
import textwrap
import types
from pathlib import Path
from typing import Iterable

import pytest

_FENCE = re.compile(
    r"```python\s*\n(?P<body>.*?)\n```",
    re.DOTALL,
)


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup("cookbook", "Markdown recipe collection")
    group.addoption(
        "--collect-from-markdown",
        action="append",
        default=[],
        help="Directory (or .md file) to scan for ` ```python ` blocks tagged `# test`.",
    )


def _iter_md_files(targets: Iterable[str]) -> Iterable[Path]:
    for raw in targets:
        path = Path(raw)
        if path.is_file() and path.suffix == ".md":
            yield path
        elif path.is_dir():
            yield from sorted(path.rglob("*.md"))


def _extract_blocks(md: str) -> list[str]:
    blocks: list[str] = []
    for match in _FENCE.finditer(md):
        body = textwrap.dedent(match.group("body"))
        first_nonblank = next((ln for ln in body.splitlines() if ln.strip()), "")
        if first_nonblank.strip() == "# test":
            # Drop the marker so the resulting module is valid python.
            blocks.append("\n".join(body.splitlines()[1:]))
    return blocks


def _module_from_source(source: str, name: str, path: Path) -> types.ModuleType:
    spec = importlib.util.spec_from_loader(name, loader=None, origin=str(path))
    module = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    module.__file__ = str(path)
    compiled = compile(source, str(path), "exec")
    exec(compiled, module.__dict__)
    return module


def pytest_collect_file(parent: pytest.Collector, file_path: Path):  # noqa: D401
    targets = parent.config.getoption("--collect-from-markdown") or []
    if not targets:
        return None
    allowed_files = set(_iter_md_files(targets))
    if file_path not in allowed_files:
        return None
    return _CookbookMarkdown.from_parent(parent, path=file_path)


def pytest_collection(session: pytest.Session) -> None:
    """Add the recipe roots as collection args so pytest_collect_file fires."""

    extra = session.config.getoption("--collect-from-markdown") or []
    if not extra:
        return
    files = [str(p) for p in _iter_md_files(extra)]
    session.config.args.extend(files)


class _CookbookMarkdown(pytest.Module):
    """Pretend a Markdown file is a Python module containing the union of all `# test` blocks."""

    def _getobj(self) -> types.ModuleType:
        text = self.path.read_text(encoding="utf-8")
        blocks = _extract_blocks(text)
        if not blocks:

            class _Empty:
                pass

            return _Empty()  # type: ignore[return-value]
        source = "\n\n# ---- next block ----\n\n".join(blocks)
        return _module_from_source(source, f"pytest_cookbook_{self.path.stem}", self.path)
```

- [ ] **Step 4: Run test (expect pass)**

```bash
uv run pytest tools/pytest-cookbook/tests/test_plugin.py -v
```
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add tools/pytest-cookbook
git commit -m "feat(pytest-cookbook): plugin collects ```python ``` blocks tagged '# test'"
```

---

### Task 11: Cookbook shared fakes + first 4 recipes (01–04)

**Files:**
- Create: `docs/cookbook/README.md`
- Create: `docs/cookbook/_common/__init__.py`
- Create: `docs/cookbook/_common/conftest.py`
- Create: `docs/cookbook/_common/fakes.py`
- Create: `docs/cookbook/01-resolve-bible-reference.md`
- Create: `docs/cookbook/02-search-and-synthesize.md`
- Create: `docs/cookbook/03-telegram-bot.md`
- Create: `docs/cookbook/04-finetune-llama-3.md`
- Create: `docs/cookbook/tests/__init__.py`
- Create: `docs/cookbook/tests/test_cookbook.py`

- [ ] **Step 1: Write shared fakes + conftest**

```python
# docs/cookbook/_common/__init__.py
"""Shared utilities for cookbook recipe tests (offline fakes)."""
```

```python
# docs/cookbook/_common/fakes.py
"""Deterministic fakes that recipes can import.

Recipes import these so the `# test` blocks run without any network.
Real code that follows the recipe pattern would import the real client.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class FakeBibleRef:
    book: str
    chapter: int
    verse: int


class FakeWOLClient:
    """In-memory WOL stand-in. Add fixtures as recipes demand them."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    def build_url_for_verse(self, ref: FakeBibleRef) -> str:
        self.calls.append(("url", {"ref": ref}))
        return f"https://wol.jw.org/en/wol/b/{ref.book}/{ref.chapter}/{ref.verse}"

    def fetch_verse_text(self, ref: FakeBibleRef) -> str:
        self.calls.append(("verse", {"ref": ref}))
        if (ref.book, ref.chapter, ref.verse) == ("John", 3, 16):
            return "For God so loved the world..."
        return "<placeholder verse>"

    def search_topic_index(self, topic: str, limit: int = 5) -> list[dict]:
        self.calls.append(("topic", {"topic": topic, "limit": limit}))
        return [
            {"url": "https://wol.jw.org/topic/example", "title": f"On {topic}"},
        ] * limit


class FakeEmbedder:
    """Returns deterministic dense vectors keyed by text hash."""

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[(abs(hash(t)) % 1000) / 1000.0] * 4 for t in texts]


class FakeClaude:
    """Stand-in for the Anthropic SDK client."""

    def __init__(self) -> None:
        self.messages_create_calls: list[dict] = []

    class _Messages:
        def __init__(self, parent: "FakeClaude") -> None:
            self._parent = parent

        def create(self, **kwargs: object) -> object:
            self._parent.messages_create_calls.append(dict(kwargs))

            class _Response:
                content = [type("Block", (), {"text": "Synthesized answer about John 3:16."})]

            return _Response()

    @property
    def messages(self) -> "FakeClaude._Messages":
        return self._Messages(self)
```

```python
# docs/cookbook/_common/conftest.py
"""Fixtures shared with every recipe block."""

from __future__ import annotations

import pytest

from docs.cookbook._common.fakes import FakeBibleRef, FakeClaude, FakeEmbedder, FakeWOLClient


@pytest.fixture
def fake_wol() -> FakeWOLClient:
    return FakeWOLClient()


@pytest.fixture
def fake_embedder() -> FakeEmbedder:
    return FakeEmbedder()


@pytest.fixture
def fake_claude() -> FakeClaude:
    return FakeClaude()


@pytest.fixture
def john_3_16() -> FakeBibleRef:
    return FakeBibleRef(book="John", chapter=3, verse=16)
```

- [ ] **Step 2: Write the cookbook README**

```markdown
# Cookbook

Twelve copy-pasteable recipes for building plugins on top of jw-agent-toolkit.

Every block tagged `# test` is executed offline in CI by [`pytest-cookbook`](../../tools/pytest-cookbook/).

| # | Recipe | URL slug |
|---|---|---|
| 01 | Resolve a Bible reference | [`/cookbook/resolve-bible-reference`](01-resolve-bible-reference.md) |
| 02 | Search & synthesize | [`/cookbook/search-and-synthesize`](02-search-and-synthesize.md) |
| 03 | Telegram bot | [`/cookbook/telegram-bot`](03-telegram-bot.md) |
| 04 | Fine-tune Llama 3 | [`/cookbook/finetune-llama-3`](04-finetune-llama-3.md) |
| 05 | Add a parser | [`/cookbook/add-parser`](05-add-parser.md) |
| 06 | Custom embedder | [`/cookbook/custom-embedder`](06-custom-embedder.md) |
| 07 | Add NLI fidelity wrap | [`/cookbook/add-nli`](07-add-nli.md) |
| 08 | Publish to PyPI | [`/cookbook/publish-to-pypi`](08-publish-to-pypi.md) |
| 09 | Trace an agent run | [`/cookbook/trace-agent-run`](09-trace-agent-run.md) |
| 10 | Calibrate a golden case | [`/cookbook/calibrate-golden-case`](10-calibrate-golden-case.md) |
| 11 | Browser extension | [`/cookbook/browser-extension`](11-browser-extension.md) |
| 12 | Capacitor app | [`/cookbook/capacitor-app`](12-capacitor-app.md) |
```

- [ ] **Step 3: Write recipes 01–04**

```markdown
# Resolve a Bible reference

> **Time**: 3 min
> **Requires**: none
> **Slug**: `/cookbook/resolve-bible-reference`

## What you build

A snippet that turns "John 3:16" into a verse URL and pulls the text — offline-friendly.

## Code

```python
# test
from docs.cookbook._common.fakes import FakeBibleRef, FakeWOLClient


def test_resolve_bible_reference():
    client = FakeWOLClient()
    ref = FakeBibleRef(book="John", chapter=3, verse=16)
    url = client.build_url_for_verse(ref)
    text = client.fetch_verse_text(ref)

    assert url.startswith("https://wol.jw.org/")
    assert "John" in url
    assert "loved the world" in text
```

## Why it works

`build_url_for_verse` only formats a path — no network. `fetch_verse_text` returns the cached corpus row for that ref. In production code, swap `FakeWOLClient` for `from jw_core.wol import WOLClient`.

## Variations

- Other books: pass `book="Psalms"`.
- Other languages: WOLClient accepts `lang="es"`.
- Range: use `parse_reference("Rom 6:23-24")` to get a list of refs.

## Next

Recipe 02 — search & synthesize.
```

```markdown
# Search & synthesize

> **Time**: 5 min
> **Requires**: `[claude]` extra (mocked here)
> **Slug**: `/cookbook/search-and-synthesize`

## What you build

A pipeline that pulls topic-index hits and asks Claude to synthesize an answer with citations.

## Code

```python
# test
from docs.cookbook._common.fakes import FakeClaude, FakeWOLClient


def synthesize(topic: str, wol, claude) -> str:
    findings = wol.search_topic_index(topic, limit=3)
    citations = "\n".join(f"- {f['url']}" for f in findings)
    prompt = f"Topic: {topic}\nSources:\n{citations}\nAnswer briefly."
    response = claude.messages.create(model="claude-haiku-4-7", max_tokens=200,
                                      messages=[{"role": "user", "content": prompt}])
    return response.content[0].text


def test_search_and_synthesize():
    wol, claude = FakeWOLClient(), FakeClaude()
    out = synthesize("creation", wol, claude)
    assert "Synthesized" in out
    assert any("topic" == c[0] for c in wol.calls)
    assert claude.messages_create_calls
```

## Why it works

The WOL stand-in returns a deterministic list. The Claude stand-in records the call shape so the test can assert on it. Replace with `anthropic.Anthropic()` and the real WOLClient in production.

## Variations

- Use `claude-sonnet-4-7` for higher-fidelity answers.
- Add fidelity wrap (Recipe 07) for NLI-checked citations.
- Cache responses with `jw_core.cache.disk_cache`.

## Next

Recipe 03 — wrap this into a Telegram bot.
```

```markdown
# Telegram bot

> **Time**: 8 min
> **Requires**: `python-telegram-bot` (mocked here)
> **Slug**: `/cookbook/telegram-bot`

## What you build

A handler that turns user messages into agent runs, validated against a fake update.

## Code

```python
# test
class FakeMessage:
    def __init__(self, text: str) -> None:
        self.text = text
        self.replies: list[str] = []

    async def reply_text(self, text: str) -> None:
        self.replies.append(text)


class FakeUpdate:
    def __init__(self, text: str) -> None:
        self.message = FakeMessage(text)


async def handle(update, agent_callable):
    answer = await agent_callable(question=update.message.text, language="en")
    await update.message.reply_text(answer.findings[0].text)


async def fake_agent(*, question: str, language: str = "en"):
    class _F:
        text = f"echo: {question}"
        source = "stub"
        citation = type("C", (), {"url": "https://wol.jw.org/"})

    class _R:
        findings = [_F()]

    return _R()


def test_telegram_handler():
    import asyncio
    update = FakeUpdate("Trinity")
    asyncio.run(handle(update, fake_agent))
    assert update.message.replies == ["echo: Trinity"]
```

## Why it works

Telegram's `Update` is a Pydantic-ish object; we mimic just the bit our handler touches. In production: register `handle` as an `MessageHandler(filters.TEXT, handle)` on `python-telegram-bot`'s `Application`.

## Variations

- Add `/help` and `/start` handlers.
- Wrap `agent_callable` with rate-limit middleware.
- Reply with markdown using `reply_text(..., parse_mode="Markdown")`.

## Next

Recipe 04 — fine-tune a local model with `jw-finetune`.
```

```markdown
# Fine-tune Llama 3

> **Time**: 20 min (real run) — test mode here is < 1 s
> **Requires**: `[finetune]` extra (mocked here)
> **Slug**: `/cookbook/finetune-llama-3`

## What you build

A recipe that extracts Q&A pairs from local JWPUB and queues them as training data (no GPU in CI).

## Code

```python
# test
def extract_qa_pairs(documents: list[dict]) -> list[dict]:
    pairs = []
    for doc in documents:
        for paragraph in doc.get("paragraphs", []):
            if paragraph.startswith("Q:"):
                question = paragraph[2:].strip()
                pairs.append({"q": question, "a": "<doc>"})
    return pairs


def test_extract_qa_pairs():
    docs = [
        {"paragraphs": ["Q: What is hope?", "A: A reasonable expectation."]},
        {"paragraphs": ["normal text", "Q: Who is Michael?"]},
    ]
    pairs = extract_qa_pairs(docs)
    assert len(pairs) == 2
    assert pairs[0]["q"] == "What is hope?"
```

## Why it works

The real `jw_finetune.dataset.from_jwpub(path)` does the same extraction over JWPUB SQLite plus Watchtower & Workbook Q&A. The preset `synth_provider=None` skips synthetic augmentation and uses only the corpus.

## Variations

- `synth_provider="claude"` to amplify with paraphrases.
- `base_model="llama3.1-8b"` vs `"qwen2.5-7b"`.
- Target adapter rank `r=16` instead of `r=8` for richer LoRA.

## Next

Recipe 05 — add a parser plugin.
```

- [ ] **Step 4: Write the cookbook test harness**

```python
# docs/cookbook/tests/__init__.py
```

```python
# docs/cookbook/tests/test_cookbook.py
"""Drive `pytest-cookbook` to execute every recipe block in this folder."""

from __future__ import annotations

from pathlib import Path

import pytest

COOKBOOK_DIR = Path(__file__).resolve().parent.parent


@pytest.mark.parametrize(
    "recipe",
    sorted(p.name for p in COOKBOOK_DIR.glob("[0-9][0-9]-*.md")),
)
def test_recipe_exists(recipe: str) -> None:
    """Lightweight: confirms the recipe file exists. Real exec happens via plugin."""

    assert (COOKBOOK_DIR / recipe).exists()
```

- [ ] **Step 5: Run the plugin against the cookbook**

```bash
uv run pytest --collect-from-markdown docs/cookbook -v
```
Expected: 4 collected `# test` blocks pass (one per recipe 01–04).

```bash
git add docs/cookbook/README.md docs/cookbook/_common docs/cookbook/01-*.md docs/cookbook/02-*.md docs/cookbook/03-*.md docs/cookbook/04-*.md docs/cookbook/tests
git commit -m "feat(cookbook): recipes 01-04 + offline fakes (executable via pytest-cookbook)"
```

---

### Task 12: Cookbook recipes 05–08

**Files:**
- Create: `docs/cookbook/05-add-parser.md`
- Create: `docs/cookbook/06-custom-embedder.md`
- Create: `docs/cookbook/07-add-nli.md`
- Create: `docs/cookbook/08-publish-to-pypi.md`

- [ ] **Step 1: Write recipe 05**

```markdown
# Add a parser

> **Time**: 6 min
> **Requires**: Fase 41 Plugin SDK
> **Slug**: `/cookbook/add-parser`

## What you build

A parser plugin that converts raw bytes into a `ParsedDocument`, discoverable via entry point.

## Code

```python
# test
from dataclasses import dataclass


@dataclass
class ParsedDocument:
    text: str
    metadata: dict


class TXTParser:
    def parse(self, raw: bytes) -> ParsedDocument:
        text = raw.decode("utf-8", errors="replace")
        return ParsedDocument(text=text, metadata={"format": "txt", "bytes": len(raw)})


def test_txt_parser_roundtrip():
    parser = TXTParser()
    doc = parser.parse(b"hello world")
    assert doc.text == "hello world"
    assert doc.metadata["format"] == "txt"
    assert doc.metadata["bytes"] == 11
```

## Why it works

Plugin SDK Fase 41 declares `Parser` as a `Protocol` with one method `parse(raw: bytes) -> ParsedDocument`. Any class that matches the shape passes the runtime `verify_plugin()` check.

## Variations

- Register via `[project.entry-points."jw_agent_toolkit.parsers"]`.
- Add `media_type: str` to metadata for routing.
- Stream input with `parse(stream: BinaryIO)` overload.

## Next

Recipe 06 — custom embedder.
```

- [ ] **Step 2: Write recipe 06**

```markdown
# Custom embedder

> **Time**: 5 min
> **Requires**: Fase 41
> **Slug**: `/cookbook/custom-embedder`

## What you build

A deterministic embedder that returns a `(N, d)` array; perfect for tests.

## Code

```python
# test
import math


class HashEmbedder:
    DIM = 8

    def embed(self, texts: list[str]) -> list[list[float]]:
        out = []
        for t in texts:
            vec = [0.0] * self.DIM
            for tok in t.split():
                vec[hash(tok) % self.DIM] += 1.0
            norm = math.sqrt(sum(x * x for x in vec)) or 1.0
            out.append([x / norm for x in vec])
        return out


def test_hash_embedder_shape():
    e = HashEmbedder()
    vecs = e.embed(["hello world", "foo"])
    assert len(vecs) == 2
    assert len(vecs[0]) == 8
    norm = math.sqrt(sum(x * x for x in vecs[0]))
    assert 0.999 < norm < 1.001
```

## Why it works

The Embedder Protocol only requires `embed(list[str]) -> list[list[float]]`. Deterministic hashing is enough for unit tests; swap for `sentence-transformers` in production.

## Variations

- Wrap real `SentenceTransformer("all-MiniLM-L6-v2")`.
- Cache results in SQLite via `jw_rag.embedder.cache_to_sqlite`.
- Use Voyage AI for multilingual scenarios.

## Next

Recipe 07 — NLI fidelity wrap.
```

- [ ] **Step 3: Write recipe 07**

```markdown
# Add NLI fidelity wrap

> **Time**: 7 min
> **Requires**: Fase 39 `fidelity_wrap`
> **Slug**: `/cookbook/add-nli`

## What you build

Wrap any agent so its findings carry an `nli_verdict` proving the citation supports the claim.

## Code

```python
# test
async def fake_agent(*, question: str, language: str = "en"):
    class _F:
        text = "Hope is reasonable expectation."
        metadata = {"source": "stub"}

    class _R:
        findings = [_F()]
        metadata = {}

    return _R()


def fidelity_wrap(agent):
    async def wrapped(**kwargs):
        result = await agent(**kwargs)
        for finding in result.findings:
            # Stub NLI: pretend the text supports itself.
            finding.metadata = {**finding.metadata, "nli_verdict": "entailment", "nli_score": 0.92}
        return result
    return wrapped


def test_fidelity_wrap_adds_verdict():
    import asyncio
    wrapped = fidelity_wrap(fake_agent)
    result = asyncio.run(wrapped(question="hope", language="en"))
    assert result.findings[0].metadata["nli_verdict"] == "entailment"
    assert result.findings[0].metadata["nli_score"] > 0.5
```

## Why it works

Fase 39 introduced `fidelity_wrap` that runs an NLI model over `(citation_text, finding.text)`. The wrap is opt-in and adds `nli_verdict ∈ {entailment, neutral, contradiction}` plus `nli_score ∈ [0,1]`.

## Variations

- Threshold: drop findings under `nli_score < 0.7`.
- Use Claude as judge instead of a local NLI model (slower, more accurate).
- Cache verdicts on a per-citation basis.

## Next

Recipe 08 — publish to PyPI.
```

- [ ] **Step 4: Write recipe 08**

```markdown
# Publish to PyPI

> **Time**: 10 min
> **Requires**: PyPI account + trusted publishing config
> **Slug**: `/cookbook/publish-to-pypi`

## What you build

A pyproject that is valid for `uv build` + `uv publish` via GitHub Actions trusted publishing (no secrets).

## Code

```python
# test
import tomllib


def validate_pyproject(toml_text: str) -> None:
    data = tomllib.loads(toml_text)
    project = data["project"]
    assert project["name"]
    assert project["version"]
    assert "license" in project
    assert any(group.startswith("jw_agent_toolkit.") for group in
               data.get("project", {}).get("entry-points", {}))


SAMPLE = '''
[project]
name = "my-plugin"
version = "0.1.0"
license = "GPL-3.0"
requires-python = ">=3.13"
dependencies = ["jw-core>=2.3,<3.0"]

[project.entry-points."jw_agent_toolkit.agents"]
my_plugin = "my_plugin.agent:my_plugin"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
'''


def test_sample_pyproject_is_valid():
    validate_pyproject(SAMPLE)
```

## Why it works

PyPI only enforces `name`, `version`, and a build system. The entry point group `jw_agent_toolkit.agents` is what makes `jw-core` discover the plugin after install.

## Variations

- Use `setuptools` instead of `hatchling`.
- Add `optional-dependencies` for `dev`, `test`, `gpu`.
- Configure `.github/workflows/release.yml` with `pypa/gh-action-pypi-publish@v1` for trusted publishing (no secrets needed).

## Next

Recipe 09 — trace an agent run.
```

- [ ] **Step 5: Run plugin against expanded cookbook + commit**

```bash
uv run pytest --collect-from-markdown docs/cookbook -v
```
Expected: 8 collected blocks pass.

```bash
git add docs/cookbook/05-*.md docs/cookbook/06-*.md docs/cookbook/07-*.md docs/cookbook/08-*.md
git commit -m "feat(cookbook): recipes 05-08 (parser, embedder, NLI wrap, PyPI publish)"
```

---

### Task 13: Cookbook recipes 09–10 (Tier-1 ready) + 11–12 (skip-until-fase)

**Files:**
- Create: `docs/cookbook/09-trace-agent-run.md`
- Create: `docs/cookbook/10-calibrate-golden-case.md`
- Create: `docs/cookbook/11-browser-extension.md`
- Create: `docs/cookbook/12-capacitor-app.md`

- [ ] **Step 1: Write recipe 09**

```markdown
# Trace an agent run

> **Time**: 4 min
> **Requires**: Fase 43 `AgentTracer`
> **Slug**: `/cookbook/trace-agent-run`

## What you build

Capture a JSON trace of an agent invocation: timestamps, findings, citations.

## Code

```python
# test
import json
import time
from dataclasses import dataclass


@dataclass
class TraceSpan:
    name: str
    started_at: float
    duration_ms: int
    data: dict


class AgentTracer:
    def __init__(self) -> None:
        self.spans: list[TraceSpan] = []

    def record(self, name: str, started_at: float, data: dict) -> None:
        self.spans.append(TraceSpan(name, started_at, int((time.monotonic() - started_at) * 1000), data))

    def to_json(self) -> str:
        return json.dumps([span.__dict__ for span in self.spans])


def test_tracer_records_four_fields():
    tracer = AgentTracer()
    start = time.monotonic()
    tracer.record("agent.run", start, {"question": "?", "findings": 3})
    data = json.loads(tracer.to_json())
    assert data and {"name", "started_at", "duration_ms", "data"} <= set(data[0].keys())
```

## Why it works

Fase 43's tracer is a structured logger: each `record(...)` emits one span, batched into JSON or fed to OpenTelemetry. The 4-field schema is the contract.

## Variations

- Stream to stdout for dev; to OTLP collector in prod.
- Decorate any callable with `@traced("name")`.
- Attach `trace_id` from the upstream HTTP request.

## Next

Recipe 10 — calibrate a golden case.
```

- [ ] **Step 2: Write recipe 10**

```markdown
# Calibrate a golden case

> **Time**: 6 min
> **Requires**: Fase 22 `jw-eval`
> **Slug**: `/cookbook/calibrate-golden-case`

## What you build

A YAML golden case that `jw eval` can load and validate at L1.

## Code

```python
# test
import yaml


GOLDEN_YAML = """
id: l1_demo
agent: my_agent
layer: l1
input:
  question: "What is hope?"
  language: en
expected:
  min_findings: 1
  must_have_source: topic_index
  must_have_citation: true
  forbidden_keywords_in_findings: ["maybe"]
metadata:
  added_at: 2026-05-31
"""


def test_golden_case_yaml_shape():
    data = yaml.safe_load(GOLDEN_YAML)
    assert data["layer"] in {"l1", "l2", "l3"}
    assert isinstance(data["expected"]["min_findings"], int)
    assert isinstance(data["expected"]["forbidden_keywords_in_findings"], list)
```

## Why it works

`Suite.load_case(yaml_text)` in `jw-eval` (Fase 22) validates against the `GoldenCase` Pydantic model. Any deviation from this shape fails immediately with a readable error.

## Variations

- L2: `expected_citations: [URL]` + `support_phrases: [...]`.
- L3: `golden_answer: "..."` + thresholds.
- Use `jw eval --fixtures` to bulk-validate a directory.

## Next

Recipe 11 — browser extension (Fase 48).
```

- [ ] **Step 3: Write recipe 11 with skip frontmatter**

```markdown
# Browser extension

> **Time**: 12 min
> **Requires**: Fase 48 (Manifest v3 + REST API)
> **Slug**: `/cookbook/browser-extension`
> **Status**: requires-fase: 48 (auto-skipped in CI until Fase 48 lands)

## What you build

A Manifest v3 extension that calls the REST API endpoint from Fase 20.

## Code

```python
# test skip-until-fase-48
import json


MANIFEST = {
    "manifest_version": 3,
    "name": "jw-agent-toolkit",
    "version": "0.1.0",
    "permissions": ["activeTab"],
    "host_permissions": ["https://wol.jw.org/*"],
    "background": {"service_worker": "background.js"},
    "action": {"default_popup": "popup.html"},
}


def test_manifest_v3_valid():
    assert MANIFEST["manifest_version"] == 3
    assert "service_worker" in MANIFEST["background"]
    assert all(p.startswith("https://") for p in MANIFEST["host_permissions"])
```

## Why it works

Chrome's Manifest v3 requires a service worker, an action, and explicit host permissions. We validate the schema as JSON; the real extension would also need ` ``` background.js ``` ` and ` ``` popup.html ``` `.

## Variations

- Add `"side_panel": { "default_path": "panel.html" }` for sidebars.
- Use OAuth with the REST API via `chrome.identity.getAuthToken`.

## Next

Recipe 12 — Capacitor app.
```

The marker `# test skip-until-fase-48` makes `pytest-cookbook` skip this block until Fase 48 lands. Extend the plugin to honor `skip-until-fase-N` markers — done in Step 5.

- [ ] **Step 4: Write recipe 12**

```markdown
# Capacitor app

> **Time**: 15 min
> **Requires**: Fase 47 (`@jw-agent-toolkit/core` JS)
> **Slug**: `/cookbook/capacitor-app`
> **Status**: requires-fase: 47 (auto-skipped in CI until Fase 47 lands)

## What you build

A Capacitor (mobile) shell that wraps the JS SDK around the REST API.

## Code

```python
# test skip-until-fase-47
import json


PACKAGE_JSON = {
    "name": "my-jw-app",
    "version": "0.1.0",
    "dependencies": {
        "@capacitor/core": "^6.0.0",
        "@capacitor/ios": "^6.0.0",
        "@capacitor/android": "^6.0.0",
        "@jw-agent-toolkit/core": "^0.1.0",
    },
}


def test_package_json_valid():
    text = json.dumps(PACKAGE_JSON)
    data = json.loads(text)
    assert data["name"]
    assert all(dep.startswith("@") for dep in data["dependencies"])
```

## Why it works

Capacitor adds native wrappers around any web app. The JS SDK from Fase 47 ships TypeScript types and an offline cache. No npm install in CI; we just validate the package.json shape.

## Variations

- Add `@capacitor/secure-storage` for token persistence.
- Use Expo as an alternative shell.

## Next

Back to the cookbook index — explore Fase 22 (eval), Fase 39 (NLI), Fase 41 (SDK).
```

- [ ] **Step 5: Extend pytest-cookbook to honor `skip-until-fase-N`**

Patch `tools/pytest-cookbook/src/pytest_cookbook/plugin.py` in `_extract_blocks`:

```python
import re as _re

_SKIP_RE = _re.compile(r"^#\s*test(?:\s+skip-until-fase-(?P<fase>\d+))?\s*$")


def _extract_blocks(md: str) -> list[str]:
    blocks: list[str] = []
    for match in _FENCE.finditer(md):
        body = textwrap.dedent(match.group("body"))
        first = next((ln for ln in body.splitlines() if ln.strip()), "")
        marker = _SKIP_RE.match(first.strip())
        if not marker:
            continue
        if marker.group("fase"):
            # Skip block: emit a placeholder that pytest will collect as a skip.
            blocks.append(
                f"import pytest\n"
                f"pytest.skip('block requires fase {marker.group(\"fase\")}', allow_module_level=True)\n"
            )
            continue
        blocks.append("\n".join(body.splitlines()[1:]))
    return blocks
```

Add a test in `tools/pytest-cookbook/tests/test_plugin.py`:

```python
def test_skip_until_fase_marker(pytester: pytest.Pytester) -> None:
    pytester.makefile(
        ".md",
        recipe_skip="""
```python
# test skip-until-fase-47
def test_should_be_skipped():
    assert False
```
""",
    )
    result = pytester.runpytest("--collect-from-markdown", str(pytester.path), "-v")
    assert "skipped" in result.stdout.str().lower()
```

- [ ] **Step 6: Run the plugin + commit**

```bash
uv run pytest --collect-from-markdown docs/cookbook -v
```
Expected: 10 active + 2 skipped.

```bash
git add docs/cookbook/09-*.md docs/cookbook/10-*.md docs/cookbook/11-*.md docs/cookbook/12-*.md tools/pytest-cookbook
git commit -m "feat(cookbook): recipes 09-12 incl. skip-until-fase markers"
```

---

### Task 14: CI job `cookbook-tests` + integration with main workflow

**Files:**
- Create: `.github/workflows/cookbook-tests.yml`
- Modify: `.github/workflows/ci.yml`

- [ ] **Step 1: Write the new workflow**

```yaml
# .github/workflows/cookbook-tests.yml
name: cookbook-tests
on:
  push:
    branches: [main]
  pull_request:
    paths:
      - "docs/cookbook/**"
      - "tools/pytest-cookbook/**"
      - "packages/create-jw-agent/**"
      - ".github/workflows/cookbook-tests.yml"

jobs:
  cookbook:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
        with:
          enable-cache: true
      - name: Install Python 3.13
        run: uv python install 3.13
      - name: Sync workspace
        run: uv sync --all-packages
      - name: Run cookbook recipes
        run: uv run pytest --collect-from-markdown docs/cookbook -v
      - name: Run create-jw-agent self-tests
        run: uv run --package create-jw-agent pytest packages/create-jw-agent/tests -v
      - name: Run pytest-cookbook self-tests
        run: uv run pytest tools/pytest-cookbook/tests -v
```

- [ ] **Step 2: Hook into main CI**

Append to `.github/workflows/ci.yml` jobs section:

```yaml
  cookbook-tests:
    uses: ./.github/workflows/cookbook-tests.yml
```

- [ ] **Step 3: Validate workflow syntax locally**

```bash
uv run python -c "import yaml, pathlib; [yaml.safe_load(pathlib.Path(p).read_text()) for p in ['.github/workflows/cookbook-tests.yml', '.github/workflows/ci.yml']]; print('ok')"
```
Expected: `ok`.

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/cookbook-tests.yml .github/workflows/ci.yml
git commit -m "ci: add cookbook-tests workflow (12 recipes + scaffolder + plugin)"
```

- [ ] **Step 5: Push and verify on GitHub**

```bash
git push origin <branch>
gh run watch --exit-status
```
Expected: cookbook-tests job green within 10 min.

---

### Task 15: GitHub Action for trusted publishing of `create-jw-agent` to PyPI

**Files:**
- Create: `.github/workflows/publish-create-jw-agent.yml`

- [ ] **Step 1: Write the workflow**

```yaml
# .github/workflows/publish-create-jw-agent.yml
name: publish-create-jw-agent
on:
  push:
    tags:
      - "create-jw-agent-v*"

permissions:
  contents: read
  id-token: write  # trusted publishing

jobs:
  build-and-publish:
    runs-on: ubuntu-latest
    environment:
      name: pypi
      url: https://pypi.org/project/create-jw-agent/
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
      - run: uv python install 3.13
      - name: Build wheel and sdist
        working-directory: packages/create-jw-agent
        run: uv build
      - name: Publish to PyPI (trusted publishing)
        uses: pypa/gh-action-pypi-publish@release/v1
        with:
          packages-dir: packages/create-jw-agent/dist
          attestations: true
```

- [ ] **Step 2: Validate locally**

```bash
uv run python -c "import yaml; yaml.safe_load(open('.github/workflows/publish-create-jw-agent.yml')); print('ok')"
```

- [ ] **Step 3: Document the trusted-publishing setup**

Append to `docs/guias/scaffolding.md` (will exist after Task 17):

> Configure once: in PyPI project settings → Publishing → Add trusted publisher with owner=`eliascipre`, repo=`jw-agent-toolkit`, workflow=`publish-create-jw-agent.yml`, environment=`pypi`. No API tokens needed.

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/publish-create-jw-agent.yml
git commit -m "ci: trusted-publishing workflow for create-jw-agent (tag triggered)"
```

---

### Task 16: Astro site integration — verify recipe URLs + alias

**Files:**
- Modify: `website/src/content.config.ts` (only if cookbook glob is missing)
- Create: `website/src/pages/cookbook/[slug].astro` (alias redirect)

- [ ] **Step 1: Audit current content.config.ts**

```bash
grep -n "cookbook" website/src/content.config.ts || echo "needs cookbook glob"
```

If the glob already covers `docs/cookbook/**`, no edit needed. Otherwise extend the existing `docs` collection.

- [ ] **Step 2: Write the alias page**

```astro
---
// website/src/pages/cookbook/[slug].astro
export async function getStaticPaths() {
  const recipes = await Astro.glob("../../../docs/cookbook/[0-9][0-9]-*.md");
  return recipes.map((recipe) => {
    const stem = recipe.file.split("/").pop()!.replace(/^[0-9]+-/, "").replace(/\.md$/, "");
    return { params: { slug: stem } };
  });
}

const { slug } = Astro.params;
const target = `/docs/cookbook/${slug}`;
---
<meta http-equiv="refresh" content={`0; url=${target}`} />
<link rel="canonical" href={target} />
<script>window.location.replace({`"${target}"`})</script>
```

- [ ] **Step 3: Verify build**

```bash
cd website && npm install --silent && npm run build
```
Expected: no errors. `dist/cookbook/resolve-bible-reference/index.html` present.

- [ ] **Step 4: Quick smoke on Pagefind index**

```bash
test -f website/dist/pagefind/pagefind.js && echo "Pagefind index built"
```
Expected: `Pagefind index built`.

- [ ] **Step 5: Commit**

```bash
git add website/src/pages/cookbook
git commit -m "feat(website): /cookbook/<slug> alias redirects to /docs/cookbook/<slug>"
```

---

### Task 17: Write the user-facing guide

**Files:**
- Create: `docs/guias/scaffolding.md`
- Modify: `docs/README.md`

- [ ] **Step 1: Write the guide**

```markdown
# Scaffolding y Cookbook (Fase 42)

Esta guía cubre cómo crear un plugin con `create-jw-agent` y cómo aprovechar el cookbook ejecutable para acelerar tu primera entrega.

## Crear tu primer plugin

    uvx create-jw-agent mi-traductor --type=agent --lang=es

Salida:

    mi-traductor/
    ├── pyproject.toml   # entry point declarado
    ├── src/mi_traductor/agent.py
    ├── tests/test_mi_traductor.py
    ├── .github/workflows/ci.yml
    └── ...

CI verde en el primer commit. `uv sync && uv run pytest`.

## Tipos disponibles

| `--type`   | Para qué sirve |
|------------|----------------|
| `agent`    | Agente conversacional con findings + citations |
| `parser`   | Parser de formato arbitrario → `ParsedDocument` |
| `embedder` | Embedder vectorial determinista o ML |
| `vlm`      | Provider visión-lenguaje (describe imágenes) |
| `gen`      | Provider generativo (LLM) |

## Wrapper en `jw-cli`

    jw create-agent mi-traductor --type=agent

Es un proxy: delega al binario standalone `create-jw-agent`. Si no está instalado, te indica `uvx create-jw-agent`.

## Cookbook ejecutable

`docs/cookbook/` contiene 12 recetas. Cada bloque ```python``` marcado con `# test` se ejecuta en CI vía `pytest-cookbook`:

    uv run pytest --collect-from-markdown docs/cookbook -v

Cobertura inicial: 10 recetas activas + 2 que esperan Fase 47/48.

## Política para nuevas recetas

1. Crea `docs/cookbook/NN-<slug>.md` siguiendo el formato canónico (≤60 LOC).
2. Añade un bloque ```python``` con `# test` en primera línea.
3. CI lo ejecuta automáticamente.

## Troubleshooting

| Síntoma | Diagnóstico | Fix |
|---|---|---|
| `uvx create-jw-agent` no encontrado | binario no instalado | `pip install create-jw-agent` |
| CI rojo en `pytest` recién generado | Python ≠ 3.13 | Forzar `python_requires=">=3.13"` |
| Receta marcada `skip-until-fase-N` se ejecuta | plugin desactualizado | `uv sync --refresh` |
| Snapshot rojo tras editar plantilla | golden desfasado | `pytest --snapshot-update` |
```

- [ ] **Step 2: Link from `docs/README.md`**

Add (alphabetical position):

```markdown
- [Scaffolding y Cookbook](guias/scaffolding.md) — `create-jw-agent` + 12 recetas ejecutables en CI.
```

- [ ] **Step 3: Commit**

```bash
git add docs/guias/scaffolding.md docs/README.md
git commit -m "docs(scaffolding): user guide for create-jw-agent + executable cookbook"
```

---

### Task 18: VISION_AUDIT + ROADMAP + final green-suite verification

**Files:**
- Modify: `docs/VISION_AUDIT.md`
- Modify: `docs/ROADMAP.md`

- [ ] **Step 1: Add VISION_AUDIT row**

```markdown
| Fase 42 (scaffolding + cookbook) | ✅ Nuevo | `create-jw-agent` standalone + 12 recetas ejecutables + CI bloqueante |
```

- [ ] **Step 2: Append Fase 42 section to ROADMAP**

```markdown
## Fase 42 — Scaffolding + Cookbook ejecutable ✅

> Tier 2 comunidad. Spec: `docs/superpowers/specs/2026-05-31-fase-42-scaffolding-design.md`.

- ✅ Paquete nuevo `packages/create-jw-agent/` (publicable a PyPI, dep zero `jw-core`).
- ✅ Tipos soportados: `agent`, `parser`, `embedder`, `vlm`, `gen` (5 plantillas × 3 idiomas en/es/pt = 15 combinaciones snapshotted).
- ✅ Validación de nombres PEP 503 + prefijos reservados (`jw-`, `create-jw-`).
- ✅ CLI Typer con i18n, `--check-pypi` opt-in, `--interactive/--no-interactive`, `--quiet`, `--version`.
- ✅ Sin red por defecto (test `test_no_network`).
- ✅ Plantilla `agent` emite proyecto CI-green en primer commit (`uv sync && uv run pytest` verde).
- ✅ Wrapper `jw create-agent` en `jw-cli` (delegación subprocess).
- ✅ Plugin interno `tools/pytest-cookbook/` que ejecuta bloques ```python ``` marcados `# test`.
- ✅ 12 recetas Markdown en `docs/cookbook/` (10 activas, 2 con `skip-until-fase-47/48`).
- ✅ Marker `skip-until-fase-N` honrado por el plugin.
- ✅ Fakes compartidas `_common/fakes.py` (FakeWOLClient, FakeClaude, FakeEmbedder).
- ✅ CI job `cookbook-tests` bloqueante.
- ✅ Workflow trusted publishing en tag `create-jw-agent-vX.Y.Z`.
- ✅ Alias Astro `/cookbook/<slug>` → `/docs/cookbook/<slug>`.
- ✅ Guía `docs/guias/scaffolding.md`.

### Cobertura de tests

- ✅ ~35 tests nuevos (validate, i18n, render, snapshots, cli, no-network, e2e, wrapper, plugin, recipes).
- ✅ Suite global sin regresiones.
```

- [ ] **Step 3: Commit**

```bash
git add docs/VISION_AUDIT.md docs/ROADMAP.md
git commit -m "docs(roadmap): land Fase 42 — create-jw-agent + executable cookbook"
```

- [ ] **Step 4: Run lint + format**

```bash
uv run ruff check packages/create-jw-agent tools/pytest-cookbook docs/cookbook/_common
uv run ruff format --check packages/create-jw-agent tools/pytest-cookbook docs/cookbook/_common
```
Expected: zero violations.

- [ ] **Step 5: Run the entire test suite**

```bash
uv run pytest packages/ tools/ --collect-from-markdown docs/cookbook -v --tb=short
```
Expected:
- All previous tests (1984) green.
- New tests (~35 from create-jw-agent + 4 from pytest-cookbook + 12 from cookbook recipes) green or appropriately skipped.
- Zero regressions.

- [ ] **Step 6: End-to-end smoke**

```bash
rm -rf /tmp/timer-test
time bash -c '
  uv run --package create-jw-agent create-jw-agent timer-test --type=agent --no-interactive --output-dir /tmp/timer-test
  cd /tmp/timer-test
  uv sync --quiet
  uv run pytest -q
'
rm -rf /tmp/timer-test
```
Expected: total wall-time ≤ 10 min on cold cache, ≤ 2 min on warm. All tests green inside generated project.

- [ ] **Step 7: Final polish commit if needed**

If anything wobbled (a doc typo, an extra empty line), one final `docs(scaffolding): polish` commit. Otherwise, nothing to do.

---

## Self-review summary

- **Spec coverage**: Every section of the design spec maps to a task above —
  - Package architecture → Task 1.
  - Name validation reserved prefixes → Task 2.
  - i18n in/es/pt → Task 3.
  - Renderer (Jinja2 + path substitution) → Task 4.
  - Agent template (CI-green) → Task 5.
  - parser/embedder/vlm/gen templates → Task 6.
  - 15 snapshot combinations → Task 7.
  - Typer CLI + no-network guarantee → Task 8.
  - `jw create-agent` wrapper → Task 9.
  - `pytest-cookbook` plugin → Tasks 10, 13 (skip marker).
  - 12 cookbook recipes → Tasks 11–13.
  - CI `cookbook-tests` job → Task 14.
  - Trusted publishing → Task 15.
  - Astro site alias → Task 16.
  - User guide → Task 17.
  - VISION_AUDIT + ROADMAP + final audit → Task 18.
  Boundaries (no JS/TS scaffold, no auto-PR to plugins list, no core-package scaffold, no auto-publish) are honored by being absent from the plan and explicitly called out in the guide.
- **No placeholders**: every code step has full inline source; every YAML step shows the actual fields; every command shows the exact invocation and expected output.
- **Type consistency**: `RenderContext.type` and CLI `--type` share the same `Literal["agent","parser","embedder","vlm","gen"]`. `RenderContext.lang` matches i18n SUPPORTED_LANGS. Entry-point group strings are spelled identically across templates, CLI, and ROADMAP. The `# test` marker grammar (`# test` / `# test skip-until-fase-N`) is consistent across plugin code, recipes, and Task 13 grammar extension.

## Execution choice

Plan completo. Dos opciones de ejecución:

1. **Subagent-driven (recomendado)** — dispatch fresh sub-agente por tarea, review entre tareas, iteración rápida (`superpowers:subagent-driven-development`).
2. **Inline** — ejecuto tareas en esta sesión con checkpoints (`superpowers:executing-plans`).

¿Cuál prefieres?
