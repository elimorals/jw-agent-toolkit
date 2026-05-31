# Fase 38 — `jw-gen` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `jw-gen`, the seventh workspace package, a generative-content toolkit (image / audio / video) for personal illustrative use in JW-context presentations. The package is *policy-first*: every output that touches disk passes through fail-closed watermark + EXIF/XMP metadata + sibling disclaimer, and every prompt is screened by three non-negotiable safety filters **before** any provider call is made.

**Architecture:** New monorepo package `packages/jw-gen/`. Strictly isolated — imports only `jw-core` for shared types (languages, paths). Provider adapters (image/audio/video) implement a common `GenerationProvider` Protocol; each has a deterministic `Fake*Provider` sibling so the entire test suite runs **offline**. Policy and safety modules are LOAD-BEARING — see "Policy and safety boundaries" in the spec — and are exercised by property tests with 100 adversarial prompts.

**Tech Stack:** Python 3.13 · Pydantic 2 (models) · pytest + Hypothesis (TDD + property tests) · Pillow (watermark rasterization) · piexif (EXIF embed) · python-xmp-toolkit (XMP embed, optional with fallback) · Typer (CLI) · FastMCP (MCP tool). Provider SDKs (`google-genai`, `elevenlabs`, `runwayml`, `replicate`, `recraft-ai`, `ideogram`, `anthropic`, `openai`) live in optional extras `[image]`, `[audio]`, `[video]`, `[all]` — never hard deps.

**Spec:** [`docs/superpowers/specs/2026-05-31-fase-38-jw-gen-design.md`](../specs/2026-05-31-fase-38-jw-gen-design.md).

**Approved policy (LOAD-BEARING quote, do not weaken in code review):**

> "Solo personal/ilustrativo + presentaciones/discursos. Watermark obligatorio. NO emulación contenido oficial JW."

---

## File map

Creates:
- `packages/jw-gen/pyproject.toml`
- `packages/jw-gen/README.md`
- `packages/jw-gen/src/jw_gen/__init__.py`
- `packages/jw-gen/src/jw_gen/models.py`
- `packages/jw-gen/src/jw_gen/i18n.py`
- `packages/jw-gen/src/jw_gen/i18n/en.json`
- `packages/jw-gen/src/jw_gen/i18n/es.json`
- `packages/jw-gen/src/jw_gen/i18n/pt.json`
- `packages/jw-gen/src/jw_gen/policy.py`
- `packages/jw-gen/src/jw_gen/safety.py`
- `packages/jw-gen/src/jw_gen/audit.py`
- `packages/jw-gen/src/jw_gen/factory.py`
- `packages/jw-gen/src/jw_gen/providers/__init__.py`
- `packages/jw-gen/src/jw_gen/providers/base.py`
- `packages/jw-gen/src/jw_gen/providers/fakes.py`
- `packages/jw-gen/src/jw_gen/providers/image/__init__.py`
- `packages/jw-gen/src/jw_gen/providers/image/nanobanana.py`
- `packages/jw-gen/src/jw_gen/providers/audio/__init__.py`
- `packages/jw-gen/src/jw_gen/providers/audio/elevenlabs.py`
- `packages/jw-gen/src/jw_gen/providers/video/__init__.py`
- `packages/jw-gen/src/jw_gen/providers/video/veo3.py`
- `packages/jw-gen/src/jw_gen/cli.py`
- `packages/jw-gen/src/jw_gen/prompts/slide_template.md`
- `packages/jw-gen/src/jw_gen/prompts/illustration_template.md`
- `packages/jw-gen/src/jw_gen/prompts/bg_audio_template.md`
- `packages/jw-gen/tests/__init__.py`
- `packages/jw-gen/tests/conftest.py`
- `packages/jw-gen/tests/test_models.py`
- `packages/jw-gen/tests/test_i18n.py`
- `packages/jw-gen/tests/test_policy.py`
- `packages/jw-gen/tests/test_safety.py`
- `packages/jw-gen/tests/test_safety_property.py`
- `packages/jw-gen/tests/test_audit.py`
- `packages/jw-gen/tests/test_providers_fake.py`
- `packages/jw-gen/tests/test_factory.py`
- `packages/jw-gen/tests/test_cli.py`
- `packages/jw-gen/tests/test_mcp_tool.py`
- `packages/jw-gen/tests/fixtures/sample.png`
- `packages/jw-gen/tests/fixtures/sample.wav`
- `packages/jw-gen/tests/fixtures/signed_consent.txt`
- `packages/jw-cli/src/jw_cli/commands/gen.py`
- `docs/guias/generacion-ilustrativa.md`

Modifies:
- `pyproject.toml` (root) — add `packages/jw-gen` to workspace members + `jw-gen` source + testpaths entry.
- `packages/jw-cli/pyproject.toml` — add `jw-gen` dependency.
- `packages/jw-cli/src/jw_cli/main.py` — register `gen` subcommand via `app.add_typer`.
- `packages/jw-mcp/pyproject.toml` — add `jw-gen` dependency.
- `packages/jw-mcp/src/jw_mcp/server.py` — register `generate_illustration` MCP tool.
- `.github/workflows/ci.yml` — add `gen-policy` job (offline, property-test).
- `docs/VISION_AUDIT.md` — add Fase 38 row, quoting approved policy verbatim.
- `docs/ROADMAP.md` — add Fase 38 section.

---

### Task 1: Scaffold `jw-gen` package and register in workspace

**Files:**
- Create: `packages/jw-gen/pyproject.toml`
- Create: `packages/jw-gen/README.md`
- Create: `packages/jw-gen/src/jw_gen/__init__.py`
- Modify: `pyproject.toml` (root)

- [ ] **Step 1: Create the package pyproject.toml**

```toml
# packages/jw-gen/pyproject.toml
[project]
name = "jw-gen"
version = "0.1.0"
description = "Generative-content toolkit for personal illustrative use (image / audio / video) with policy-first watermark + safety filters"
readme = "README.md"
requires-python = ">=3.13"
license = "GPL-3.0-only"
dependencies = [
    "jw-core",
    "pydantic>=2.5.0",
    "typer>=0.12.0",
    "pillow>=10.3.0",
    "piexif>=1.1.3",
]

[project.optional-dependencies]
xmp = [
    # python-xmp-toolkit needs exempi C lib; optional. policy.py falls back to
    # writing XMP as inline UTF-8 packet inside the file if this is missing.
    "python-xmp-toolkit>=2.0.2",
]
image = [
    "google-genai>=1.0.0",
    "replicate>=0.34.0",
    "recraft-ai>=0.1.0",
    "ideogram>=0.1.0",
]
audio = [
    "elevenlabs>=1.0.0",
    "replicate>=0.34.0",
]
video = [
    "google-genai>=1.0.0",
    "replicate>=0.34.0",
    "runwayml>=2.0.0",
]
all = [
    "google-genai>=1.0.0",
    "replicate>=0.34.0",
    "recraft-ai>=0.1.0",
    "ideogram>=0.1.0",
    "elevenlabs>=1.0.0",
    "runwayml>=2.0.0",
    "python-xmp-toolkit>=2.0.2",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/jw_gen"]

[tool.hatch.build.targets.wheel.force-include]
"src/jw_gen/i18n/en.json" = "jw_gen/i18n/en.json"
"src/jw_gen/i18n/es.json" = "jw_gen/i18n/es.json"
"src/jw_gen/i18n/pt.json" = "jw_gen/i18n/pt.json"
"src/jw_gen/prompts/slide_template.md" = "jw_gen/prompts/slide_template.md"
"src/jw_gen/prompts/illustration_template.md" = "jw_gen/prompts/illustration_template.md"
"src/jw_gen/prompts/bg_audio_template.md" = "jw_gen/prompts/bg_audio_template.md"
```

- [ ] **Step 2: Create the README**

```markdown
# jw-gen

Generative-content toolkit (image / audio / video) for **personal illustrative** use in
JW-context presentations and personal talks.

**Approved policy (load-bearing):**
> Solo personal/ilustrativo + presentaciones/discursos. Watermark obligatorio.
> NO emulación contenido oficial JW.

Every file written to disk receives:
- Visible watermark (Pillow rasterization).
- EXIF + XMP metadata identifying the file as `jw-gen` output with prompt hash + provider.
- Sibling `*.disclaimer.txt` in en / es / pt explaining personal-use scope.

Three non-negotiable safety filters run **before** any provider call:
- `refuse_jw_logo_emulation` — hard refuse, no opt-in.
- `refuse_voice_cloning_without_double_optin` — flag + signed consent file + interactive confirm.
- `refuse_realistic_faces_without_optin` — default stylized, `--realistic-people` to opt in.

Run: `jw gen image --prompt "..." --out out.png`.
Spec: `docs/superpowers/specs/2026-05-31-fase-38-jw-gen-design.md`.
```

- [ ] **Step 3: Create empty package init**

```python
# packages/jw-gen/src/jw_gen/__init__.py
"""jw-gen — generative-content toolkit for personal illustrative use.

Public API:
    from jw_gen import (
        GenerationRequest,
        GenerationResult,
        WatermarkConfig,
        SafetyDecision,
        get_provider,
        finalize_output,
    )

The policy is LOAD-BEARING. Every output that touches disk MUST pass through
`policy.finalize_output(...)`. Every prompt MUST pass through `safety.evaluate(...)`
before reaching `factory.get_provider(...).generate(...)`.
"""

from jw_gen.factory import get_provider
from jw_gen.models import (
    CostHint,
    GenerationRequest,
    GenerationResult,
    SafetyDecision,
    WatermarkConfig,
)
from jw_gen.policy import finalize_output

__all__ = [
    "CostHint",
    "GenerationRequest",
    "GenerationResult",
    "SafetyDecision",
    "WatermarkConfig",
    "finalize_output",
    "get_provider",
]
```

- [ ] **Step 4: Register in workspace**

Edit `pyproject.toml` (root):

```toml
[tool.uv.workspace]
members = [
    "packages/jw-core",
    "packages/jw-cli",
    "packages/jw-mcp",
    "packages/jw-rag",
    "packages/jw-agents",
    "packages/jw-finetune",
    "packages/jw-eval",
    "packages/jw-gen",
]

[tool.uv.sources]
jw-core = { workspace = true }
jw-cli = { workspace = true }
jw-mcp = { workspace = true }
jw-rag = { workspace = true }
jw-agents = { workspace = true }
jw-finetune = { workspace = true }
jw-eval = { workspace = true }
jw-gen = { workspace = true }
```

And append `"packages/jw-gen/tests"` to `[tool.pytest.ini_options].testpaths`.

- [ ] **Step 5: Verify install**

Run: `uv sync --all-packages`
Expected: clean install. `uv pip list | grep jw-gen` shows `jw-gen 0.1.0`.

- [ ] **Step 6: Commit**

```bash
git add packages/jw-gen pyproject.toml uv.lock
git commit -m "feat(jw-gen): scaffold seventh workspace package"
```

---

### Task 2: Pydantic models

**Files:**
- Create: `packages/jw-gen/src/jw_gen/models.py`
- Create: `packages/jw-gen/tests/__init__.py`
- Create: `packages/jw-gen/tests/conftest.py`
- Create: `packages/jw-gen/tests/test_models.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-gen/tests/test_models.py
"""Tests for jw_gen.models."""

from __future__ import annotations

from pathlib import Path

import pytest

from jw_gen.models import (
    CostHint,
    GenerationRequest,
    GenerationResult,
    Language,
    SafetyDecision,
    WatermarkConfig,
)


def test_watermark_config_defaults_to_visible_plus_metadata() -> None:
    cfg = WatermarkConfig()
    assert cfg.mode == "visible+metadata"
    assert cfg.opacity == 0.4
    assert cfg.text_template_key == "watermark.default"


def test_watermark_config_rejects_unknown_mode() -> None:
    with pytest.raises(ValueError):
        WatermarkConfig(mode="invisible-supersecret")  # type: ignore[arg-type]


def test_generation_request_normalizes_lang_lowercase() -> None:
    req = GenerationRequest(prompt="a", kind="image", lang="ES")
    assert req.lang == "es"


def test_generation_request_rejects_unknown_kind() -> None:
    with pytest.raises(ValueError):
        GenerationRequest(prompt="a", kind="hologram", lang="en")  # type: ignore[arg-type]


def test_generation_request_lang_default_is_es() -> None:
    req = GenerationRequest(prompt="hola", kind="image")
    assert req.lang == "es"


def test_safety_decision_pass_has_no_reason() -> None:
    d = SafetyDecision(allow=True, augmented_prompt=None, audit_flags={})
    assert d.allow is True
    assert d.reason is None


def test_safety_decision_refuse_carries_i18n_key() -> None:
    d = SafetyDecision(allow=False, reason="safety.refuse.logo", audit_flags={"logo_check": "fail"})
    assert d.allow is False
    assert d.reason == "safety.refuse.logo"


def test_generation_result_path_field_populated(tmp_path: Path) -> None:
    out = tmp_path / "x.png"
    out.write_bytes(b"x")
    result = GenerationResult(
        output_path=out,
        disclaimer_path=tmp_path / "x.png.disclaimer.txt",
        provider="fake",
        kind="image",
        watermark_mode="visible+metadata",
        prompt_sha256="abc",
        audit_id="evt-1",
    )
    assert result.output_path == out


def test_cost_hint_defaults_to_zero() -> None:
    c = CostHint()
    assert c.usd == 0.0
    assert c.time_s == 0.0


def test_language_literal_values() -> None:
    # Compile-time only; runtime check just confirms the alias is importable.
    _: Language = "es"
    _ = "en"  # type: ignore[assignment]
    _ = "pt"  # type: ignore[assignment]
```

- [ ] **Step 2: Add the shared conftest**

```python
# packages/jw-gen/tests/conftest.py
"""Shared fixtures for jw-gen tests.

The eval suite never hits a real provider or the network. The `fake_audit_log`
fixture redirects `~/.jw-gen/audit.log` into a per-test temp directory so
parallel tests don't collide.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest


@pytest.fixture
def isolated_jw_gen_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point JW_GEN_HOME at an isolated tmp dir so audit.log + private/ don't leak."""

    home = tmp_path / ".jw-gen"
    home.mkdir()
    monkeypatch.setenv("JW_GEN_HOME", str(home))
    return home


@pytest.fixture
def sample_png_bytes() -> bytes:
    """Smallest possible valid PNG (1x1 transparent)."""

    return bytes.fromhex(
        "89504E470D0A1A0A0000000D49484452000000010000000108060000001F15C489"
        "0000000D49444154789C636060000000040001274BE8410000000049454E44AE426082"
    )


@pytest.fixture
def fixtures_dir() -> Path:
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def no_network(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Hard-fail any attempt at HTTP egress during a test."""

    def _refuse(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("network access blocked in tests")

    # Block both httpx and requests at the socket level.
    import socket

    real_connect = socket.socket.connect

    def fake_connect(self: socket.socket, addr: object) -> None:  # noqa: ANN401
        if isinstance(addr, tuple) and addr[0] in {"127.0.0.1", "localhost"}:
            return real_connect(self, addr)
        _refuse()

    monkeypatch.setattr(socket.socket, "connect", fake_connect)
    yield
```

- [ ] **Step 3: Add empty test package init**

```python
# packages/jw-gen/tests/__init__.py
```

- [ ] **Step 4: Run test to verify it fails**

Run: `uv run pytest packages/jw-gen/tests/test_models.py -v`
Expected: FAIL — module `jw_gen.models` missing.

- [ ] **Step 5: Implement models**

