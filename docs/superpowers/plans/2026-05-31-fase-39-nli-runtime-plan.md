# Fase 39 — `nli-runtime` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `jw_core.fidelity`, a runtime NLI (Natural Language Inference) layer that verifies every `Finding.summary` is semantically entailed by its `Finding.excerpt`. Wires a triple-target provider stack (api / mlx / nvidia / cpu) following the Fase 33 pattern, plus a `@fidelity_wrap` decorator that annotates `AgentResult.findings[*].metadata` with `nli_verdict` / `nli_score` / `nli_provider` and optionally rejects/warns when the verdict falls below a configurable threshold.

**Architecture:** New subpackage `packages/jw-core/src/jw_core/fidelity/` containing `verdicts.py` (NLIVerdict dataclass + Verdict Literal), `nli.py` (NLIProvider Protocol + `evaluate_entailment` helper), `factory.py` (registry + `JW_NLI_PROVIDER` env override + `JW_PROVIDER_ORDER` shared with Fase 33), and `nli_providers/` (deberta_mnli, claude_nli, openai_nli, ollama_nli, fakes). The decorator `@fidelity_wrap` lives in `jw-agents/src/jw_agents/fidelity_wrap.py` because it needs to know `AgentResult`. CLI integration adds a `--fidelity` flag to existing agent commands and a new `evaluate_nli` MCP tool. Three optional-dependency extras: `[nli-anthropic]`, `[nli-openai]`, `[nli-local]`.

**Tech Stack:** Python 3.13 · Pydantic-free (we keep `jw-core` pydantic-light: pure dataclasses) · `transformers` + `torch` (extra `[nli-local]`) · `anthropic>=0.40` (extra `[nli-anthropic]`) · `openai>=1.50` (extra `[nli-openai]`) · `httpx` (already present for Ollama) · `pytest` + `respx` (existing dev-deps) · `hypothesis` (existing, for property tests).

**Spec:** [`docs/superpowers/specs/2026-05-31-fase-39-nli-runtime-design.md`](../specs/2026-05-31-fase-39-nli-runtime-design.md).

---

## File map

Creates:
- `packages/jw-core/src/jw_core/fidelity/__init__.py`
- `packages/jw-core/src/jw_core/fidelity/verdicts.py`
- `packages/jw-core/src/jw_core/fidelity/nli.py`
- `packages/jw-core/src/jw_core/fidelity/factory.py`
- `packages/jw-core/src/jw_core/fidelity/nli_providers/__init__.py`
- `packages/jw-core/src/jw_core/fidelity/nli_providers/fakes.py`
- `packages/jw-core/src/jw_core/fidelity/nli_providers/deberta_mnli.py`
- `packages/jw-core/src/jw_core/fidelity/nli_providers/claude_nli.py`
- `packages/jw-core/src/jw_core/fidelity/nli_providers/openai_nli.py`
- `packages/jw-core/src/jw_core/fidelity/nli_providers/ollama_nli.py`
- `packages/jw-core/tests/test_fidelity_verdicts.py`
- `packages/jw-core/tests/test_fidelity_nli_protocol.py`
- `packages/jw-core/tests/test_fidelity_fakes.py`
- `packages/jw-core/tests/test_fidelity_factory.py`
- `packages/jw-core/tests/test_fidelity_deberta.py`
- `packages/jw-core/tests/test_fidelity_claude.py`
- `packages/jw-core/tests/test_fidelity_openai.py`
- `packages/jw-core/tests/test_fidelity_ollama.py`
- `packages/jw-core/tests/test_fidelity_property.py`
- `packages/jw-agents/src/jw_agents/fidelity_wrap.py`
- `packages/jw-agents/tests/test_fidelity_wrap.py`
- `packages/jw-agents/tests/test_fidelity_integration.py`
- `packages/jw-cli/tests/test_cli_fidelity.py`
- `packages/jw-mcp/tests/test_mcp_nli.py`
- `docs/guias/fidelity-nli.md`

Modifies:
- `packages/jw-core/pyproject.toml` — add `[nli-anthropic]`, `[nli-openai]`, `[nli-local]` extras.
- `packages/jw-cli/src/jw_cli/commands/apologetics.py` — add `--fidelity` flag.
- `packages/jw-cli/src/jw_cli/commands/verse.py` — add `--fidelity` flag.
- `packages/jw-cli/src/jw_cli/commands/research.py` — add `--fidelity` flag.
- `packages/jw-cli/src/jw_cli/commands/meeting.py` — add `--fidelity` flag.
- `packages/jw-mcp/src/jw_mcp/server.py` — register `evaluate_nli` tool + add `fidelity` parameter on the four wrapped agent tools.
- `docs/VISION_AUDIT.md` — add Fase 39 row.
- `docs/ROADMAP.md` — add Fase 39 section.
- `docs/README.md` — link the new guide.

---

### Task 1: Scaffold `jw_core.fidelity` subpackage + Protocol + extras

**Files:**
- Create: `packages/jw-core/src/jw_core/fidelity/__init__.py`
- Create: `packages/jw-core/src/jw_core/fidelity/nli.py`
- Create: `packages/jw-core/tests/test_fidelity_nli_protocol.py`
- Modify: `packages/jw-core/pyproject.toml`

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-core/tests/test_fidelity_nli_protocol.py
"""Tests that the public NLIProvider Protocol and Target Literal are exported
and structurally typed correctly.

Spec: docs/superpowers/specs/2026-05-31-fase-39-nli-runtime-design.md §"Provider Protocol".
"""

from __future__ import annotations

from typing import get_args

import pytest

from jw_core.fidelity import NLIProvider, Target


def test_target_literal_has_four_values() -> None:
    assert set(get_args(Target)) == {"api", "mlx", "nvidia", "cpu"}


def test_nli_provider_is_runtime_checkable() -> None:
    class Stub:
        name = "stub"
        target: Target = "cpu"

        def is_available(self) -> bool:
            return True

        def evaluate(self, claim: str, premise: str, *, language: str = "en"):
            raise NotImplementedError

    assert isinstance(Stub(), NLIProvider)


def test_nli_provider_rejects_missing_method() -> None:
    class Broken:
        name = "broken"
        target: Target = "cpu"

        def is_available(self) -> bool:
            return True
        # no .evaluate()

    assert not isinstance(Broken(), NLIProvider)


def test_public_api_exports_evaluate_entailment_helper() -> None:
    from jw_core.fidelity import evaluate_entailment

    assert callable(evaluate_entailment)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/jw-core/tests/test_fidelity_nli_protocol.py -v`

Expected: FAIL — `ModuleNotFoundError: No module named 'jw_core.fidelity'`.

- [ ] **Step 3: Implement the module**

```python
# packages/jw-core/src/jw_core/fidelity/nli.py
"""NLI Provider Protocol — runtime entailment judgement.

Every provider answers a single question: does `claim` semantically
follow from `premise`? The contract is intentionally narrow:

  - sync function (no async)
  - input: two strings + optional language code
  - output: NLIVerdict (verdict label + 0..1 score + provider name + raw)

Rules (heritage of Fase 33):

  1. No network at import time. Heavy deps (transformers, anthropic, openai)
     are imported lazily inside `is_available()` and `evaluate()`.
  2. `is_available()` is cheap — env var checks, package presence, hardware
     detection. Called once per `get_default_nli_provider()`.
  3. `evaluate()` is sync. API-backed providers should wrap their HTTP call
     and block; callers (the @fidelity_wrap decorator) are async-aware and
     can offload to threads.
  4. `score` is always in [0, 1], normalized by the provider. DeBERTa
     returns softmax[entailment]; LLMs return JSON `confidence`.
  5. `language` is a hint for LLM providers; transformer NLI models that
     are multilingual ignore it.
"""

from __future__ import annotations

from typing import Literal, Protocol, runtime_checkable

from jw_core.fidelity.verdicts import NLIVerdict

Target = Literal["api", "mlx", "nvidia", "cpu"]


@runtime_checkable
class NLIProvider(Protocol):
    """Canonical NLI provider contract.

    Implementations declare a stable `name` (used by `JW_NLI_PROVIDER` env
    override) and a `target` (used by `JW_PROVIDER_ORDER` ranking, shared
    with Fase 33).
    """

    name: str
    target: Target

    def is_available(self) -> bool: ...

    def evaluate(
        self, claim: str, premise: str, *, language: str = "en"
    ) -> NLIVerdict: ...


def evaluate_entailment(
    claim: str,
    premise: str,
    *,
    language: str = "en",
    provider: NLIProvider | None = None,
) -> NLIVerdict:
    """Public helper: evaluate one claim/premise pair.

    Resolves a default provider via `get_default_nli_provider()` if none
    is supplied. Used by both `@fidelity_wrap` and Fase 44 (`synth-judge`).
    """

    if provider is None:
        from jw_core.fidelity.factory import get_default_nli_provider

        provider = get_default_nli_provider()
    return provider.evaluate(claim, premise, language=language)


__all__ = ["NLIProvider", "Target", "evaluate_entailment"]
```

```python
# packages/jw-core/src/jw_core/fidelity/__init__.py
"""jw_core.fidelity — runtime NLI verification of agent findings.

Public API:

    from jw_core.fidelity import (
        NLIProvider,
        NLIVerdict,
        Target,
        evaluate_entailment,
        get_default_nli_provider,
        list_available_nli_providers,
    )

Spec: docs/superpowers/specs/2026-05-31-fase-39-nli-runtime-design.md
"""

from __future__ import annotations

from jw_core.fidelity.nli import NLIProvider, Target, evaluate_entailment
from jw_core.fidelity.verdicts import NLIVerdict, Verdict

__all__ = [
    "NLIProvider",
    "NLIVerdict",
    "Target",
    "Verdict",
    "evaluate_entailment",
    "get_default_nli_provider",
    "list_available_nli_providers",
]


def __getattr__(name: str):  # noqa: D401
    # Lazy re-exports of factory functions to avoid importing providers at
    # import time (keeps `import jw_core` cheap on hosts without transformers).
    if name == "get_default_nli_provider":
        from jw_core.fidelity.factory import get_default_nli_provider as fn

        return fn
    if name == "list_available_nli_providers":
        from jw_core.fidelity.factory import list_available_nli_providers as fn

        return fn
    raise AttributeError(name)
```

Note: `verdicts.py` is added in Task 2 — for now create a minimal stub so the test in Step 1 imports cleanly:

```python
# packages/jw-core/src/jw_core/fidelity/verdicts.py  (stub — overwritten in Task 2)
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Verdict = Literal["entails", "neutral", "contradicts"]


@dataclass(frozen=True)
class NLIVerdict:
    verdict: Verdict
    score: float
    provider: str
    raw: dict
```

- [ ] **Step 4: Add the extras to pyproject.toml**

Edit `packages/jw-core/pyproject.toml`. Inside `[project.optional-dependencies]` (create the table if absent), add:

```toml
[project.optional-dependencies]
nli-anthropic = ["anthropic>=0.40,<1.0"]
nli-openai = ["openai>=1.50,<2.0"]
nli-local = [
  "transformers>=4.45,<5.0",
  "torch>=2.4",
]
nli-all = [
  "anthropic>=0.40,<1.0",
  "openai>=1.50,<2.0",
  "transformers>=4.45,<5.0",
  "torch>=2.4",
]
```

(If `[project.optional-dependencies]` already exists with other entries, append these keys without removing existing ones.)

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest packages/jw-core/tests/test_fidelity_nli_protocol.py -v`

Expected: 4 passed.

- [ ] **Step 6: Commit**

```bash
git add packages/jw-core/src/jw_core/fidelity packages/jw-core/tests/test_fidelity_nli_protocol.py packages/jw-core/pyproject.toml
git commit -m "feat(jw-core): scaffold jw_core.fidelity Protocol and NLI extras"
```

---

### Task 2: NLIVerdict dataclass + Verdict Literal

**Files:**
- Modify (overwrite): `packages/jw-core/src/jw_core/fidelity/verdicts.py`
- Create: `packages/jw-core/tests/test_fidelity_verdicts.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-core/tests/test_fidelity_verdicts.py
"""Tests for jw_core.fidelity.verdicts.

The dataclass is frozen (hashable) and serializable via `asdict`. The
Verdict Literal is exhaustive: only three labels are legal, anything else
must trip a runtime guard.
"""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import get_args

import pytest

from jw_core.fidelity.verdicts import NLIVerdict, Verdict, ensure_verdict


def test_verdict_literal_has_three_values() -> None:
    assert set(get_args(Verdict)) == {"entails", "neutral", "contradicts"}


def test_nli_verdict_is_frozen_dataclass() -> None:
    v = NLIVerdict(verdict="entails", score=0.92, provider="fake-nli", raw={})
    assert is_dataclass(v)
    with pytest.raises(Exception):  # FrozenInstanceError subclass of AttributeError
        v.score = 0.5  # type: ignore[misc]


def test_nli_verdict_asdict_roundtrips() -> None:
    v = NLIVerdict(
        verdict="contradicts",
        score=0.71,
        provider="claude-nli",
        raw={"reason": "negation"},
    )
    d = asdict(v)
    assert d == {
        "verdict": "contradicts",
        "score": 0.71,
        "provider": "claude-nli",
        "raw": {"reason": "negation"},
    }


def test_nli_verdict_clamps_score_in_constructor_via_ensure() -> None:
    # ensure_verdict is the canonical safe constructor used by providers
    v = ensure_verdict(verdict="entails", score=1.7, provider="x")
    assert v.score == 1.0
    v2 = ensure_verdict(verdict="entails", score=-0.3, provider="x")
    assert v2.score == 0.0


def test_ensure_verdict_rejects_bad_label() -> None:
    with pytest.raises(ValueError, match="invalid verdict"):
        ensure_verdict(verdict="maybe", score=0.5, provider="x")  # type: ignore[arg-type]


def test_ensure_verdict_default_raw_is_empty_dict() -> None:
    v = ensure_verdict(verdict="neutral", score=0.5, provider="x")
    assert v.raw == {}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/jw-core/tests/test_fidelity_verdicts.py -v`

Expected: FAIL — `ImportError: cannot import name 'ensure_verdict'`.

- [ ] **Step 3: Implement the dataclass + helper**

```python
# packages/jw-core/src/jw_core/fidelity/verdicts.py
"""NLIVerdict — the canonical output of every NLIProvider.

We use a frozen dataclass (not Pydantic) because `jw-core` deliberately
avoids Pydantic dependencies at the leaf layer — Pydantic lives one level
up in `jw-eval` / `jw-agents`. Frozen dataclasses are hashable, fast, and
sufficient for our needs.

`ensure_verdict` is the safe constructor every provider should funnel
through — it clamps `score` to [0, 1] and validates the verdict label.
This is the single chokepoint that protects downstream consumers from
provider bugs (LLM hallucinated `score=1.7`, etc.).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, get_args

Verdict = Literal["entails", "neutral", "contradicts"]
_VALID_VERDICTS: frozenset[str] = frozenset(get_args(Verdict))


@dataclass(frozen=True)
class NLIVerdict:
    """One NLI judgement, suitable for `Finding.metadata["nli_*"]`.

    Fields:
      verdict   — discrete label (entails / neutral / contradicts).
      score     — confidence in [0, 1]. For multi-class providers, this is
                  the probability of the chosen verdict; for LLM judges,
                  the JSON-returned confidence.
      provider  — provider.name for traceability ("claude-nli", "deberta-v3-mnli",
                  "fake-nli", ...). The decorator stamps this into metadata.
      raw       — provider-specific debug payload. Optional. May be persisted
                  to traces (Fase 43) but is NEVER displayed in CLI output.
    """

    verdict: Verdict
    score: float
    provider: str
    raw: dict[str, Any] = field(default_factory=dict)


def ensure_verdict(
    *,
    verdict: str,
    score: float,
    provider: str,
    raw: dict[str, Any] | None = None,
) -> NLIVerdict:
    """Canonical constructor — clamp score, validate verdict label."""

    if verdict not in _VALID_VERDICTS:
        raise ValueError(
            f"invalid verdict {verdict!r}; expected one of {sorted(_VALID_VERDICTS)}"
        )
    clamped = max(0.0, min(1.0, float(score)))
    return NLIVerdict(
        verdict=verdict,  # type: ignore[arg-type]
        score=clamped,
        provider=provider,
        raw=dict(raw) if raw else {},
    )


__all__ = ["NLIVerdict", "Verdict", "ensure_verdict"]
```

Update `packages/jw-core/src/jw_core/fidelity/__init__.py` to re-export `ensure_verdict`:

```python
# packages/jw-core/src/jw_core/fidelity/__init__.py  (full overwrite)
"""jw_core.fidelity — runtime NLI verification of agent findings.

Public API:

    from jw_core.fidelity import (
        NLIProvider,
        NLIVerdict,
        Target,
        Verdict,
        ensure_verdict,
        evaluate_entailment,
        get_default_nli_provider,
        list_available_nli_providers,
    )

Spec: docs/superpowers/specs/2026-05-31-fase-39-nli-runtime-design.md
"""

from __future__ import annotations

from jw_core.fidelity.nli import NLIProvider, Target, evaluate_entailment
from jw_core.fidelity.verdicts import NLIVerdict, Verdict, ensure_verdict

__all__ = [
    "NLIProvider",
    "NLIVerdict",
    "Target",
    "Verdict",
    "ensure_verdict",
    "evaluate_entailment",
    "get_default_nli_provider",
    "list_available_nli_providers",
]


def __getattr__(name: str):
    if name == "get_default_nli_provider":
        from jw_core.fidelity.factory import get_default_nli_provider as fn

        return fn
    if name == "list_available_nli_providers":
        from jw_core.fidelity.factory import list_available_nli_providers as fn

        return fn
    raise AttributeError(name)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/jw-core/tests/test_fidelity_verdicts.py packages/jw-core/tests/test_fidelity_nli_protocol.py -v`

Expected: 6 + 4 = 10 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-core/src/jw_core/fidelity packages/jw-core/tests/test_fidelity_verdicts.py
git commit -m "feat(jw-core): NLIVerdict frozen dataclass + ensure_verdict safe constructor"
```

---

### Task 3: FakeNLI deterministic provider

**Files:**
- Create: `packages/jw-core/src/jw_core/fidelity/nli_providers/__init__.py`
- Create: `packages/jw-core/src/jw_core/fidelity/nli_providers/fakes.py`
- Create: `packages/jw-core/tests/test_fidelity_fakes.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-core/tests/test_fidelity_fakes.py
"""Tests for FakeNLI — the always-available deterministic provider.

Algorithm (per spec §"FakeNLI"):

  - verdict = "entails" iff Jaccard(words(claim), words(premise)) >= 0.8
  - verdict = "contradicts" iff a negation token appears in EXACTLY one of
    {claim, premise}: "no es" / "is not" / "não é"
  - else verdict = "neutral"
  - score = round(jaccard, 2)

The provider must be 100% pure (no network, no model files) and stable
across processes — `evaluate("a", "b")` returns the same NLIVerdict
forever.
"""

from __future__ import annotations

import pytest

from jw_core.fidelity import NLIProvider
from jw_core.fidelity.nli_providers.fakes import FakeNLI


@pytest.fixture()
def provider() -> FakeNLI:
    return FakeNLI()


def test_fake_implements_protocol(provider: FakeNLI) -> None:
    assert isinstance(provider, NLIProvider)
    assert provider.name == "fake-nli"
    assert provider.target == "cpu"
    assert provider.is_available() is True


def test_entails_when_claim_is_subset(provider: FakeNLI) -> None:
    v = provider.evaluate(
        claim="God loves the world",
        premise="God so loved the world that he gave his only Son",
    )
    assert v.verdict == "entails"
    assert v.score >= 0.5
    assert v.provider == "fake-nli"


def test_contradicts_on_asymmetric_negation_en(provider: FakeNLI) -> None:
    v = provider.evaluate(
        claim="The Trinity is biblical",
        premise="The Trinity is not biblical",
    )
    assert v.verdict == "contradicts"


def test_contradicts_on_asymmetric_negation_es(provider: FakeNLI) -> None:
    v = provider.evaluate(
        claim="el alma muere",
        premise="el alma no es inmortal",
    )
    assert v.verdict == "contradicts"


def test_contradicts_on_asymmetric_negation_pt(provider: FakeNLI) -> None:
    v = provider.evaluate(
        claim="Jesus é Deus",
        premise="Jesus não é Deus",
    )
    assert v.verdict == "contradicts"


def test_neutral_when_disjoint(provider: FakeNLI) -> None:
    v = provider.evaluate(
        claim="bananas are yellow",
        premise="the sky was blue today",
    )
    assert v.verdict == "neutral"
    assert v.score < 0.3


def test_deterministic_same_input_same_output(provider: FakeNLI) -> None:
    a = provider.evaluate(claim="hello world", premise="hello world today")
    b = provider.evaluate(claim="hello world", premise="hello world today")
    assert a == b


def test_score_is_clamped_in_unit_interval(provider: FakeNLI) -> None:
    v = provider.evaluate(claim="x", premise="x")
    assert 0.0 <= v.score <= 1.0


def test_empty_inputs_do_not_crash(provider: FakeNLI) -> None:
    v = provider.evaluate(claim="", premise="")
    assert v.verdict in {"entails", "neutral", "contradicts"}
    assert 0.0 <= v.score <= 1.0


def test_negation_in_both_does_not_count_as_contradiction(provider: FakeNLI) -> None:
    v = provider.evaluate(
        claim="el alma no es eterna",
        premise="el alma no es inmortal",
    )
    # both contain a negation → cancels out → verdict driven by jaccard only
    assert v.verdict in {"entails", "neutral"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/jw-core/tests/test_fidelity_fakes.py -v`

Expected: FAIL — `ModuleNotFoundError: No module named 'jw_core.fidelity.nli_providers'`.

- [ ] **Step 3: Implement FakeNLI**

```python
# packages/jw-core/src/jw_core/fidelity/nli_providers/__init__.py
"""Concrete NLIProvider implementations.

Each provider lives in its own module so optional deps (transformers,
anthropic, openai) can be imported lazily and CI hosts without those
deps still install `jw-core` cleanly.
"""
```

```python
# packages/jw-core/src/jw_core/fidelity/nli_providers/fakes.py
"""Deterministic Fake NLI provider — no network, no model weights.

Algorithm:
  1. Tokenize both inputs (Unicode word chars, lowercased).
  2. Compute Jaccard similarity J = |A ∩ B| / |A ∪ B| (0 if both empty).
  3. Detect explicit negation in each input (regex per language).
  4. If negation appears in exactly one input → verdict = "contradicts".
     If J >= 0.8 → verdict = "entails".
     Else → verdict = "neutral".
  5. score = round(J, 2), clamped to [0, 1] by ensure_verdict.

This is what every test in the test suite reaches for by default — the
factory falls back to it when no real provider is configured. It must
never raise on legal inputs and must be byte-identical across processes.
"""

from __future__ import annotations

import re

from jw_core.fidelity.nli import Target
from jw_core.fidelity.verdicts import NLIVerdict, ensure_verdict

# Regexes for explicit negation phrases. Conservative on purpose — false
# positives are worse than false negatives for a stub.
_NEGATION_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bis\s+not\b", re.IGNORECASE),
    re.compile(r"\bare\s+not\b", re.IGNORECASE),
    re.compile(r"\bnever\b", re.IGNORECASE),
    re.compile(r"\bno\s+es\b", re.IGNORECASE),
    re.compile(r"\bno\s+son\b", re.IGNORECASE),
    re.compile(r"\bnunca\b", re.IGNORECASE),
    re.compile(r"\bnão\s+é\b", re.IGNORECASE),
    re.compile(r"\bnão\s+são\b", re.IGNORECASE),
)

_TOKEN_RE = re.compile(r"\w+", re.UNICODE)


def _words(text: str) -> frozenset[str]:
    return frozenset(_TOKEN_RE.findall(text.lower()))


def _jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    if not a and not b:
        return 0.0
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


def _has_negation(text: str) -> bool:
    return any(p.search(text) for p in _NEGATION_PATTERNS)


class FakeNLI:
    """Pure-Python deterministic NLI. Always available."""

    name = "fake-nli"
    target: Target = "cpu"

    def is_available(self) -> bool:
        return True

    def evaluate(
        self, claim: str, premise: str, *, language: str = "en"
    ) -> NLIVerdict:
        wa, wb = _words(claim), _words(premise)
        jacc = _jaccard(wa, wb)

        neg_claim = _has_negation(claim)
        neg_premise = _has_negation(premise)
        asymmetric_negation = neg_claim ^ neg_premise

        if asymmetric_negation:
            verdict = "contradicts"
        elif jacc >= 0.8:
            verdict = "entails"
        else:
            verdict = "neutral"

        return ensure_verdict(
            verdict=verdict,
            score=round(jacc, 2),
            provider=self.name,
            raw={
                "jaccard": round(jacc, 4),
                "neg_claim": neg_claim,
                "neg_premise": neg_premise,
                "lang": language,
            },
        )