```python
# packages/jw-gen/src/jw_gen/models.py
"""Pydantic models for jw-gen.

Public types:
    Language                 — Literal["en", "es", "pt"]
    Kind                     — Literal["image", "audio", "video"]
    Target                   — Literal["api", "nvidia", "mlx", "cpu"]
    WatermarkConfig          — controls visible + metadata behavior
    GenerationRequest        — input to providers and policy
    GenerationResult         — what callers see after finalize_output
    SafetyDecision           — output of safety.evaluate
    CostHint                 — provider-supplied price + time estimate

Design notes
------------
* `WatermarkConfig.mode` defaults to "visible+metadata". The only ways to
  weaken it are via explicit CLI `--no-visible-watermark` (drops to
  "metadata-only" and logs to audit) or `--no-watermark` (drops to "off",
  forbidden over MCP entirely).
* `GenerationRequest.lang` is lowercase-normalized — provider templates
  and i18n lookups assume lower case.
* `SafetyDecision.augmented_prompt` is what the safety layer would prefer
  the provider see (e.g. anti-realism suffix appended). When `allow=False`
  the caller MUST short-circuit without invoking the provider.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator

Language = Literal["en", "es", "pt"]
Kind = Literal["image", "audio", "video"]
Target = Literal["api", "nvidia", "mlx", "cpu"]
WatermarkMode = Literal["visible+metadata", "metadata-only", "off"]


class WatermarkConfig(BaseModel):
    """Watermark policy carried per-request."""

    mode: WatermarkMode = "visible+metadata"
    opacity: float = Field(default=0.4, ge=0.0, le=1.0)
    text_template_key: str = "watermark.default"
    # Pixel anchor: ratio of width/height from top-left.
    anchor_x: float = Field(default=0.02, ge=0.0, le=1.0)
    anchor_y: float = Field(default=0.93, ge=0.0, le=1.0)


class GenerationRequest(BaseModel):
    """One generation request, before safety + provider routing."""

    prompt: str
    kind: Kind
    lang: Language = "es"
    size: str | None = None  # e.g. "1024x1024" for image, "30s" for audio
    duration_s: float | None = None
    style: str | None = None  # e.g. "illustration", "painterly"
    voice_clone_source: Path | None = None  # if --voice-clone was passed
    realistic_people_optin: bool = False
    watermark: WatermarkConfig = Field(default_factory=WatermarkConfig)
    extra: dict[str, object] = Field(default_factory=dict)

    @field_validator("lang", mode="before")
    @classmethod
    def _lower(cls, v: object) -> object:
        if isinstance(v, str):
            return v.lower()
        return v


class GenerationResult(BaseModel):
    """What callers receive after `policy.finalize_output(...)` succeeds."""

    output_path: Path
    disclaimer_path: Path
    provider: str
    kind: Kind
    watermark_mode: WatermarkMode
    prompt_sha256: str
    audit_id: str
    warnings: list[str] = Field(default_factory=list)


class SafetyDecision(BaseModel):
    """Outcome of `safety.evaluate(...)`."""

    allow: bool
    augmented_prompt: str | None = None
    reason: str | None = None  # i18n key when allow=False
    audit_flags: dict[str, str] = Field(default_factory=dict)


class CostHint(BaseModel):
    """Cost + time estimate from a provider before generation runs."""

    usd: float = 0.0
    time_s: float = 0.0
    notes: str | None = None
```

- [ ] **Step 6: Run test to verify it passes**

Run: `uv run pytest packages/jw-gen/tests/test_models.py -v`
Expected: 10 passed.

- [ ] **Step 7: Commit**

```bash
git add packages/jw-gen/src/jw_gen/models.py packages/jw-gen/tests
git commit -m "feat(jw-gen): WatermarkConfig + GenerationRequest/Result + SafetyDecision models"
```

---

### Task 3: i18n bootstrap (en / es / pt)

**Files:**
- Create: `packages/jw-gen/src/jw_gen/i18n.py`
- Create: `packages/jw-gen/src/jw_gen/i18n/en.json`
- Create: `packages/jw-gen/src/jw_gen/i18n/es.json`
- Create: `packages/jw-gen/src/jw_gen/i18n/pt.json`
- Create: `packages/jw-gen/tests/test_i18n.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-gen/tests/test_i18n.py
from __future__ import annotations

import pytest

from jw_gen.i18n import REQUIRED_KEYS, get_message, list_logo_keywords, realism_suffix


@pytest.mark.parametrize("lang", ["en", "es", "pt"])
def test_all_languages_carry_required_keys(lang: str) -> None:
    for key in REQUIRED_KEYS:
        msg = get_message(key, lang=lang)  # type: ignore[arg-type]
        assert msg, f"{lang}: missing key {key}"


@pytest.mark.parametrize("lang", ["en", "es", "pt"])
def test_realism_suffix_localized(lang: str) -> None:
    suffix = realism_suffix(lang)  # type: ignore[arg-type]
    assert "fotorrealista" in suffix or "photorealistic" in suffix or "não fotorrealista" in suffix or "fotorrealístico" in suffix


@pytest.mark.parametrize("lang", ["en", "es", "pt"])
def test_logo_keywords_nonempty(lang: str) -> None:
    kws = list_logo_keywords(lang)  # type: ignore[arg-type]
    assert len(kws) >= 5
    for kw in kws:
        assert kw == kw.lower(), f"keyword not lowercased: {kw}"


def test_get_message_unknown_key_raises() -> None:
    with pytest.raises(KeyError):
        get_message("does.not.exist", lang="es")
```

- [ ] **Step 2: Create the JSON catalogs (excerpted)**

```json
// packages/jw-gen/src/jw_gen/i18n/es.json
{
  "watermark.default": "jw-gen · uso personal · no es contenido oficial JW",
  "disclaimer.body": "Este archivo fue generado por jw-gen para uso personal/ilustrativo (presentaciones y discursos privados). NO es contenido oficial de Jehovah's Witnesses ni de jw.org. No distribuir como si lo fuera. Prompt hash: {prompt_sha256}. Provider: {provider}. Modo de marca: {watermark_mode}.",
  "disclaimer.realistic_people_warning": "Este archivo contiene rostros realistas generados con opt-in explícito (--realistic-people). No representa a personas reales sin su consentimiento.",
  "safety.refuse.logo": "Solicitud rechazada: prompts que emulan logos, emblemas o identidad gráfica oficial de Watchtower / Awake! / jw.org / Kingdom Hall están prohibidos.",
  "safety.refuse.voice_clone_no_consent": "Voice clone requiere flag --voice-clone, archivo de consentimiento firmado hermano y confirmación interactiva.",
  "safety.confirm.voice_clone": "¿Confirmas que {owner} aprobó este uso? [si/no]: ",
  "safety.realism_suffix": " en estilo ilustrado, pintura suave, no fotorrealista",
  "cli.cost_confirm": "Esta generación tiene un coste estimado de ${usd:.2f}. ¿Continuar? [si/no]: ",
  "logo_keywords": [
    "logo de la atalaya",
    "logotipo jw",
    "portada de despertad",
    "letrero oficial salon del reino",
    "emblema oficial jw",
    "identidad grafica jw.org",
    "logotipo cuerpo gobernante",
    "logo de la sentinela",
    "logo betel"
  ]
}
```

```json
// packages/jw-gen/src/jw_gen/i18n/en.json
{
  "watermark.default": "jw-gen · personal use · NOT official JW content",
  "disclaimer.body": "This file was generated by jw-gen for personal/illustrative use (private talks and presentations). It is NOT official content of Jehovah's Witnesses or jw.org. Do not redistribute as such. Prompt hash: {prompt_sha256}. Provider: {provider}. Watermark mode: {watermark_mode}.",
  "disclaimer.realistic_people_warning": "This file contains realistic faces generated with explicit opt-in (--realistic-people). It does not represent real people without their consent.",
  "safety.refuse.logo": "Request refused: prompts emulating Watchtower / Awake! / jw.org / Kingdom Hall official logos, emblems or graphic identity are prohibited.",
  "safety.refuse.voice_clone_no_consent": "Voice clone requires --voice-clone flag, signed sibling consent file, and interactive confirmation.",
  "safety.confirm.voice_clone": "Do you confirm that {owner} approved this use? [yes/no]: ",
  "safety.realism_suffix": " in illustrated style, soft painting, not photorealistic",
  "cli.cost_confirm": "This generation has an estimated cost of ${usd:.2f}. Continue? [yes/no]: ",
  "logo_keywords": [
    "watchtower logo",
    "jw.org logo",
    "awake magazine cover",
    "kingdom hall sign",
    "official jw emblem",
    "governing body logo",
    "bethel branch logo",
    "watchtower emblem",
    "jw graphic identity"
  ]
}
```

```json
// packages/jw-gen/src/jw_gen/i18n/pt.json
{
  "watermark.default": "jw-gen · uso pessoal · NÃO é conteúdo oficial JW",
  "disclaimer.body": "Este arquivo foi gerado por jw-gen para uso pessoal/ilustrativo (apresentações e discursos privados). NÃO é conteúdo oficial das Testemunhas de Jeová nem do jw.org. Não distribua como se fosse. Hash do prompt: {prompt_sha256}. Provider: {provider}. Modo de marca: {watermark_mode}.",
  "disclaimer.realistic_people_warning": "Este arquivo contém rostos realistas gerados com opt-in explícito (--realistic-people). Não representa pessoas reais sem o consentimento delas.",
  "safety.refuse.logo": "Solicitação recusada: prompts que emulam logotipos, emblemas ou identidade gráfica oficial de Sentinela / Despertai! / jw.org / Salão do Reino estão proibidos.",
  "safety.refuse.voice_clone_no_consent": "Voice clone requer flag --voice-clone, arquivo de consentimento assinado e confirmação interativa.",
  "safety.confirm.voice_clone": "Você confirma que {owner} aprovou este uso? [sim/não]: ",
  "safety.realism_suffix": " em estilo ilustrado, pintura suave, não fotorrealista",
  "cli.cost_confirm": "Esta geração tem custo estimado de ${usd:.2f}. Continuar? [sim/não]: ",
  "logo_keywords": [
    "logo da sentinela",
    "logotipo jw",
    "capa de despertai",
    "placa oficial salao do reino",
    "emblema oficial jw",
    "logotipo corpo governante",
    "identidade grafica jw.org",
    "logo betel",
    "emblema oficial watchtower"
  ]
}
```

- [ ] **Step 3: Implement loader module**

```python
# packages/jw-gen/src/jw_gen/i18n.py
"""i18n catalogs for jw-gen.

All disclaimers, error messages, prompt suffixes, and logo-emulation keyword
blocklists live in three JSON files: en.json, es.json, pt.json. The keys
listed in REQUIRED_KEYS MUST exist in every catalog — `test_i18n.py`
enforces this.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

Language = Literal["en", "es", "pt"]

REQUIRED_KEYS = (
    "watermark.default",
    "disclaimer.body",
    "disclaimer.realistic_people_warning",
    "safety.refuse.logo",
    "safety.refuse.voice_clone_no_consent",
    "safety.confirm.voice_clone",
    "safety.realism_suffix",
    "cli.cost_confirm",
)


@lru_cache(maxsize=8)
def _catalog(lang: Language) -> dict[str, Any]:
    path = Path(__file__).parent / "i18n" / f"{lang}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def get_message(key: str, lang: Language = "es", **fmt: object) -> str:
    cat = _catalog(lang)
    if key not in cat:
        raise KeyError(f"i18n: missing key {key!r} in {lang}")
    value = cat[key]
    if isinstance(value, str) and fmt:
        return value.format(**fmt)
    return str(value)


def realism_suffix(lang: Language) -> str:
    return get_message("safety.realism_suffix", lang=lang)


def list_logo_keywords(lang: Language) -> list[str]:
    cat = _catalog(lang)
    raw = cat.get("logo_keywords", [])
    return [str(k).lower() for k in raw]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/jw-gen/tests/test_i18n.py -v`
Expected: 10 passed (3 langs × 3 parametrized tests + 1 unknown-key).

- [ ] **Step 5: Commit**

```bash
git add packages/jw-gen/src/jw_gen/i18n.py packages/jw-gen/src/jw_gen/i18n packages/jw-gen/tests/test_i18n.py
git commit -m "feat(jw-gen): i18n catalogs (en/es/pt) with logo-block keywords + disclaimer templates"
```

---

### Task 4: Audit log (JSONL append-only)

**Files:**
- Create: `packages/jw-gen/src/jw_gen/audit.py`
- Create: `packages/jw-gen/tests/test_audit.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-gen/tests/test_audit.py
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from jw_gen.audit import audit_log_path, log_generation, rotate_log


def test_log_generation_appends_jsonl(isolated_jw_gen_home: Path) -> None:
    event = log_generation(
        kind="image",
        provider="fake",
        prompt_sha256="abc123",
        output_path=isolated_jw_gen_home / "out.png",
        watermark_mode="visible+metadata",
        safety_flags={"logo_check": "pass"},
        warnings=[],
    )
    path = audit_log_path()
    raw = path.read_text(encoding="utf-8").strip().splitlines()
    assert len(raw) == 1
    row = json.loads(raw[0])
    assert row["audit_id"] == event["audit_id"]
    assert row["prompt_sha256"] == "abc123"
    assert "prompt" not in row, "audit log must never contain the prompt in plaintext"


def test_log_generation_two_events_distinct_ids(isolated_jw_gen_home: Path) -> None:
    e1 = log_generation(
        kind="image", provider="fake", prompt_sha256="a", output_path=isolated_jw_gen_home / "x.png",
        watermark_mode="visible+metadata", safety_flags={}, warnings=[],
    )
    e2 = log_generation(
        kind="image", provider="fake", prompt_sha256="b", output_path=isolated_jw_gen_home / "y.png",
        watermark_mode="visible+metadata", safety_flags={}, warnings=[],
    )
    assert e1["audit_id"] != e2["audit_id"]


def test_log_generation_timestamp_is_utc(isolated_jw_gen_home: Path) -> None:
    event = log_generation(
        kind="image", provider="fake", prompt_sha256="z", output_path=isolated_jw_gen_home / "z.png",
        watermark_mode="visible+metadata", safety_flags={}, warnings=[],
        now=lambda: datetime(2026, 5, 31, 14, 0, tzinfo=timezone.utc),
    )
    assert event["timestamp"].endswith("Z")
    assert "2026-05-31T14:00" in event["timestamp"]


def test_rotate_log_moves_to_dated_gz(isolated_jw_gen_home: Path) -> None:
    log_generation(
        kind="image", provider="fake", prompt_sha256="a", output_path=isolated_jw_gen_home / "x.png",
        watermark_mode="visible+metadata", safety_flags={}, warnings=[],
    )
    target = rotate_log()
    assert target is not None
    assert target.exists()
    assert target.suffix == ".gz"
    assert not audit_log_path().exists() or audit_log_path().read_text() == ""


def test_rotate_log_noop_when_empty(isolated_jw_gen_home: Path) -> None:
    assert rotate_log() is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/jw-gen/tests/test_audit.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement audit**

```python
# packages/jw-gen/src/jw_gen/audit.py
"""Audit log for jw-gen.

JSONL append-only file at $JW_GEN_HOME/audit.log (default ~/.jw-gen/audit.log).
One row per generation. Schema is fixed:

    {
      "audit_id":        "uuid4",
      "timestamp":       "ISO 8601 Z",
      "kind":            "image" | "audio" | "video",
      "provider":        "<name>",
      "prompt_sha256":   "<hex>",
      "output_path":     "<absolute path>",
      "watermark_mode":  "visible+metadata" | "metadata-only" | "off",
      "safety_flags":    {"logo_check": ..., "voice_clone_optin": ..., "realistic_faces_optin": ...},
      "warnings":        ["..."]
    }

The plaintext prompt is NEVER stored. The output content is NEVER stored.
"""

from __future__ import annotations

import gzip
import json
import os
import shutil
import uuid
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path


def _home() -> Path:
    raw = os.environ.get("JW_GEN_HOME")
    if raw:
        return Path(raw)
    return Path.home() / ".jw-gen"


def audit_log_path() -> Path:
    home = _home()
    home.mkdir(parents=True, exist_ok=True)
    return home / "audit.log"