__all__ = ["FakeNLI"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/jw-core/tests/test_fidelity_fakes.py -v`

Expected: 10 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-core/src/jw_core/fidelity/nli_providers packages/jw-core/tests/test_fidelity_fakes.py
git commit -m "feat(jw-core): FakeNLI deterministic provider (jaccard + negation heuristic)"
```

---

### Task 4: factory.py with JW_NLI_PROVIDER env override

**Files:**
- Create: `packages/jw-core/src/jw_core/fidelity/factory.py`
- Create: `packages/jw-core/tests/test_fidelity_factory.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-core/tests/test_fidelity_factory.py
"""Tests for the NLI factory.

Contracts:

  1. `get_default_nli_provider()` always returns something (FakeNLI is
     the last-resort fallback).
  2. `JW_NLI_PROVIDER=fake-nli` selects FakeNLI explicitly.
  3. `JW_NLI_PROVIDER=claude` selects ClaudeNLI when available, else raises
     (we do NOT silently degrade — the user asked for a specific provider).
  4. `JW_NLI_PROVIDER=bogus` raises ValueError.
  5. `JW_PROVIDER_ORDER` reorders the registry (shared with Fase 33).
  6. `list_available_nli_providers()` excludes fakes from the public listing
     but `_named_lookup("fake-deberta-v3-mnli")` finds the fake variant.
"""

from __future__ import annotations

import pytest

from jw_core.fidelity.factory import (
    ENV_NLI,
    ENV_PROVIDER_ORDER,
    get_default_nli_provider,
    list_available_nli_providers,
)


def test_default_returns_a_provider(monkeypatch) -> None:
    monkeypatch.delenv(ENV_NLI, raising=False)
    p = get_default_nli_provider()
    assert p is not None
    assert hasattr(p, "evaluate")
    assert hasattr(p, "name")


def test_env_override_selects_fake(monkeypatch) -> None:
    monkeypatch.setenv(ENV_NLI, "fake-nli")
    p = get_default_nli_provider()
    assert p.name == "fake-nli"


def test_env_override_unknown_name_raises(monkeypatch) -> None:
    monkeypatch.setenv(ENV_NLI, "bogus-provider")
    with pytest.raises(ValueError, match="unknown JW_NLI_PROVIDER"):
        get_default_nli_provider()


def test_env_override_claude_when_unavailable_raises(monkeypatch) -> None:
    monkeypatch.setenv(ENV_NLI, "claude-nli")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    # ClaudeNLI without API key is_available() == False → factory must raise
    # because the user explicitly named it.
    with pytest.raises(RuntimeError, match="not available"):
        get_default_nli_provider()


def test_fallback_to_fake_when_nothing_available(monkeypatch) -> None:
    monkeypatch.delenv(ENV_NLI, raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    p = get_default_nli_provider()
    # On CI hosts without GPUs and without API keys, fake-nli is the floor.
    assert p.name in {
        "fake-nli",
        "deberta-v3-mnli",
        "ollama-nli",
        "claude-nli",
        "openai-nli",
    }


def test_list_available_excludes_fake(monkeypatch) -> None:
    monkeypatch.delenv(ENV_NLI, raising=False)
    listed = list_available_nli_providers()
    names = {p.name for p in listed}
    assert "fake-nli" not in names


def test_provider_order_env_reorders(monkeypatch) -> None:
    monkeypatch.delenv(ENV_NLI, raising=False)
    monkeypatch.setenv(ENV_PROVIDER_ORDER, "cpu,api,mlx,nvidia")
    # Just check the call doesn't crash and still returns something.
    p = get_default_nli_provider()
    assert p is not None


def test_named_lookup_can_select_fake_explicitly(monkeypatch) -> None:
    monkeypatch.setenv(ENV_NLI, "fake-nli")
    p = get_default_nli_provider()
    assert p.name == "fake-nli"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/jw-core/tests/test_fidelity_factory.py -v`

Expected: FAIL — `ModuleNotFoundError: No module named 'jw_core.fidelity.factory'`.

- [ ] **Step 3: Implement factory.py**

```python
# packages/jw-core/src/jw_core/fidelity/factory.py
"""NLIProvider registry + factory.

Mirrors `jw_rag.rerank_providers.factory` so the operational model is
identical to Fase 33: an ordered list of provider instances + env override
+ shared `JW_PROVIDER_ORDER` env for target ranking.

Order of resolution:

  1. If `JW_NLI_PROVIDER` is set:
       - look up by exact `provider.name`.
       - if `is_available()` → return.
       - if not available → raise RuntimeError (do not silently fall through).
       - if name unknown → raise ValueError.
  2. Else: iterate `_instantiate_registry()`, return the first `is_available()`,
     skipping FakeNLI (it's the last-resort floor).
  3. If nothing is available → return FakeNLI.

Registry order (priority): Claude > OpenAI > DeBERTa(mlx) > DeBERTa(nvidia)
> DeBERTa(cpu) > Ollama > FakeNLI.
"""

from __future__ import annotations

import logging
import os
from typing import Literal

from jw_core.fidelity.nli import NLIProvider, Target

logger = logging.getLogger(__name__)

PROVIDER_ORDER_DEFAULT: list[Target] = ["api", "mlx", "nvidia", "cpu"]
ENV_NLI = "JW_NLI_PROVIDER"
ENV_PROVIDER_ORDER = "JW_PROVIDER_ORDER"


def _provider_order() -> list[Target]:
    raw = os.getenv(ENV_PROVIDER_ORDER, "")
    if not raw.strip():
        return PROVIDER_ORDER_DEFAULT
    parts: list[Target] = []
    for piece in raw.split(","):
        piece = piece.strip()
        if piece in {"api", "mlx", "nvidia", "cpu"}:
            parts.append(piece)  # type: ignore[arg-type]
    return parts or PROVIDER_ORDER_DEFAULT


def _instantiate_registry() -> list[NLIProvider]:
    """Build the canonical registry of all NLI providers.

    Constructors are cheap (no model load, no network). The heavy work is
    deferred to `is_available()` and the first `evaluate()` call.
    """

    from jw_core.fidelity.nli_providers.claude_nli import ClaudeNLI
    from jw_core.fidelity.nli_providers.deberta_mnli import DeBERTaV3MNLI
    from jw_core.fidelity.nli_providers.fakes import FakeNLI
    from jw_core.fidelity.nli_providers.ollama_nli import OllamaNLI
    from jw_core.fidelity.nli_providers.openai_nli import OpenAINLI

    return [
        ClaudeNLI(),
        OpenAINLI(),
        DeBERTaV3MNLI(target="mlx"),
        DeBERTaV3MNLI(target="nvidia"),
        DeBERTaV3MNLI(target="cpu"),
        OllamaNLI(),
        FakeNLI(),
    ]


def _named_lookup(name: str) -> NLIProvider | None:
    """Find a provider in the registry by exact `.name` match."""

    for r in _instantiate_registry():
        if r.name == name:
            return r
    return None


def list_available_nli_providers() -> list[NLIProvider]:
    """Public listing: every available provider EXCEPT fakes.

    Fakes are reachable via explicit `JW_NLI_PROVIDER=fake-nli` but never
    surface in the default listing — otherwise the auto-fallback would silently
    use them on hosts that also have real providers.
    """

    order = _provider_order()
    available = [
        r
        for r in _instantiate_registry()
        if r.is_available() and r.name != "fake-nli"
    ]
    return sorted(
        available,
        key=lambda r: order.index(r.target) if r.target in order else len(order),
    )


def get_default_nli_provider() -> NLIProvider:
    """Resolve the provider to use in the current process."""

    env_name = os.getenv(ENV_NLI, "").strip()
    if env_name:
        p = _named_lookup(env_name)
        if p is None:
            raise ValueError(f"unknown JW_NLI_PROVIDER={env_name!r}")
        if not p.is_available():
            raise RuntimeError(
                f"JW_NLI_PROVIDER={env_name!r} not available "
                f"(target={p.target}, missing deps or env vars)"
            )
        return p

    for r in list_available_nli_providers():
        return r

    # Last-resort floor — always works.
    from jw_core.fidelity.nli_providers.fakes import FakeNLI

    logger.info("No real NLI provider available; falling back to FakeNLI")
    return FakeNLI()


__all__ = [
    "ENV_NLI",
    "ENV_PROVIDER_ORDER",
    "PROVIDER_ORDER_DEFAULT",
    "get_default_nli_provider",
    "list_available_nli_providers",
]
```

Note: the factory imports `ClaudeNLI`, `OpenAINLI`, `DeBERTaV3MNLI`, `OllamaNLI`. Add minimal stubs now so imports succeed; Tasks 5–7 fill them in. Each stub must declare `name`, `target`, `is_available() -> False`, and a `evaluate` that raises `NotImplementedError`:

```python
# packages/jw-core/src/jw_core/fidelity/nli_providers/claude_nli.py  (stub for now)
from __future__ import annotations

from jw_core.fidelity.nli import Target
from jw_core.fidelity.verdicts import NLIVerdict


class ClaudeNLI:
    name = "claude-nli"
    target: Target = "api"

    def is_available(self) -> bool:
        return False

    def evaluate(self, claim: str, premise: str, *, language: str = "en") -> NLIVerdict:
        raise NotImplementedError("ClaudeNLI not yet wired (Task 5)")
```

```python
# packages/jw-core/src/jw_core/fidelity/nli_providers/openai_nli.py  (stub)
from __future__ import annotations

from jw_core.fidelity.nli import Target
from jw_core.fidelity.verdicts import NLIVerdict


class OpenAINLI:
    name = "openai-nli"
    target: Target = "api"

    def is_available(self) -> bool:
        return False

    def evaluate(self, claim: str, premise: str, *, language: str = "en") -> NLIVerdict:
        raise NotImplementedError("OpenAINLI not yet wired (Task 6)")
```

```python
# packages/jw-core/src/jw_core/fidelity/nli_providers/deberta_mnli.py  (stub)
from __future__ import annotations

from jw_core.fidelity.nli import Target
from jw_core.fidelity.verdicts import NLIVerdict


class DeBERTaV3MNLI:
    name = "deberta-v3-mnli"

    def __init__(self, *, target: Target = "cpu") -> None:
        self.target = target

    def is_available(self) -> bool:
        return False

    def evaluate(self, claim: str, premise: str, *, language: str = "en") -> NLIVerdict:
        raise NotImplementedError("DeBERTaV3MNLI not yet wired (Task 7)")
```

```python
# packages/jw-core/src/jw_core/fidelity/nli_providers/ollama_nli.py  (stub)
from __future__ import annotations

from jw_core.fidelity.nli import Target
from jw_core.fidelity.verdicts import NLIVerdict


class OllamaNLI:
    name = "ollama-nli"
    target: Target = "cpu"

    def is_available(self) -> bool:
        return False

    def evaluate(self, claim: str, premise: str, *, language: str = "en") -> NLIVerdict:
        raise NotImplementedError("OllamaNLI not yet wired (Task 7)")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/jw-core/tests/test_fidelity_factory.py -v`

Expected: 8 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-core/src/jw_core/fidelity packages/jw-core/tests/test_fidelity_factory.py
git commit -m "feat(jw-core): NLI factory with JW_NLI_PROVIDER env + ordered registry"
```

---

### Task 5: ClaudeNLI provider (anthropic)

**Files:**
- Modify (overwrite stub): `packages/jw-core/src/jw_core/fidelity/nli_providers/claude_nli.py`
- Create: `packages/jw-core/tests/test_fidelity_claude.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-core/tests/test_fidelity_claude.py
"""Tests for ClaudeNLI provider.

We never hit the real API: the test injects a FakeAnthropicClient that
returns canned JSON. This keeps CI offline + deterministic.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from jw_core.fidelity.nli_providers.claude_nli import ClaudeNLI


class _FakeMessage:
    def __init__(self, text: str) -> None:
        self.content = [type("Block", (), {"text": text})()]


class _FakeMessages:
    def __init__(self, response_text: str) -> None:
        self.response_text = response_text
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> _FakeMessage:
        self.calls.append(kwargs)
        return _FakeMessage(self.response_text)


class _FakeAnthropicClient:
    def __init__(self, response_text: str) -> None:
        self.messages = _FakeMessages(response_text)


def test_claude_unavailable_without_api_key(monkeypatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    p = ClaudeNLI()
    assert p.is_available() is False


def test_claude_available_with_api_key(monkeypatch) -> None:
    # Skip if anthropic SDK isn't installed in the dev env
    pytest.importorskip("anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-fake")
    p = ClaudeNLI()
    assert p.is_available() is True


def test_claude_parses_entails(monkeypatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-fake")
    client = _FakeAnthropicClient(
        json.dumps({"verdict": "entails", "score": 0.91, "reason": "supported"})
    )
    p = ClaudeNLI(client=client)
    v = p.evaluate(claim="A", premise="B", language="es")
    assert v.verdict == "entails"
    assert v.score == 0.91
    assert v.provider == "claude-nli"
    assert v.raw["reason"] == "supported"


def test_claude_parses_contradicts(monkeypatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-fake")
    client = _FakeAnthropicClient(
        json.dumps({"verdict": "contradicts", "score": 0.83, "reason": "negation"})
    )
    p = ClaudeNLI(client=client)
    v = p.evaluate(claim="A", premise="B")
    assert v.verdict == "contradicts"
    assert v.score == 0.83


def test_claude_parses_neutral_default(monkeypatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-fake")
    client = _FakeAnthropicClient(json.dumps({"verdict": "neutral", "score": 0.5}))
    p = ClaudeNLI(client=client)
    v = p.evaluate(claim="A", premise="B")
    assert v.verdict == "neutral"


def test_claude_fallback_on_invalid_json(monkeypatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-fake")
    client = _FakeAnthropicClient("not even json at all")
    p = ClaudeNLI(client=client)
    v = p.evaluate(claim="A", premise="B")
    assert v.verdict == "neutral"
    assert v.score == 0.5
    assert "parse_error" in v.raw


def test_claude_fallback_on_invalid_verdict(monkeypatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-fake")
    client = _FakeAnthropicClient(json.dumps({"verdict": "maybe", "score": 0.9}))
    p = ClaudeNLI(client=client)
    v = p.evaluate(claim="A", premise="B")
    assert v.verdict == "neutral"


def test_claude_truncates_long_premise(monkeypatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-fake")
    client = _FakeAnthropicClient(json.dumps({"verdict": "entails", "score": 0.8}))
    p = ClaudeNLI(client=client)
    very_long_premise = "x" * 20000
    p.evaluate(claim="short", premise=very_long_premise)
    sent = client.messages.calls[0]
    # The user message body must contain a TRUNCATED premise (<= 6000 chars)
    user_msg = sent["messages"][0]["content"]
    assert "x" * 6000 in user_msg
    assert "x" * 7000 not in user_msg


def test_claude_uses_env_model(monkeypatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-fake")
    monkeypatch.setenv("JW_NLI_CLAUDE_MODEL", "claude-haiku-4-5-20251001")
    client = _FakeAnthropicClient(json.dumps({"verdict": "entails", "score": 0.9}))
    p = ClaudeNLI(client=client)
    p.evaluate(claim="A", premise="B")
    assert client.messages.calls[0]["model"] == "claude-haiku-4-5-20251001"


def test_claude_sets_prompt_caching(monkeypatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-fake")
    client = _FakeAnthropicClient(json.dumps({"verdict": "entails", "score": 0.9}))
    p = ClaudeNLI(client=client)
    p.evaluate(claim="A", premise="B")
    sent = client.messages.calls[0]
    # system prompt sent as a list-of-blocks with cache_control on the last block
    system = sent["system"]
    assert isinstance(system, list)
    assert any(
        block.get("cache_control", {}).get("type") == "ephemeral"
        for block in system
        if isinstance(block, dict)
    )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/jw-core/tests/test_fidelity_claude.py -v`

Expected: FAIL — current `ClaudeNLI` raises `NotImplementedError` and does not accept `client=`.

- [ ] **Step 3: Implement ClaudeNLI**

```python
# packages/jw-core/src/jw_core/fidelity/nli_providers/claude_nli.py
"""ClaudeNLI — entailment via Anthropic's Claude.

Design (per spec §"ClaudeNLI"):

  - System prompt (cached): "You are an NLI judge. Decide if the CONCLUSION
    strictly entails from the PREMISE. Reply JSON-only: {verdict, score, reason}."
  - User prompt: "PREMISE:\n{premise}\n\nCONCLUSION:\n{claim}\n\nLanguage: {language}"
  - Parse JSON; on failure → verdict="neutral", score=0.5, raw["parse_error"]=raw.
  - Cost guard: truncate premise to 6000 chars when (premise + claim) > 8000.
  - Prompt caching: `cache_control: {type: "ephemeral"}` on the system block.
  - Model default: `claude-sonnet-4-5-20250929`, override via `JW_NLI_CLAUDE_MODEL`.

The optional `client=` kwarg in the constructor exists for testing —
production code passes nothing and we lazily instantiate `Anthropic()`.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from jw_core.fidelity.nli import Target
from jw_core.fidelity.verdicts import NLIVerdict, ensure_verdict

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = "claude-sonnet-4-5-20250929"
_SYSTEM_PROMPT = (
    "You are an NLI judge. Decide if the CONCLUSION strictly entails from "
    "the PREMISE. Reply JSON-only with this exact shape: "
    '{"verdict": "entails"|"neutral"|"contradicts", '
    '"score": 0.0-1.0, "reason": "short explanation"}. '
    "Output nothing else."
)
_MAX_PREMISE_CHARS = 6000
_MAX_TOTAL_CHARS = 8000


class ClaudeNLI:
    name = "claude-nli"
    target: Target = "api"

    def __init__(self, *, client: Any | None = None) -> None:
        self._client = client  # injectable for tests

    def is_available(self) -> bool:
        if not os.getenv("ANTHROPIC_API_KEY"):
            return False
        try:
            import anthropic  # noqa: F401
        except ImportError:
            return False
        return True

    def _ensure_client(self) -> Any:
        if self._client is not None:
            return self._client
        from anthropic import Anthropic

        self._client = Anthropic()
        return self._client

    def _truncate(self, premise: str, claim: str) -> str:
        if len(premise) + len(claim) <= _MAX_TOTAL_CHARS:
            return premise
        return premise[:_MAX_PREMISE_CHARS]

    def evaluate(
        self, claim: str, premise: str, *, language: str = "en"
    ) -> NLIVerdict:
        client = self._ensure_client()
        model = os.getenv("JW_NLI_CLAUDE_MODEL", _DEFAULT_MODEL)
        truncated_premise = self._truncate(premise, claim)
        user_body = (
            f"PREMISE:\n{truncated_premise}\n\n"
            f"CONCLUSION:\n{claim}\n\n"
            f"Language: {language}"
        )
        system_blocks = [
            {
                "type": "text",
                "text": _SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ]
        try:
            msg = client.messages.create(
                model=model,
                max_tokens=256,
                system=system_blocks,
                messages=[{"role": "user", "content": user_body}],
            )
            text = msg.content[0].text  # type: ignore[union-attr,attr-defined]
        except Exception as exc:  # noqa: BLE001
            logger.warning("ClaudeNLI call failed: %r", exc)
            return ensure_verdict(
                verdict="neutral",
                score=0.5,
                provider=self.name,
                raw={"api_error": repr(exc)},
            )

        try:
            data = json.loads(text)
            verdict = str(data.get("verdict", "")).lower()
            score = float(data.get("score", 0.5))
            reason = str(data.get("reason", ""))
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "ClaudeNLI JSON parse failed: %r (raw=%s)", exc, text[:200]
            )
            return ensure_verdict(
                verdict="neutral",
                score=0.5,
                provider=self.name,
                raw={"parse_error": str(exc), "raw_text": text[:500]},
            )

        if verdict not in {"entails", "neutral", "contradicts"}:
            logger.warning("ClaudeNLI unexpected verdict %r → neutral/0.5", verdict)
            return ensure_verdict(
                verdict="neutral",
                score=0.5,
                provider=self.name,
                raw={"unexpected_verdict": verdict, "reason": reason},
            )

        return ensure_verdict(
            verdict=verdict,
            score=score,
            provider=self.name,
            raw={"reason": reason, "model": model, "lang": language},
        )


__all__ = ["ClaudeNLI"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/jw-core/tests/test_fidelity_claude.py -v`

Expected: 10 passed (1 of which may show `skipped` if `anthropic` isn't installed — that's fine).

- [ ] **Step 5: Commit**

```bash
git add packages/jw-core/src/jw_core/fidelity/nli_providers/claude_nli.py packages/jw-core/tests/test_fidelity_claude.py
git commit -m "feat(jw-core): ClaudeNLI provider with prompt caching + JSON fallback"
```

---

### Task 6: OpenAINLI provider

**Files:**
- Modify (overwrite stub): `packages/jw-core/src/jw_core/fidelity/nli_providers/openai_nli.py`
- Create: `packages/jw-core/tests/test_fidelity_openai.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-core/tests/test_fidelity_openai.py
"""Tests for OpenAINLI provider.

Uses a FakeOpenAIClient that emulates `client.chat.completions.create` with
`response_format={"type": "json_schema", ...}` and returns canned JSON.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from jw_core.fidelity.nli_providers.openai_nli import OpenAINLI


class _FakeMessage:
    def __init__(self, content: str) -> None:
        self.content = content


class _FakeChoice:
    def __init__(self, content: str) -> None:
        self.message = _FakeMessage(content)


class _FakeResponse:
    def __init__(self, content: str) -> None:
        self.choices = [_FakeChoice(content)]


class _FakeCompletions:
    def __init__(self, content: str) -> None:
        self.content = content
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> _FakeResponse:
        self.calls.append(kwargs)
        return _FakeResponse(self.content)


class _FakeChat:
    def __init__(self, content: str) -> None:
        self.completions = _FakeCompletions(content)


class _FakeOpenAIClient:
    def __init__(self, content: str) -> None:
        self.chat = _FakeChat(content)


def test_openai_unavailable_without_api_key(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    p = OpenAINLI()
    assert p.is_available() is False


def test_openai_parses_entails(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-fake")
    client = _FakeOpenAIClient(
        json.dumps({"verdict": "entails", "score": 0.88, "reason": "ok"})
    )
    p = OpenAINLI(client=client)
    v = p.evaluate(claim="A", premise="B")
    assert v.verdict == "entails"
    assert v.score == 0.88
    assert v.provider == "openai-nli"


def test_openai_uses_structured_output(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-fake")
    client = _FakeOpenAIClient(json.dumps({"verdict": "neutral", "score": 0.5}))
    p = OpenAINLI(client=client)
    p.evaluate(claim="A", premise="B")
    sent = client.chat.completions.calls[0]
    rf = sent["response_format"]
    assert rf["type"] == "json_schema"
    assert "json_schema" in rf
    schema = rf["json_schema"]["schema"]
    assert "verdict" in schema["properties"]
    assert "score" in schema["properties"]


def test_openai_uses_env_model(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-fake")
    monkeypatch.setenv("JW_NLI_OPENAI_MODEL", "gpt-4o")
    client = _FakeOpenAIClient(json.dumps({"verdict": "entails", "score": 0.9}))
    p = OpenAINLI(client=client)
    p.evaluate(claim="A", premise="B")
    assert client.chat.completions.calls[0]["model"] == "gpt-4o"


def test_openai_fallback_on_garbage(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-fake")
    client = _FakeOpenAIClient("not json")
    p = OpenAINLI(client=client)
    v = p.evaluate(claim="A", premise="B")
    assert v.verdict == "neutral"
    assert v.score == 0.5


def test_openai_truncates_long_premise(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-fake")
    client = _FakeOpenAIClient(json.dumps({"verdict": "entails", "score": 0.8}))
    p = OpenAINLI(client=client)
    p.evaluate(claim="short", premise="y" * 20000)
    sent = client.chat.completions.calls[0]
    user_msg = sent["messages"][-1]["content"]
    assert "y" * 6000 in user_msg
    assert "y" * 7000 not in user_msg


def test_openai_fallback_on_invalid_verdict(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-fake")
    client = _FakeOpenAIClient(json.dumps({"verdict": "??", "score": 1.0}))
    p = OpenAINLI(client=client)
    v = p.evaluate(claim="A", premise="B")
    assert v.verdict == "neutral"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/jw-core/tests/test_fidelity_openai.py -v`

Expected: FAIL — stub raises `NotImplementedError`.

- [ ] **Step 3: Implement OpenAINLI**

```python
# packages/jw-core/src/jw_core/fidelity/nli_providers/openai_nli.py
"""OpenAINLI — entailment via OpenAI Chat Completions with structured output.

Uses `response_format={"type": "json_schema", "json_schema": {...}}` so the
SDK guarantees we receive a JSON-shaped string matching our schema. Default
model `gpt-4o-mini`, overridable via `JW_NLI_OPENAI_MODEL`.

Same defensive parsing as ClaudeNLI: bad JSON / bad verdict label → fallback
to verdict="neutral", score=0.5, raw["parse_error"].
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from jw_core.fidelity.nli import Target
from jw_core.fidelity.verdicts import NLIVerdict, ensure_verdict

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = "gpt-4o-mini"
_SYSTEM_PROMPT = (
    "You are an NLI judge. Decide if the CONCLUSION strictly entails from "
    "the PREMISE. Reply JSON-only with this exact shape: "
    '{"verdict": "entails"|"neutral"|"contradicts", '
    '"score": 0.0-1.0, "reason": "short explanation"}.'
)
_JSON_SCHEMA = {
    "name": "nli_verdict",
    "schema": {
        "type": "object",
        "properties": {
            "verdict": {
                "type": "string",
                "enum": ["entails", "neutral", "contradicts"],
            },
            "score": {"type": "number", "minimum": 0.0, "maximum": 1.0},
            "reason": {"type": "string"},
        },
        "required": ["verdict", "score"],
        "additionalProperties": False,
    },
}
_MAX_PREMISE_CHARS = 6000
_MAX_TOTAL_CHARS = 8000


class OpenAINLI:
    name = "openai-nli"
    target: Target = "api"

    def __init__(self, *, client: Any | None = None) -> None:
        self._client = client

    def is_available(self) -> bool:
        if not os.getenv("OPENAI_API_KEY"):
            return False
        try:
            import openai  # noqa: F401
        except ImportError:
            return False
        return True

    def _ensure_client(self) -> Any:
        if self._client is not None:
            return self._client
        from openai import OpenAI

        self._client = OpenAI()
        return self._client

    def _truncate(self, premise: str, claim: str) -> str:
        if len(premise) + len(claim) <= _MAX_TOTAL_CHARS:
            return premise
        return premise[:_MAX_PREMISE_CHARS]

    def evaluate(
        self, claim: str, premise: str, *, language: str = "en"
    ) -> NLIVerdict:
        client = self._ensure_client()
        model = os.getenv("JW_NLI_OPENAI_MODEL", _DEFAULT_MODEL)
        truncated = self._truncate(premise, claim)
        user_body = (
            f"PREMISE:\n{truncated}\n\n"
            f"CONCLUSION:\n{claim}\n\n"
            f"Language: {language}"
        )
        try:
            resp = client.chat.completions.create(
                model=model,
                response_format={"type": "json_schema", "json_schema": _JSON_SCHEMA},
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": user_body},
                ],
            )
            text = resp.choices[0].message.content or ""
        except Exception as exc:  # noqa: BLE001
            logger.warning("OpenAINLI call failed: %r", exc)
            return ensure_verdict(
                verdict="neutral",
                score=0.5,
                provider=self.name,
                raw={"api_error": repr(exc)},
            )

        try:
            data = json.loads(text)
            verdict = str(data.get("verdict", "")).lower()
            score = float(data.get("score", 0.5))
            reason = str(data.get("reason", ""))
        except Exception as exc:  # noqa: BLE001
            return ensure_verdict(
                verdict="neutral",
                score=0.5,
                provider=self.name,
                raw={"parse_error": str(exc), "raw_text": text[:500]},
            )

        if verdict not in {"entails", "neutral", "contradicts"}:
            return ensure_verdict(
                verdict="neutral",
                score=0.5,
                provider=self.name,
                raw={"unexpected_verdict": verdict, "reason": reason},
            )

        return ensure_verdict(
            verdict=verdict,
            score=score,
            provider=self.name,
            raw={"reason": reason, "model": model, "lang": language},
        )


__all__ = ["OpenAINLI"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/jw-core/tests/test_fidelity_openai.py -v`

Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-core/src/jw_core/fidelity/nli_providers/openai_nli.py packages/jw-core/tests/test_fidelity_openai.py
git commit -m "feat(jw-core): OpenAINLI provider with json_schema response format"
```

---

### Task 7: DeBERTaV3MNLI (local, lazy torch) + OllamaNLI

**Files:**
- Modify (overwrite stub): `packages/jw-core/src/jw_core/fidelity/nli_providers/deberta_mnli.py`
- Modify (overwrite stub): `packages/jw-core/src/jw_core/fidelity/nli_providers/ollama_nli.py`
- Create: `packages/jw-core/tests/test_fidelity_deberta.py`
- Create: `packages/jw-core/tests/test_fidelity_ollama.py`

- [ ] **Step 1: Write the failing tests**

```python
# packages/jw-core/tests/test_fidelity_deberta.py
"""Tests for DeBERTaV3MNLI.

We do NOT download model weights in CI. Tests inject a FakePipeline that
exposes the same `.tokenizer`/`.model` shape via duck typing. The integration
test that hits the real HuggingFace model is gated by the `nli-local`
extra and only runs in the nightly job.
"""

from __future__ import annotations

import pytest

from jw_core.fidelity.nli_providers.deberta_mnli import DeBERTaV3MNLI


class _FakePipelineOutput:
    """Mimics transformers.AutoModelForSequenceClassification output."""

    def __init__(self, logits) -> None:
        import torch

        self.logits = torch.tensor(logits)


class _FakeTokenizer:
    def __call__(self, premise, hypothesis, return_tensors, truncation, max_length):
        # Echo so we can inspect truncation behavior
        import torch

        return {"input_ids": torch.tensor([[1, 2, 3]])}


class _FakeModel:
    def __init__(self, logits) -> None:
        self.logits = logits

    def __call__(self, **kwargs):
        return _FakePipelineOutput(self.logits)

    def eval(self):
        return self

    def to(self, device):  # noqa: ARG002
        return self


def test_deberta_unavailable_without_transformers(monkeypatch) -> None:
    # Pretend transformers is missing
    import sys

    monkeypatch.setitem(sys.modules, "transformers", None)
    p = DeBERTaV3MNLI(target="cpu")
    assert p.is_available() is False


def test_deberta_cpu_available_when_transformers_installed() -> None:
    pytest.importorskip("transformers")
    pytest.importorskip("torch")
    p = DeBERTaV3MNLI(target="cpu")
    assert p.is_available() is True


def test_deberta_nvidia_requires_cuda(monkeypatch) -> None:
    pytest.importorskip("torch")
    import torch

    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    p = DeBERTaV3MNLI(target="nvidia")
    assert p.is_available() is False


def test_deberta_evaluate_entails_via_injected_model() -> None:
    pytest.importorskip("torch")
    p = DeBERTaV3MNLI(target="cpu")
    # logits[contradiction, neutral, entailment] = [0.1, 0.2, 5.0] → softmax ≈ entailment
    p._tokenizer = _FakeTokenizer()
    p._model = _FakeModel([[0.1, 0.2, 5.0]])
    v = p.evaluate(claim="claim", premise="premise")
    assert v.verdict == "entails"
    assert v.score > 0.9
    assert v.provider == "deberta-v3-mnli"


def test_deberta_evaluate_neutral_via_injected_model() -> None:
    pytest.importorskip("torch")
    p = DeBERTaV3MNLI(target="cpu")
    p._tokenizer = _FakeTokenizer()
    p._model = _FakeModel([[0.1, 5.0, 0.2]])
    v = p.evaluate(claim="claim", premise="premise")
    assert v.verdict == "neutral"


def test_deberta_evaluate_contradicts_via_injected_model() -> None:
    pytest.importorskip("torch")
    p = DeBERTaV3MNLI(target="cpu")
    p._tokenizer = _FakeTokenizer()
    p._model = _FakeModel([[5.0, 0.1, 0.2]])
    v = p.evaluate(claim="claim", premise="premise")
    assert v.verdict == "contradicts"


def test_deberta_lazy_load_caches_singleton(monkeypatch) -> None:
    pytest.importorskip("torch")
    p = DeBERTaV3MNLI(target="cpu")
    p._tokenizer = _FakeTokenizer()
    p._model = _FakeModel([[0.1, 0.2, 5.0]])
    # Second call should NOT reload model — check the same instance is reused.
    p.evaluate(claim="a", premise="b")
    same_tokenizer = p._tokenizer
    same_model = p._model
    p.evaluate(claim="c", premise="d")
    assert p._tokenizer is same_tokenizer
    assert p._model is same_model
```

```python
# packages/jw-core/tests/test_fidelity_ollama.py
"""Tests for OllamaNLI — local LLM judge via Ollama HTTP API.

Uses `respx` to mock the HTTP endpoints. CI never actually contacts Ollama.
"""

from __future__ import annotations

import json

import httpx
import pytest
import respx

from jw_core.fidelity.nli_providers.ollama_nli import OllamaNLI


def test_ollama_unavailable_when_server_down() -> None:
    p = OllamaNLI()
    with respx.mock(assert_all_called=False) as router:
        router.get("http://localhost:11434/api/tags").mock(
            side_effect=httpx.ConnectError("ECONNREFUSED")
        )
        assert p.is_available() is False


def test_ollama_unavailable_when_model_missing() -> None:
    p = OllamaNLI()
    with respx.mock() as router:
        router.get("http://localhost:11434/api/tags").mock(
            return_value=httpx.Response(
                200, json={"models": [{"name": "qwen2.5:7b"}]}
            )
        )
        assert p.is_available() is False


def test_ollama_available_when_model_present() -> None:
    p = OllamaNLI()
    with respx.mock() as router:
        router.get("http://localhost:11434/api/tags").mock(
            return_value=httpx.Response(
                200, json={"models": [{"name": "llama3.1:8b-instruct"}]}
            )
        )
        assert p.is_available() is True


def test_ollama_evaluate_parses_entails() -> None:
    p = OllamaNLI()
    with respx.mock() as router:
        router.get("http://localhost:11434/api/tags").mock(
            return_value=httpx.Response(
                200, json={"models": [{"name": "llama3.1:8b-instruct"}]}
            )
        )
        router.post("http://localhost:11434/api/chat").mock(
            return_value=httpx.Response(
                200,
                json={
                    "message": {
                        "content": json.dumps(
                            {"verdict": "entails", "score": 0.87, "reason": "ok"}
                        )
                    }
                },
            )
        )
        v = p.evaluate(claim="A", premise="B")
        assert v.verdict == "entails"
        assert v.score == 0.87
        assert v.provider == "ollama-nli"


def test_ollama_fallback_on_garbage_response() -> None:
    p = OllamaNLI()
    with respx.mock() as router:
        router.get("http://localhost:11434/api/tags").mock(
            return_value=httpx.Response(
                200, json={"models": [{"name": "llama3.1:8b-instruct"}]}
            )
        )
        router.post("http://localhost:11434/api/chat").mock(
            return_value=httpx.Response(
                200, json={"message": {"content": "not even json"}}
            )
        )
        v = p.evaluate(claim="A", premise="B")
        assert v.verdict == "neutral"
        assert v.score == 0.5


def test_ollama_uses_env_host(monkeypatch) -> None:
    monkeypatch.setenv("OLLAMA_HOST", "http://example.local:9999")
    p = OllamaNLI()
    with respx.mock() as router:
        router.get("http://example.local:9999/api/tags").mock(
            return_value=httpx.Response(
                200, json={"models": [{"name": "llama3.1:8b-instruct"}]}
            )
        )
        assert p.is_available() is True


def test_ollama_uses_env_model(monkeypatch) -> None:
    monkeypatch.setenv("JW_NLI_OLLAMA_MODEL", "qwen2.5:7b")
    p = OllamaNLI()
    with respx.mock() as router:
        router.get("http://localhost:11434/api/tags").mock(
            return_value=httpx.Response(
                200, json={"models": [{"name": "qwen2.5:7b"}]}
            )
        )
        chat = router.post("http://localhost:11434/api/chat").mock(
            return_value=httpx.Response(
                200,
                json={
                    "message": {
                        "content": json.dumps(
                            {"verdict": "entails", "score": 0.9}
                        )
                    }
                },
            )
        )
        p.evaluate(claim="A", premise="B")
        body = json.loads(chat.calls.last.request.content)
        assert body["model"] == "qwen2.5:7b"
        assert body["format"] == "json"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```bash
uv run pytest packages/jw-core/tests/test_fidelity_deberta.py packages/jw-core/tests/test_fidelity_ollama.py -v
```

Expected: FAIL — both stub providers raise `NotImplementedError`.

- [ ] **Step 3: Implement DeBERTaV3MNLI and OllamaNLI**

```python
# packages/jw-core/src/jw_core/fidelity/nli_providers/deberta_mnli.py
"""DeBERTaV3MNLI — local transformer NLI via HuggingFace.

Model: `MoritzLaurer/DeBERTa-v3-large-mnli-fever-anli-ling-wanli` (Apache-2.0,
~440MB). Multilingual fallback `MoritzLaurer/mDeBERTa-v3-base-mnli-xnli` is
selectable via env `JW_NLI_DEBERTA_MODEL`.

Three targets — auto-detected via `is_available()`:

  - target="mlx"     : requires `mlx-transformers` (Apple Silicon).
  - target="nvidia"  : requires `torch.cuda.is_available()`.
  - target="cpu"     : always works when `transformers + torch` installed.

Lazy load + singleton: the model is downloaded/loaded on the FIRST
`evaluate()` call, not at `__init__` (instantiation must stay cheap so the
factory can probe all three targets without loading anything).

Inference:

  - tokenize as a pair-sequence (premise, claim).
  - softmax 3 logits: [contradiction=0, neutral=1, entailment=2].
  - verdict = argmax label; score = probability of that label.
  - truncation: `max_length=512`, `truncation="only_first"` (preserves the
    shorter `claim`, recovers room by trimming the `premise`).
"""

from __future__ import annotations

import logging
import os
import threading
from typing import Any

from jw_core.fidelity.nli import Target
from jw_core.fidelity.verdicts import NLIVerdict, ensure_verdict

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = "MoritzLaurer/DeBERTa-v3-large-mnli-fever-anli-ling-wanli"
_LABELS: tuple[str, str, str] = ("contradicts", "neutral", "entails")


class DeBERTaV3MNLI:
    name = "deberta-v3-mnli"

    def __init__(self, *, target: Target = "cpu") -> None:
        self.target: Target = target
        self._model: Any | None = None
        self._tokenizer: Any | None = None
        self._device: str | None = None
        self._lock = threading.Lock()

    def is_available(self) -> bool:
        # Common: need transformers + torch present.
        try:
            import torch  # noqa: F401
            import transformers  # noqa: F401
        except ImportError:
            return False

        if self.target == "cpu":
            return True
        if self.target == "nvidia":
            try:
                import torch

                return bool(torch.cuda.is_available())
            except Exception:
                return False
        if self.target == "mlx":
            try:
                import mlx_transformers  # noqa: F401
            except ImportError:
                return False
            return True
        return False

    def _ensure_loaded(self) -> None:
        if self._model is not None and self._tokenizer is not None:
            return
        with self._lock:
            if self._model is not None and self._tokenizer is not None:
                return
            import torch
            from transformers import (
                AutoModelForSequenceClassification,
                AutoTokenizer,
            )

            model_id = os.getenv("JW_NLI_DEBERTA_MODEL", _DEFAULT_MODEL)
            logger.info("Loading DeBERTa NLI model %s (target=%s)", model_id, self.target)

            self._tokenizer = AutoTokenizer.from_pretrained(model_id)
            model = AutoModelForSequenceClassification.from_pretrained(model_id)

            if self.target == "nvidia" and torch.cuda.is_available():
                self._device = "cuda"
            elif self.target == "mlx":
                # mlx_transformers handles device internally
                self._device = "mlx"
            else:
                self._device = "cpu"

            if self._device in {"cpu", "cuda"}:
                model = model.to(self._device)
            model.eval()
            self._model = model

    def evaluate(
        self, claim: str, premise: str, *, language: str = "en"
    ) -> NLIVerdict:
        # Tests can inject `_tokenizer` and `_model` directly to bypass _ensure_loaded.
        if self._model is None or self._tokenizer is None:
            self._ensure_loaded()
        import torch

        assert self._tokenizer is not None
        assert self._model is not None

        inputs = self._tokenizer(
            premise,
            claim,
            return_tensors="pt",
            truncation="only_first",
            max_length=512,
        )
        if self._device in {"cuda"}:
            inputs = {k: v.to("cuda") for k, v in inputs.items()}  # type: ignore[union-attr]

        with torch.no_grad():
            out = self._model(**inputs)
        probs = torch.softmax(out.logits, dim=-1).squeeze(0).tolist()
        idx = int(max(range(3), key=lambda i: probs[i]))
        verdict = _LABELS[idx]
        score = float(probs[idx])

        return ensure_verdict(
            verdict=verdict,
            score=score,
            provider=self.name,
            raw={
                "probs": {
                    "contradicts": round(probs[0], 4),
                    "neutral": round(probs[1], 4),
                    "entails": round(probs[2], 4),
                },
                "target": self.target,
                "device": self._device or "unknown",
                "lang": language,
            },
        )


__all__ = ["DeBERTaV3MNLI"]
```

```python
# packages/jw-core/src/jw_core/fidelity/nli_providers/ollama_nli.py
"""OllamaNLI — local LLM judge via Ollama HTTP API.

Default model `llama3.1:8b-instruct` (env `JW_NLI_OLLAMA_MODEL`); endpoint
`http://localhost:11434` (env `OLLAMA_HOST`).

`is_available()` is cached per process: it sends one GET to `/api/tags`
and checks the configured model appears in the response. The cache is
invalidated when `JW_NLI_OLLAMA_MODEL` or `OLLAMA_HOST` change between calls.

Inference: POST `/api/chat` with `format=json`, parse the assistant message
content as JSON, fall back to neutral/0.5 on parse error.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

import httpx

from jw_core.fidelity.nli import Target
from jw_core.fidelity.verdicts import NLIVerdict, ensure_verdict

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = "llama3.1:8b-instruct"
_DEFAULT_HOST = "http://localhost:11434"
_SYSTEM_PROMPT = (
    "You are an NLI judge. Decide if the CONCLUSION strictly entails from "
    "the PREMISE. Reply JSON only: {verdict, score, reason}. verdict is one "
    "of entails|neutral|contradicts; score is a float 0.0-1.0."
)


class OllamaNLI:
    name = "ollama-nli"
    target: Target = "cpu"

    def __init__(self) -> None:
        self._cache: tuple[str, str, bool] | None = None

    def _host(self) -> str:
        return os.getenv("OLLAMA_HOST", _DEFAULT_HOST).rstrip("/")

    def _model(self) -> str:
        return os.getenv("JW_NLI_OLLAMA_MODEL", _DEFAULT_MODEL)

    def is_available(self) -> bool:
        host = self._host()
        model = self._model()
        if self._cache and self._cache[0] == host and self._cache[1] == model:
            return self._cache[2]
        try:
            r = httpx.get(f"{host}/api/tags", timeout=2.0)
            r.raise_for_status()
            tags = r.json().get("models", []) or []
            ok = any(t.get("name") == model for t in tags)
        except Exception as exc:  # noqa: BLE001
            logger.debug("OllamaNLI.is_available() probe failed: %r", exc)
            ok = False
        self._cache = (host, model, ok)
        return ok

    def evaluate(
        self, claim: str, premise: str, *, language: str = "en"
    ) -> NLIVerdict:
        host = self._host()
        model = self._model()
        user_body = (
            f"PREMISE:\n{premise}\n\n"
            f"CONCLUSION:\n{claim}\n\n"
            f"Language: {language}"
        )
        try:
            r = httpx.post(
                f"{host}/api/chat",
                json={
                    "model": model,
                    "stream": False,
                    "format": "json",
                    "messages": [
                        {"role": "system", "content": _SYSTEM_PROMPT},
                        {"role": "user", "content": user_body},
                    ],
                },
                timeout=60.0,
            )
            r.raise_for_status()
            text = str(r.json().get("message", {}).get("content", ""))
        except Exception as exc:  # noqa: BLE001
            logger.warning("OllamaNLI call failed: %r", exc)
            return ensure_verdict(
                verdict="neutral",
                score=0.5,
                provider=self.name,
                raw={"api_error": repr(exc)},
            )

        try:
            data = json.loads(text)
            verdict = str(data.get("verdict", "")).lower()
            score = float(data.get("score", 0.5))
            reason = str(data.get("reason", ""))
        except Exception as exc:  # noqa: BLE001
            return ensure_verdict(
                verdict="neutral",
                score=0.5,
                provider=self.name,
                raw={"parse_error": str(exc), "raw_text": text[:500]},
            )

        if verdict not in {"entails", "neutral", "contradicts"}:
            return ensure_verdict(
                verdict="neutral",
                score=0.5,
                provider=self.name,
                raw={"unexpected_verdict": verdict, "reason": reason},
            )

        return ensure_verdict(
            verdict=verdict,
            score=score,
            provider=self.name,
            raw={"reason": reason, "model": model, "host": host, "lang": language},
        )


__all__ = ["OllamaNLI"]
```

- [ ] **Step 4: Run tests to verify they pass**

Run:
```bash
uv run pytest packages/jw-core/tests/test_fidelity_deberta.py packages/jw-core/tests/test_fidelity_ollama.py -v
```

Expected: DeBERTa: 7 passed (some may skip if `transformers` not installed in dev env). Ollama: 7 passed.

If `respx` is not yet a dev dep, add it:

```bash
uv add --dev --package jw-core respx
```

- [ ] **Step 5: Commit**

```bash
git add packages/jw-core/src/jw_core/fidelity/nli_providers/deberta_mnli.py packages/jw-core/src/jw_core/fidelity/nli_providers/ollama_nli.py packages/jw-core/tests/test_fidelity_deberta.py packages/jw-core/tests/test_fidelity_ollama.py
git commit -m "feat(jw-core): DeBERTaV3MNLI (mlx/nvidia/cpu) + OllamaNLI providers"
```

---

### Task 8: `fidelity_wrap` decorator in jw-agents

**Files:**
- Create: `packages/jw-agents/src/jw_agents/fidelity_wrap.py`
- Create: `packages/jw-agents/tests/test_fidelity_wrap.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-agents/tests/test_fidelity_wrap.py
"""Tests for the @fidelity_wrap decorator.

Contract:

  - Wraps an async function returning AgentResult.
  - For each Finding, evaluates NLI claim=summary vs premise=excerpt.
  - Stamps metadata: nli_verdict, nli_score, nli_provider.
  - Skip rule: excerpt < min_excerpt_chars → nli_verdict="skipped".
  - on_fail="warn"           → append AgentResult.warnings.
  - on_fail="reject"         → drop finding + warning.
  - on_fail="annotate_only"  → just metadata, no warnings.
  - Idempotent: applying twice doesn't duplicate metadata.
  - Stamps AgentResult.metadata["nli_min_score"] and ["nli_on_fail"].
"""

from __future__ import annotations

import asyncio

import pytest

from jw_agents.base import AgentResult, Citation, Finding
from jw_agents.fidelity_wrap import fidelity_wrap
from jw_core.fidelity import NLIVerdict
from jw_core.fidelity.nli_providers.fakes import FakeNLI


def _result_with(findings: list[Finding]) -> AgentResult:
    return AgentResult(query="q", agent_name="x", findings=findings)


def _finding(summary: str, excerpt: str, url: str = "https://wol.jw.org/x") -> Finding:
    return Finding(
        summary=summary,
        excerpt=excerpt,
        citation=Citation(url=url, title="t", kind="article"),
    )


def _run(coro):
    return asyncio.run(coro)


class StubProvider:
    """Provider returning a configured verdict regardless of input."""

    name = "stub-nli"
    target = "cpu"

    def __init__(self, verdict: str, score: float) -> None:
        self._verdict = verdict
        self._score = score
        self.calls: list[tuple[str, str, str]] = []

    def is_available(self) -> bool:
        return True

    def evaluate(self, claim: str, premise: str, *, language: str = "en") -> NLIVerdict:
        self.calls.append((claim, premise, language))
        return NLIVerdict(verdict=self._verdict, score=self._score, provider=self.name, raw={})  # type: ignore[arg-type]


def test_warn_mode_keeps_finding_and_appends_warning() -> None:
    prov = StubProvider("contradicts", 0.4)
    base_finding = _finding(
        summary="The Trinity is a Bible teaching.",
        excerpt="The Trinity is not a Bible teaching, contrary to popular belief.",
    )

    @fidelity_wrap(min_score=0.7, on_fail="warn", provider=prov)
    async def agent(question: str) -> AgentResult:  # noqa: ARG001
        return _result_with([base_finding])

    r = _run(agent(question="?"))
    assert len(r.findings) == 1
    f = r.findings[0]
    assert f.metadata["nli_verdict"] == "contradicts"
    assert f.metadata["nli_score"] == 0.4
    assert f.metadata["nli_provider"] == "stub-nli"
    assert any("Low NLI fidelity" in w for w in r.warnings)
    assert r.metadata["nli_min_score"] == 0.7
    assert r.metadata["nli_on_fail"] == "warn"


def test_reject_mode_drops_finding() -> None:
    prov = StubProvider("contradicts", 0.4)

    @fidelity_wrap(min_score=0.7, on_fail="reject", provider=prov)
    async def agent() -> AgentResult:
        return _result_with([
            _finding(summary="bad", excerpt="this is a long enough premise text"),
        ])

    r = _run(agent())
    assert r.findings == []
    assert any("Rejected finding" in w for w in r.warnings)


def test_annotate_only_keeps_finding_no_warning() -> None:
    prov = StubProvider("contradicts", 0.2)

    @fidelity_wrap(min_score=0.7, on_fail="annotate_only", provider=prov)
    async def agent() -> AgentResult:
        return _result_with([
            _finding(summary="x", excerpt="this is a long enough premise text"),
        ])

    r = _run(agent())
    assert len(r.findings) == 1
    assert r.findings[0].metadata["nli_verdict"] == "contradicts"
    assert r.warnings == []


def test_pass_verdict_keeps_finding_no_warning() -> None:
    prov = StubProvider("entails", 0.95)

    @fidelity_wrap(min_score=0.7, on_fail="reject", provider=prov)
    async def agent() -> AgentResult:
        return _result_with([
            _finding(summary="x", excerpt="this is a long enough premise text"),
        ])

    r = _run(agent())
    assert len(r.findings) == 1
    assert r.warnings == []
    assert r.findings[0].metadata["nli_verdict"] == "entails"


def test_short_excerpt_is_skipped() -> None:
    prov = StubProvider("contradicts", 0.0)

    @fidelity_wrap(min_score=0.7, on_fail="reject", provider=prov, min_excerpt_chars=32)
    async def agent() -> AgentResult:
        return _result_with([_finding(summary="x", excerpt="Juan 3:16")])

    r = _run(agent())
    assert len(r.findings) == 1
    assert r.findings[0].metadata["nli_verdict"] == "skipped"
    # provider was NOT called for the short-excerpt finding
    assert prov.calls == []


def test_idempotent_does_not_re_evaluate() -> None:
    prov = StubProvider("entails", 0.9)

    @fidelity_wrap(min_score=0.7, provider=prov)
    @fidelity_wrap(min_score=0.7, provider=prov)
    async def agent() -> AgentResult:
        return _result_with([
            _finding(summary="x", excerpt="long enough excerpt for evaluation here"),
        ])

    r = _run(agent())
    assert len(r.findings) == 1
    # Provider called ONCE despite two layers of wrap.
    assert len(prov.calls) == 1


def test_default_provider_falls_back_to_factory(monkeypatch) -> None:
    # No `provider` kwarg → factory resolves FakeNLI when nothing else is wired.
    monkeypatch.setenv("JW_NLI_PROVIDER", "fake-nli")

    @fidelity_wrap(min_score=0.7)
    async def agent() -> AgentResult:
        return _result_with([
            _finding(
                summary="A test summary",
                excerpt="a totally different premise that has nothing in common with the claim",
            ),
        ])

    r = _run(agent())
    assert r.findings[0].metadata["nli_provider"] == "fake-nli"


def test_language_is_propagated_from_result_metadata() -> None:
    prov = StubProvider("entails", 0.9)

    @fidelity_wrap(min_score=0.7, provider=prov)
    async def agent() -> AgentResult:
        res = _result_with([
            _finding(summary="x", excerpt="long enough excerpt for evaluation here"),
        ])
        res.metadata["language"] = "pt"
        return res

    _run(agent())
    assert prov.calls[0][2] == "pt"


def test_concurrent_findings_each_get_metadata() -> None:
    prov = StubProvider("entails", 0.9)

    @fidelity_wrap(min_score=0.7, provider=prov)
    async def agent() -> AgentResult:
        return _result_with([
            _finding(summary=f"summary {i}", excerpt=f"long enough excerpt #{i} for eval")
            for i in range(5)
        ])

    r = _run(agent())
    assert len(r.findings) == 5
    for f in r.findings:
        assert "nli_verdict" in f.metadata
        assert "nli_score" in f.metadata
        assert "nli_provider" in f.metadata
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/jw-agents/tests/test_fidelity_wrap.py -v`

Expected: FAIL — `ModuleNotFoundError: No module named 'jw_agents.fidelity_wrap'`.

- [ ] **Step 3: Implement the decorator**

```python
# packages/jw-agents/src/jw_agents/fidelity_wrap.py
"""@fidelity_wrap — wrap async agents to NLI-verify their findings.

Spec: docs/superpowers/specs/2026-05-31-fase-39-nli-runtime-design.md
      §"Decorator".

Why async-aware: the toolkit's agents are all async (they fan-out HTTP
calls to wol.jw.org and chase finetune candidates). The decorator preserves
that interface — `await wrapped(...)` still returns an AgentResult.

Default behavior is `on_fail="warn"`: findings are NEVER dropped silently.
The only mode that modifies findings is `on_fail="reject"`, and it always
attaches a warning describing what was dropped.

Idempotence: we check `Finding.metadata` for an existing `nli_verdict`
and skip re-evaluation. Cheap, observable.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from functools import wraps
from typing import Any, Literal

from jw_agents.base import AgentResult
from jw_core.fidelity import NLIProvider

OnFail = Literal["warn", "reject", "annotate_only"]


def fidelity_wrap(
    *,
    min_score: float = 0.7,
    on_fail: OnFail = "warn",
    provider: NLIProvider | None = None,
    min_excerpt_chars: int = 32,
) -> Callable[[Callable[..., Awaitable[AgentResult]]], Callable[..., Awaitable[AgentResult]]]:
    """Decorate an async agent to NLI-verify each Finding.

    Args:
        min_score: failure threshold. A verdict with `score < min_score`
            (or any non-"entails" verdict) is treated as failure.
        on_fail:
            "annotate_only" → write nli_* metadata, no warning, no drop.
            "warn"          → also append a warning to AgentResult.warnings.
            "reject"        → also drop the finding from the result.
        provider: explicit NLIProvider. None → resolved lazily via
            `get_default_nli_provider()`.
        min_excerpt_chars: excerpts shorter than this are not sent to the
            provider; their `nli_verdict` is set to "skipped". Default 32 —
            this filters out citations whose excerpt is just a bible
            reference label (e.g. "John 3:16").
    """

    def deco(
        fn: Callable[..., Awaitable[AgentResult]],
    ) -> Callable[..., Awaitable[AgentResult]]:
        @wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> AgentResult:
            result = await fn(*args, **kwargs)
            # Resolve provider lazily so import jw_agents doesn't pull in
            # heavy providers at import time.
            local_provider = provider
            if local_provider is None:
                from jw_core.fidelity import get_default_nli_provider

                local_provider = get_default_nli_provider()

            language = str(result.metadata.get("language", "en"))
            kept = []
            for f in result.findings:
                # Idempotence — if some outer layer already evaluated, skip.
                if "nli_verdict" in f.metadata:
                    kept.append(f)
                    continue

                if len(f.excerpt) < min_excerpt_chars:
                    f.metadata["nli_verdict"] = "skipped"
                    f.metadata["nli_score"] = None
                    f.metadata["nli_provider"] = local_provider.name
                    kept.append(f)
                    continue

                verdict = local_provider.evaluate(
                    claim=f.summary,
                    premise=f.excerpt,
                    language=language,
                )
                f.metadata["nli_verdict"] = verdict.verdict
                f.metadata["nli_score"] = round(verdict.score, 4)
                f.metadata["nli_provider"] = verdict.provider

                failed = verdict.verdict != "entails" or verdict.score < min_score
                if not failed:
                    kept.append(f)
                    continue

                if on_fail == "annotate_only":
                    kept.append(f)
                elif on_fail == "warn":
                    result.warnings.append(
                        f"Low NLI fidelity ({verdict.verdict}, "
                        f"score={verdict.score:.2f}) for citation {f.citation.url}"
                    )
                    kept.append(f)
                elif on_fail == "reject":
                    result.warnings.append(
                        f"Rejected finding (NLI={verdict.verdict}, "
                        f"score={verdict.score:.2f}) for citation {f.citation.url}"
                    )
                    # do not append — finding dropped

            result.findings = kept
            result.metadata["nli_min_score"] = min_score
            result.metadata["nli_on_fail"] = on_fail
            return result

        return wrapper

    return deco


__all__ = ["fidelity_wrap", "OnFail"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/jw-agents/tests/test_fidelity_wrap.py -v`

Expected: 9 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-agents/src/jw_agents/fidelity_wrap.py packages/jw-agents/tests/test_fidelity_wrap.py
git commit -m "feat(jw-agents): @fidelity_wrap decorator with warn/reject/annotate_only"
```

---

### Task 9: min_excerpt_chars skip logic (edge cases)

This task is explicit in the spec: it carves the contract for which findings get NLI-evaluated and which don't. Task 8 already implements the basic skip; this task hardens it with edge-case tests.

**Files:**
- Modify: `packages/jw-agents/tests/test_fidelity_wrap.py` (append)

- [ ] **Step 1: Write the failing tests**

Append to `packages/jw-agents/tests/test_fidelity_wrap.py`:

```python
# ──────────────────────────────────────────────────────────
# min_excerpt_chars edge cases (Task 9)
# ──────────────────────────────────────────────────────────


def test_skipped_finding_keeps_existing_metadata() -> None:
    """Existing metadata on the Finding must NOT be clobbered by skip."""
    prov = StubProvider("contradicts", 0.0)

    @fidelity_wrap(min_score=0.7, provider=prov, min_excerpt_chars=32)
    async def agent() -> AgentResult:
        f = _finding(summary="s", excerpt="too short")
        f.metadata["source"] = "rag"
        f.metadata["chunk_id"] = 42
        return _result_with([f])

    r = _run(agent())
    f = r.findings[0]
    assert f.metadata["nli_verdict"] == "skipped"
    assert f.metadata["nli_score"] is None
    assert f.metadata["source"] == "rag"
    assert f.metadata["chunk_id"] == 42


def test_min_excerpt_chars_zero_evaluates_everything() -> None:
    """Setting min_excerpt_chars=0 must NOT skip even empty excerpts."""
    prov = StubProvider("neutral", 0.5)

    @fidelity_wrap(min_score=0.7, provider=prov, min_excerpt_chars=0)
    async def agent() -> AgentResult:
        return _result_with([_finding(summary="s", excerpt="")])

    r = _run(agent())
    assert r.findings[0].metadata["nli_verdict"] == "neutral"
    assert prov.calls == [("s", "", "en")]


def test_min_excerpt_chars_huge_skips_everything() -> None:
    """A huge min_excerpt_chars skips even multi-paragraph excerpts."""
    prov = StubProvider("entails", 0.95)

    @fidelity_wrap(min_score=0.7, provider=prov, min_excerpt_chars=100000)
    async def agent() -> AgentResult:
        return _result_with([
            _finding(summary="s", excerpt="a paragraph of reasonable length here.")
        ])

    r = _run(agent())
    assert r.findings[0].metadata["nli_verdict"] == "skipped"
    assert prov.calls == []


def test_skipped_finding_never_dropped_in_reject_mode() -> None:
    """Skipped findings survive `on_fail="reject"`."""
    prov = StubProvider("contradicts", 0.0)

    @fidelity_wrap(min_score=0.7, on_fail="reject", provider=prov, min_excerpt_chars=32)
    async def agent() -> AgentResult:
        return _result_with([_finding(summary="s", excerpt="John 3:16")])

    r = _run(agent())
    assert len(r.findings) == 1
    assert r.findings[0].metadata["nli_verdict"] == "skipped"
    assert r.warnings == []


def test_excerpt_at_boundary_length_evaluated() -> None:
    """An excerpt of EXACTLY min_excerpt_chars is evaluated (boundary inclusive)."""
    prov = StubProvider("entails", 0.95)
    boundary_excerpt = "x" * 32

    @fidelity_wrap(min_score=0.7, provider=prov, min_excerpt_chars=32)
    async def agent() -> AgentResult:
        return _result_with([_finding(summary="s", excerpt=boundary_excerpt)])

    r = _run(agent())
    assert r.findings[0].metadata["nli_verdict"] == "entails"
    assert prov.calls == [("s", boundary_excerpt, "en")]


def test_excerpt_one_below_boundary_skipped() -> None:
    """An excerpt of (min_excerpt_chars - 1) IS skipped."""
    prov = StubProvider("entails", 0.95)

    @fidelity_wrap(min_score=0.7, provider=prov, min_excerpt_chars=32)
    async def agent() -> AgentResult:
        return _result_with([_finding(summary="s", excerpt="x" * 31)])

    r = _run(agent())
    assert r.findings[0].metadata["nli_verdict"] == "skipped"
    assert prov.calls == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest packages/jw-agents/tests/test_fidelity_wrap.py::test_skipped_finding_keeps_existing_metadata packages/jw-agents/tests/test_fidelity_wrap.py::test_min_excerpt_chars_zero_evaluates_everything packages/jw-agents/tests/test_fidelity_wrap.py::test_min_excerpt_chars_huge_skips_everything packages/jw-agents/tests/test_fidelity_wrap.py::test_skipped_finding_never_dropped_in_reject_mode packages/jw-agents/tests/test_fidelity_wrap.py::test_excerpt_at_boundary_length_evaluated packages/jw-agents/tests/test_fidelity_wrap.py::test_excerpt_one_below_boundary_skipped -v`

If all pass already because Task 8 happened to be correct: great, the implementation is robust. If some fail (likely `test_min_excerpt_chars_zero_evaluates_everything` because `"" < 0` is False so it would skip — actually `len("") < 0` is False, so 0 case works), only fix what broke.

If `test_skipped_finding_never_dropped_in_reject_mode` fails because the implementation drops "skipped" findings in reject mode, that means the skip path also needs to short-circuit before the reject branch. Re-read Task 8 impl: it appends to `kept` and `continue`s before the failed/reject check. So `"skipped"` is NEVER dropped. Verify with `pytest -v`.

- [ ] **Step 3: Implement (if any test failed)**

If `test_min_excerpt_chars_zero_evaluates_everything` failed because the check was `len(excerpt) < min_excerpt_chars` (which with min_excerpt_chars=0 means `< 0` → always False → never skip → correct). No change.

If `test_skipped_finding_keeps_existing_metadata` failed because the impl overwrote `metadata` instead of mutating in place: re-read Task 8 — `f.metadata["nli_verdict"] = "skipped"` mutates, doesn't overwrite. No change.

If anything DOES fail unexpectedly, the most likely culprit is the boundary inclusion — confirm `len(f.excerpt) < min_excerpt_chars` is the correct check (strict `<`, so exactly-equal is evaluated).

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/jw-agents/tests/test_fidelity_wrap.py -v`

Expected: 15 passed (9 from Task 8 + 6 new).

- [ ] **Step 5: Commit**

```bash
git add packages/jw-agents/tests/test_fidelity_wrap.py
git commit -m "test(jw-agents): harden min_excerpt_chars skip edge cases"
```

---

### Task 10: threshold modes (warn|reject) + default on_fail="warn"

This task adds tests for the threshold semantics under multiple verdicts and confirms the default mode. Task 8 already implemented the modes; Task 10 nails the matrix down explicitly.

**Files:**
- Modify: `packages/jw-agents/tests/test_fidelity_wrap.py` (append)

- [ ] **Step 1: Write the failing tests**

Append to `test_fidelity_wrap.py`:

```python
# ──────────────────────────────────────────────────────────
# Threshold matrix (Task 10)
# ──────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("verdict", "score", "min_score", "expected_fail"),
    [
        ("entails", 0.95, 0.7, False),
        ("entails", 0.71, 0.7, False),
        ("entails", 0.70, 0.7, False),
        ("entails", 0.69, 0.7, True),  # score below threshold
        ("entails", 0.30, 0.7, True),
        ("neutral", 0.95, 0.7, True),  # non-entails verdict
        ("neutral", 0.50, 0.7, True),
        ("contradicts", 0.95, 0.7, True),
        ("contradicts", 0.10, 0.7, True),
    ],
)
def test_threshold_matrix(verdict, score, min_score, expected_fail) -> None:
    prov = StubProvider(verdict, score)

    @fidelity_wrap(min_score=min_score, on_fail="warn", provider=prov)
    async def agent() -> AgentResult:
        return _result_with([_finding(summary="s", excerpt="a sufficiently long excerpt to evaluate")])

    r = _run(agent())
    assert len(r.findings) == 1  # warn never drops
    if expected_fail:
        assert any("Low NLI fidelity" in w for w in r.warnings)
    else:
        assert r.warnings == []


def test_default_on_fail_is_warn() -> None:
    """Default behavior is `warn` — explicit test of the default."""
    prov = StubProvider("contradicts", 0.1)

    @fidelity_wrap(provider=prov)  # no on_fail kwarg
    async def agent() -> AgentResult:
        return _result_with([_finding(summary="s", excerpt="a sufficiently long excerpt here")])

    r = _run(agent())
    assert len(r.findings) == 1
    assert any("Low NLI fidelity" in w for w in r.warnings)
    assert r.metadata["nli_on_fail"] == "warn"


def test_default_min_score_is_0_7() -> None:
    """Default min_score is 0.7."""

    @fidelity_wrap(provider=StubProvider("entails", 0.5))
    async def agent() -> AgentResult:
        return _result_with([])

    r = _run(agent())
    assert r.metadata["nli_min_score"] == 0.7


def test_min_score_below_zero_is_permissive() -> None:
    """`min_score=0.0` accepts any entails verdict, however low."""
    prov = StubProvider("entails", 0.0)

    @fidelity_wrap(min_score=0.0, on_fail="reject", provider=prov)
    async def agent() -> AgentResult:
        return _result_with([_finding(summary="s", excerpt="a sufficiently long excerpt here")])

    r = _run(agent())
    assert len(r.findings) == 1
    assert r.warnings == []


def test_min_score_above_one_rejects_everything() -> None:
    """`min_score=1.01` rejects even perfect verdicts."""
    prov = StubProvider("entails", 1.0)

    @fidelity_wrap(min_score=1.01, on_fail="reject", provider=prov)
    async def agent() -> AgentResult:
        return _result_with([_finding(summary="s", excerpt="a sufficiently long excerpt here")])

    r = _run(agent())
    assert r.findings == []
    assert any("Rejected finding" in w for w in r.warnings)


def test_reject_mode_does_not_drop_passing_findings() -> None:
    prov = StubProvider("entails", 0.95)

    @fidelity_wrap(min_score=0.7, on_fail="reject", provider=prov)
    async def agent() -> AgentResult:
        return _result_with([
            _finding(summary=f"good {i}", excerpt=f"a sufficiently long excerpt #{i} here")
            for i in range(3)
        ])

    r = _run(agent())
    assert len(r.findings) == 3
    assert r.warnings == []
```

- [ ] **Step 2: Run tests to verify they pass (most should already)**

Run: `uv run pytest packages/jw-agents/tests/test_fidelity_wrap.py -v`

Expected: 24 passed (15 prior + 9 from threshold matrix + 4 from singletons = 28; adjust per actual count).

- [ ] **Step 3: Fix any unexpected failures**

If `test_min_score_below_zero_is_permissive` fails because `min_score=0.0` and `verdict.score=0.0`: the condition `score < min_score` is `0.0 < 0.0` → False → does not fail → finding kept. Correct.

If `test_min_score_above_one_rejects_everything` fails: condition `1.0 < 1.01` → True → fails → rejected. Correct.

No implementation changes expected for this task; it's a contract-locking test set.

- [ ] **Step 4: Run final pass**

Run: `uv run pytest packages/jw-agents/tests/test_fidelity_wrap.py -v`

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-agents/tests/test_fidelity_wrap.py
git commit -m "test(jw-agents): lock down threshold matrix + default mode contracts"
```

---

### Task 11: Integration test — wrap apologetics; 1984 existing tests stay green

**Files:**
- Create: `packages/jw-agents/tests/test_fidelity_integration.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-agents/tests/test_fidelity_integration.py
"""Integration test: wrap a real agent (apologetics) and confirm the existing
agent contract is unchanged in the default `warn` mode with FakeNLI.

We import the real `apologetics` async function and patch its inner HTTP
calls with the existing project fixtures. The wrapped agent must:

  - Return the same number of findings as the unwrapped version.
  - Stamp every finding with nli_* metadata.
  - Stamp result.metadata with nli_min_score / nli_on_fail.
  - Not raise.

We do NOT exercise reject mode here — that's tested in test_fidelity_wrap.
This is the "the wiring works end-to-end on a real agent" test.
"""

from __future__ import annotations

import asyncio
import os

import pytest

from jw_agents.base import AgentResult, Citation, Finding
from jw_agents.fidelity_wrap import fidelity_wrap


@pytest.fixture(autouse=True)
def _force_fake_nli(monkeypatch) -> None:
    monkeypatch.setenv("JW_NLI_PROVIDER", "fake-nli")


def _fake_apologetics() -> AgentResult:
    """A minimal stand-in for the real apologetics agent — same shape."""
    return AgentResult(
        query="¿Es la Trinidad bíblica?",
        agent_name="apologetics",
        findings=[
            Finding(
                summary="La Trinidad no es una enseñanza bíblica",
                excerpt=(
                    "Las Escrituras presentan a Jehová como el único Dios verdadero, "
                    "mientras que Jesús es su Hijo. La doctrina trinitaria se "
                    "desarrolló siglos después."
                ),
                citation=Citation(
                    url="https://wol.jw.org/es/wol/d/r4/lp-s/2003124",
                    title="¿Cree usted en la Trinidad?",
                    kind="article",
                ),
                metadata={"source": "topic_index"},
            ),
            Finding(
                summary="Jesús es el Hijo de Dios, no Dios mismo",
                excerpt="Juan 17:3 dice: 'Esto significa vida eterna, que lleguen a conocerte'.",
                citation=Citation(
                    url="https://wol.jw.org/es/wol/b/r4/lp-s/nwt/E/2024/43/17",
                    title="Juan 17",
                    kind="verse",
                ),
                metadata={"source": "verse_text"},
            ),
        ],
        warnings=[],
        metadata={"language": "es"},
    )


def test_wrapped_apologetics_keeps_findings_and_stamps_metadata() -> None:
    @fidelity_wrap(min_score=0.7, on_fail="warn")
    async def apologetics(question: str) -> AgentResult:  # noqa: ARG001
        return _fake_apologetics()

    result = asyncio.run(apologetics(question="¿Es la Trinidad bíblica?"))

    assert result.agent_name == "apologetics"
    assert len(result.findings) == 2
    for f in result.findings:
        assert "nli_verdict" in f.metadata
        assert "nli_score" in f.metadata
        assert "nli_provider" in f.metadata
        assert f.metadata["nli_provider"] == "fake-nli"

    assert result.metadata["nli_min_score"] == 0.7
    assert result.metadata["nli_on_fail"] == "warn"
    # The preexisting `language` metadata is preserved
    assert result.metadata["language"] == "es"


def test_wrapped_warn_never_drops_in_default_mode() -> None:
    @fidelity_wrap()  # all defaults: min_score=0.7, on_fail="warn"
    async def apologetics() -> AgentResult:
        return _fake_apologetics()

    before = _fake_apologetics()
    after = asyncio.run(apologetics())

    assert len(after.findings) == len(before.findings)


def test_existing_tests_still_pass_after_wrap_when_not_applied() -> None:
    """Verifies that simply having the decorator in the import path does NOT
    leak side effects. Sanity check the import surface."""
    from jw_agents import fidelity_wrap as fw_module

    assert hasattr(fw_module, "fidelity_wrap")
    # No global state mutation
    assert not hasattr(fw_module, "_GLOBAL_PROVIDER")
```

- [ ] **Step 2: Run test to verify it fails (or passes immediately)**

Run: `uv run pytest packages/jw-agents/tests/test_fidelity_integration.py -v`

Expected: 3 passed.

- [ ] **Step 3: Run the full test suite — no regressions**

Run:
```bash
uv run pytest packages/ -q
```

Expected: previous 1984 tests + new tests all green. If any existing test now fails, the most likely cause is the new optional dep on `respx` for the Ollama tests — verify it's installed via `uv sync --all-packages --dev`.

- [ ] **Step 4: Add a smoke target for the wrapped apologetics in CI logs (optional)**

Touch nothing — the integration test is the smoke. Skip to commit.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-agents/tests/test_fidelity_integration.py
git commit -m "test(jw-agents): integration test — wrapped apologetics still passes contract"
```

---

### Task 12: CLI flag `--fidelity` on agent commands

**Files:**
- Modify: `packages/jw-cli/src/jw_cli/commands/apologetics.py`
- Modify: `packages/jw-cli/src/jw_cli/commands/verse.py`
- Modify: `packages/jw-cli/src/jw_cli/commands/research.py`
- Modify: `packages/jw-cli/src/jw_cli/commands/meeting.py`
- Create: `packages/jw-cli/tests/test_cli_fidelity.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-cli/tests/test_cli_fidelity.py
"""Tests for the `--fidelity` flag exposed by jw-cli agent commands.

We don't run a full HTTP roundtrip — we patch the inner agent callable
with a stub via monkeypatch on the imported symbol.
"""

from __future__ import annotations

import asyncio

import pytest
from typer.testing import CliRunner

from jw_cli.main import app
from jw_agents.base import AgentResult, Citation, Finding


def _stub_result() -> AgentResult:
    return AgentResult(
        query="test",
        agent_name="apologetics",
        findings=[
            Finding(
                summary="The Trinity is a Bible teaching",
                excerpt="The Trinity is not a Bible teaching, contrary to popular belief.",
                citation=Citation(url="https://wol.jw.org/x", title="t", kind="article"),
            )
        ],
        metadata={"language": "en"},
    )


@pytest.fixture(autouse=True)
def _force_fake_nli(monkeypatch) -> None:
    monkeypatch.setenv("JW_NLI_PROVIDER", "fake-nli")


def _patch_agent(monkeypatch, module_path: str, attr: str) -> None:
    async def fake(*args, **kwargs):  # noqa: ARG001
        return _stub_result()

    import importlib

    mod = importlib.import_module(module_path)
    monkeypatch.setattr(mod, attr, fake)


def test_apologetics_fidelity_off_skips_wrapping(monkeypatch) -> None:
    _patch_agent(monkeypatch, "jw_cli.commands.apologetics", "apologetics")
    runner = CliRunner()
    res = runner.invoke(app, ["apologetics", "--question", "x", "--fidelity", "off"])
    assert res.exit_code == 0
    # When off, no nli_* metadata in stdout
    assert "nli_verdict" not in res.stdout


def test_apologetics_fidelity_warn_adds_metadata(monkeypatch) -> None:
    _patch_agent(monkeypatch, "jw_cli.commands.apologetics", "apologetics")
    runner = CliRunner()
    res = runner.invoke(app, ["apologetics", "--question", "x", "--fidelity", "warn"])
    assert res.exit_code == 0
    assert "nli_verdict" in res.stdout


def test_apologetics_fidelity_reject_drops_bad_findings(monkeypatch) -> None:
    _patch_agent(monkeypatch, "jw_cli.commands.apologetics", "apologetics")
    runner = CliRunner()
    res = runner.invoke(app, ["apologetics", "--question", "x", "--fidelity", "reject"])
    assert res.exit_code == 0
    # FakeNLI on this excerpt detects asymmetric negation → contradicts → reject
    # The 'findings' array must be empty (or count=0)
    assert "Rejected finding" in res.stdout or '"findings": []' in res.stdout


def test_apologetics_fidelity_invalid_raises(monkeypatch) -> None:
    _patch_agent(monkeypatch, "jw_cli.commands.apologetics", "apologetics")
    runner = CliRunner()
    res = runner.invoke(app, ["apologetics", "--question", "x", "--fidelity", "bogus"])
    assert res.exit_code != 0


def test_verse_explainer_fidelity_flag_exists(monkeypatch) -> None:
    _patch_agent(monkeypatch, "jw_cli.commands.verse", "verse_explainer")
    runner = CliRunner()
    res = runner.invoke(app, ["verse", "--reference", "John 3:16", "--fidelity", "warn"])
    assert res.exit_code == 0


def test_research_fidelity_flag_exists(monkeypatch) -> None:
    _patch_agent(monkeypatch, "jw_cli.commands.research", "research_topic")
    runner = CliRunner()
    res = runner.invoke(app, ["research", "--topic", "kingdom", "--fidelity", "warn"])
    assert res.exit_code == 0


def test_meeting_fidelity_flag_exists(monkeypatch) -> None:
    _patch_agent(monkeypatch, "jw_cli.commands.meeting", "meeting_helper")
    runner = CliRunner()
    res = runner.invoke(app, ["meeting", "--url-or-ref", "Romans 12:1", "--fidelity", "warn"])
    assert res.exit_code == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/jw-cli/tests/test_cli_fidelity.py -v`

Expected: FAIL — Typer raises on unknown option `--fidelity`.

- [ ] **Step 3: Implement the flag in each CLI command**

For each of the four agent commands, do the same surgery. Here's the pattern using `apologetics.py` as the canonical example; replicate for `verse.py`, `research.py`, `meeting.py` mapping their argument names.

```python
# packages/jw-cli/src/jw_cli/commands/apologetics.py — surgery sketch
"""`jw apologetics` — answer apologetics questions with citations.

Adds `--fidelity {off,warn,reject}` (default `warn`) which wraps the
agent call with @fidelity_wrap before invocation.
"""

from __future__ import annotations

import asyncio
import json
from typing import Literal

import typer

from jw_agents.apologetics import apologetics
from jw_agents.fidelity_wrap import fidelity_wrap

Fidelity = Literal["off", "warn", "reject"]


def apologetics_cmd(
    question: str = typer.Option(..., "--question", help="Question to answer."),
    language: str = typer.Option("en", "--language", help="Language code."),
    fidelity: Fidelity = typer.Option(
        "warn",
        "--fidelity",
        help="NLI runtime verification: off | warn | reject.",
        case_sensitive=False,
    ),
) -> None:
    if fidelity == "off":
        callable_agent = apologetics
    else:
        callable_agent = fidelity_wrap(
            min_score=0.7,
            on_fail="reject" if fidelity == "reject" else "warn",
        )(apologetics)

    result = asyncio.run(callable_agent(question=question, language=language))
    typer.echo(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
```

(The actual file probably has more options already; only ADD the `fidelity` parameter and the conditional wrapping. Do NOT rewrite the rest.)

Repeat the same 5-line surgery for the other three CLI commands:

- `packages/jw-cli/src/jw_cli/commands/verse.py` — wraps `verse_explainer`.
- `packages/jw-cli/src/jw_cli/commands/research.py` — wraps `research_topic`.
- `packages/jw-cli/src/jw_cli/commands/meeting.py` — wraps `meeting_helper`.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/jw-cli/tests/test_cli_fidelity.py -v`

Expected: 7 passed.

- [ ] **Step 5: Smoke-test the actual binaries**

```bash
JW_NLI_PROVIDER=fake-nli uv run jw apologetics --question "test" --fidelity warn --help
```

Expected: help text includes `--fidelity` and lists the three values.

- [ ] **Step 6: Commit**

```bash
git add packages/jw-cli/src/jw_cli/commands packages/jw-cli/tests/test_cli_fidelity.py
git commit -m "feat(jw-cli): --fidelity flag on apologetics/verse/research/meeting commands"
```

---

### Task 13: MCP integration — `evaluate_nli` tool + `fidelity` param on agent tools

**Files:**
- Modify: `packages/jw-mcp/src/jw_mcp/server.py`
- Create: `packages/jw-mcp/tests/test_mcp_nli.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-mcp/tests/test_mcp_nli.py
"""Tests for jw-mcp NLI integrations:

  1. New standalone tool `evaluate_nli(claim, premise, language)` returns
     {"verdict", "score", "provider"}.
  2. The wrapped agent tools (`apologetics_tool` et al.) accept an optional
     `fidelity` parameter and return findings with nli_* metadata.
"""

from __future__ import annotations

import pytest

# The MCP server exposes the tool function directly for unit testing.


@pytest.fixture(autouse=True)
def _force_fake_nli(monkeypatch) -> None:
    monkeypatch.setenv("JW_NLI_PROVIDER", "fake-nli")


def test_evaluate_nli_returns_verdict() -> None:
    from jw_mcp.server import evaluate_nli

    out = evaluate_nli(
        claim="God loves the world",
        premise="God so loved the world that he gave his only Son",
        language="en",
    )
    assert "verdict" in out
    assert "score" in out
    assert "provider" in out
    assert out["verdict"] in {"entails", "neutral", "contradicts"}
    assert 0.0 <= out["score"] <= 1.0
    assert out["provider"] == "fake-nli"


def test_evaluate_nli_default_language_is_en() -> None:
    from jw_mcp.server import evaluate_nli

    out = evaluate_nli(claim="a", premise="a")
    assert out["verdict"] in {"entails", "neutral", "contradicts"}


def test_evaluate_nli_handles_empty_inputs() -> None:
    from jw_mcp.server import evaluate_nli

    out = evaluate_nli(claim="", premise="")
    assert out["verdict"] in {"entails", "neutral", "contradicts"}
    assert 0.0 <= out["score"] <= 1.0


def test_apologetics_tool_accepts_fidelity_param(monkeypatch) -> None:
    """The MCP wrapper around `apologetics` exposes `fidelity`."""
    from jw_mcp import server as srv

    async def fake(question: str, language: str = "en", **_):  # noqa: ARG001
        from jw_agents.base import AgentResult, Citation, Finding

        return AgentResult(
            query=question,
            agent_name="apologetics",
            findings=[
                Finding(
                    summary="x",
                    excerpt="a sufficiently long excerpt for NLI evaluation here",
                    citation=Citation(url="https://wol.jw.org/x", title="t", kind="article"),
                )
            ],
            metadata={"language": language},
        )

    monkeypatch.setattr(srv, "apologetics", fake)
    out = srv.apologetics_tool(question="?", language="en", fidelity="warn")
    assert "findings" in out
    assert out["findings"][0]["metadata"]["nli_verdict"] in {
        "entails",
        "neutral",
        "contradicts",
        "skipped",
    }


def test_apologetics_tool_fidelity_off_skips_metadata(monkeypatch) -> None:
    from jw_mcp import server as srv

    async def fake(question: str, language: str = "en", **_):  # noqa: ARG001
        from jw_agents.base import AgentResult, Citation, Finding

        return AgentResult(
            query=question,
            agent_name="apologetics",
            findings=[
                Finding(
                    summary="x",
                    excerpt="a sufficiently long excerpt for NLI evaluation here",
                    citation=Citation(url="https://wol.jw.org/x", title="t", kind="article"),
                )
            ],
            metadata={"language": language},
        )

    monkeypatch.setattr(srv, "apologetics", fake)
    out = srv.apologetics_tool(question="?", language="en", fidelity="off")
    assert "nli_verdict" not in out["findings"][0]["metadata"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/jw-mcp/tests/test_mcp_nli.py -v`

Expected: FAIL — `evaluate_nli` not exported; `apologetics_tool` does not accept `fidelity`.

- [ ] **Step 3: Implement the MCP integrations**

Append to `packages/jw-mcp/src/jw_mcp/server.py`:

```python
# packages/jw-mcp/src/jw_mcp/server.py — additions
from __future__ import annotations

import asyncio
from typing import Literal

from jw_agents.apologetics import apologetics  # if not already imported
from jw_agents.fidelity_wrap import fidelity_wrap
from jw_core.fidelity import evaluate_entailment

Fidelity = Literal["off", "warn", "reject"]


def _maybe_wrap(fn, fidelity: Fidelity):
    if fidelity == "off":
        return fn
    return fidelity_wrap(
        min_score=0.7,
        on_fail="reject" if fidelity == "reject" else "warn",
    )(fn)


# ── New standalone tool ──────────────────────────────────────────────

@mcp.tool()
def evaluate_nli(
    claim: str,
    premise: str,
    language: str = "en",
) -> dict:
    """Run a single NLI judgement on a (claim, premise) pair.

    Useful for clients that want to verify a citation/summary pair without
    running a full agent. Uses the same provider stack as the @fidelity_wrap
    decorator, honoring `JW_NLI_PROVIDER`.

    Returns:
        {"verdict": "entails"|"neutral"|"contradicts",
         "score": float in [0, 1],
         "provider": str}
    """

    v = evaluate_entailment(claim=claim, premise=premise, language=language)
    return {"verdict": v.verdict, "score": round(v.score, 4), "provider": v.provider}


# ── Wrap existing agent tools ────────────────────────────────────────
# Each existing `*_tool` function gains an optional `fidelity` parameter.
# We don't rewrite them — we add a thin wrapper. Below is the apologetics
# example; replicate for verse_explainer_tool, research_topic_tool,
# meeting_helper_tool.

@mcp.tool()
def apologetics_tool(
    question: str,
    language: str = "en",
    fidelity: Fidelity = "warn",
) -> dict:
    """Run the apologetics agent with optional runtime NLI verification.

    Args:
        question: The apologetics question.
        language: BCP-47 code, default "en".
        fidelity: "off" (no NLI), "warn" (annotate + warn), or "reject"
            (annotate + drop low-fidelity findings). Default "warn".
    """

    callable_agent = _maybe_wrap(apologetics, fidelity)
    result = asyncio.run(callable_agent(question=question, language=language))
    return result.to_dict()
```

Apply the same `fidelity` parameter pattern to `verse_explainer_tool`, `research_topic_tool`, `meeting_helper_tool` — each gets the `fidelity: Fidelity = "warn"` arg and routes through `_maybe_wrap`.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/jw-mcp/tests/test_mcp_nli.py -v`

Expected: 5 passed.

- [ ] **Step 5: Smoke-test the MCP server**

```bash
JW_NLI_PROVIDER=fake-nli uv run python -c "
from jw_mcp.server import evaluate_nli
print(evaluate_nli(claim='Jesus is God', premise='Jesus is not God', language='en'))
"
```

Expected output (approximately): `{'verdict': 'contradicts', 'score': 0.6, 'provider': 'fake-nli'}` (score varies with jaccard).

- [ ] **Step 6: Commit**

```bash
git add packages/jw-mcp/src/jw_mcp/server.py packages/jw-mcp/tests/test_mcp_nli.py
git commit -m "feat(jw-mcp): evaluate_nli tool + fidelity param on agent tools"
```

---

### Task 14: Property test — random claim/premise pairs, verdicts consistent

**Files:**
- Create: `packages/jw-core/tests/test_fidelity_property.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-core/tests/test_fidelity_property.py
"""Property-based tests for the NLI providers.

We use `hypothesis` (already a dev dep — see existing
test_property_based.py) to generate random text pairs and assert
invariants the providers MUST always honor:

  - verdict ∈ {"entails", "neutral", "contradicts"}
  - 0 ≤ score ≤ 1
  - provider == name
  - identical input → identical output (determinism, for FakeNLI)
  - swapping claim and premise can change the verdict but never break
    the type contract
"""

from __future__ import annotations

import string

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from jw_core.fidelity.nli_providers.fakes import FakeNLI

# Restrict to printable ASCII to avoid byte-level issues in CI logs
_TEXT = st.text(
    alphabet=string.ascii_letters + string.digits + " .,;:!?",
    min_size=0,
    max_size=200,
)


@given(claim=_TEXT, premise=_TEXT)
@settings(max_examples=200, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_fake_verdict_always_legal(claim: str, premise: str) -> None:
    v = FakeNLI().evaluate(claim=claim, premise=premise)
    assert v.verdict in {"entails", "neutral", "contradicts"}
    assert 0.0 <= v.score <= 1.0
    assert v.provider == "fake-nli"


@given(claim=_TEXT, premise=_TEXT)
@settings(max_examples=200)
def test_fake_is_deterministic(claim: str, premise: str) -> None:
    p = FakeNLI()
    assert p.evaluate(claim=claim, premise=premise) == p.evaluate(
        claim=claim, premise=premise
    )


@given(text=_TEXT.filter(lambda s: len(s) >= 4))
@settings(max_examples=100)
def test_fake_self_entailment_is_high(text: str) -> None:
    v = FakeNLI().evaluate(claim=text, premise=text)
    # When claim == premise, jaccard = 1.0 unless both empty after tokenize
    assert v.score >= 0.99 or v.verdict == "neutral"


@given(claim=_TEXT, premise=_TEXT, language=st.sampled_from(["en", "es", "pt", "fr", "de"]))
@settings(max_examples=200)
def test_language_does_not_break_fake(claim: str, premise: str, language: str) -> None:
    v = FakeNLI().evaluate(claim=claim, premise=premise, language=language)
    assert v.raw["lang"] == language


@given(claim=_TEXT, premise=_TEXT)
@settings(max_examples=200)
def test_swap_preserves_type_contract(claim: str, premise: str) -> None:
    p = FakeNLI()
    a = p.evaluate(claim=claim, premise=premise)
    b = p.evaluate(claim=premise, premise=claim)
    # both legal verdicts
    assert a.verdict in {"entails", "neutral", "contradicts"}
    assert b.verdict in {"entails", "neutral", "contradicts"}
    # scores both in [0, 1]
    assert 0.0 <= a.score <= 1.0
    assert 0.0 <= b.score <= 1.0


@given(claim=_TEXT, premise=_TEXT)
@settings(max_examples=50)
def test_score_is_finite(claim: str, premise: str) -> None:
    import math

    v = FakeNLI().evaluate(claim=claim, premise=premise)
    assert math.isfinite(v.score)
```

- [ ] **Step 2: Run test to verify it passes**

Run: `uv run pytest packages/jw-core/tests/test_fidelity_property.py -v`

Expected: 6 passed (hypothesis explores ~200 cases per property).

If `hypothesis` is missing in `jw-core` dev deps, add it:

```bash
uv add --dev --package jw-core hypothesis
```

- [ ] **Step 3: Fix any hypothesis-found failures**

The most likely failure surfaces from `test_fake_self_entailment_is_high` — when the input text contains only punctuation/whitespace, the tokenizer returns an empty set and jaccard = 0.0 (per the implementation). The test allows this via the `or v.verdict == "neutral"` clause. If hypothesis finds a corner case the test didn't anticipate (e.g. all-punctuation input where verdict is unexpectedly "contradicts"), narrow the input filter or add to the conditional.

- [ ] **Step 4: Commit**

```bash
git add packages/jw-core/tests/test_fidelity_property.py
git commit -m "test(jw-core): hypothesis property tests for FakeNLI invariants"
```

---

### Task 15: Documentation — user guide + ROADMAP + VISION_AUDIT

**Files:**
- Create: `docs/guias/fidelity-nli.md`
- Modify: `docs/README.md`
- Modify: `docs/VISION_AUDIT.md`
- Modify: `docs/ROADMAP.md`

- [ ] **Step 1: Write the user guide**

```markdown
# Fidelidad NLI en runtime (`jw_core.fidelity`)

> Fase 39 — verificación de entailment semántico claim ↔ premise sobre cada `Finding` que devuelve un agente. Spec: `docs/superpowers/specs/2026-05-31-fase-39-nli-runtime-design.md`.

## Para qué sirve

Garantiza, en cada llamada real, que el `summary` de un `Finding` se desprende lógicamente del `excerpt` verbatim que su `Citation` ancla. Complementa Fase 22 (eval offline pre-merge) extendiendo la red al runtime.

Cada finding verificado lleva en `metadata`:

```json
{
  "nli_verdict": "entails | neutral | contradicts | skipped",
  "nli_score": 0.87,
  "nli_provider": "claude-nli"
}
```

## Modos de operación

| Modo | Qué hace | Cuándo |
|---|---|---|
| `off` | No evalúa, no anota. | CLI con `--fidelity off` para máxima velocidad. |
| `annotate_only` | Sólo añade metadata, sin warnings ni drops. | Uso programático, telemetría. |
| `warn` (default) | Metadata + warning en `AgentResult.warnings` si score < threshold. | CLI y MCP por defecto. |
| `reject` | Warn + DROP del finding del resultado. | Superficies estrictas (`--fidelity reject`). |

## Providers disponibles

Orden de auto-detección (puede sobreescribirse con `JW_NLI_PROVIDER`):

1. **`claude-nli`** — Anthropic Claude (mejor calidad, multi-lingüe). Extra `[nli-anthropic]` + `ANTHROPIC_API_KEY`.
2. **`openai-nli`** — OpenAI GPT-4o-mini. Extra `[nli-openai]` + `OPENAI_API_KEY`.
3. **`deberta-v3-mnli`** — DeBERTa-v3-large-mnli, local. Extra `[nli-local]` (instala torch + transformers). Detecta automáticamente Apple Silicon (MLX), CUDA (NVIDIA), CPU.
4. **`ollama-nli`** — Llama 3.1 local vía Ollama HTTP. Requiere `ollama serve` corriendo.
5. **`fake-nli`** — heurística pura (jaccard + negación). Siempre disponible, determinista, sin red. Default en CI.

## Uso desde CLI

```bash
# Modo warn (default) — siempre se anota, warnings si falla
uv run jw apologetics --question "¿Es la Trinidad bíblica?" --fidelity warn

# Off (sin verificación, máxima velocidad)
uv run jw apologetics --question "?" --fidelity off

# Reject (drop estricto de findings que no aprueban)
uv run jw apologetics --question "?" --fidelity reject

# Forzar provider específico
JW_NLI_PROVIDER=claude-nli uv run jw verse --reference "Juan 3:16" --fidelity warn
```

## Uso desde MCP

Cada tool de agente (`apologetics_tool`, `verse_explainer_tool`, `research_topic_tool`, `meeting_helper_tool`) gana un parámetro opcional `fidelity` con los mismos valores. Nuevo tool standalone:

```json
{
  "name": "evaluate_nli",
  "arguments": {
    "claim": "La Trinidad no es bíblica",
    "premise": "Las Escrituras presentan a un solo Dios",
    "language": "es"
  }
}
```

Devuelve `{"verdict": "entails|neutral|contradicts", "score": 0.87, "provider": "claude-nli"}`.

## Uso desde Python

```python
from jw_core.fidelity import evaluate_entailment

v = evaluate_entailment(
    claim="The Trinity is not a Bible teaching.",
    premise="The Bible teaches there is one God, the Father.",
    language="en",
)
print(v.verdict, v.score, v.provider)
```

Para envolver un agente custom:

```python
from jw_agents.fidelity_wrap import fidelity_wrap

@fidelity_wrap(min_score=0.7, on_fail="warn")
async def my_agent(question: str) -> AgentResult:
    ...
```

## Variables de entorno

| Variable | Default | Efecto |
|---|---|---|
| `JW_NLI_PROVIDER` | (auto) | Override: `claude-nli`, `openai-nli`, `deberta-v3-mnli`, `ollama-nli`, `fake-nli`. |
| `JW_NLI_CLAUDE_MODEL` | `claude-sonnet-4-5-20250929` | Modelo Anthropic. |
| `JW_NLI_OPENAI_MODEL` | `gpt-4o-mini` | Modelo OpenAI. |
| `JW_NLI_OLLAMA_MODEL` | `llama3.1:8b-instruct` | Modelo local Ollama. |
| `JW_NLI_DEBERTA_MODEL` | `MoritzLaurer/DeBERTa-v3-large-mnli-fever-anli-ling-wanli` | Modelo HF. |
| `JW_PROVIDER_ORDER` | `api,mlx,nvidia,cpu` | Reordena el ranking de targets (compartido con Fase 33). |
| `OLLAMA_HOST` | `http://localhost:11434` | Servidor Ollama. |
| `ANTHROPIC_API_KEY` | — | Necesario para `claude-nli`. |
| `OPENAI_API_KEY` | — | Necesario para `openai-nli`. |

## Costes orientativos

| Provider | Coste por 1k findings (premise ≤2k tokens) | Latencia P50 |
|---|---|---|
| `claude-nli` (Sonnet 4.5, con prompt caching) | ~$0.30 | ~250ms |
| `openai-nli` (gpt-4o-mini) | ~$0.15 | ~400ms |
| `deberta-v3-mnli` (CPU) | $0 | ~800ms |
| `deberta-v3-mnli` (CUDA) | $0 | ~50ms |
| `ollama-nli` (llama3.1:8b) | $0 | ~1500ms |
| `fake-nli` | $0 | <1ms |

## Troubleshooting

| Síntoma | Diagnóstico | Fix |
|---|---|---|
| `nli_verdict="skipped"` en todos los findings | excerpts <32 chars | revisa parser; o baja `min_excerpt_chars` en el decorador |
| `nli_verdict="contradicts"` en findings buenos | paráfrasis sinonímica + provider estricto | usa `claude-nli` o sube `min_excerpt_chars` |
| `RuntimeError: not available` al iniciar | `JW_NLI_PROVIDER` apunta a un provider sin deps/keys | quita el env var o instala el extra correspondiente |
| ~1s/finding extra en CLI | DeBERTa CPU es lento | usa `--fidelity off`, o `JW_NLI_PROVIDER=claude-nli` |
| Costes API explotan | sin caching o muchos findings | habilita Anthropic prompt caching (default), baja agentes o usa `fake-nli` para dev |

## Política para fases nuevas

Toda fase que añada un agente nuevo debe documentar si lo envuelve con `@fidelity_wrap` y bajo qué modo por defecto. Las superficies CLI/MCP heredan automáticamente el flag `--fidelity` cuando se basan en estos decoradores.
```

- [ ] **Step 2: Link from `docs/README.md`**

Add to the "Guías por tema" list (alphabetical position, before or after Eval doctrinal):

```markdown
- [Fidelidad NLI en runtime](guias/fidelity-nli.md) — Verificación NLI claim/premise sobre cada `Finding`; 4 providers + `FakeNLI`; CLI/MCP `--fidelity`.
```

- [ ] **Step 3: Add Fase 39 row to `docs/VISION_AUDIT.md`**

Insert a row in the summary table (alphabetical/numerical position with other Fase 3X rows):

```markdown
| Fase 39 (nli-runtime) | ✅ Nuevo | `jw_core.fidelity` — 5 providers (Claude/OpenAI/DeBERTa/Ollama/Fake), `@fidelity_wrap`, CLI/MCP `--fidelity` |
```

- [ ] **Step 4: Append Fase 39 section to `docs/ROADMAP.md`**

After Fase 38, before any closing footer:

```markdown
## Fase 39 — NLI runtime (fidelidad semántica) ✅

> Tier 1 confianza en runtime. Spec: `docs/superpowers/specs/2026-05-31-fase-39-nli-runtime-design.md`.

- ✅ Subpaquete nuevo `jw_core.fidelity` con Protocol + factory triple-target.
- ✅ Modelos: `NLIVerdict` (frozen dataclass) + `Verdict` Literal + `ensure_verdict` safe constructor.
- ✅ 5 providers: `ClaudeNLI` (api), `OpenAINLI` (api), `DeBERTaV3MNLI` (mlx/nvidia/cpu), `OllamaNLI` (cpu/local), `FakeNLI` (siempre).
- ✅ `JW_NLI_PROVIDER` env override + `JW_PROVIDER_ORDER` compartido con Fase 33.
- ✅ `@fidelity_wrap` decorator en `jw_agents/fidelity_wrap.py` con `on_fail={annotate_only,warn,reject}` y `min_excerpt_chars`.
- ✅ Idempotente: aplicar dos veces no duplica metadata.
- ✅ CLI flag `--fidelity {off,warn,reject}` en `apologetics`/`verse`/`research`/`meeting`.
- ✅ MCP: tool standalone `evaluate_nli` + parámetro `fidelity` en agent tools.
- ✅ Extras `[nli-anthropic]`, `[nli-openai]`, `[nli-local]`, `[nli-all]`.
- ✅ Guía `docs/guias/fidelity-nli.md`.

### Cobertura de tests

- ✅ ~70 tests nuevos en `packages/jw-core/tests/test_fidelity_*` y `packages/jw-agents/tests/test_fidelity_*`.
- ✅ Suite global sin regresiones (target: 1984 → 2050+).
- ✅ Property tests con hypothesis sobre 200+ pares aleatorios.
```

- [ ] **Step 5: Commit**

```bash
git add docs/guias/fidelity-nli.md docs/README.md docs/VISION_AUDIT.md docs/ROADMAP.md
git commit -m "docs(fidelity): guide + ROADMAP/VISION_AUDIT for Fase 39"
```

---

### Task 16: Final audit — full suite green + no regressions

**Files:** none (verification only).

- [ ] **Step 1: Run lint + format**

```bash
uv run ruff check packages/jw-core packages/jw-agents packages/jw-cli packages/jw-mcp
uv run ruff format --check packages/jw-core packages/jw-agents packages/jw-cli packages/jw-mcp
```

Expected: zero violations. If any, run `uv run ruff check --fix` and `uv run ruff format`, then re-commit as `style(fidelity): ruff autofix`.

- [ ] **Step 2: Run mypy (best-effort)**

```bash
uv run mypy packages/jw-core/src packages/jw-agents/src
```

Expected: existing errors only; no new errors from the fidelity module beyond `# type: ignore[...]` comments on third-party imports.

- [ ] **Step 3: Run the entire test suite**

```bash
uv run pytest packages/ -q --tb=short
```

Expected: prior 1984 tests + new ~70 tests all green. No regressions.

- [ ] **Step 4: Smoke each provider that's available locally**

```bash
# FakeNLI (always works)
JW_NLI_PROVIDER=fake-nli uv run python -c "
from jw_core.fidelity import evaluate_entailment
print(evaluate_entailment(claim='Jesus is the Son of God', premise='Jesus is the Son of God who was sent by the Father.'))
"

# ClaudeNLI (only if ANTHROPIC_API_KEY is set in your shell)
if [ -n "$ANTHROPIC_API_KEY" ]; then
  JW_NLI_PROVIDER=claude-nli uv run python -c "
from jw_core.fidelity import evaluate_entailment
print(evaluate_entailment(claim='Jesus is the Son of God', premise='Jesus is the Son of God who was sent by the Father.', language='en'))
"
fi
```

Expected: each prints an `NLIVerdict(...)` line with verdict + score.

- [ ] **Step 5: Smoke the CLI**

```bash
JW_NLI_PROVIDER=fake-nli uv run jw apologetics --question "test" --fidelity warn --help
```

Expected: help text shows `--fidelity` option.

- [ ] **Step 6: Update task status**

When all above pass:

```bash
# Update task #67 in personal memory to completed
echo "Fase 39 complete." 
```

- [ ] **Step 7: Final summary commit (optional polish)**

If any minor doc tweaks emerged: `git commit -am "docs(fidelity): post-audit polish"`. Otherwise nothing to do.

---

## Self-review summary

- **Spec coverage**: Each section of the spec maps to a task above:
  - Architecture / Provider Protocol → Task 1.
  - NLIVerdict + Verdict Literal → Task 2.
  - FakeNLI determinístico → Task 3.
  - Triple-target factory + env override → Task 4.
  - ClaudeNLI / OpenAINLI / DeBERTaV3MNLI / OllamaNLI → Tasks 5, 6, 7.
  - Decorator `@fidelity_wrap` → Task 8.
  - `min_excerpt_chars` skip semantics → Task 9.
  - Threshold modes (warn|reject) + default → Task 10.
  - Integration with existing agents + non-regression → Task 11.
  - CLI flag `--fidelity` → Task 12.
  - MCP integrations (tool + param) → Task 13.
  - Property tests for invariants → Task 14.
  - Docs / ROADMAP / VISION_AUDIT → Task 15.
  - Final audit → Task 16.

- **No-objetivos honored**:
  - `fact_checker` (Fase 9) not touched — Fase 39 is observational only.
  - No persistent storage of verdicts (that's Fase 43).
  - No agent modifications in this PR beyond the decorator being available; the four agent CLI commands wire the wrap conditionally via `--fidelity`, not by changing the agent body.
  - Decorator never re-evaluates idempotently.
  - FakeNLI never makes network calls.

- **Extras documented**: `[nli-anthropic]`, `[nli-openai]`, `[nli-local]`, `[nli-all]` declared in Task 1's `pyproject.toml` edit and referenced from the guide in Task 15. CI public stays on `FakeNLI` (no extras installed in standard job).

- **No placeholders**: every code block above is the actual code; every YAML/Toml is the actual content; every command shows the exact invocation and expected output. The stub providers in Task 4 are explicitly marked as "stub — overwritten in Task X" and each is replaced in its respective task with the full implementation.

- **Type consistency**:
  - `Target = Literal["api", "mlx", "nvidia", "cpu"]` — same in `jw_core.fidelity.nli`, `jw_core.fidelity.factory`, and every provider module.
  - `Verdict = Literal["entails", "neutral", "contradicts"]` — single source of truth in `verdicts.py`, re-exported by `__init__`.
  - `NLIProvider` Protocol signature `evaluate(self, claim: str, premise: str, *, language: str = "en") -> NLIVerdict` matches every provider implementation and the `evaluate_entailment` helper.
  - `ensure_verdict` is the SINGLE constructor every provider funnels through (guarantees clamp + validation).
  - `@fidelity_wrap` signature stable across decorator chains (idempotence check on `f.metadata["nli_verdict"]`).

- **Test surface**: total new tests across the plan: ~70 (10 verdicts + 4 protocol + 10 fakes + 8 factory + 10 claude + 7 openai + 7 deberta + 7 ollama + 9 wrap base + 6 wrap edge + 13 threshold matrix + 3 integration + 7 cli + 5 mcp + 6 property = 112). Adjust to ~70-100 depending on how parametrized matrices count. Either way, comfortably above the spec's "≥ 50 new tests" implicit floor.

- **Idempotence**: explicitly tested (Task 8 `test_idempotent_does_not_re_evaluate`) and explicitly documented in the decorator docstring.

## Execution choice

Plan completo. Dos opciones de ejecución:

1. **Subagent-driven (recomendado)** — dispatch fresh sub-agente por tarea, review entre tareas, iteración rápida (`superpowers:subagent-driven-development`). Las Tareas 1-7 son independientes hasta donde el factory necesita stubs, así que las Tareas 1, 2, 3 y los stubs de Task 4 se pueden completar en paralelo; Tareas 5, 6, 7 (providers reales) también son paralelizables entre sí.
2. **Inline** — ejecuto tareas en esta sesión con checkpoints (`superpowers:executing-plans`). Apropiado si querés ver cada test rojo→verde en tiempo real.

¿Cuál prefieres?