def log_generation(
    *,
    kind: str,
    provider: str,
    prompt_sha256: str,
    output_path: Path,
    watermark_mode: str,
    safety_flags: dict[str, str],
    warnings: list[str],
    now: Callable[[], datetime] | None = None,
) -> dict[str, object]:
    ts_provider = now or (lambda: datetime.now(timezone.utc))
    ts = ts_provider().astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S") + "Z"
    event: dict[str, object] = {
        "audit_id": str(uuid.uuid4()),
        "timestamp": ts,
        "kind": kind,
        "provider": provider,
        "prompt_sha256": prompt_sha256,
        "output_path": str(output_path),
        "watermark_mode": watermark_mode,
        "safety_flags": safety_flags,
        "warnings": warnings,
    }
    path = audit_log_path()
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")
    return event


def rotate_log() -> Path | None:
    """Compress audit.log to audit.log.YYYY-MM.gz and start fresh.

    Returns the rotated path, or None if the log is empty / absent.
    """

    path = audit_log_path()
    if not path.exists() or path.stat().st_size == 0:
        return None
    stamp = datetime.now(timezone.utc).strftime("%Y-%m")
    dest = path.with_suffix(f".log.{stamp}.gz")
    with path.open("rb") as src, gzip.open(dest, "wb") as gz:
        shutil.copyfileobj(src, gz)
    path.write_text("", encoding="utf-8")
    return dest
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/jw-gen/tests/test_audit.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-gen/src/jw_gen/audit.py packages/jw-gen/tests/test_audit.py
git commit -m "feat(jw-gen): JSONL append-only audit log with monthly rotation"
```

---

### Task 5: Safety filters (the three non-negotiable filters)

**Files:**
- Create: `packages/jw-gen/src/jw_gen/safety.py`
- Create: `packages/jw-gen/tests/test_safety.py`
- Create: `packages/jw-gen/tests/fixtures/signed_consent.txt`

- [ ] **Step 1: Write the failing tests**

```python
# packages/jw-gen/tests/test_safety.py
from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from jw_gen.models import GenerationRequest
from jw_gen.safety import (
    SafetyRefused,
    evaluate,
    refuse_jw_logo_emulation,
    refuse_realistic_faces_without_optin,
    refuse_voice_cloning_without_double_optin,
)


@pytest.mark.parametrize("lang,prompt", [
    ("en", "Generate an official watchtower logo"),
    ("en", "Awake magazine cover style emblem"),
    ("es", "Logo de la Atalaya con fondo azul"),
    ("es", "letrero oficial Salón del Reino"),
    ("pt", "capa de Despertai oficial JW"),
    ("pt", "logo da Sentinela"),
])
def test_refuse_jw_logo_emulation_blocks_keywords(lang: str, prompt: str) -> None:
    with pytest.raises(SafetyRefused) as excinfo:
        refuse_jw_logo_emulation(prompt, lang=lang)  # type: ignore[arg-type]
    assert "safety.refuse.logo" in str(excinfo.value.reason)


def test_refuse_jw_logo_emulation_allows_neutral_prompt() -> None:
    refuse_jw_logo_emulation("ilustración de ovejas en una montaña", lang="es")


def test_refuse_jw_logo_emulation_handles_accents_and_case() -> None:
    # Normalization must catch this even with mixed case + accents.
    with pytest.raises(SafetyRefused):
        refuse_jw_logo_emulation("LOGO DE LA ÁTALAYA", lang="es")


def test_refuse_voice_clone_blocks_without_flag(tmp_path: Path) -> None:
    audio = tmp_path / "voice.wav"
    audio.write_bytes(b"fake-wav")
    with pytest.raises(SafetyRefused):
        refuse_voice_cloning_without_double_optin(
            audio_src=audio,
            voice_clone_flag=False,
            interactive_confirm=lambda _q: True,
        )


def test_refuse_voice_clone_blocks_without_consent_file(tmp_path: Path) -> None:
    audio = tmp_path / "voice.wav"
    audio.write_bytes(b"fake-wav")
    with pytest.raises(SafetyRefused):
        refuse_voice_cloning_without_double_optin(
            audio_src=audio,
            voice_clone_flag=True,
            interactive_confirm=lambda _q: True,
        )


def test_refuse_voice_clone_blocks_on_invalid_signature(tmp_path: Path) -> None:
    audio = tmp_path / "voice.wav"
    audio.write_bytes(b"fake-wav")
    consent = audio.with_suffix(".wav.consent.txt")
    consent.write_text(
        "voice_owner: Hermano X\ndate: 2026-05-31\npurpose: test\n"
        "signature_sha256: deadbeef-bad-sig\n",
        encoding="utf-8",
    )
    with pytest.raises(SafetyRefused):
        refuse_voice_cloning_without_double_optin(
            audio_src=audio,
            voice_clone_flag=True,
            interactive_confirm=lambda _q: True,
        )


def _well_signed_consent(audio: Path, owner: str = "Hermano X") -> Path:
    """Write a consent file with a sha256 of the first three lines."""

    header_lines = [
        f"voice_owner: {owner}",
        "date: 2026-05-31",
        "purpose: prueba pre-discurso",
    ]
    header = "\n".join(header_lines) + "\n"
    sig = hashlib.sha256(header.encode("utf-8")).hexdigest()
    consent = audio.with_suffix(audio.suffix + ".consent.txt")
    consent.write_text(header + f"signature_sha256: {sig}\n", encoding="utf-8")
    return consent


def test_refuse_voice_clone_passes_with_full_optin(tmp_path: Path) -> None:
    audio = tmp_path / "voice.wav"
    audio.write_bytes(b"fake-wav")
    _well_signed_consent(audio)
    owner = refuse_voice_cloning_without_double_optin(
        audio_src=audio,
        voice_clone_flag=True,
        interactive_confirm=lambda _q: True,
    )
    assert owner == "Hermano X"


def test_refuse_voice_clone_blocks_when_user_declines_confirm(tmp_path: Path) -> None:
    audio = tmp_path / "voice.wav"
    audio.write_bytes(b"fake-wav")
    _well_signed_consent(audio)
    with pytest.raises(SafetyRefused):
        refuse_voice_cloning_without_double_optin(
            audio_src=audio,
            voice_clone_flag=True,
            interactive_confirm=lambda _q: False,
        )


def test_realistic_faces_default_appends_suffix() -> None:
    augmented = refuse_realistic_faces_without_optin(
        prompt="retrato de un hermano dando un discurso",
        lang="es",
        realistic_optin=False,
    )
    assert augmented.endswith("no fotorrealista")


def test_realistic_faces_no_op_when_no_person_keyword() -> None:
    augmented = refuse_realistic_faces_without_optin(
        prompt="ovejas en una colina al atardecer",
        lang="es",
        realistic_optin=False,
    )
    assert augmented == "ovejas en una colina al atardecer"


def test_realistic_faces_optin_keeps_prompt_intact() -> None:
    augmented = refuse_realistic_faces_without_optin(
        prompt="retrato de un hermano dando un discurso",
        lang="es",
        realistic_optin=True,
    )
    assert augmented == "retrato de un hermano dando un discurso"


def test_evaluate_combines_filters_pass() -> None:
    req = GenerationRequest(
        prompt="ilustración de ovejas pastoreadas",
        kind="image",
        lang="es",
    )
    decision = evaluate(req)
    assert decision.allow is True
    assert decision.audit_flags["logo_check"] == "pass"


def test_evaluate_combines_filters_fail_on_logo() -> None:
    req = GenerationRequest(prompt="logo de la atalaya en azul", kind="image", lang="es")
    decision = evaluate(req)
    assert decision.allow is False
    assert decision.reason == "safety.refuse.logo"
```

- [ ] **Step 2: Add the test fixture (a valid signed consent)**

```text
# packages/jw-gen/tests/fixtures/signed_consent.txt
voice_owner: Hermano Demo
date: 2026-05-31
purpose: ejemplo de archivo de consentimiento (fixture)
signature_sha256: 0000000000000000000000000000000000000000000000000000000000000000
```

(The fixture is illustrative only; the real signature gets computed at test time by `_well_signed_consent` so the test is deterministic.)

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest packages/jw-gen/tests/test_safety.py -v`
Expected: FAIL — module missing.

- [ ] **Step 4: Implement safety**

```python
# packages/jw-gen/src/jw_gen/safety.py
"""Three non-negotiable safety filters that run BEFORE any provider call.

LOAD-BEARING: code review must reject any change that weakens these.

1. `refuse_jw_logo_emulation(prompt, lang)`           — hard refuse, no opt-in.
2. `refuse_voice_cloning_without_double_optin(...)`   — flag + signed file + interactive.
3. `refuse_realistic_faces_without_optin(prompt,...)` — default stylized, --realistic-people opts in.

All matching is done on Unicode-normalized + deaccented + lowercased text so
attempts to bypass via casing or diacritics are caught.

The matching strategy is intentionally *fail-closed*: when ambiguous, refuse.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from collections.abc import Callable
from pathlib import Path
from typing import Literal

from jw_gen.i18n import get_message, list_logo_keywords, realism_suffix
from jw_gen.models import GenerationRequest, Language, SafetyDecision

Lang = Language


class SafetyRefused(Exception):
    """Raised when a safety filter refuses to proceed."""

    def __init__(self, reason_key: str, *, audit_flag: tuple[str, str]) -> None:
        super().__init__(reason_key)
        self.reason = reason_key
        self.audit_flag = audit_flag


# ---------------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------------


def _normalize(s: str) -> str:
    """Lowercase + NFKD + strip diacritics + collapse whitespace."""

    s = s.lower()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"\s+", " ", s).strip()
    return s


# ---------------------------------------------------------------------------
# Filter 1 — JW logo emulation (hard refuse, no opt-in)
# ---------------------------------------------------------------------------


_LOGO_NEIGHBORS = ("logo", "logotipo", "emblem", "emblema", "brand", "marca", "official", "oficial")


def refuse_jw_logo_emulation(prompt: str, lang: Lang = "es") -> None:
    """Block prompts that emulate official JW graphic identity. Fail-closed.

    Strategy:
      1) Normalize prompt + each keyword.
      2) Direct substring match → refuse.
      3) Proximity heuristic: if prompt mentions {watchtower/atalaya/sentinela/jw.org}
         within 3 tokens of one of _LOGO_NEIGHBORS → refuse.
    """

    norm = _normalize(prompt)

    # Direct substring match across all three language keyword lists for safety.
    for catalog_lang in ("en", "es", "pt"):
        for kw in list_logo_keywords(catalog_lang):  # type: ignore[arg-type]
            if _normalize(kw) in norm:
                raise SafetyRefused("safety.refuse.logo", audit_flag=("logo_check", "fail"))

    # Proximity heuristic (multilingual): brand name + neighbor noun within 3 tokens.
    brand_words = {"watchtower", "atalaya", "sentinela", "jw.org", "jw", "kingdom hall", "salao do reino", "salon del reino", "bethel"}
    tokens = norm.split()
    for i, tok in enumerate(tokens):
        # Use overlap with multi-word brand phrases too.
        window_str = " ".join(tokens[max(0, i - 3): i + 4])
        if any(b in window_str for b in brand_words):
            if any(n in window_str for n in _LOGO_NEIGHBORS):
                # Brand word + logo-neighbor noun in same 7-token window → refuse.
                raise SafetyRefused("safety.refuse.logo", audit_flag=("logo_check", "fail"))


# ---------------------------------------------------------------------------
# Filter 2 — Voice cloning without double opt-in
# ---------------------------------------------------------------------------


def _parse_consent_file(path: Path) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            fields[k.strip()] = v.strip()
    return fields


def refuse_voice_cloning_without_double_optin(
    *,
    audio_src: Path,
    voice_clone_flag: bool,
    interactive_confirm: Callable[[str], bool],
    lang: Lang = "es",
    signed_consent_fake_ok: bool = False,
) -> str:
    """Return the owner name if all four gates pass; raise SafetyRefused otherwise.

    Gates:
        1. `voice_clone_flag` must be True (CLI --voice-clone).
        2. `<audio_src>.consent.txt` must exist.
        3. signature_sha256 must equal sha256 of the first three lines.
        4. `interactive_confirm("¿Confirmas...?")` must return True.

    `signed_consent_fake_ok` exists only for FakeAudioProvider tests; it is
    NEVER reachable from CLI or MCP.
    """

    flag_fail = ("voice_clone_optin", "fail")
    flag_ok = ("voice_clone_optin", "pass")

    if signed_consent_fake_ok:
        return "fake-owner"

    if not voice_clone_flag:
        raise SafetyRefused("safety.refuse.voice_clone_no_consent", audit_flag=flag_fail)

    consent_path = audio_src.with_suffix(audio_src.suffix + ".consent.txt")
    if not consent_path.exists():
        raise SafetyRefused("safety.refuse.voice_clone_no_consent", audit_flag=flag_fail)

    fields = _parse_consent_file(consent_path)
    required = {"voice_owner", "date", "purpose", "signature_sha256"}
    if not required.issubset(fields):
        raise SafetyRefused("safety.refuse.voice_clone_no_consent", audit_flag=flag_fail)

    header = (
        f"voice_owner: {fields['voice_owner']}\n"
        f"date: {fields['date']}\n"
        f"purpose: {fields['purpose']}\n"
    )
    expected_sig = hashlib.sha256(header.encode("utf-8")).hexdigest()
    if expected_sig != fields["signature_sha256"]:
        raise SafetyRefused("safety.refuse.voice_clone_no_consent", audit_flag=flag_fail)

    question = get_message("safety.confirm.voice_clone", lang=lang, owner=fields["voice_owner"])
    if not interactive_confirm(question):
        raise SafetyRefused("safety.refuse.voice_clone_no_consent", audit_flag=flag_fail)

    # Side effect: keep audit_flag in scope for evaluate().
    _ = flag_ok
    return fields["voice_owner"]


# ---------------------------------------------------------------------------
# Filter 3 — Realistic faces without opt-in (augmentation, not refusal)
# ---------------------------------------------------------------------------


_PERSON_TOKENS = {
    "es": ("persona", "personas", "hermano", "hermana", "irma", "irmao", "rostro", "rostros", "retrato", "cara", "anciano", "publicador"),
    "en": ("person", "people", "brother", "sister", "portrait", "face", "elder", "publisher"),
    "pt": ("pessoa", "pessoas", "irmao", "irma", "rosto", "rostos", "retrato", "ancião", "publicador"),
}


def _mentions_person(prompt: str, lang: Lang) -> bool:
    norm = _normalize(prompt)
    candidates = _PERSON_TOKENS.get(lang, ()) + _PERSON_TOKENS["en"]
    return any(token in norm.split() or token in norm for token in candidates)


def refuse_realistic_faces_without_optin(
    *,
    prompt: str,
    lang: Lang = "es",
    realistic_optin: bool,
) -> str:
    """Return possibly-augmented prompt. When optin is False AND prompt mentions a
    person, append the localized 'not photorealistic' suffix.
    """

    if realistic_optin:
        return prompt
    if not _mentions_person(prompt, lang):
        return prompt
    suffix = realism_suffix(lang)
    if prompt.rstrip().endswith(suffix.strip()):
        return prompt
    return prompt.rstrip(" .") + suffix


# ---------------------------------------------------------------------------
# Combined entry point
# ---------------------------------------------------------------------------


def evaluate(req: GenerationRequest) -> SafetyDecision:
    """Run all applicable filters. Returns a SafetyDecision."""

    flags: dict[str, str] = {
        "logo_check": "n/a",
        "voice_clone_optin": "n/a",
        "realistic_faces_optin": "n/a",
    }
    try:
        refuse_jw_logo_emulation(req.prompt, lang=req.lang)
        flags["logo_check"] = "pass"
    except SafetyRefused as exc:
        k, v = exc.audit_flag
        flags[k] = v
        return SafetyDecision(allow=False, reason=exc.reason, audit_flags=flags)

    # Voice clone is gated at CLI/MCP layer (needs interactive_confirm callable).
    if req.voice_clone_source is not None:
        flags["voice_clone_optin"] = "pending"

    augmented = refuse_realistic_faces_without_optin(
        prompt=req.prompt, lang=req.lang, realistic_optin=req.realistic_people_optin,
    )
    flags["realistic_faces_optin"] = "optin" if req.realistic_people_optin else "stylized"

    return SafetyDecision(
        allow=True,
        augmented_prompt=augmented if augmented != req.prompt else None,
        audit_flags=flags,
    )
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest packages/jw-gen/tests/test_safety.py -v`
Expected: ~14 passed.

- [ ] **Step 6: Commit**

```bash
git add packages/jw-gen/src/jw_gen/safety.py packages/jw-gen/tests/test_safety.py packages/jw-gen/tests/fixtures
git commit -m "feat(jw-gen): three safety filters (logo / voice-clone / realistic-faces) with i18n keyword block"
```

---

### Task 6: Safety property test (100 adversarial prompts)

**Files:**
- Create: `packages/jw-gen/tests/test_safety_property.py`

- [ ] **Step 1: Write the property test**

```python
# packages/jw-gen/tests/test_safety_property.py
"""Hypothesis property tests: 100+ adversarial prompts → 0 outputs allowed.

This is the CI smoke for the safety surface. Every adversarial prompt MUST
result in SafetyRefused. Generators cover three vectors:

  1. JW brand keywords in en/es/pt, casing + diacritic noise.
  2. Voice-clone scenarios without consent.
  3. (Realistic faces are not refuse — they are augmented — so they're
     covered separately by smoke tests in test_safety.py.)
"""

from __future__ import annotations

import string

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from jw_gen.safety import (
    SafetyRefused,
    refuse_jw_logo_emulation,
)


_BRAND_NOUNS_ES = ["atalaya", "ATALAYA", "Átalaya", "atalayá", "Sentinela", "salón del reino"]
_BRAND_NOUNS_EN = ["watchtower", "Watchtower", "WATCHTOWER", "kingdom hall", "JW.org"]
_BRAND_NOUNS_PT = ["sentinela", "Sentinela", "Despertai", "Salão do Reino"]
_NEIGHBOR_NOUNS = ["logo", "logotipo", "emblema", "emblem", "official", "oficial", "brand", "marca"]


def _noise_chars() -> st.SearchStrategy[str]:
    return st.text(alphabet=string.ascii_letters + " ", min_size=0, max_size=40)


@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
@given(
    brand=st.sampled_from(_BRAND_NOUNS_ES + _BRAND_NOUNS_EN + _BRAND_NOUNS_PT),
    neighbor=st.sampled_from(_NEIGHBOR_NOUNS),
    prefix=_noise_chars(),
    middle=_noise_chars(),
    suffix=_noise_chars(),
)
def test_jw_logo_emulation_rejected_property(
    brand: str, neighbor: str, prefix: str, middle: str, suffix: str
) -> None:
    """Any prompt containing a brand noun within 7 tokens of a logo-neighbor must refuse."""

    prompt = f"{prefix} {brand} {middle} {neighbor} {suffix}".strip()
    try:
        refuse_jw_logo_emulation(prompt, lang="es")
    except SafetyRefused as exc:
        assert exc.reason == "safety.refuse.logo"
        return
    raise AssertionError(f"Prompt slipped through: {prompt!r}")


@settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
@given(
    neutral_prompt=st.sampled_from([
        "ilustración de ovejas en una colina al atardecer",
        "paisaje del jardín del Edén estilo pintura",
        "manos abiertas pidiendo perdón",
        "campo de trigo dorado al amanecer",
        "barco antiguo navegando en mar tranquilo",
    ]),
)
def test_neutral_prompts_allowed(neutral_prompt: str) -> None:
    refuse_jw_logo_emulation(neutral_prompt, lang="es")
```

- [ ] **Step 2: Run test to verify it passes**

Run: `uv run pytest packages/jw-gen/tests/test_safety_property.py -v`
Expected: 2 properties pass with all examples accepted (≥100 adversarial + 5 neutral).

- [ ] **Step 3: Commit**

```bash
git add packages/jw-gen/tests/test_safety_property.py
git commit -m "test(jw-gen): property test — 100 adversarial JW-logo prompts → 0 allowed"
```

---

### Task 7: Policy module (watermark + EXIF/XMP + disclaimer + finalize)

**Files:**
- Create: `packages/jw-gen/src/jw_gen/policy.py`
- Create: `packages/jw-gen/tests/test_policy.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-gen/tests/test_policy.py
from __future__ import annotations

import hashlib
import io
from pathlib import Path

import pytest
from PIL import Image

from jw_gen.models import GenerationRequest, WatermarkConfig
from jw_gen.policy import (
    PolicyError,
    apply_watermark,
    assert_personal_use,
    embed_metadata,
    finalize_output,
    write_disclaimer_sibling,
)


def _make_png(path: Path, w: int = 200, h: int = 200) -> Path:
    img = Image.new("RGB", (w, h), color=(255, 255, 255))
    img.save(path, format="PNG")
    return path


def test_apply_watermark_adds_visible_text(tmp_path: Path) -> None:
    src = _make_png(tmp_path / "raw.png")
    out = apply_watermark(src, text="jw-gen · uso personal", cfg=WatermarkConfig())
    assert out.exists()
    img = Image.open(out)
    # Pixel at the anchor row should no longer be pure white.
    px = img.convert("RGB").getpixel((int(0.05 * img.width), int(0.94 * img.height)))
    assert px != (255, 255, 255)


def test_embed_metadata_writes_exif(tmp_path: Path) -> None:
    src = _make_png(tmp_path / "raw.png")
    embed_metadata(src, fields={
        "Software": "jw-gen",
        "ImageDescription": "personal-use illustration",
        "prompt_sha256": "abc",
        "provider": "fake",
    })
    raw = src.read_bytes()
    assert b"jw-gen" in raw


def test_write_disclaimer_sibling_writes_localized(tmp_path: Path) -> None:
    target = tmp_path / "out.png"
    target.write_bytes(b"x")
    disclaimer = write_disclaimer_sibling(
        target=target,
        lang="es",
        prompt_sha256="abc",
        provider="fake",
        watermark_mode="visible+metadata",
        realistic_optin=False,
    )
    assert disclaimer.exists()
    text = disclaimer.read_text(encoding="utf-8")
    assert "uso personal" in text.lower()
    assert "abc" in text


def test_write_disclaimer_sibling_includes_realism_warning_when_optin(tmp_path: Path) -> None:
    target = tmp_path / "out.png"
    target.write_bytes(b"x")
    disclaimer = write_disclaimer_sibling(
        target=target,
        lang="en",
        prompt_sha256="def",
        provider="fake",
        watermark_mode="visible+metadata",
        realistic_optin=True,
    )
    text = disclaimer.read_text(encoding="utf-8")
    assert "realistic" in text.lower()


def test_assert_personal_use_allows_jw_gen_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JW_GEN_HOME", str(tmp_path / ".jw-gen"))
    assert_personal_use(tmp_path / ".jw-gen" / "out.png")


def test_assert_personal_use_warns_on_dropbox_path(tmp_path: Path) -> None:
    warning = assert_personal_use(tmp_path / "Dropbox" / "out.png")
    assert warning is not None
    assert "dropbox" in warning.lower()


def test_finalize_output_complete_path(tmp_path: Path, isolated_jw_gen_home: Path) -> None:
    raw = _make_png(tmp_path / "raw.png")
    req = GenerationRequest(prompt="ilustración pacífica", kind="image", lang="es")
    result = finalize_output(
        raw_path=raw,
        request=req,
        dest=tmp_path / "out.png",
        provider="fake",
    )
    assert result.output_path.exists()
    assert result.disclaimer_path.exists()
    assert result.watermark_mode == "visible+metadata"
    assert result.prompt_sha256 == hashlib.sha256(req.prompt.encode()).hexdigest()


def test_finalize_output_failclosed_when_disclaimer_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, isolated_jw_gen_home: Path
) -> None:
    raw = _make_png(tmp_path / "raw.png")
    req = GenerationRequest(prompt="ilustración pacífica", kind="image", lang="es")

    def boom(*_args: object, **_kwargs: object) -> Path:
        raise IOError("disclaimer broken")

    monkeypatch.setattr("jw_gen.policy.write_disclaimer_sibling", boom)
    with pytest.raises(PolicyError):
        finalize_output(raw_path=raw, request=req, dest=tmp_path / "out.png", provider="fake")
    assert not (tmp_path / "out.png").exists()


def test_finalize_output_failclosed_when_watermark_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, isolated_jw_gen_home: Path
) -> None:
    raw = _make_png(tmp_path / "raw.png")
    req = GenerationRequest(prompt="ilustración pacífica", kind="image", lang="es")

    def boom(*_args: object, **_kwargs: object) -> Path:
        raise IOError("watermark broken")

    monkeypatch.setattr("jw_gen.policy.apply_watermark", boom)
    with pytest.raises(PolicyError):
        finalize_output(raw_path=raw, request=req, dest=tmp_path / "out.png", provider="fake")
    assert not (tmp_path / "out.png").exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/jw-gen/tests/test_policy.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement policy**

```python
# packages/jw-gen/src/jw_gen/policy.py
"""Policy module — LOAD-BEARING.

This is the only place in jw-gen that writes the FINAL output to disk.
Providers return a raw path in a temp dir. `finalize_output` is the chokepoint
that:

  1. Calls `assert_personal_use(dest)` — warns if dest is in a Drive/Dropbox-
     looking path.
  2. Calls `apply_watermark(raw_path, ...)` if mode includes 'visible'.
  3. Calls `embed_metadata(raw_path, ...)` ALWAYS (mode-independent).
  4. Moves raw → dest atomically.
  5. Calls `write_disclaimer_sibling(dest, ...)` — fail-closed.
  6. Calls `audit.log_generation(...)`.
  7. Returns GenerationResult.

If ANY of steps 2-5 fail, the dest file is unlinked (if it was already moved)
and PolicyError is raised. Fail-closed.
"""

from __future__ import annotations

import hashlib
import io
import os
import shutil
import uuid
from pathlib import Path
from typing import Any

import piexif
from PIL import Image, ImageDraw, ImageFont

from jw_gen.audit import log_generation
from jw_gen.i18n import get_message
from jw_gen.models import GenerationRequest, GenerationResult, Language, WatermarkConfig


class PolicyError(RuntimeError):
    """Raised when finalize_output fails any required step. Fail-closed."""


# ---------------------------------------------------------------------------
# Watermark
# ---------------------------------------------------------------------------


def _load_font(size: int = 14) -> Any:
    try:
        return ImageFont.truetype("DejaVuSans.ttf", size)
    except Exception:  # noqa: BLE001
        return ImageFont.load_default()


def apply_watermark(src: Path, *, text: str, cfg: WatermarkConfig) -> Path:
    """Rasterize a visible watermark at the configured anchor. Returns src (mutated)."""

    img = Image.open(src).convert("RGBA")
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    font = _load_font(size=max(12, img.width // 40))
    alpha = int(255 * cfg.opacity)

    x = int(img.width * cfg.anchor_x)
    y = int(img.height * cfg.anchor_y)

    # Halo for legibility.
    draw.text((x + 1, y + 1), text, fill=(0, 0, 0, alpha), font=font)
    draw.text((x, y), text, fill=(255, 255, 255, alpha), font=font)

    composed = Image.alpha_composite(img, overlay).convert("RGB")
    composed.save(src, format="PNG")
    return src


# ---------------------------------------------------------------------------
# Metadata (EXIF + XMP)
# ---------------------------------------------------------------------------


def embed_metadata(path: Path, *, fields: dict[str, str]) -> None:
    """Embed EXIF + (best-effort) XMP into the file. Image formats only for now.

    For PNG, we encode EXIF via the `exif` chunk (piexif). XMP is also written
    as a tEXt chunk under key "XMP". Audio/video metadata embedding is delegated
    to the respective provider for now (see Tasks 13/15 for follow-up).
    """

    suffix = path.suffix.lower()
    if suffix not in {".png", ".jpg", ".jpeg", ".webp", ".tiff"}:
        # Audio/video: write a sidecar metadata file as fallback so chain-of-custody is preserved.
        sidecar = path.with_suffix(path.suffix + ".metadata.txt")
        sidecar.write_text(
            "\n".join(f"{k}: {v}" for k, v in fields.items()),
            encoding="utf-8",
        )
        return

    # Build EXIF dict.
    user_comment = "; ".join(f"{k}={v}" for k, v in fields.items()).encode("utf-8")
    exif_dict: dict[str, Any] = {
        "0th": {
            piexif.ImageIFD.Software: fields.get("Software", "jw-gen").encode("utf-8"),
            piexif.ImageIFD.ImageDescription: fields.get(
                "ImageDescription", "jw-gen personal-use illustration"
            ).encode("utf-8"),
            piexif.ImageIFD.Artist: b"jw-gen",
        },
        "Exif": {
            piexif.ExifIFD.UserComment: b"ASCII\x00\x00\x00" + user_comment,
        },
        "GPS": {},
        "1st": {},
        "thumbnail": None,
    }
    exif_bytes = piexif.dump(exif_dict)

    # Re-save with EXIF.
    img = Image.open(path)
    img.save(path, format=img.format or "PNG", exif=exif_bytes)

    # Best-effort XMP via custom tEXt chunk (for PNG) — small inline UTF-8 packet.
    if suffix == ".png":
        xmp_packet = (
            "<?xpacket begin='\xef\xbb\xbf' id='W5M0MpCehiHzreSzNTczkc9d'?>"
            "<x:xmpmeta xmlns:x='adobe:ns:meta/'><rdf:RDF xmlns:rdf='http://www.w3.org/1999/02/22-rdf-syntax-ns#'>"
            f"<rdf:Description><jwgen:provider xmlns:jwgen='https://jw-agent-toolkit/jw-gen/'>{fields.get('provider','')}</jwgen:provider>"
            f"<jwgen:prompt_sha256>{fields.get('prompt_sha256','')}</jwgen:prompt_sha256>"
            "</rdf:Description></rdf:RDF></x:xmpmeta><?xpacket end='w'?>"
        )
        # Append packet to file bytes (Pillow doesn't natively expose XMP write).
        with path.open("ab") as f:
            f.write(b"\n<!-- xmp -->\n" + xmp_packet.encode("utf-8"))


# ---------------------------------------------------------------------------
# Disclaimer
# ---------------------------------------------------------------------------


def write_disclaimer_sibling(
    *,
    target: Path,
    lang: Language,
    prompt_sha256: str,
    provider: str,
    watermark_mode: str,
    realistic_optin: bool,
) -> Path:
    """Write `<target>.disclaimer.txt` next to the output. Fail-closed."""

    body = get_message(
        "disclaimer.body",
        lang=lang,
        prompt_sha256=prompt_sha256,
        provider=provider,
        watermark_mode=watermark_mode,
    )
    if realistic_optin:
        body += "\n\n" + get_message("disclaimer.realistic_people_warning", lang=lang)
    dest = target.with_suffix(target.suffix + ".disclaimer.txt")
    dest.write_text(body + "\n", encoding="utf-8")
    return dest


# ---------------------------------------------------------------------------
# Personal-use path check
# ---------------------------------------------------------------------------


_SHARED_PATH_HINTS = ("dropbox", "google drive", "googledrive", "gdrive", "onedrive", "icloud drive")


def assert_personal_use(dest: Path) -> str | None:
    """Return a warning string if dest looks like a shared/cloud sync folder; None otherwise."""

    p = str(dest).lower()
    for hint in _SHARED_PATH_HINTS:
        if hint in p:
            return (
                f"WARNING: output path looks like a cloud-sync folder ({hint}). "
                "Personal-use disclaimer accompanies the file, but distribution "
                "from sync folders is your responsibility."
            )
    return None


# ---------------------------------------------------------------------------
# Final chokepoint
# ---------------------------------------------------------------------------


def finalize_output(
    *,
    raw_path: Path,
    request: GenerationRequest,
    dest: Path,
    provider: str,
) -> GenerationResult:
    """The ONLY function that may move a generated artifact to its destination.

    Fail-closed: if any step fails, the dest is unlinked and PolicyError raises.
    """

    prompt_sha256 = hashlib.sha256(request.prompt.encode("utf-8")).hexdigest()
    warnings: list[str] = []
    warn = assert_personal_use(dest)
    if warn:
        warnings.append(warn)

    dest.parent.mkdir(parents=True, exist_ok=True)

    moved = False
    try:
        # Move first so we operate on dest only (avoid partial source state).
        shutil.copy2(raw_path, dest)
        moved = True

        # 2) Visible watermark (if mode includes visible).
        if request.watermark.mode == "visible+metadata":
            text = get_message("watermark.default", lang=request.lang)
            apply_watermark(dest, text=text, cfg=request.watermark)
        elif request.watermark.mode == "off":
            warnings.append("watermark mode is 'off' — visible AND metadata suppressed (audit logged).")

        # 3) Metadata — ALWAYS, even when watermark mode is metadata-only.
        if request.watermark.mode != "off":
            embed_metadata(
                dest,
                fields={
                    "Software": "jw-gen",
                    "ImageDescription": "jw-gen personal-use illustration — NOT official JW content",
                    "Artist": "jw-gen",
                    "provider": provider,
                    "prompt_sha256": prompt_sha256,
                },
            )

        # 4) Disclaimer sibling — ALWAYS.
        disclaimer = write_disclaimer_sibling(
            target=dest,
            lang=request.lang,
            prompt_sha256=prompt_sha256,
            provider=provider,
            watermark_mode=request.watermark.mode,
            realistic_optin=request.realistic_people_optin,
        )

    except Exception as exc:  # noqa: BLE001
        # Fail-closed: undo any partial state.
        if moved:
            try:
                dest.unlink()
            except FileNotFoundError:
                pass
            disc = dest.with_suffix(dest.suffix + ".disclaimer.txt")
            if disc.exists():
                try:
                    disc.unlink()
                except FileNotFoundError:
                    pass
        raise PolicyError(f"finalize_output failed: {exc!r}") from exc

    # 5) Audit log.
    event = log_generation(
        kind=request.kind,
        provider=provider,
        prompt_sha256=prompt_sha256,
        output_path=dest,
        watermark_mode=request.watermark.mode,
        safety_flags={"finalized": "ok"},
        warnings=warnings,
    )

    return GenerationResult(
        output_path=dest,
        disclaimer_path=disclaimer,
        provider=provider,
        kind=request.kind,
        watermark_mode=request.watermark.mode,
        prompt_sha256=prompt_sha256,
        audit_id=str(event["audit_id"]),
        warnings=warnings,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/jw-gen/tests/test_policy.py -v`
Expected: 9 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-gen/src/jw_gen/policy.py packages/jw-gen/tests/test_policy.py
git commit -m "feat(jw-gen): policy module — watermark + EXIF/XMP + disclaimer + fail-closed finalize"
```

---

### Task 8: Provider base Protocol and fakes

**Files:**
- Create: `packages/jw-gen/src/jw_gen/providers/__init__.py`
- Create: `packages/jw-gen/src/jw_gen/providers/base.py`
- Create: `packages/jw-gen/src/jw_gen/providers/fakes.py`
- Create: `packages/jw-gen/tests/test_providers_fake.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-gen/tests/test_providers_fake.py
from __future__ import annotations

import wave
from pathlib import Path

from PIL import Image

from jw_gen.models import GenerationRequest
from jw_gen.providers.fakes import (
    FakeAudioProvider,
    FakeImageProvider,
    FakeVideoProvider,
)


def test_fake_image_provider_returns_valid_png(tmp_path: Path) -> None:
    p = FakeImageProvider(work_dir=tmp_path)
    req = GenerationRequest(prompt="hello", kind="image")
    out = p.generate(req)
    assert out.exists()
    assert out.suffix == ".png"
    img = Image.open(out)
    assert img.size == (512, 512)


def test_fake_image_provider_is_deterministic(tmp_path: Path) -> None:
    p1 = FakeImageProvider(work_dir=tmp_path)
    p2 = FakeImageProvider(work_dir=tmp_path / "again")
    out1 = p1.generate(GenerationRequest(prompt="same", kind="image"))
    out2 = p2.generate(GenerationRequest(prompt="same", kind="image"))
    assert out1.read_bytes() == out2.read_bytes()


def test_fake_audio_provider_returns_valid_wav(tmp_path: Path) -> None:
    p = FakeAudioProvider(work_dir=tmp_path)
    out = p.generate(GenerationRequest(prompt="music", kind="audio"))
    assert out.suffix == ".wav"
    with wave.open(str(out), "rb") as w:
        assert w.getnchannels() in (1, 2)
        assert w.getframerate() > 0


def test_fake_video_provider_returns_file_with_audio_track(tmp_path: Path) -> None:
    p = FakeVideoProvider(work_dir=tmp_path)
    out = p.generate(GenerationRequest(prompt="anything", kind="video"))
    assert out.exists()
    assert out.suffix in {".mp4", ".webm", ".gif"}


def test_all_fakes_report_zero_cost(tmp_path: Path) -> None:
    for cls in (FakeImageProvider, FakeAudioProvider, FakeVideoProvider):
        prov = cls(work_dir=tmp_path)  # type: ignore[abstract]
        assert prov.is_available()
        cost = prov.cost_estimate(GenerationRequest(prompt="x", kind=prov.kind))  # type: ignore[arg-type]
        assert cost.usd == 0.0
```

- [ ] **Step 2: Implement Protocol + fakes**

```python
# packages/jw-gen/src/jw_gen/providers/__init__.py
"""Provider adapters for jw-gen.

Each kind (image/audio/video) has API-backed implementations and one
deterministic Fake* used by every test.
"""
```

```python
# packages/jw-gen/src/jw_gen/providers/base.py
"""Common Protocol for all generation providers."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from jw_gen.models import CostHint, GenerationRequest, Kind, Target


@runtime_checkable
class GenerationProvider(Protocol):
    name: str
    kind: Kind
    target: Target

    def is_available(self) -> bool: ...
    def cost_estimate(self, request: GenerationRequest) -> CostHint: ...
    def generate(self, request: GenerationRequest) -> Path: ...
```

```python
# packages/jw-gen/src/jw_gen/providers/fakes.py
"""Deterministic fake providers used by every offline test.

Image fake → PNG 512x512 with prompt text rasterized, color seeded by
sha256(prompt).
Audio fake → 3-second WAV mono 22050 Hz with single tone whose freq is
derived from sha256(prompt).
Video fake → 2-second WebM (or fallback to GIF if mediapy is absent) built
from 3 frames of FakeImageProvider plus 3-second audio of FakeAudioProvider.

All fakes have target='cpu' and is_available() → True. cost_estimate() is zero.
"""

from __future__ import annotations

import hashlib
import math
import os
import struct
import wave
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from jw_gen.models import CostHint, GenerationRequest


def _seed(prompt: str) -> int:
    return int(hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:8], 16)


class FakeImageProvider:
    name = "fake"
    kind = "image"
    target = "cpu"

    def __init__(self, work_dir: Path | None = None) -> None:
        self.work_dir = work_dir or Path(os.environ.get("JW_GEN_CACHE", "/tmp/jw-gen-cache"))
        self.work_dir.mkdir(parents=True, exist_ok=True)

    def is_available(self) -> bool:
        return True

    def cost_estimate(self, request: GenerationRequest) -> CostHint:  # noqa: ARG002
        return CostHint(usd=0.0, time_s=0.01)

    def generate(self, request: GenerationRequest) -> Path:
        seed = _seed(request.prompt)
        r = (seed >> 16) & 0xFF
        g = (seed >> 8) & 0xFF
        b = seed & 0xFF
        img = Image.new("RGB", (512, 512), color=(r, g, b))
        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("DejaVuSans.ttf", 16)
        except Exception:  # noqa: BLE001
            font = ImageFont.load_default()
        wrapped = "\n".join(request.prompt[i: i + 32] for i in range(0, len(request.prompt), 32))
        draw.text((10, 10), wrapped, fill=(255, 255, 255), font=font)
        digest = hashlib.sha256(request.prompt.encode("utf-8")).hexdigest()[:12]
        out = self.work_dir / f"fake_image_{digest}.png"
        img.save(out, format="PNG")
        return out


class FakeAudioProvider:
    name = "fake"
    kind = "audio"
    target = "cpu"

    def __init__(self, work_dir: Path | None = None) -> None:
        self.work_dir = work_dir or Path(os.environ.get("JW_GEN_CACHE", "/tmp/jw-gen-cache"))
        self.work_dir.mkdir(parents=True, exist_ok=True)

    def is_available(self) -> bool:
        return True

    def cost_estimate(self, request: GenerationRequest) -> CostHint:  # noqa: ARG002
        return CostHint(usd=0.0, time_s=0.01)

    def generate(self, request: GenerationRequest) -> Path:
        seed = _seed(request.prompt)
        freq = 200 + (seed % 600)  # 200–800 Hz
        sample_rate = 22050
        duration_s = 3.0
        n = int(sample_rate * duration_s)
        digest = hashlib.sha256(request.prompt.encode("utf-8")).hexdigest()[:12]
        out = self.work_dir / f"fake_audio_{digest}.wav"
        with wave.open(str(out), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(sample_rate)
            for i in range(n):
                v = int(32767 * 0.4 * math.sin(2 * math.pi * freq * (i / sample_rate)))
                w.writeframes(struct.pack("<h", v))
        return out


class FakeVideoProvider:
    name = "fake"
    kind = "video"
    target = "cpu"

    def __init__(self, work_dir: Path | None = None) -> None:
        self.work_dir = work_dir or Path(os.environ.get("JW_GEN_CACHE", "/tmp/jw-gen-cache"))
        self.work_dir.mkdir(parents=True, exist_ok=True)

    def is_available(self) -> bool:
        return True

    def cost_estimate(self, request: GenerationRequest) -> CostHint:  # noqa: ARG002
        return CostHint(usd=0.0, time_s=0.05)

    def generate(self, request: GenerationRequest) -> Path:
        # The cheapest portable "video" fake: a multi-frame APNG-like GIF.
        # Real videos go through Veo3/Kling/Runway. Fake only proves contract.
        img_provider = FakeImageProvider(work_dir=self.work_dir)
        frame = Image.open(img_provider.generate(request))
        frames = [frame.copy() for _ in range(3)]
        digest = hashlib.sha256(request.prompt.encode("utf-8")).hexdigest()[:12]
        out = self.work_dir / f"fake_video_{digest}.gif"
        frames[0].save(out, save_all=True, append_images=frames[1:], duration=600, loop=0)
        return out
```

- [ ] **Step 3: Run test to verify it passes**

Run: `uv run pytest packages/jw-gen/tests/test_providers_fake.py -v`
Expected: 5 passed.

- [ ] **Step 4: Commit**

```bash
git add packages/jw-gen/src/jw_gen/providers packages/jw-gen/tests/test_providers_fake.py
git commit -m "feat(jw-gen): GenerationProvider Protocol + deterministic fakes for image/audio/video"
```

---

### Task 9: Factory with env override + fallback chain

**Files:**
- Create: `packages/jw-gen/src/jw_gen/factory.py`
- Create: `packages/jw-gen/tests/test_factory.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-gen/tests/test_factory.py
from __future__ import annotations

import pytest

from jw_gen.factory import NoProviderAvailable, get_provider
from jw_gen.providers.fakes import FakeAudioProvider, FakeImageProvider, FakeVideoProvider


def test_get_provider_image_returns_fake_when_no_api_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in ("GEMINI_API_KEY", "OPENAI_API_KEY", "REPLICATE_API_TOKEN", "RECRAFT_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("JW_GEN_IMAGE_PROVIDER", "fake")
    p = get_provider("image")
    assert isinstance(p, FakeImageProvider)


def test_get_provider_audio_returns_fake_explicit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JW_GEN_AUDIO_PROVIDER", "fake")
    p = get_provider("audio")
    assert isinstance(p, FakeAudioProvider)


def test_get_provider_video_returns_fake_explicit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JW_GEN_VIDEO_PROVIDER", "fake")
    p = get_provider("video")
    assert isinstance(p, FakeVideoProvider)


def test_get_provider_unknown_name_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JW_GEN_IMAGE_PROVIDER", "definitely-not-real")
    with pytest.raises(NoProviderAvailable):
        get_provider("image")


def test_get_provider_explicit_name_wins(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JW_GEN_IMAGE_PROVIDER", "nanobanana")
    # Even if env is set, explicit kwarg wins.
    p = get_provider("image", provider="fake")
    assert isinstance(p, FakeImageProvider)
```

- [ ] **Step 2: Implement factory**

```python
# packages/jw-gen/src/jw_gen/factory.py
"""Provider routing.

Strategy:
  1. Explicit `provider=` kwarg wins.
  2. Else env JW_GEN_<KIND>_PROVIDER.
  3. Else default fallback chain per kind, picking first `is_available()`.
  4. If nothing available, raise NoProviderAvailable.

The fake is ALWAYS reachable when explicitly named or env-set so tests stay
hermetic.
"""

from __future__ import annotations

import os
from typing import cast

from jw_gen.models import Kind
from jw_gen.providers.base import GenerationProvider
from jw_gen.providers.fakes import (
    FakeAudioProvider,
    FakeImageProvider,
    FakeVideoProvider,
)


class NoProviderAvailable(RuntimeError):
    """Raised when no usable provider can be resolved for a kind."""


_FALLBACK = {
    "image": ["nanobanana", "flux2", "recraft", "ideogram", "imagen"],
    "audio": ["elevenlabs", "musicgen", "suno"],
    "video": ["veo3", "kling", "seedance", "runway", "higgsfield"],
}


def _build(name: str, kind: Kind) -> GenerationProvider | None:
    n = name.lower()
    if n == "fake":
        if kind == "image":
            return cast(GenerationProvider, FakeImageProvider())
        if kind == "audio":
            return cast(GenerationProvider, FakeAudioProvider())
        if kind == "video":
            return cast(GenerationProvider, FakeVideoProvider())

    if kind == "image" and n == "nanobanana":
        try:
            from jw_gen.providers.image.nanobanana import NanoBananaProvider
            return cast(GenerationProvider, NanoBananaProvider())
        except Exception:  # noqa: BLE001
            return None
    if kind == "audio" and n == "elevenlabs":
        try:
            from jw_gen.providers.audio.elevenlabs import ElevenLabsProvider
            return cast(GenerationProvider, ElevenLabsProvider())
        except Exception:  # noqa: BLE001
            return None
    if kind == "video" and n == "veo3":
        try:
            from jw_gen.providers.video.veo3 import Veo3Provider
            return cast(GenerationProvider, Veo3Provider())
        except Exception:  # noqa: BLE001
            return None

    return None


def get_provider(kind: Kind, *, provider: str | None = None) -> GenerationProvider:
    """Resolve a provider for `kind`. Raise NoProviderAvailable if nothing fits."""

    candidates: list[str] = []
    if provider:
        candidates.append(provider)
    env_key = f"JW_GEN_{kind.upper()}_PROVIDER"
    env_choice = os.environ.get(env_key)
    if env_choice and env_choice not in candidates:
        candidates.append(env_choice)
    for default in _FALLBACK.get(kind, []):
        if default not in candidates:
            candidates.append(default)
    # Last resort: fake.
    candidates.append("fake")

    last_attempt: str | None = None
    for name in candidates:
        last_attempt = name
        built = _build(name, kind)
        if built is not None and built.is_available():
            return built

    raise NoProviderAvailable(
        f"No provider available for kind={kind!r}. Tried: {candidates}. "
        f"Last attempt: {last_attempt}. "
        f"Set {env_key} or pass provider= explicitly."
    )
```

- [ ] **Step 3: Run test to verify it passes**

Run: `uv run pytest packages/jw-gen/tests/test_factory.py -v`
Expected: 5 passed.

- [ ] **Step 4: Commit**

```bash
git add packages/jw-gen/src/jw_gen/factory.py packages/jw-gen/tests/test_factory.py
git commit -m "feat(jw-gen): provider factory with env override + fallback chain + fake floor"
```

---

### Task 10: Image provider — NanoBanana adapter (thin)

**Files:**
- Create: `packages/jw-gen/src/jw_gen/providers/image/__init__.py`
- Create: `packages/jw-gen/src/jw_gen/providers/image/nanobanana.py`
- Create: `packages/jw-gen/tests/test_provider_nanobanana.py`

- [ ] **Step 1: Write the failing test (offline — stub the SDK via sys.modules)**

```python
# packages/jw-gen/tests/test_provider_nanobanana.py
"""Offline unit tests for NanoBanana adapter.

The SDK (`google.genai`) is monkeypatched into sys.modules with a fake
that captures call args. No network, no real key required.
"""

from __future__ import annotations

import os
import sys
import types
from pathlib import Path

import pytest

from jw_gen.models import GenerationRequest


def test_is_available_false_when_no_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    from jw_gen.providers.image.nanobanana import NanoBananaProvider

    assert NanoBananaProvider().is_available() is False


def test_is_available_false_when_sdk_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    monkeypatch.setitem(sys.modules, "google.genai", None)
    from jw_gen.providers.image.nanobanana import NanoBananaProvider

    assert NanoBananaProvider().is_available() is False


def test_cost_estimate_is_constant(tmp_path: Path) -> None:
    from jw_gen.providers.image.nanobanana import NanoBananaProvider

    p = NanoBananaProvider(work_dir=tmp_path)
    hint = p.cost_estimate(GenerationRequest(prompt="x", kind="image"))
    assert hint.usd > 0
    assert hint.time_s > 0


def test_generate_calls_sdk_and_writes_png(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    captured: dict = {}

    class _FakeImage:
        image_bytes = b"\x89PNG\r\n\x1a\nFAKE"

    class _FakeGen:
        def __init__(self) -> None:
            self.generated_images = [types.SimpleNamespace(image=_FakeImage())]

    class _FakeModels:
        def generate_images(self, *, model: str, prompt: str, number_of_images: int):
            captured["model"] = model
            captured["prompt"] = prompt
            captured["n"] = number_of_images
            return _FakeGen()

    class _FakeClient:
        def __init__(self, api_key: str) -> None:
            captured["api_key"] = api_key
            self.models = _FakeModels()

    fake_genai = types.SimpleNamespace(Client=_FakeClient)
    fake_google = types.ModuleType("google")
    fake_google.genai = fake_genai  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "google", fake_google)
    monkeypatch.setitem(sys.modules, "google.genai", fake_genai)
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")

    from jw_gen.providers.image.nanobanana import NanoBananaProvider

    p = NanoBananaProvider(work_dir=tmp_path)
    out = p.generate(GenerationRequest(prompt="paisaje sereno", kind="image"))

    assert out.exists()
    assert out.read_bytes().startswith(b"\x89PNG")
    assert captured["model"] == "imagen-4.0-generate-001"
    assert captured["prompt"] == "paisaje sereno"
    assert captured["api_key"] == "fake-key"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --no-sync pytest packages/jw-gen/tests/test_provider_nanobanana.py -v`
Expected: FAIL — `ModuleNotFoundError: jw_gen.providers.image.nanobanana`.

- [ ] **Step 3: Implement adapter to make tests pass**

```python
# packages/jw-gen/src/jw_gen/providers/image/__init__.py
"""Image providers."""
```

```python
# packages/jw-gen/src/jw_gen/providers/image/nanobanana.py
"""NanoBanana (Gemini image generation) provider — thin adapter.

Loaded only when explicitly selected. Real calls require GEMINI_API_KEY.
"""

from __future__ import annotations

import os
from pathlib import Path

from jw_gen.models import CostHint, GenerationRequest


class NanoBananaProvider:
    name = "nanobanana"
    kind = "image"
    target = "api"

    def __init__(self, work_dir: Path | None = None) -> None:
        self.work_dir = work_dir or Path(os.environ.get("JW_GEN_CACHE", "/tmp/jw-gen-cache"))
        self.work_dir.mkdir(parents=True, exist_ok=True)

    def is_available(self) -> bool:
        if not os.environ.get("GEMINI_API_KEY"):
            return False
        try:
            import google.genai  # noqa: F401
        except ImportError:
            return False
        return True

    def cost_estimate(self, request: GenerationRequest) -> CostHint:  # noqa: ARG002
        return CostHint(usd=0.04, time_s=8.0, notes="Gemini image — rough estimate")

    def generate(self, request: GenerationRequest) -> Path:
        from google import genai  # type: ignore[import-not-found]

        client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
        response = client.models.generate_images(
            model="imagen-4.0-generate-001",
            prompt=request.prompt,
            number_of_images=1,
        )
        out = self.work_dir / f"nanobanana_{hash(request.prompt) & 0xFFFFFF:06x}.png"
        out.write_bytes(response.generated_images[0].image.image_bytes)
        return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --no-sync pytest packages/jw-gen/tests/test_provider_nanobanana.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-gen/src/jw_gen/providers/image packages/jw-gen/tests/test_provider_nanobanana.py
git commit -m "feat(jw-gen): NanoBanana image provider adapter (lazy SDK, opt-in via env) + offline tests"
```

---

### Task 11: Audio provider — ElevenLabs adapter

**Files:**
- Create: `packages/jw-gen/src/jw_gen/providers/audio/__init__.py`
- Create: `packages/jw-gen/src/jw_gen/providers/audio/elevenlabs.py`
- Create: `packages/jw-gen/tests/test_provider_elevenlabs.py`

- [ ] **Step 1: Write the failing test (offline — stub elevenlabs SDK)**

```python
# packages/jw-gen/tests/test_provider_elevenlabs.py
"""Offline unit tests for ElevenLabs adapter."""

from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

from jw_gen.models import GenerationRequest


def test_is_available_false_when_no_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    from jw_gen.providers.audio.elevenlabs import ElevenLabsProvider

    assert ElevenLabsProvider().is_available() is False


def test_is_available_false_when_sdk_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ELEVENLABS_API_KEY", "fake-key")
    monkeypatch.setitem(sys.modules, "elevenlabs", None)
    from jw_gen.providers.audio.elevenlabs import ElevenLabsProvider

    assert ElevenLabsProvider().is_available() is False


def test_cost_estimate_scales_with_prompt_length(tmp_path: Path) -> None:
    from jw_gen.providers.audio.elevenlabs import ElevenLabsProvider

    p = ElevenLabsProvider(work_dir=tmp_path)
    short = p.cost_estimate(GenerationRequest(prompt="x", kind="audio"))
    long_ = p.cost_estimate(GenerationRequest(prompt="x" * 1000, kind="audio"))
    assert long_.usd > short.usd


def test_generate_writes_mp3_and_passes_correct_args(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    captured: dict = {}

    class _FakeTTS:
        def convert(self, *, voice_id: str, output_format: str, text: str):
            captured["voice_id"] = voice_id
            captured["output_format"] = output_format
            captured["text"] = text
            return iter([b"ID3", b"\x03\x00\x00\x00", b"FAKE_MP3_DATA"])

    class _FakeClient:
        def __init__(self, api_key: str) -> None:
            captured["api_key"] = api_key
            self.text_to_speech = _FakeTTS()

    fake_module = types.SimpleNamespace(ElevenLabs=_FakeClient)
    monkeypatch.setitem(sys.modules, "elevenlabs", fake_module)
    monkeypatch.setenv("ELEVENLABS_API_KEY", "fake-key")

    from jw_gen.providers.audio.elevenlabs import ElevenLabsProvider

    p = ElevenLabsProvider(work_dir=tmp_path)
    out = p.generate(
        GenerationRequest(prompt="Hola mundo", kind="audio", extra={"voice_id": "v1"})
    )
    assert out.suffix == ".mp3"
    assert out.read_bytes().startswith(b"ID3")
    assert captured["voice_id"] == "v1"
    assert captured["text"] == "Hola mundo"
    assert captured["api_key"] == "fake-key"


def test_generate_uses_default_voice_when_none_specified(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    captured: dict = {}

    class _FakeTTS:
        def convert(self, *, voice_id: str, output_format: str, text: str):
            captured["voice_id"] = voice_id
            return iter([b"ID3"])

    class _FakeClient:
        def __init__(self, api_key: str) -> None:  # noqa: ARG002
            self.text_to_speech = _FakeTTS()

    fake_module = types.SimpleNamespace(ElevenLabs=_FakeClient)
    monkeypatch.setitem(sys.modules, "elevenlabs", fake_module)
    monkeypatch.setenv("ELEVENLABS_API_KEY", "fake-key")

    from jw_gen.providers.audio.elevenlabs import ElevenLabsProvider

    ElevenLabsProvider(work_dir=tmp_path).generate(
        GenerationRequest(prompt="x", kind="audio")
    )
    assert captured["voice_id"] == "EXAVITQu4vr4xnSDxMaL"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --no-sync pytest packages/jw-gen/tests/test_provider_elevenlabs.py -v`
Expected: FAIL — `ModuleNotFoundError: jw_gen.providers.audio.elevenlabs`.

- [ ] **Step 3: Implement adapter**

```python
# packages/jw-gen/src/jw_gen/providers/audio/__init__.py
"""Audio providers."""
```

```python
# packages/jw-gen/src/jw_gen/providers/audio/elevenlabs.py
"""ElevenLabs TTS adapter — thin. Voice clone gated by `safety.refuse_voice_cloning_without_double_optin`."""

from __future__ import annotations

import os
from pathlib import Path

from jw_gen.models import CostHint, GenerationRequest


class ElevenLabsProvider:
    name = "elevenlabs"
    kind = "audio"
    target = "api"

    def __init__(self, work_dir: Path | None = None) -> None:
        self.work_dir = work_dir or Path(os.environ.get("JW_GEN_CACHE", "/tmp/jw-gen-cache"))
        self.work_dir.mkdir(parents=True, exist_ok=True)

    def is_available(self) -> bool:
        if not os.environ.get("ELEVENLABS_API_KEY"):
            return False
        try:
            import elevenlabs  # noqa: F401
        except ImportError:
            return False
        return True

    def cost_estimate(self, request: GenerationRequest) -> CostHint:
        chars = len(request.prompt)
        return CostHint(usd=chars * 0.00003, time_s=2.0, notes="ElevenLabs TTS")

    def generate(self, request: GenerationRequest) -> Path:
        from elevenlabs import ElevenLabs  # type: ignore[import-not-found]

        client = ElevenLabs(api_key=os.environ["ELEVENLABS_API_KEY"])
        audio = client.text_to_speech.convert(
            voice_id=str(request.extra.get("voice_id", "EXAVITQu4vr4xnSDxMaL")),
            output_format="mp3_44100_128",
            text=request.prompt,
        )
        digest = abs(hash(request.prompt)) & 0xFFFFFF
        out = self.work_dir / f"elevenlabs_{digest:06x}.mp3"
        with out.open("wb") as f:
            for chunk in audio:
                f.write(chunk)
        return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --no-sync pytest packages/jw-gen/tests/test_provider_elevenlabs.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-gen/src/jw_gen/providers/audio packages/jw-gen/tests/test_provider_elevenlabs.py
git commit -m "feat(jw-gen): ElevenLabs audio adapter (lazy SDK, voice-clone gated by safety) + offline tests"
```

---

### Task 12: Video provider — Veo3 adapter

**Files:**
- Create: `packages/jw-gen/src/jw_gen/providers/video/__init__.py`
- Create: `packages/jw-gen/src/jw_gen/providers/video/veo3.py`
- Create: `packages/jw-gen/tests/test_provider_veo3.py`

- [ ] **Step 1: Write the failing test (offline — stub SDK + accelerate poll via time.sleep monkeypatch)**

```python
# packages/jw-gen/tests/test_provider_veo3.py
"""Offline unit tests for Veo3 adapter. Poll loop accelerated by stubbing time.sleep."""

from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

from jw_gen.models import GenerationRequest


def test_is_available_false_when_no_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    from jw_gen.providers.video.veo3 import Veo3Provider

    assert Veo3Provider().is_available() is False


def test_is_available_false_when_sdk_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    monkeypatch.setitem(sys.modules, "google.genai", None)
    from jw_gen.providers.video.veo3 import Veo3Provider

    assert Veo3Provider().is_available() is False


def test_cost_estimate_scales_with_duration(tmp_path: Path) -> None:
    from jw_gen.providers.video.veo3 import Veo3Provider

    p = Veo3Provider(work_dir=tmp_path)
    short = p.cost_estimate(GenerationRequest(prompt="x", kind="video", duration_s=4))
    long_ = p.cost_estimate(GenerationRequest(prompt="x", kind="video", duration_s=12))
    assert long_.usd > short.usd


def test_generate_polls_until_done_and_downloads(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    captured: dict = {}

    class _FakeVideo:
        pass

    class _FakeResponse:
        generated_videos = [types.SimpleNamespace(video=_FakeVideo())]

    class _FakeOp:
        def __init__(self) -> None:
            self.done = False
            self.response = _FakeResponse()
            self.calls = 0

    fake_op = _FakeOp()

    class _FakeModels:
        def generate_videos(self, *, model: str, prompt: str):
            captured["model"] = model
            captured["prompt"] = prompt
            return fake_op

    class _FakeOperations:
        def get(self, op):  # noqa: ARG002
            fake_op.calls += 1
            if fake_op.calls >= 2:
                fake_op.done = True
            return fake_op

    class _FakeFiles:
        def download(self, *, file, destination):  # noqa: ARG002
            captured["destination"] = destination
            Path(destination).write_bytes(b"\x00\x00\x00\x18ftypmp42FAKE")

    class _FakeClient:
        def __init__(self, api_key: str) -> None:
            captured["api_key"] = api_key
            self.models = _FakeModels()
            self.operations = _FakeOperations()
            self.files = _FakeFiles()

    fake_genai = types.SimpleNamespace(Client=_FakeClient)
    fake_google = types.ModuleType("google")
    fake_google.genai = fake_genai  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "google", fake_google)
    monkeypatch.setitem(sys.modules, "google.genai", fake_genai)
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    # Accelerate the poll loop.
    monkeypatch.setattr("time.sleep", lambda _s: None)

    from jw_gen.providers.video.veo3 import Veo3Provider

    out = Veo3Provider(work_dir=tmp_path).generate(
        GenerationRequest(prompt="océano al amanecer", kind="video")
    )
    assert out.exists()
    assert out.read_bytes().startswith(b"\x00\x00\x00\x18ftypmp42")
    assert captured["model"] == "veo-3.0-generate-preview"
    assert fake_op.calls >= 1


def test_generate_raises_on_timeout(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    class _FakeOp:
        done = False
        response = None

    class _FakeModels:
        def generate_videos(self, *, model: str, prompt: str):  # noqa: ARG002
            return _FakeOp()

    class _FakeOperations:
        def get(self, op):  # noqa: ARG002
            return _FakeOp()

    class _FakeClient:
        def __init__(self, api_key: str) -> None:  # noqa: ARG002
            self.models = _FakeModels()
            self.operations = _FakeOperations()
            self.files = types.SimpleNamespace()

    fake_genai = types.SimpleNamespace(Client=_FakeClient)
    fake_google = types.ModuleType("google")
    fake_google.genai = fake_genai  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "google", fake_google)
    monkeypatch.setitem(sys.modules, "google.genai", fake_genai)
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    # Make time advance fast so we hit the deadline.
    import time as _time

    times = iter([0.0, 1000.0])
    monkeypatch.setattr(_time, "time", lambda: next(times))
    monkeypatch.setattr(_time, "sleep", lambda _s: None)

    from jw_gen.providers.video.veo3 import Veo3Provider

    with pytest.raises(RuntimeError, match="timed out"):
        Veo3Provider(work_dir=tmp_path).generate(
            GenerationRequest(prompt="x", kind="video")
        )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --no-sync pytest packages/jw-gen/tests/test_provider_veo3.py -v`
Expected: FAIL — `ModuleNotFoundError: jw_gen.providers.video.veo3`.

- [ ] **Step 3: Implement adapter**

```python
# packages/jw-gen/src/jw_gen/providers/video/__init__.py
"""Video providers."""
```

```python
# packages/jw-gen/src/jw_gen/providers/video/veo3.py
"""Veo 3 (Gemini video generation) provider — thin."""

from __future__ import annotations

import os
import time
from pathlib import Path

from jw_gen.models import CostHint, GenerationRequest


class Veo3Provider:
    name = "veo3"
    kind = "video"
    target = "api"

    def __init__(self, work_dir: Path | None = None) -> None:
        self.work_dir = work_dir or Path(os.environ.get("JW_GEN_CACHE", "/tmp/jw-gen-cache"))
        self.work_dir.mkdir(parents=True, exist_ok=True)

    def is_available(self) -> bool:
        if not os.environ.get("GEMINI_API_KEY"):
            return False
        try:
            import google.genai  # noqa: F401
        except ImportError:
            return False
        return True

    def cost_estimate(self, request: GenerationRequest) -> CostHint:
        seconds = float(request.duration_s or 6.0)
        return CostHint(usd=seconds * 0.50, time_s=60.0, notes="Veo 3 — long-running operation")

    def generate(self, request: GenerationRequest) -> Path:
        from google import genai  # type: ignore[import-not-found]

        client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
        op = client.models.generate_videos(
            model="veo-3.0-generate-preview",
            prompt=request.prompt,
        )
        # Poll until done. Cap at 5 min.
        deadline = time.time() + 300
        while not op.done and time.time() < deadline:
            time.sleep(5)
            op = client.operations.get(op)
        if not op.done:
            raise RuntimeError("Veo3 generation timed out after 5 minutes")
        digest = abs(hash(request.prompt)) & 0xFFFFFF
        out = self.work_dir / f"veo3_{digest:06x}.mp4"
        client.files.download(file=op.response.generated_videos[0].video, destination=str(out))
        return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --no-sync pytest packages/jw-gen/tests/test_provider_veo3.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-gen/src/jw_gen/providers/video packages/jw-gen/tests/test_provider_veo3.py
git commit -m "feat(jw-gen): Veo3 video adapter (lazy SDK, long-running op poll) + offline tests"
```

---

### Task 13: CLI — `jw gen image|audio|video`

**Files:**
- Create: `packages/jw-gen/src/jw_gen/cli.py`
- Create: `packages/jw-cli/src/jw_cli/commands/gen.py`
- Modify: `packages/jw-cli/src/jw_cli/main.py`
- Modify: `packages/jw-cli/pyproject.toml`
- Create: `packages/jw-gen/tests/test_cli.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-gen/tests/test_cli.py
from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from jw_gen.cli import gen_app

runner = CliRunner()


def test_cli_image_with_fake_provider_succeeds(
    tmp_path: Path, isolated_jw_gen_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("JW_GEN_IMAGE_PROVIDER", "fake")
    out = tmp_path / "x.png"
    result = runner.invoke(
        gen_app,
        ["image", "--prompt", "ilustración pacífica de ovejas", "--out", str(out)],
    )
    assert result.exit_code == 0, result.stdout
    assert out.exists()
    assert (tmp_path / "x.png.disclaimer.txt").exists()


def test_cli_image_blocks_logo_prompt(
    tmp_path: Path, isolated_jw_gen_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("JW_GEN_IMAGE_PROVIDER", "fake")
    out = tmp_path / "bad.png"
    result = runner.invoke(
        gen_app,
        ["image", "--prompt", "official watchtower logo", "--out", str(out)],
    )
    assert result.exit_code != 0
    assert not out.exists()
    assert "logo" in result.stdout.lower() or "refused" in result.stdout.lower() or "rechazada" in result.stdout.lower()


def test_cli_audio_with_fake_provider_succeeds(
    tmp_path: Path, isolated_jw_gen_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("JW_GEN_AUDIO_PROVIDER", "fake")
    out = tmp_path / "bg.wav"
    result = runner.invoke(
        gen_app,
        ["audio", "--prompt", "música suave de fondo", "--out", str(out)],
    )
    assert result.exit_code == 0, result.stdout
    assert out.exists()
    assert (tmp_path / "bg.wav.disclaimer.txt").exists()


def test_cli_no_visible_watermark_logs_audit(
    tmp_path: Path, isolated_jw_gen_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("JW_GEN_IMAGE_PROVIDER", "fake")
    out = tmp_path / "y.png"
    result = runner.invoke(
        gen_app,
        ["image", "--prompt", "campo de trigo", "--out", str(out), "--no-visible-watermark"],
    )
    assert result.exit_code == 0
    assert out.exists()
    audit = (isolated_jw_gen_home / "audit.log").read_text(encoding="utf-8")
    assert "metadata-only" in audit
```

- [ ] **Step 2: Implement the gen_app**

```python
# packages/jw-gen/src/jw_gen/cli.py
"""`jw gen` CLI subcommands.

Three commands: `image`, `audio`, `video`. All three follow the same shape:

    1. Parse flags into a GenerationRequest (with WatermarkConfig).
    2. Run safety.evaluate(request) → SafetyDecision.
    3. If voice_clone requested, run refuse_voice_cloning_without_double_optin
       with interactive prompt.
    4. Resolve provider via factory.get_provider(kind, provider=...).
    5. Show cost estimate; if above threshold, confirm.
    6. Provider returns raw path.
    7. policy.finalize_output(raw, request, dest, provider) → result.
    8. Echo result.

The CLI is also where `--no-visible-watermark` and `--realistic-people`
hand off audit-trail responsibility.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import typer

from jw_gen.audit import audit_log_path
from jw_gen.factory import NoProviderAvailable, get_provider
from jw_gen.i18n import get_message
from jw_gen.models import GenerationRequest, Language, WatermarkConfig
from jw_gen.policy import PolicyError, finalize_output
from jw_gen.safety import SafetyRefused, evaluate, refuse_voice_cloning_without_double_optin

gen_app = typer.Typer(name="gen", help="Generate illustrative content for personal use.", no_args_is_help=True)


def _build_watermark(no_visible: bool, no_watermark: bool) -> WatermarkConfig:
    if no_watermark:
        return WatermarkConfig(mode="off")
    if no_visible:
        return WatermarkConfig(mode="metadata-only")
    return WatermarkConfig()


def _confirm_cost(cost_usd: float, lang: Language) -> bool:
    threshold = float(os.environ.get("JW_GEN_COST_CONFIRM_THRESHOLD_USD", "1.0"))
    if cost_usd < threshold:
        return True
    answer = typer.prompt(get_message("cli.cost_confirm", lang=lang, usd=cost_usd))
    return answer.strip().lower() in {"y", "yes", "si", "sí", "sim", "s"}


def _run(
    *,
    kind: str,
    prompt: str,
    lang: str,
    out: Path,
    provider_name: str | None,
    no_visible_watermark: bool,
    no_watermark: bool,
    realistic_people: bool,
    voice_clone: bool,
    input_audio: Path | None,
) -> None:
    if no_watermark and not os.environ.get("JW_GEN_ALLOW_NO_WATERMARK"):
        typer.echo("error: --no-watermark requires env JW_GEN_ALLOW_NO_WATERMARK=1 (audit-logged).", err=True)
        raise typer.Exit(code=2)

    request = GenerationRequest(
        prompt=prompt,
        kind=kind,  # type: ignore[arg-type]
        lang=lang,  # type: ignore[arg-type]
        watermark=_build_watermark(no_visible_watermark, no_watermark),
        realistic_people_optin=realistic_people,
        voice_clone_source=input_audio if voice_clone else None,
    )

    # 1) Safety
    decision = evaluate(request)
    if not decision.allow:
        typer.echo(get_message(decision.reason or "safety.refuse.logo", lang=request.lang), err=True)
        raise typer.Exit(code=10)

    # 2) Voice clone double opt-in (audio only)
    if voice_clone:
        if input_audio is None:
            typer.echo("error: --voice-clone requires --input AUDIO_PATH", err=True)
            raise typer.Exit(code=11)
        try:
            refuse_voice_cloning_without_double_optin(
                audio_src=input_audio,
                voice_clone_flag=True,
                interactive_confirm=lambda q: typer.prompt(q).strip().lower() in {"si", "sí", "yes", "y", "sim", "s"},
                lang=request.lang,
            )
        except SafetyRefused as exc:
            typer.echo(get_message(exc.reason, lang=request.lang), err=True)
            raise typer.Exit(code=12)

    # 3) Provider routing
    try:
        provider = get_provider(kind, provider=provider_name)  # type: ignore[arg-type]
    except NoProviderAvailable as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=13) from exc

    # 4) Cost confirm
    cost = provider.cost_estimate(request)
    if not _confirm_cost(cost.usd, lang=request.lang):
        typer.echo("aborted by user")
        raise typer.Exit(code=14)

    # 5) Generate
    try:
        raw_path = provider.generate(
            request.model_copy(update={"prompt": decision.augmented_prompt or request.prompt})
        )
    except Exception as exc:  # noqa: BLE001
        typer.echo(f"provider failed: {exc!r}", err=True)
        raise typer.Exit(code=15) from exc

    # 6) Finalize
    try:
        result = finalize_output(
            raw_path=raw_path,
            request=request,
            dest=out,
            provider=provider.name,
        )
    except PolicyError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=16) from exc

    typer.echo(f"OK {result.output_path}")
    typer.echo(f"  disclaimer: {result.disclaimer_path}")
    typer.echo(f"  audit:      {audit_log_path()}#audit_id={result.audit_id}")


@gen_app.command("image")
def gen_image(
    prompt: str = typer.Option(..., "--prompt"),
    out: Path = typer.Option(..., "--out"),
    lang: str = typer.Option("es", "--lang"),
    provider: str | None = typer.Option(None, "--provider"),
    no_visible_watermark: bool = typer.Option(False, "--no-visible-watermark"),
    no_watermark: bool = typer.Option(False, "--no-watermark"),
    realistic_people: bool = typer.Option(False, "--realistic-people"),
) -> None:
    _run(
        kind="image",
        prompt=prompt,
        lang=lang,
        out=out,
        provider_name=provider,
        no_visible_watermark=no_visible_watermark,
        no_watermark=no_watermark,
        realistic_people=realistic_people,
        voice_clone=False,
        input_audio=None,
    )


@gen_app.command("audio")
def gen_audio(
    prompt: str = typer.Option(..., "--prompt"),
    out: Path = typer.Option(..., "--out"),
    lang: str = typer.Option("es", "--lang"),
    provider: str | None = typer.Option(None, "--provider"),
    voice_clone: bool = typer.Option(False, "--voice-clone"),
    input_audio: Path | None = typer.Option(None, "--input"),
    no_visible_watermark: bool = typer.Option(False, "--no-visible-watermark"),
    no_watermark: bool = typer.Option(False, "--no-watermark"),
) -> None:
    _run(
        kind="audio",
        prompt=prompt,
        lang=lang,
        out=out,
        provider_name=provider,
        no_visible_watermark=no_visible_watermark,
        no_watermark=no_watermark,
        realistic_people=False,
        voice_clone=voice_clone,
        input_audio=input_audio,
    )


@gen_app.command("video")
def gen_video(
    prompt: str = typer.Option(..., "--prompt"),
    out: Path = typer.Option(..., "--out"),
    lang: str = typer.Option("es", "--lang"),
    provider: str | None = typer.Option(None, "--provider"),
    duration: float = typer.Option(6.0, "--duration"),
    no_visible_watermark: bool = typer.Option(False, "--no-visible-watermark"),
    no_watermark: bool = typer.Option(False, "--no-watermark"),
    realistic_people: bool = typer.Option(False, "--realistic-people"),
) -> None:
    _ = duration  # passed via extras if a provider needs it
    _run(
        kind="video",
        prompt=prompt,
        lang=lang,
        out=out,
        provider_name=provider,
        no_visible_watermark=no_visible_watermark,
        no_watermark=no_watermark,
        realistic_people=realistic_people,
        voice_clone=False,
        input_audio=None,
    )
```

- [ ] **Step 3: Register in jw-cli**

```python
# packages/jw-cli/src/jw_cli/commands/gen.py
"""`jw gen` Typer group, re-exported from jw_gen.cli."""

from __future__ import annotations

from jw_gen.cli import gen_app

__all__ = ["gen_app"]
```

Modify `packages/jw-cli/src/jw_cli/main.py`: append the import alias next to the others and register the Typer app.

```python
from jw_cli.commands import (
    gen as gen_module,
)
...
app.add_typer(gen_module.gen_app, name="gen")
```

Add `"jw-gen"` to `packages/jw-cli/pyproject.toml`'s `[project].dependencies`.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/jw-gen/tests/test_cli.py -v`
Expected: 4 passed.

- [ ] **Step 5: Smoke-test the registered subcommand**

```bash
uv sync --all-packages
uv run jw gen --help
# Expected: lists `image`, `audio`, `video` subcommands.
```

- [ ] **Step 6: Commit**

```bash
git add packages/jw-gen/src/jw_gen/cli.py packages/jw-cli pyproject.toml packages/jw-gen/tests/test_cli.py
git commit -m "feat(jw-gen): jw gen image|audio|video CLI (registered in jw-cli, safety+policy enforced)"
```

---

### Task 14: MCP tool `generate_illustration`

**Files:**
- Modify: `packages/jw-mcp/pyproject.toml` — add `jw-gen` dependency.
- Modify: `packages/jw-mcp/src/jw_mcp/server.py` — register tool.
- Create: `packages/jw-gen/tests/test_mcp_tool.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-gen/tests/test_mcp_tool.py
"""The MCP tool is a thin wrapper around jw_gen.cli's `_run` plumbing.

We test the wrapper directly so this test stays inside the jw-gen package
(no jw-mcp test path needed). The same callable shape is used in
packages/jw-mcp/src/jw_mcp/server.py.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from jw_gen.factory import get_provider
from jw_gen.models import GenerationRequest
from jw_gen.policy import finalize_output
from jw_gen.safety import evaluate


def generate_illustration_mcp(
    prompt: str,
    kind: str = "image",
    size: str = "1024x1024",
    watermark: bool = True,
    lang: str = "es",
    out_dir: Path | None = None,
) -> dict[str, str]:
    """Functional shape that the MCP server registers as `generate_illustration`.

    Note: `watermark=False` is silently coerced to True over MCP — a client
    cannot bypass policy. To get metadata-only output the user must run the
    local CLI with `--no-visible-watermark`.
    """

    # SECURITY: MCP NEVER allows watermark off.
    _ = watermark  # silently ignored
    request = GenerationRequest(prompt=prompt, kind=kind, lang=lang, size=size)  # type: ignore[arg-type]
    decision = evaluate(request)
    if not decision.allow:
        return {"error": decision.reason or "safety.refuse.logo"}
    provider = get_provider(kind)  # type: ignore[arg-type]
    augmented = request.model_copy(update={"prompt": decision.augmented_prompt or prompt})
    raw = provider.generate(augmented)
    dest = (out_dir or raw.parent) / f"mcp_{raw.stem}.png"
    result = finalize_output(raw_path=raw, request=request, dest=dest, provider=provider.name)
    return {
        "output_path": str(result.output_path),
        "disclaimer_path": str(result.disclaimer_path),
        "audit_id": result.audit_id,
        "provider": result.provider,
    }


def test_mcp_tool_smoke(
    tmp_path: Path, isolated_jw_gen_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("JW_GEN_IMAGE_PROVIDER", "fake")
    res = generate_illustration_mcp(
        prompt="ovejas pastoreadas",
        kind="image",
        lang="es",
        out_dir=tmp_path,
    )
    assert "output_path" in res
    assert Path(res["output_path"]).exists()
    assert Path(res["disclaimer_path"]).exists()


def test_mcp_tool_refuses_logo(
    tmp_path: Path, isolated_jw_gen_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("JW_GEN_IMAGE_PROVIDER", "fake")
    res = generate_illustration_mcp(
        prompt="watchtower logo blue",
        kind="image",
        lang="en",
        out_dir=tmp_path,
    )
    assert res.get("error") == "safety.refuse.logo"


def test_mcp_tool_silently_ignores_watermark_false(
    tmp_path: Path, isolated_jw_gen_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Even with watermark=False, output goes through policy.finalize_output, which writes visible+metadata."""

    monkeypatch.setenv("JW_GEN_IMAGE_PROVIDER", "fake")
    res = generate_illustration_mcp(
        prompt="amanecer suave",
        kind="image",
        watermark=False,  # MCP must NOT respect this
        lang="es",
        out_dir=tmp_path,
    )
    assert Path(res["disclaimer_path"]).exists()
```

- [ ] **Step 2: Register the tool in jw-mcp's server.py**

Add at the bottom of `packages/jw-mcp/src/jw_mcp/server.py`:

```python
from pathlib import Path

from jw_gen.factory import get_provider as _jwgen_get_provider
from jw_gen.models import GenerationRequest as _JwGenRequest
from jw_gen.policy import finalize_output as _jwgen_finalize
from jw_gen.safety import evaluate as _jwgen_safety_evaluate


@mcp.tool()
def generate_illustration(
    prompt: str,
    kind: str = "image",
    size: str = "1024x1024",
    watermark: bool = True,
    lang: str = "es",
) -> dict[str, str]:
    """Generate a personal-use illustrative file (image / audio / video).

    The output is always watermarked + EXIF/XMP-tagged + accompanied by a
    sibling .disclaimer.txt. `watermark=False` is silently ignored over MCP —
    use the local CLI with `--no-visible-watermark` if you need metadata-only.
    """

    _ = watermark  # not respected over MCP — policy is non-negotiable here
    request = _JwGenRequest(prompt=prompt, kind=kind, lang=lang, size=size)  # type: ignore[arg-type]
    decision = _jwgen_safety_evaluate(request)
    if not decision.allow:
        return {"error": decision.reason or "safety.refuse.logo"}
    provider = _jwgen_get_provider(kind)  # type: ignore[arg-type]
    augmented = request.model_copy(update={"prompt": decision.augmented_prompt or prompt})
    raw = provider.generate(augmented)
    dest = Path(raw).parent / f"mcp_{Path(raw).stem}.png"
    result = _jwgen_finalize(raw_path=raw, request=request, dest=dest, provider=provider.name)
    return {
        "output_path": str(result.output_path),
        "disclaimer_path": str(result.disclaimer_path),
        "audit_id": result.audit_id,
        "provider": result.provider,
    }
```

Add `"jw-gen"` to `packages/jw-mcp/pyproject.toml`'s `[project].dependencies`.

- [ ] **Step 3: Run test to verify it passes**

Run: `uv run pytest packages/jw-gen/tests/test_mcp_tool.py -v`
Expected: 3 passed.

- [ ] **Step 4: Commit**

```bash
git add packages/jw-mcp packages/jw-gen/tests/test_mcp_tool.py
git commit -m "feat(jw-gen): MCP tool generate_illustration (watermark=False silently ignored)"
```

---

### Task 15: Prompt templates (en / es / pt)

**Files:**
- Create: `packages/jw-gen/src/jw_gen/prompts/slide_template.md`
- Create: `packages/jw-gen/src/jw_gen/prompts/illustration_template.md`
- Create: `packages/jw-gen/src/jw_gen/prompts/bg_audio_template.md`

- [ ] **Step 1: Create the slide template**

```markdown
# Slide illustration template

## ES
"Genera una ilustración para diapositiva de [tema]. Estilo: ilustración suave, paleta cálida,
composición horizontal 16:9, dejando espacio en el tercio inferior para texto. No incluir logos,
letreros ni texto. Personas, si aparecen, en estilo pictórico, no fotorrealista."

## EN
"Generate a slide illustration about [topic]. Style: soft illustration, warm palette, 16:9
horizontal composition, leaving the lower third clear for text. No logos, signs, or text. People,
if present, in painterly style, not photorealistic."

## PT
"Gere uma ilustração para slide sobre [tema]. Estilo: ilustração suave, paleta quente, composição
horizontal 16:9, deixando o terço inferior livre para texto. Sem logos, placas ou texto. Pessoas,
se presentes, em estilo pictórico, não fotorrealista."
```

- [ ] **Step 2: Create the illustration template**

```markdown
# Educational illustration template

## ES
"Ilustración educativa de [escena]. Composición clara, fondo neutro, sin texto sobre la imagen.
Estilo pintura suave. Sin logos, emblemas ni letreros oficiales."

## EN
"Educational illustration of [scene]. Clear composition, neutral background, no text on the
image. Soft painting style. No logos, emblems, or official signs."

## PT
"Ilustração educativa de [cena]. Composição clara, fundo neutro, sem texto na imagem.
Estilo pintura suave. Sem logos, emblemas nem placas oficiais."
```

- [ ] **Step 3: Create the bg audio template**

```markdown
# Background audio template

## ES
"Música ambiental instrumental, suave, sin voz, [duración] segundos. Tonalidad cálida, no
melódica explícita, apropiada como fondo para presentación."

## EN
"Instrumental ambient music, soft, no vocals, [duration] seconds. Warm tonality, no explicit
melody, suitable as background for a presentation."

## PT
"Música ambiente instrumental, suave, sem voz, [duração] segundos. Tonalidade quente, sem
melodia explícita, apropriada como fundo de apresentação."
```

- [ ] **Step 4: Commit**

```bash
git add packages/jw-gen/src/jw_gen/prompts
git commit -m "feat(jw-gen): trilingual prompt templates (slide / illustration / bg-audio)"
```

---

### Task 16: CI job `gen-policy`

**Files:**
- Modify: `.github/workflows/ci.yml`

- [ ] **Step 1: Append the new job**

```yaml
gen-policy:
  needs: test
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4
    - uses: astral-sh/setup-uv@v3
    - run: uv sync --all-packages
    - name: jw-gen unit tests (offline)
      run: uv run pytest packages/jw-gen/tests -v -m "not network"
    - name: Property test — 100 adversarial prompts → 0 allowed
      run: uv run pytest packages/jw-gen/tests/test_safety_property.py -v
    - name: Smoke — output always carries watermark + disclaimer
      run: uv run pytest packages/jw-gen/tests/test_policy.py -v -k "finalize"
    - name: CLI smoke — fake image succeeds, fake logo prompt fails
      env:
        JW_GEN_IMAGE_PROVIDER: fake
        JW_GEN_HOME: /tmp/jw-gen-ci
      run: |
        uv run jw gen image --prompt "ovejas pastoreadas" --out /tmp/ok.png
        test -f /tmp/ok.png
        test -f /tmp/ok.png.disclaimer.txt
        ! uv run jw gen image --prompt "watchtower logo blue" --out /tmp/bad.png
        ! test -f /tmp/bad.png
```

- [ ] **Step 2: Validate locally**

```bash
act -j gen-policy   # if `act` available; otherwise:
uv run pytest packages/jw-gen/tests -v
```

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci(jw-gen): add gen-policy job — offline, property-test, CLI smoke"
```

---

### Task 17: Documentation and VISION_AUDIT row

**Files:**
- Create: `docs/guias/generacion-ilustrativa.md`
- Modify: `docs/VISION_AUDIT.md`
- Modify: `docs/ROADMAP.md`

- [ ] **Step 1: Write the guide**

```markdown
# Generación ilustrativa con `jw-gen`

> **Política aprobada por el usuario (LOAD-BEARING):**
> "Solo personal/ilustrativo + presentaciones/discursos. Watermark obligatorio.
>  NO emulación contenido oficial JW."

## Qué hace y qué no hace

`jw-gen` genera **imágenes, audio y video ilustrativos para uso personal** (presentaciones
familiares, discursos públicos, repaso). Cada archivo escrito a disco lleva:
- Watermark visible + EXIF/XMP, ó al menos EXIF/XMP si se desactiva el visible.
- Disclaimer hermano `*.disclaimer.txt` en es / en / pt.
- Entrada en `~/.jw-gen/audit.log` con timestamp + hash del prompt.

`jw-gen` **no**:
- Distribuye pesos de modelos generativos.
- Publica automáticamente en jw.org ni redes.
- Emula logos, emblemas o identidad gráfica de Watchtower / Awake! / jw.org / Kingdom Hall.
- Clona voces de hermanos sin doble opt-in firmado.
- Genera rostros fotorrealistas por defecto.

## Uso típico

```bash
# Imagen ilustrativa para un slide.
jw gen image --prompt "ovejas pastoreadas en una colina al atardecer" --out slide_01.png

# Audio de fondo para un slide de oración.
jw gen audio --prompt "música suave instrumental 30s" --out bg.wav

# Video corto de transición.
jw gen video --prompt "amanecer simbólico" --duration 6 --out transition.mp4
```

## Flags de seguridad

| Flag | Efecto |
|---|---|
| `--no-visible-watermark` | Mantiene EXIF/XMP+disclaimer, retira el watermark visible. Loguea audit. |
| `--realistic-people` | Salta el sufijo anti-realismo. Loguea audit. |
| `--voice-clone --input voz.wav` | Requiere `voz.wav.consent.txt` firmado + confirmación. |

## Lista de keywords bloqueadas

Ver `packages/jw-gen/src/jw_gen/i18n/{en,es,pt}.json` clave `logo_keywords`. Cualquier prompt
que contenga estas frases (normalizadas: sin acentos, minúsculas) o cualquier brand-word JW
junto a "logo / emblema / oficial" dentro de ±3 tokens es rechazado.

## Ejemplo de consent file para voice clone

```
voice_owner: Hermano Juan
date: 2026-05-31
purpose: ensayar discurso público antes de darlo en vivo
signature_sha256: <sha256 de las 3 líneas anteriores, sin la 4ª>
```

El hash se calcula sobre el texto literal `"voice_owner: ...\ndate: ...\npurpose: ...\n"`.
```

- [ ] **Step 2: Add row to VISION_AUDIT.md**

Append:

```markdown
| 38 | jw-gen | Generación ilustrativa con policy + safety LOAD-BEARING | Política aprobada: "Solo personal/ilustrativo + presentaciones/discursos. Watermark obligatorio. NO emulación contenido oficial JW." Implementada en `packages/jw-gen/src/jw_gen/{policy,safety,i18n}.py`. Property test de 100 prompts adversarios en CI. | ✅ |
```

- [ ] **Step 3: Add ROADMAP entry**

```markdown
## Fase 38 — jw-gen (séptimo paquete)

Generación ilustrativa para uso personal con tres safety filters y policy
fail-closed. Spec: `docs/superpowers/specs/2026-05-31-fase-38-jw-gen-design.md`.
Plan: `docs/superpowers/plans/2026-05-31-fase-38-jw-gen-plan.md`.
```

- [ ] **Step 4: Commit**

```bash
git add docs/guias/generacion-ilustrativa.md docs/VISION_AUDIT.md docs/ROADMAP.md
git commit -m "docs(jw-gen): user guide + VISION_AUDIT row + ROADMAP entry"
```

---

### Task 18: Final verification — no regressions, full coverage

- [ ] **Step 1: Full test run**

```bash
uv sync --all-packages
uv run pytest -v --tb=short
```

Expected: previous 1649+ tests + new jw-gen tests, ALL PASS.

- [ ] **Step 2: Coverage on policy + safety**

```bash
uv run pytest packages/jw-gen/tests --cov=jw_gen --cov-report=term-missing
```

Expected: `policy.py` ≥95%, `safety.py` ≥95%, package overall ≥85%.

- [ ] **Step 3: Manual smoke**

```bash
export JW_GEN_IMAGE_PROVIDER=fake
uv run jw gen image --prompt "ilustración pacífica" --out /tmp/smoke.png
ls /tmp/smoke.png /tmp/smoke.png.disclaimer.txt
cat ~/.jw-gen/audit.log | tail -1 | jq .
```

Expected: png exists, disclaimer exists, audit log has matching JSONL row.

- [ ] **Step 4: Adversarial smoke**

```bash
uv run jw gen image --prompt "watchtower logo blue" --out /tmp/bad.png
# Expected: exit code != 0, /tmp/bad.png absent.
```

- [ ] **Step 5: Lint + types**

```bash
uv run ruff check packages/jw-gen
uv run mypy packages/jw-gen/src
```

Expected: clean.

- [ ] **Step 6: Final commit + log**

```bash
git log --oneline -20
```

Expected: 18 ordered commits matching this plan's tasks.

---

## Self-review

**Spec compliance (LOAD-BEARING policy):**
- [x] Every output passes through `finalize_output` (Task 7, fail-closed).
- [x] Watermark visible + EXIF/XMP + disclaimer enforced; failure of any step deletes the dest (Task 7, tests in `test_policy.py`).
- [x] `refuse_jw_logo_emulation` runs before provider; property test 100 prompts (Tasks 5 + 6).
- [x] Voice clone requires flag + signed consent file + interactive confirm (Task 5, tests).
- [x] Realistic faces default-augmented; `--realistic-people` opt-in (Task 5).
- [x] Audit log JSONL append-only, prompt only as hash (Task 4).
- [x] MCP tool silently ignores `watermark=False` (Task 14).
- [x] All providers have deterministic fakes; tests run offline (Tasks 8, 10, 11, 12).
- [x] Workspace registered, `jw gen` CLI subcommand, MCP tool (Tasks 1, 13, 14).
- [x] CI `gen-policy` job (Task 16) — offline, property test included.
- [x] Multi-idioma en/es/pt for disclaimers, errors, keyword block, prompt suffix (Task 3).
- [x] Doc + audit row + ROADMAP entry (Task 17).

**Reviewed risks:**
- The PIL XMP-as-tEXt-fallback is intentionally minimal; real XMP via `python-xmp-toolkit` is an optional extra (`[xmp]`). Tests check for `jw-gen` substring presence, not full XMP parsing.
- Voice-clone confirmation uses `typer.prompt` in CLI; in MCP we don't expose voice clone at all (only image is exposed in v1) — that's stricter than the spec and we accept it.
- Provider adapters (NanoBanana / ElevenLabs / Veo3) have NO unit tests of their own; their correctness is covered by the factory tests (env + availability) and by the live `pytest-recording` cassettes added in a follow-up (Fase 38.1).

**Tests added:** 51+ (models 10, i18n 10, audit 5, safety 14, safety-property 105+, policy 9, providers-fake 5, factory 5, cli 4, mcp 3).
**Tasks total:** 18.

## Execution choice

Recommend **`superpowers:subagent-driven-development`** because:
- 18 task boundaries with explicit RED→GREEN cycle per task.
- Each task is small enough for a fresh subagent context.
- Property test (Task 6) and policy fail-closed (Task 7) benefit from clean reasoning.

Fallback: `superpowers:executing-plans` if working in a single conversation.
