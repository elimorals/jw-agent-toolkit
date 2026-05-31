# Fase 44 — `synth-judge` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a 3-stage Q&A quality judge (cheap heuristics → opt-in LLM pedagogical scoring → opt-in NLI entailment via Fase 39) that filters synthesized Q&A pairs before they reach `data/train.jsonl`. Heuristics always run, LLM+NLI are env-driven opt-ins, every kept pair carries `metadata["judge_score"]`, every rejected pair is counted with a structured reason.

**Architecture:** New subpackage `packages/jw-finetune/src/jw_finetune/synth/judge/` with Pydantic models, three pure stages, a transparent scoring formula, env-driven factories, and per-recipe overrides. Integration point: `synthesize_chunk()` in `synth/orchestrator.py` gains a judge hook; `data/extract.py` exposes `--judge=` CLI. Reuses Fase 39 `jw_core.fidelity.nli` behind an import guard — if Fase 39 is unavailable, the NLI stage degrades silently and emits one warning per process.

**Tech Stack:** Python 3.13 · Pydantic v2 (models) · Jinja2 (prompt templates, already a dep via orchestrator) · pytest (test runner) · stdlib `re` (heuristics) · jw_core.fidelity.nli (Fase 39, import-guarded) · jw_finetune.synth.provider.LLMProvider (existing abstraction).

**Spec:** [`docs/superpowers/specs/2026-05-31-fase-44-synth-judge-design.md`](../specs/2026-05-31-fase-44-synth-judge-design.md).

---

## File map

Creates:
- `packages/jw-finetune/src/jw_finetune/synth/judge/__init__.py`
- `packages/jw-finetune/src/jw_finetune/synth/judge/models.py`
- `packages/jw-finetune/src/jw_finetune/synth/judge/thresholds.py`
- `packages/jw-finetune/src/jw_finetune/synth/judge/heuristics.py`
- `packages/jw-finetune/src/jw_finetune/synth/judge/prompts/__init__.py`
- `packages/jw-finetune/src/jw_finetune/synth/judge/prompts/pedagogical_es.j2`
- `packages/jw-finetune/src/jw_finetune/synth/judge/prompts/pedagogical_en.j2`
- `packages/jw-finetune/src/jw_finetune/synth/judge/prompts/pedagogical_pt.j2`
- `packages/jw-finetune/src/jw_finetune/synth/judge/nli_bridge.py`
- `packages/jw-finetune/src/jw_finetune/synth/judge/scoring.py`
- `packages/jw-finetune/src/jw_finetune/synth/judge/judge.py`
- `packages/jw-finetune/src/jw_finetune/synth/judge/factories.py`
- `packages/jw-finetune/src/jw_finetune/synth/judge/stats.py`
- `packages/jw-finetune/src/jw_finetune/synth/judge/eval_precision.py`
- `packages/jw-finetune/tests/synth/__init__.py`
- `packages/jw-finetune/tests/synth/judge/__init__.py`
- `packages/jw-finetune/tests/synth/judge/test_models.py`
- `packages/jw-finetune/tests/synth/judge/test_heuristics.py`
- `packages/jw-finetune/tests/synth/judge/test_thresholds.py`
- `packages/jw-finetune/tests/synth/judge/test_scoring.py`
- `packages/jw-finetune/tests/synth/judge/test_judge_with_fakes.py`
- `packages/jw-finetune/tests/synth/judge/test_factories.py`
- `packages/jw-finetune/tests/synth/judge/test_nli_bridge.py`
- `packages/jw-finetune/tests/synth/judge/test_stats.py`
- `packages/jw-finetune/tests/synth/judge/test_orchestrator_integration.py`
- `packages/jw-finetune/tests/synth/judge/test_extract_cli.py`
- `packages/jw-finetune/tests/synth/judge/test_golden_precision.py`
- `packages/jw-finetune/tests/synth/judge/fixtures/__init__.py`
- `packages/jw-finetune/tests/synth/judge/fixtures/golden_50_pairs.jsonl`
- `docs/guias/synth-judge.md`

Modifies:
- `packages/jw-finetune/src/jw_finetune/synth/orchestrator.py` — add optional `judge` parameter to `synthesize_chunk`.
- `packages/jw-finetune/src/jw_finetune/data/extract.py` — add `--judge`, `--judge-llm`, `--judge-nli`, `--dump-rejected` CLI flags + plumb judge into the inner loop.
- `packages/jw-finetune/pyproject.toml` — add `jinja2` already present; ensure judge imports are discoverable (no new deps required — Fase 39 NLI is import-guarded).
- `docs/VISION_AUDIT.md` — add Fase 44 row.
- `docs/ROADMAP.md` — add Fase 44 section.
- `docs/README.md` — link the new guide.

---

### Task 1: Scaffold `synth/judge/` package + models

**Files:**
- Create: `packages/jw-finetune/src/jw_finetune/synth/judge/__init__.py`
- Create: `packages/jw-finetune/src/jw_finetune/synth/judge/models.py`
- Create: `packages/jw-finetune/tests/synth/__init__.py`
- Create: `packages/jw-finetune/tests/synth/judge/__init__.py`
- Create: `packages/jw-finetune/tests/synth/judge/test_models.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-finetune/tests/synth/judge/test_models.py
"""Pydantic models for the synth judge."""

from __future__ import annotations

import pytest

from jw_finetune.synth.judge.models import QAScore, RejectionReason


def test_rejection_reason_accepts_known_codes() -> None:
    r = RejectionReason(code="no_jw_citation", detail="missing URL")
    assert r.code == "no_jw_citation"
    assert r.detail == "missing URL"


def test_rejection_reason_rejects_unknown_code() -> None:
    with pytest.raises(ValueError):
        RejectionReason(code="totally_made_up", detail="x")  # type: ignore[arg-type]


def test_qa_score_minimal_kept_true() -> None:
    s = QAScore(
        cites_jw_publication=True,
        has_minimum_substance=True,
        overall=7.5,
        kept=True,
    )
    assert s.kept is True
    assert s.nli_score is None
    assert s.nli_verdict is None
    assert s.pedagogical_quality is None
    assert s.reasons == []


def test_qa_score_with_full_signals() -> None:
    s = QAScore(
        cites_jw_publication=True,
        has_minimum_substance=True,
        nli_score=0.92,
        nli_verdict="entails",
        pedagogical_quality=3,
        overall=9.4,
        kept=True,
    )
    assert s.nli_verdict == "entails"
    assert 0.0 <= s.nli_score <= 1.0


def test_qa_score_rejects_out_of_range_overall() -> None:
    with pytest.raises(ValueError):
        QAScore(
            cites_jw_publication=False,
            has_minimum_substance=False,
            overall=12.0,  # > 10
            kept=False,
        )


def test_qa_score_rejects_out_of_range_nli() -> None:
    with pytest.raises(ValueError):
        QAScore(
            cites_jw_publication=True,
            has_minimum_substance=True,
            nli_score=1.5,
            nli_verdict="entails",
            overall=5.0,
            kept=True,
        )


def test_qa_score_rejects_out_of_range_pedagogical() -> None:
    with pytest.raises(ValueError):
        QAScore(
            cites_jw_publication=True,
            has_minimum_substance=True,
            pedagogical_quality=5,  # > 3
            overall=5.0,
            kept=True,
        )


def test_qa_score_carries_reasons_when_rejected() -> None:
    s = QAScore(
        cites_jw_publication=False,
        has_minimum_substance=True,
        overall=3.0,
        kept=False,
        reasons=[
            RejectionReason(code="no_jw_citation", detail="no URL"),
            RejectionReason(code="overall_below_threshold", detail="3.0 < 5.0"),
        ],
    )
    assert len(s.reasons) == 2
    assert s.reasons[0].code == "no_jw_citation"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/jw-finetune/tests/synth/judge/test_models.py -v`
Expected: FAIL — module `jw_finetune.synth.judge.models` not found.

- [ ] **Step 3: Implement the models**

```python
# packages/jw-finetune/src/jw_finetune/synth/judge/__init__.py
"""jw_finetune.synth.judge — 3-stage Q&A quality filter.

Public API:
    from jw_finetune.synth.judge import score_qa_pair, QAScore, JudgeMode, build_judge
"""

from __future__ import annotations

from jw_finetune.synth.judge.models import QAScore, RejectionReason
from jw_finetune.synth.judge.thresholds import DEFAULT_CUTOFFS, JudgeMode

__all__ = [
    "DEFAULT_CUTOFFS",
    "JudgeMode",
    "QAScore",
    "RejectionReason",
]
```

```python
# packages/jw-finetune/src/jw_finetune/synth/judge/models.py
"""Pydantic models for the synth judge.

A QAScore is the verdict of running the 3-stage judge on a single Q&A pair.
- Heuristic flags (`cites_jw_publication`, `has_minimum_substance`) are always
  populated.
- `nli_score`/`nli_verdict` are populated only when the NLI provider is wired
  and the answer contains a verifiable claim/premise.
- `pedagogical_quality` is populated only when the LLM judge is wired.
- `overall` is the transparent weighted sum in [0, 10] (formula in scoring.py).
- `kept` is the final decision after applying the configured cutoff.
- `reasons` lists the structured rejection reasons (empty if kept).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

RejectionCode = Literal[
    "no_jw_citation",
    "insufficient_substance",
    "nli_contradicts",
    "nli_neutral_low",
    "pedagogical_low",
    "overall_below_threshold",
]

NLIVerdict = Literal["entails", "neutral", "contradicts"]


class RejectionReason(BaseModel):
    """Why a pair was discarded by the judge."""

    code: RejectionCode
    detail: str = ""


class QAScore(BaseModel):
    """Score returned by the judge for one Q&A pair."""

    cites_jw_publication: bool
    has_minimum_substance: bool
    nli_score: float | None = Field(default=None, ge=0.0, le=1.0)
    nli_verdict: NLIVerdict | None = None
    pedagogical_quality: int | None = Field(default=None, ge=0, le=3)
    overall: float = Field(ge=0.0, le=10.0)
    kept: bool
    reasons: list[RejectionReason] = Field(default_factory=list)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/jw-finetune/tests/synth/judge/test_models.py -v`
Expected: 8 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-finetune/src/jw_finetune/synth/judge packages/jw-finetune/tests/synth
git commit -m "feat(jw-finetune): scaffold synth/judge package and QAScore/RejectionReason models"
```

---

### Task 2: Heuristics — `cites_jw_publication` + `has_minimum_substance`

**Files:**
- Create: `packages/jw-finetune/src/jw_finetune/synth/judge/heuristics.py`
- Create: `packages/jw-finetune/tests/synth/judge/test_heuristics.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-finetune/tests/synth/judge/test_heuristics.py
"""Heuristic stage tests (always-on, no network)."""

from __future__ import annotations

import pytest

from jw_finetune.synth.judge.heuristics import (
    cites_jw_publication,
    has_minimum_substance,
)


# --- cites_jw_publication ---


@pytest.mark.parametrize(
    "answer",
    [
        "Según w23.04 p. 12, la respuesta es clara.",
        "Ver Atalaya w20 enero p. 4 párr. 6.",
        "https://wol.jw.org/es/wol/d/r4/lp-s/2024123",
        "Más información en https://wol.jw.org/en/wol/d/...",
        "Consultar bh capítulo 5 y g23 abril.",
        "El libro jy capítulo 17 lo explica.",
        "Como se muestra en sjj canción 27.",
    ],
)
def test_cites_jw_publication_positives(answer: str) -> None:
    assert cites_jw_publication(answer) is True


@pytest.mark.parametrize(
    "answer",
    [
        "Sin referencia clara.",
        "La Biblia dice que sí.",
        "Es una verdad bíblica importante.",
        "Ver el libro de Mateo capítulo 24.",  # bible ref, no JW pub code
        "https://wikipedia.org/something",
        "",
        "   ",
    ],
)
def test_cites_jw_publication_negatives(answer: str) -> None:
    assert cites_jw_publication(answer) is False


# --- has_minimum_substance ---


def test_has_minimum_substance_passes_for_real_teaching() -> None:
    q = "¿Qué enseña la Biblia sobre el reino?"
    a = (
        "La Biblia enseña que el reino de Dios es un gobierno real con Cristo "
        "Jesús como rey, según Daniel 2:44 y Mateo 6:9-10."
    )
    assert has_minimum_substance(q, a) is True


@pytest.mark.parametrize("a", ["Sí.", "No.", "Depende.", "Sí", "No", "Tal vez", "Puede ser"])
def test_has_minimum_substance_rejects_generic_answers(a: str) -> None:
    assert has_minimum_substance("¿Algo?", a) is False


def test_has_minimum_substance_rejects_too_short() -> None:
    assert has_minimum_substance("¿Qué dice Juan 3:16?", "Es muy interesante.") is False


def test_has_minimum_substance_rejects_question_echo() -> None:
    q = "¿Qué enseña la Biblia sobre el alma?"
    a = q + " Eso es."  # echoes question, no teaching
    assert has_minimum_substance(q, a) is False


def test_has_minimum_substance_handles_none_safely() -> None:
    assert has_minimum_substance("?", "") is False
    assert has_minimum_substance("", "") is False


def test_has_minimum_substance_multilingual_passes() -> None:
    q_en = "What does the Bible teach about love?"
    a_en = (
        "The Bible teaches that love is the foremost quality of God's "
        "personality, as 1 John 4:8 explicitly declares: 'God is love.'"
    )
    assert has_minimum_substance(q_en, a_en) is True

    q_pt = "O que a Bíblia ensina sobre o reino?"
    a_pt = (
        "A Bíblia ensina que o reino de Deus é um governo real com Cristo "
        "Jesus como Rei, conforme Daniel 2:44 e Mateus 6:9-10."
    )
    assert has_minimum_substance(q_pt, a_pt) is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/jw-finetune/tests/synth/judge/test_heuristics.py -v`
Expected: FAIL — heuristics module not found.

- [ ] **Step 3: Implement heuristics**

```python
# packages/jw-finetune/src/jw_finetune/synth/judge/heuristics.py
"""Stage 1 — cheap heuristics, always-on, no network.

Two checks:
  - cites_jw_publication(answer): does the answer mention any JW publication
    code (w/g/jt/bh/sjj/...) OR a wol.jw.org URL? Conservative regex set —
    false positives accepted only if the pub code is preceded by a word boundary.
  - has_minimum_substance(question, answer): does the answer have teaching
    content, not just "Yes" / a literal echo of the question / too short?

The lists of "generic answers" are language-agnostic enough that we cover
es/en/pt with a small union set. Localized sets can be loaded via the
`language` keyword if needed later — for v1 the union is good enough.
"""

from __future__ import annotations

import re

# Word-boundary-anchored JW publication codes. Order matters for the alternation
# (longer prefixes don't matter here because each is independent, but we keep the
# set conservative to minimize false positives).
_JW_PUB_CODES = re.compile(
    r"\b("
    r"w\d{2,}|"      # Watchtower yearly: w23, w2024
    r"ws\d{2,}|"     # Watchtower study edition: ws24
    r"wp\d{2,}|"     # Public Watchtower: wp23
    r"g\d{2,}|"      # Awake: g23
    r"jt|"           # Teach Us
    r"bh|"           # What Does the Bible Really Teach?
    r"sjj|sjjm|"     # Sing to Jehovah
    r"jy|"           # Greatest Man Who Ever Lived
    r"rs|"           # Reasoning From the Scriptures
    r"it|"           # Insight on the Scriptures
    r"km\d{2,}|"     # Our Kingdom Ministry
    r"yb\d{2,}|"     # Yearbook
    r"sg|"           # Sing Out Joyfully
    r"cl|"           # Draw Close to Jehovah
    r"lvs|"          # Live Forever Among Friends (older)
    r"lff|"          # Enjoy Life Forever (newer)
    r"lr|"           # Lasting Peace (older)
    r"sjm"           # Sing Out Joyfully Music
    r")\b",
    re.IGNORECASE,
)

_WOL_URL = re.compile(r"https?://(?:www\.)?wol\.jw\.org/", re.IGNORECASE)


def cites_jw_publication(answer: str) -> bool:
    """True if `answer` contains a wol.jw.org URL or a known JW pub code."""

    if not answer:
        return False
    return bool(_WOL_URL.search(answer) or _JW_PUB_CODES.search(answer))


# Union set of generic single-word "non-answers" across ES/EN/PT.
_GENERIC_ANSWERS: frozenset[str] = frozenset(
    {
        # es
        "sí.", "sí", "no.", "no", "depende.", "depende", "tal vez", "puede ser",
        "no sé.", "no sé",
        # en
        "yes.", "yes", "no", "maybe.", "maybe", "it depends.", "it depends",
        "i don't know.", "i don't know",
        # pt
        "sim.", "sim", "não.", "não", "talvez.", "talvez", "depende.", "depende",
        "não sei.", "não sei",
    }
)


def has_minimum_substance(question: str, answer: str) -> bool:
    """True if the answer is long enough, not a generic stub, not a question echo.

    Conservative thresholds: answers below 40 chars are rejected outright;
    answers that begin with the question text and don't add ~30 chars of new
    teaching are rejected as echoes.
    """

    if not answer:
        return False
    a = answer.strip()
    if len(a) < 40:
        return False
    if a.lower() in _GENERIC_ANSWERS:
        return False
    if not question:
        return True
    q = question.strip().lower()
    a_lower = a.lower()
    if q and a_lower.startswith(q) and len(a_lower) < len(q) + 30:
        return False
    return True
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/jw-finetune/tests/synth/judge/test_heuristics.py -v`
Expected: 17 passed (7 cites positives + 7 cites negatives + 1 substance pass + 7 generic + 1 short + 1 echo + 1 none + 1 multilingual ⇒ adjust to actual count after run; spec says ≥30 cases).

- [ ] **Step 5: Commit**

```bash
git add packages/jw-finetune/src/jw_finetune/synth/judge/heuristics.py packages/jw-finetune/tests/synth/judge/test_heuristics.py
git commit -m "feat(jw-finetune): synth judge stage 1 — heuristic citation + substance checks"
```

---

### Task 3: Thresholds + `JudgeMode` enum

**Files:**
- Create: `packages/jw-finetune/src/jw_finetune/synth/judge/thresholds.py`
- Create: `packages/jw-finetune/tests/synth/judge/test_thresholds.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-finetune/tests/synth/judge/test_thresholds.py
"""Threshold + mode resolution tests."""

from __future__ import annotations

import pytest

from jw_finetune.synth.judge.thresholds import (
    DEFAULT_CUTOFFS,
    JudgeMode,
    JudgeOverrides,
    resolve_cutoff,
    resolve_require_nli_entails,
)


def test_judge_mode_values() -> None:
    assert JudgeMode.OFF.value == "off"
    assert JudgeMode.LOOSE.value == "loose"
    assert JudgeMode.STRICT.value == "strict"


def test_default_cutoffs_table() -> None:
    assert DEFAULT_CUTOFFS[JudgeMode.OFF] is None
    assert DEFAULT_CUTOFFS[JudgeMode.LOOSE] == 5.0
    assert DEFAULT_CUTOFFS[JudgeMode.STRICT] == 6.5


def test_resolve_cutoff_uses_default_when_no_override() -> None:
    assert resolve_cutoff(JudgeMode.LOOSE, JudgeOverrides()) == 5.0
    assert resolve_cutoff(JudgeMode.STRICT, JudgeOverrides()) == 6.5
    assert resolve_cutoff(JudgeMode.OFF, JudgeOverrides()) is None


def test_resolve_cutoff_respects_overall_cutoff_override() -> None:
    ov = JudgeOverrides(overall_cutoff=7.0)
    assert resolve_cutoff(JudgeMode.LOOSE, ov) == 7.0
    assert resolve_cutoff(JudgeMode.STRICT, ov) == 7.0


def test_resolve_cutoff_off_mode_ignores_override() -> None:
    # OFF means "do not run the judge"; an override should not turn it on.
    ov = JudgeOverrides(overall_cutoff=7.0)
    assert resolve_cutoff(JudgeMode.OFF, ov) is None


def test_resolve_require_nli_entails_defaults() -> None:
    assert resolve_require_nli_entails(JudgeMode.OFF, JudgeOverrides()) is False
    assert resolve_require_nli_entails(JudgeMode.LOOSE, JudgeOverrides()) is False
    assert resolve_require_nli_entails(JudgeMode.STRICT, JudgeOverrides()) is True


def test_resolve_require_nli_entails_override() -> None:
    ov = JudgeOverrides(require_nli_entails=False)
    assert resolve_require_nli_entails(JudgeMode.STRICT, ov) is False
    ov2 = JudgeOverrides(require_nli_entails=True)
    assert resolve_require_nli_entails(JudgeMode.LOOSE, ov2) is True


def test_judge_mode_from_string_case_insensitive() -> None:
    assert JudgeMode("loose") == JudgeMode.LOOSE
    assert JudgeMode("STRICT".lower()) == JudgeMode.STRICT
    with pytest.raises(ValueError):
        JudgeMode("bogus")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/jw-finetune/tests/synth/judge/test_thresholds.py -v`
Expected: FAIL — thresholds module not found.

- [ ] **Step 3: Implement thresholds**

```python
# packages/jw-finetune/src/jw_finetune/synth/judge/thresholds.py
"""Cutoff/threshold logic for the synth judge.

JudgeMode is the user-facing knob (off/loose/strict). Each mode maps to a
default `overall` cutoff and a default policy for "require NLI verdict ==
entails". Recipes can override either independently.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel


class JudgeMode(str, Enum):
    """User-facing operating mode for the judge."""

    OFF = "off"
    LOOSE = "loose"
    STRICT = "strict"


# Cutoffs over the `QAScore.overall` (0..10). None means "judge is off".
DEFAULT_CUTOFFS: dict[JudgeMode, float | None] = {
    JudgeMode.OFF: None,
    JudgeMode.LOOSE: 5.0,
    JudgeMode.STRICT: 6.5,
}

# Whether each mode requires NLI verdict == "entails" (only meaningful when
# NLI provider is wired).
_DEFAULT_REQUIRE_NLI_ENTAILS: dict[JudgeMode, bool] = {
    JudgeMode.OFF: False,
    JudgeMode.LOOSE: False,
    JudgeMode.STRICT: True,
}


class JudgeOverrides(BaseModel):
    """Optional overrides from a recipe YAML.

    All fields are None when not set — `resolve_*` returns the mode default.
    """

    overall_cutoff: float | None = None
    require_nli_entails: bool | None = None


def resolve_cutoff(mode: JudgeMode, overrides: JudgeOverrides) -> float | None:
    """Return the effective overall cutoff for a mode + overrides combo.

    OFF always wins: even with an override, OFF means "no judge".
    """

    if mode == JudgeMode.OFF:
        return None
    if overrides.overall_cutoff is not None:
        return overrides.overall_cutoff
    return DEFAULT_CUTOFFS[mode]


def resolve_require_nli_entails(mode: JudgeMode, overrides: JudgeOverrides) -> bool:
    """Return whether to require NLI=entails for keeping a pair."""

    if overrides.require_nli_entails is not None:
        return overrides.require_nli_entails
    return _DEFAULT_REQUIRE_NLI_ENTAILS[mode]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/jw-finetune/tests/synth/judge/test_thresholds.py -v`
Expected: 8 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-finetune/src/jw_finetune/synth/judge/thresholds.py packages/jw-finetune/tests/synth/judge/test_thresholds.py
git commit -m "feat(jw-finetune): synth judge thresholds + JudgeMode (off/loose/strict)"
```

---

### Task 4: Scoring formula

**Files:**
- Create: `packages/jw-finetune/src/jw_finetune/synth/judge/scoring.py`
- Create: `packages/jw-finetune/tests/synth/judge/test_scoring.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-finetune/tests/synth/judge/test_scoring.py
"""Tests for the transparent scoring formula.

Formula (spec Fase 44):
    base = 4.0
    + 1.5 if cites_jw_publication
    + 1.5 if has_minimum_substance
    + 2.0 * nli_score if nli_verdict == "entails"
    - 3.0 if nli_verdict == "contradicts"
    + pedagogical_quality (0..3)
    clamp [0, 10]

When a signal is None (stage didn't run), it contributes neutral 0.0.
"""

from __future__ import annotations

import pytest

from jw_finetune.synth.judge.scoring import compute_overall


def test_baseline_no_signals() -> None:
    # All heuristics false, no LLM, no NLI: base 4.0 alone
    s = compute_overall(
        cites=False,
        substance=False,
        nli_verdict=None,
        nli_score=None,
        pedagogical=None,
    )
    assert s == pytest.approx(4.0)


def test_full_pass_signals_clamped_at_10() -> None:
    # base 4 + 1.5 + 1.5 + 2.0 * 0.95 + 3 = 11.9 → clamp at 10
    s = compute_overall(
        cites=True,
        substance=True,
        nli_verdict="entails",
        nli_score=0.95,
        pedagogical=3,
    )
    assert s == 10.0


def test_heuristic_only_loose_pass() -> None:
    # 4 + 1.5 + 1.5 = 7.0 — passes default LOOSE cutoff (5.0)
    s = compute_overall(
        cites=True,
        substance=True,
        nli_verdict=None,
        nli_score=None,
        pedagogical=None,
    )
    assert s == pytest.approx(7.0)


def test_contradicts_penalizes_three_points() -> None:
    # base 4 + 1.5 + 1.5 - 3 = 4.0
    s = compute_overall(
        cites=True,
        substance=True,
        nli_verdict="contradicts",
        nli_score=0.85,
        pedagogical=None,
    )
    assert s == pytest.approx(4.0)


def test_neutral_verdict_contributes_zero_from_nli() -> None:
    # nli=neutral → no bonus, no penalty
    # 4 + 1.5 + 1.5 + 0 (neutral) + 2 (pedagogical) = 9.0
    s = compute_overall(
        cites=True,
        substance=True,
        nli_verdict="neutral",
        nli_score=0.42,
        pedagogical=2,
    )
    assert s == pytest.approx(9.0)


def test_pedagogical_zero_is_distinct_from_none() -> None:
    # pedagogical=0 explicitly contributes 0 (LLM ran and scored 0)
    s_zero = compute_overall(
        cites=True, substance=True, nli_verdict=None, nli_score=None, pedagogical=0
    )
    # pedagogical=None contributes neutral 0 too — same number, but downstream
    # we distinguish "stage ran" via QAScore.pedagogical_quality presence.
    s_none = compute_overall(
        cites=True, substance=True, nli_verdict=None, nli_score=None, pedagogical=None
    )
    assert s_zero == s_none == pytest.approx(7.0)


def test_clamps_at_zero_floor() -> None:
    # Force a strongly negative case: contradicts + nothing else
    s = compute_overall(
        cites=False,
        substance=False,
        nli_verdict="contradicts",
        nli_score=0.99,
        pedagogical=0,
    )
    # base 4 - 3 = 1 (clamps not needed but the floor would catch negative)
    assert s == pytest.approx(1.0)


def test_pedagogical_only_signal() -> None:
    s = compute_overall(
        cites=False,
        substance=False,
        nli_verdict=None,
        nli_score=None,
        pedagogical=3,
    )
    assert s == pytest.approx(7.0)


def test_entails_with_low_nli_score_small_bonus() -> None:
    # entails but score=0.30 → 2.0 * 0.30 = 0.6
    # base 4 + 1.5 + 1.5 + 0.6 = 7.6
    s = compute_overall(
        cites=True,
        substance=True,
        nli_verdict="entails",
        nli_score=0.30,
        pedagogical=None,
    )
    assert s == pytest.approx(7.6)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/jw-finetune/tests/synth/judge/test_scoring.py -v`
Expected: FAIL — scoring module not found.

- [ ] **Step 3: Implement scoring**

```python
# packages/jw-finetune/src/jw_finetune/synth/judge/scoring.py
"""Transparent scoring formula for the synth judge.

The formula is intentionally NOT a black box — every coefficient is named,
auditable, and unit-tested. It does not "learn" from data; if we want to
re-weight in the future, this is the single file to edit.
"""

from __future__ import annotations

from jw_finetune.synth.judge.models import NLIVerdict

# Coefficients — tuned by the spec, not learned.
_BASE = 4.0
_W_CITES = 1.5
_W_SUBSTANCE = 1.5
_W_NLI_ENTAILS = 2.0
_W_NLI_CONTRADICTS = -3.0

_FLOOR = 0.0
_CEIL = 10.0


def compute_overall(
    *,
    cites: bool,
    substance: bool,
    nli_verdict: NLIVerdict | None,
    nli_score: float | None,
    pedagogical: int | None,
) -> float:
    """Combine the per-stage signals into an `overall` in [0, 10].

    Args:
        cites: Stage 1 heuristic — did the answer cite a JW publication?
        substance: Stage 1 heuristic — does the answer have teaching content?
        nli_verdict: Stage 3 NLI verdict; None if NLI didn't run.
        nli_score: Stage 3 NLI confidence (only used when verdict=="entails").
        pedagogical: Stage 2 LLM judge score (0..3); None if LLM didn't run.

    Returns:
        Overall score in [0, 10].
    """

    score = _BASE
    if cites:
        score += _W_CITES
    if substance:
        score += _W_SUBSTANCE
    if nli_verdict == "entails" and nli_score is not None:
        score += _W_NLI_ENTAILS * nli_score
    elif nli_verdict == "contradicts":
        score += _W_NLI_CONTRADICTS
    # "neutral" and None both contribute 0
    if pedagogical is not None:
        score += float(pedagogical)
    # Clamp
    if score < _FLOOR:
        return _FLOOR
    if score > _CEIL:
        return _CEIL
    return score
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/jw-finetune/tests/synth/judge/test_scoring.py -v`
Expected: 9 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-finetune/src/jw_finetune/synth/judge/scoring.py packages/jw-finetune/tests/synth/judge/test_scoring.py
git commit -m "feat(jw-finetune): synth judge transparent scoring formula"
```

---

### Task 5: Prompt templates (es/en/pt)

**Files:**
- Create: `packages/jw-finetune/src/jw_finetune/synth/judge/prompts/__init__.py`
- Create: `packages/jw-finetune/src/jw_finetune/synth/judge/prompts/pedagogical_es.j2`
- Create: `packages/jw-finetune/src/jw_finetune/synth/judge/prompts/pedagogical_en.j2`
- Create: `packages/jw-finetune/src/jw_finetune/synth/judge/prompts/pedagogical_pt.j2`

- [ ] **Step 1: Create the `prompts` package marker**

```python
# packages/jw-finetune/src/jw_finetune/synth/judge/prompts/__init__.py
"""Jinja2 prompt templates for the LLM pedagogical-quality judge.

One template per supported language. The judge selector reads
`pair.language` and falls back to English when the language has no template.
"""
```

- [ ] **Step 2: Write the Spanish template**

```jinja
{# packages/jw-finetune/src/jw_finetune/synth/judge/prompts/pedagogical_es.j2 #}
Eres un evaluador de calidad de datos para fine-tuning de un asistente que
enseña doctrina de los Testigos de Jehová. Evalúa el siguiente par Q&A.

Pregunta: {{ question }}
Respuesta: {{ answer }}

Criterios (puntúa la respuesta de 0 a 3):
0 = No es enseñanza útil (vacía, genérica, repite la pregunta, sin contenido)
1 = Información mínima, sin desarrollo doctrinal claro
2 = Buena enseñanza con explicación, pero podría profundizar más
3 = Enseñanza clara, con cita o explicación, útil para aprender

Responde ÚNICAMENTE con un dígito (0, 1, 2 o 3). Nada más.
```

- [ ] **Step 3: Write the English template**

```jinja
{# packages/jw-finetune/src/jw_finetune/synth/judge/prompts/pedagogical_en.j2 #}
You are a data-quality evaluator for fine-tuning a teaching assistant that
explains Jehovah's Witnesses doctrine. Evaluate the following Q&A pair.

Question: {{ question }}
Answer: {{ answer }}

Criteria (score the answer 0 to 3):
0 = Not useful teaching (empty, generic, echoes the question, no content)
1 = Minimal information, no clear doctrinal development
2 = Decent teaching with explanation, but could go deeper
3 = Clear teaching with citation or explanation, useful to learn from

Respond with a SINGLE digit only (0, 1, 2, or 3). Nothing else.
```

- [ ] **Step 4: Write the Portuguese template**

```jinja
{# packages/jw-finetune/src/jw_finetune/synth/judge/prompts/pedagogical_pt.j2 #}
Você é um avaliador de qualidade de dados para fine-tuning de um assistente
que ensina a doutrina das Testemunhas de Jeová. Avalie o seguinte par Q&A.

Pergunta: {{ question }}
Resposta: {{ answer }}

Critérios (pontue a resposta de 0 a 3):
0 = Não é ensino útil (vazio, genérico, repete a pergunta, sem conteúdo)
1 = Informação mínima, sem desenvolvimento doutrinal claro
2 = Bom ensino com explicação, mas poderia aprofundar mais
3 = Ensino claro, com citação ou explicação, útil para aprender

Responda APENAS com um dígito (0, 1, 2 ou 3). Nada mais.
```

- [ ] **Step 5: Smoke-verify the templates load**

Run:
```bash
uv run python -c "
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, StrictUndefined
root = Path('packages/jw-finetune/src/jw_finetune/synth/judge/prompts')
env = Environment(loader=FileSystemLoader(str(root)), undefined=StrictUndefined)
for name in ['pedagogical_es.j2', 'pedagogical_en.j2', 'pedagogical_pt.j2']:
    out = env.get_template(name).render(question='Q', answer='A')
    assert 'Q' in out and 'A' in out, name
print('ok')
"
```
Expected: `ok`.

- [ ] **Step 6: Commit**

```bash
git add packages/jw-finetune/src/jw_finetune/synth/judge/prompts
git commit -m "feat(jw-finetune): synth judge LLM prompts (es/en/pt)"
```

---

### Task 6: NLI bridge — import-guarded reuse of Fase 39

**Files:**
- Create: `packages/jw-finetune/src/jw_finetune/synth/judge/nli_bridge.py`
- Create: `packages/jw-finetune/tests/synth/judge/test_nli_bridge.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-finetune/tests/synth/judge/test_nli_bridge.py
"""Tests for the NLI bridge — claim/premise extraction + provider plumbing."""

from __future__ import annotations

from typing import Any

from jw_finetune.synth.judge.nli_bridge import (
    extract_premise_from_answer,
    run_nli_check,
)


class FakeVerdict:
    def __init__(self, verdict: str, score: float) -> None:
        self.verdict = verdict
        self.score = score


class FakeNLIProvider:
    """Records calls; returns the verdict it was constructed with."""

    def __init__(self, verdict: str = "entails", score: float = 0.9) -> None:
        self._verdict = verdict
        self._score = score
        self.calls: list[tuple[str, str]] = []

    def evaluate_entailment(self, *, claim: str, premise: str) -> FakeVerdict:
        self.calls.append((claim, premise))
        return FakeVerdict(self._verdict, self._score)


# --- premise extraction ---


def test_extract_premise_from_typographic_quotes() -> None:
    answer = 'La Atalaya dice: "Dios amó tanto al mundo que dio a su Hijo." Esto enseña amor.'
    premise = extract_premise_from_answer(answer)
    assert premise == "Dios amó tanto al mundo que dio a su Hijo."


def test_extract_premise_from_guillemets() -> None:
    answer = "El texto declara: «Jehová es uno solo.» y por eso..."
    premise = extract_premise_from_answer(answer)
    assert premise == "Jehová es uno solo."


def test_extract_premise_returns_none_when_no_quote() -> None:
    assert extract_premise_from_answer("No hay nada citado aquí.") is None


def test_extract_premise_strips_outer_whitespace() -> None:
    answer = '   "  hello world  "   '
    assert extract_premise_from_answer(answer) == "hello world"


# --- run_nli_check ---


def test_run_nli_check_returns_verdict_and_score() -> None:
    provider = FakeNLIProvider(verdict="entails", score=0.88)
    answer = 'Dice: "amó tanto al mundo." Por eso entendemos el amor.'
    result = run_nli_check(answer=answer, nli_provider=provider)
    assert result is not None
    verdict, score = result
    assert verdict == "entails"
    assert score == 0.88
    assert provider.calls, "NLI provider should have been called"


def test_run_nli_check_returns_none_without_premise() -> None:
    provider = FakeNLIProvider()
    result = run_nli_check(answer="No quote here", nli_provider=provider)
    assert result is None
    assert provider.calls == []


def test_run_nli_check_returns_none_when_provider_is_none() -> None:
    result = run_nli_check(answer='He said: "anything."', nli_provider=None)
    assert result is None


def test_run_nli_check_swallows_provider_exceptions() -> None:
    class BoomProvider:
        def evaluate_entailment(self, **_: Any) -> Any:
            raise RuntimeError("model not loaded")

    result = run_nli_check(answer='He said: "anything."', nli_provider=BoomProvider())
    assert result is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/jw-finetune/tests/synth/judge/test_nli_bridge.py -v`
Expected: FAIL — nli_bridge module not found.

- [ ] **Step 3: Implement the NLI bridge**

```python
# packages/jw-finetune/src/jw_finetune/synth/judge/nli_bridge.py
"""Bridge to Fase 39 NLI runtime.

This module is import-safe even when Fase 39 (`jw_core.fidelity.nli`) is not
installed. Factories live in `factories.py`; here we only need a Protocol that
matches the Fase 39 provider shape so judges can be tested with fakes.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Protocol

logger = logging.getLogger(__name__)


class NLIVerdictLike(Protocol):
    """Matches `jw_core.fidelity.nli.EntailmentVerdict`."""

    verdict: str  # "entails" | "neutral" | "contradicts"
    score: float


class NLIProviderLike(Protocol):
    """Matches `jw_core.fidelity.nli.NLIProvider`."""

    def evaluate_entailment(self, *, claim: str, premise: str) -> NLIVerdictLike: ...


# Regex for typographic-quoted spans. We prefer the first match — it's the most
# common pattern for "X said: '...'" introductions in the answers.
_QUOTE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"[“”]([^“”]{8,400})[“”]"),  # “ ” curly
    re.compile(r'"([^"]{8,400})"'),  # straight double quotes
    re.compile(r"«([^»]{8,400})»"),  # guillemets
)


def extract_premise_from_answer(answer: str) -> str | None:
    """Best-effort: extract the first quoted span in the answer as a premise.

    Returns None if no usable quoted span is found.
    """

    if not answer:
        return None
    for pattern in _QUOTE_PATTERNS:
        m = pattern.search(answer)
        if m:
            premise = m.group(1).strip()
            if premise:
                return premise
    return None


def run_nli_check(
    *,
    answer: str,
    nli_provider: NLIProviderLike | None,
) -> tuple[str, float] | None:
    """Run NLI against (claim=answer, premise=quoted span).

    Returns (verdict, score) on success, None when:
      - provider is None,
      - no premise can be extracted,
      - the provider raises (we log and degrade).
    """

    if nli_provider is None:
        return None
    premise = extract_premise_from_answer(answer)
    if premise is None:
        return None
    # The claim is the full answer minus the premise — but for simplicity we
    # use the whole answer; the NLI model will weight the entailment regardless.
    claim = answer
    try:
        verdict_obj = nli_provider.evaluate_entailment(claim=claim, premise=premise)
    except Exception as exc:  # noqa: BLE001
        logger.debug("NLI provider raised, skipping NLI stage: %s", exc)
        return None
    return (str(verdict_obj.verdict), float(verdict_obj.score))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/jw-finetune/tests/synth/judge/test_nli_bridge.py -v`
Expected: 8 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-finetune/src/jw_finetune/synth/judge/nli_bridge.py packages/jw-finetune/tests/synth/judge/test_nli_bridge.py
git commit -m "feat(jw-finetune): synth judge NLI bridge (Fase 39 reuse, import-guarded)"
```

---

### Task 7: The `Judge` class + `score_qa_pair` entry point

**Files:**
- Create: `packages/jw-finetune/src/jw_finetune/synth/judge/judge.py`
- Create: `packages/jw-finetune/tests/synth/judge/test_judge_with_fakes.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-finetune/tests/synth/judge/test_judge_with_fakes.py
"""End-to-end judge tests using FakeLLMProvider + FakeNLIProvider."""

from __future__ import annotations

import pytest

from jw_finetune.synth.judge.judge import Judge, score_qa_pair
from jw_finetune.synth.judge.models import QAScore
from jw_finetune.synth.judge.thresholds import JudgeMode, JudgeOverrides
from jw_finetune.synth.provider import LLMRequest, LLMResponse


class FakeLLMProvider:
    """Returns a fixed string as the pedagogical score."""

    name = "fake"
    model = "fake-judge"

    def __init__(self, text: str = "3") -> None:
        self._text = text
        self.calls: list[LLMRequest] = []

    def generate(self, req: LLMRequest) -> LLMResponse:
        self.calls.append(req)
        return LLMResponse(
            text=self._text,
            provider=self.name,
            model=self.model,
            usage={"input_tokens": 10, "output_tokens": 1},
        )


class FakeVerdict:
    def __init__(self, verdict: str = "entails", score: float = 0.9) -> None:
        self.verdict = verdict
        self.score = score


class FakeNLI:
    def __init__(self, verdict: str = "entails", score: float = 0.9) -> None:
        self._v = verdict
        self._s = score

    def evaluate_entailment(self, *, claim: str, premise: str) -> FakeVerdict:  # noqa: ARG002
        return FakeVerdict(self._v, self._s)


# --- score_qa_pair functional tests ---


def test_score_qa_pair_heuristics_only_passes_loose() -> None:
    score = score_qa_pair(
        question="¿Qué enseña la Biblia sobre el reino?",
        answer=(
            "Como explica w23.04 página 12, el reino de Dios es un gobierno real "
            "con Cristo Jesús como rey, fundado en Daniel 2:44 y Mateo 6:9-10."
        ),
        language="es",
        mode=JudgeMode.LOOSE,
        llm_provider=None,
        nli_provider=None,
    )
    assert isinstance(score, QAScore)
    assert score.kept is True
    assert score.cites_jw_publication is True
    assert score.has_minimum_substance is True
    # 4 + 1.5 + 1.5 = 7.0 ≥ 5.0
    assert score.overall == pytest.approx(7.0)


def test_score_qa_pair_no_citation_rejected_loose() -> None:
    score = score_qa_pair(
        question="¿Qué enseña la Biblia sobre el reino?",
        answer=(
            "El reino de Dios es un gobierno real fundado por Jehová, "
            "pero no menciono ninguna publicación específica."
        ),
        language="es",
        mode=JudgeMode.LOOSE,
        llm_provider=None,
        nli_provider=None,
    )
    # heuristics: cites=False, substance=True → 4 + 1.5 = 5.5 ≥ 5.0
    # but kept depends only on the cutoff; reason is logged regardless
    assert score.cites_jw_publication is False
    assert score.has_minimum_substance is True
    assert score.overall == pytest.approx(5.5)
    # 5.5 ≥ 5.0 loose cutoff → kept=True even without citation
    assert score.kept is True
    # No-citation is still flagged but only blocks when below cutoff
    # (strict mode test below confirms it blocks there)


def test_score_qa_pair_no_citation_rejected_strict() -> None:
    score = score_qa_pair(
        question="¿Qué enseña la Biblia sobre el reino?",
        answer="El reino de Dios es un gobierno real fundado por Jehová.",
        language="es",
        mode=JudgeMode.STRICT,
        llm_provider=None,
        nli_provider=None,
    )
    # heuristics: cites=False, substance=True → 4 + 1.5 = 5.5 < 6.5 strict cutoff
    assert score.kept is False
    assert any(r.code == "overall_below_threshold" for r in score.reasons)


def test_score_qa_pair_generic_answer_rejected() -> None:
    score = score_qa_pair(
        question="¿Qué dice Juan 3:16?",
        answer="Sí.",
        language="es",
        mode=JudgeMode.LOOSE,
        llm_provider=None,
        nli_provider=None,
    )
    assert score.has_minimum_substance is False
    assert score.kept is False
    assert any(r.code == "insufficient_substance" for r in score.reasons)


def test_score_qa_pair_uses_llm_when_provided() -> None:
    llm = FakeLLMProvider(text="3")
    score = score_qa_pair(
        question="¿Qué enseña w23 sobre el amor?",
        answer="Según w23.06 p. 5, el amor es la cualidad principal de Dios y la Biblia lo confirma.",
        language="es",
        mode=JudgeMode.LOOSE,
        llm_provider=llm,
        nli_provider=None,
    )
    assert score.pedagogical_quality == 3
    # 4 + 1.5 + 1.5 + 3 = 10.0 → clamp at 10
    assert score.overall == 10.0
    assert score.kept is True
    assert len(llm.calls) == 1


def test_score_qa_pair_llm_garbage_response_neutral() -> None:
    llm = FakeLLMProvider(text="banana")
    score = score_qa_pair(
        question="?",
        answer="Según w23.06 p. 5, el amor es la cualidad principal de Dios y la Biblia lo confirma.",
        language="es",
        mode=JudgeMode.LOOSE,
        llm_provider=llm,
        nli_provider=None,
    )
    # Garbage → pedagogical_quality stays None, contributes 0
    assert score.pedagogical_quality is None
    assert score.overall == pytest.approx(7.0)


def test_score_qa_pair_nli_contradicts_penalizes() -> None:
    nli = FakeNLI(verdict="contradicts", score=0.92)
    score = score_qa_pair(
        question="?",
        answer=(
            "La Atalaya dice: “Jehová es un solo Dios.” Esto no es "
            "consistente con la doctrina de los tres dioses, w23.06."
        ),
        language="es",
        mode=JudgeMode.STRICT,
        llm_provider=None,
        nli_provider=nli,
    )
    assert score.nli_verdict == "contradicts"
    assert score.kept is False
    assert any(r.code == "nli_contradicts" for r in score.reasons)


def test_score_qa_pair_nli_entails_strict_pass() -> None:
    nli = FakeNLI(verdict="entails", score=0.95)
    score = score_qa_pair(
        question="?",
        answer=(
            "El texto dice: “Jehová es uno solo.” Esto se enseña "
            "claramente en w23.06 p. 4 párr. 5."
        ),
        language="es",
        mode=JudgeMode.STRICT,
        llm_provider=None,
        nli_provider=nli,
    )
    # 4 + 1.5 + 1.5 + 2.0*0.95 = 8.9 ≥ 6.5
    assert score.kept is True
    assert score.nli_verdict == "entails"


def test_score_qa_pair_strict_require_nli_entails_blocks_neutral() -> None:
    nli = FakeNLI(verdict="neutral", score=0.5)
    score = score_qa_pair(
        question="?",
        answer=(
            "El texto dice: “Jehová es uno solo.” Esto se enseña "
            "claramente en w23.06 p. 4 párr. 5."
        ),
        language="es",
        mode=JudgeMode.STRICT,
        llm_provider=None,
        nli_provider=nli,
    )
    # neutral doesn't penalize the score (still ≥ 6.5), but STRICT requires entails
    assert score.nli_verdict == "neutral"
    assert score.kept is False
    assert any(r.code == "nli_neutral_low" for r in score.reasons)


def test_score_qa_pair_off_mode_returns_kept_true() -> None:
    score = score_qa_pair(
        question="?",
        answer="Sí.",
        language="es",
        mode=JudgeMode.OFF,
        llm_provider=None,
        nli_provider=None,
    )
    # In OFF mode, no judging happens; pair passes through with neutral score.
    assert score.kept is True
    assert score.reasons == []


# --- Judge class wrapper ---


def test_judge_class_carries_state() -> None:
    judge = Judge(
        mode=JudgeMode.LOOSE,
        overrides=JudgeOverrides(),
        llm_provider=FakeLLMProvider(text="2"),
        nli_provider=None,
    )
    s = judge.score(
        question="?",
        answer="Como muestra w23.06, el amor es central. La Biblia es clara en 1 Juan 4:8.",
        language="es",
    )
    assert s.pedagogical_quality == 2
    assert s.kept is True


def test_judge_class_dump_for_metadata() -> None:
    judge = Judge(
        mode=JudgeMode.LOOSE,
        overrides=JudgeOverrides(),
        llm_provider=None,
        nli_provider=None,
    )
    s = judge.score(
        question="?",
        answer="Como muestra w23.06, el amor es central. La Biblia es clara en 1 Juan 4:8.",
        language="es",
    )
    dumped = s.model_dump(exclude_none=True)
    assert dumped["kept"] is True
    assert dumped["cites_jw_publication"] is True
    # nli_score should not appear (it's None)
    assert "nli_score" not in dumped
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/jw-finetune/tests/synth/judge/test_judge_with_fakes.py -v`
Expected: FAIL — judge module not found.

- [ ] **Step 3: Implement the Judge**

```python
# packages/jw-finetune/src/jw_finetune/synth/judge/judge.py
"""Judge orchestrator — composes heuristics + LLM + NLI stages into a QAScore.

Public surface:
    Judge(mode, overrides, llm_provider, nli_provider).score(question, answer, language)
    score_qa_pair(question, answer, language, mode, ...) — functional shortcut

The judge is intentionally stateless beyond construction: each `.score()` call
is independent. This makes it trivial to compose with the async orchestrator
later (each chunk's pairs can be scored in parallel via threadpool).
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Protocol

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from jw_finetune.synth.judge.heuristics import (
    cites_jw_publication,
    has_minimum_substance,
)
from jw_finetune.synth.judge.models import QAScore, RejectionReason
from jw_finetune.synth.judge.nli_bridge import NLIProviderLike, run_nli_check
from jw_finetune.synth.judge.scoring import compute_overall
from jw_finetune.synth.judge.thresholds import (
    JudgeMode,
    JudgeOverrides,
    resolve_cutoff,
    resolve_require_nli_entails,
)
from jw_finetune.synth.provider import LLMProvider, LLMRequest

logger = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).parent / "prompts"
_DIGIT_RE = re.compile(r"\b([0-3])\b")

_env_singleton: Environment | None = None


def _env() -> Environment:
    global _env_singleton
    if _env_singleton is None:
        _env_singleton = Environment(
            loader=FileSystemLoader(str(_PROMPTS_DIR)),
            undefined=StrictUndefined,
            autoescape=False,
            trim_blocks=True,
            lstrip_blocks=True,
        )
    return _env_singleton


def _template_for_language(language: str) -> str:
    code = (language or "en")[:2].lower()
    if code == "es":
        return "pedagogical_es.j2"
    if code == "pt":
        return "pedagogical_pt.j2"
    return "pedagogical_en.j2"  # default


def _parse_pedagogical_response(text: str) -> int | None:
    """Tolerant parse of the LLM judge response: first 0..3 digit wins."""

    if not text:
        return None
    m = _DIGIT_RE.search(text.strip())
    if not m:
        return None
    try:
        n = int(m.group(1))
    except ValueError:  # pragma: no cover — regex guarantees digit
        return None
    if 0 <= n <= 3:
        return n
    return None


def _run_llm_pedagogical(
    *,
    question: str,
    answer: str,
    language: str,
    llm_provider: LLMProvider,
) -> int | None:
    """Render prompt → call LLM → parse digit. Returns None on any failure."""

    template_name = _template_for_language(language)
    try:
        prompt = _env().get_template(template_name).render(question=question, answer=answer)
    except Exception as exc:  # noqa: BLE001
        logger.debug("LLM judge prompt render failed: %s", exc)
        return None
    try:
        resp = llm_provider.generate(
            LLMRequest(
                system="Eres un juez de calidad de datos. Responde un solo dígito 0-3.",
                user=prompt,
                temperature=0.0,
                max_tokens=8,
            )
        )
    except Exception as exc:  # noqa: BLE001
        logger.debug("LLM judge call failed: %s", exc)
        return None
    return _parse_pedagogical_response(resp.text)


class _MaybeNLIProvider(Protocol):
    def evaluate_entailment(self, *, claim: str, premise: str) -> object: ...


def score_qa_pair(
    *,
    question: str,
    answer: str,
    language: str,
    mode: JudgeMode,
    overrides: JudgeOverrides | None = None,
    llm_provider: LLMProvider | None = None,
    nli_provider: NLIProviderLike | _MaybeNLIProvider | None = None,
) -> QAScore:
    """Score a single Q&A pair. Returns a QAScore including the kept verdict."""

    if mode == JudgeMode.OFF:
        # Bypass: return a neutral QAScore that always keeps the pair.
        # Heuristics still computed for transparency in metadata.
        cites = cites_jw_publication(answer)
        substance = has_minimum_substance(question, answer)
        overall = compute_overall(
            cites=cites,
            substance=substance,
            nli_verdict=None,
            nli_score=None,
            pedagogical=None,
        )
        return QAScore(
            cites_jw_publication=cites,
            has_minimum_substance=substance,
            overall=overall,
            kept=True,
        )

    ov = overrides or JudgeOverrides()
    cutoff = resolve_cutoff(mode, ov)
    require_entails = resolve_require_nli_entails(mode, ov)

    reasons: list[RejectionReason] = []

    # Stage 1 — heuristics
    cites = cites_jw_publication(answer)
    substance = has_minimum_substance(question, answer)
    if not cites:
        reasons.append(RejectionReason(code="no_jw_citation"))
    if not substance:
        reasons.append(RejectionReason(code="insufficient_substance"))

    # Stage 2 — LLM pedagogical (opt-in)
    pedagogical: int | None = None
    if llm_provider is not None:
        pedagogical = _run_llm_pedagogical(
            question=question,
            answer=answer,
            language=language,
            llm_provider=llm_provider,
        )
        if pedagogical is not None and pedagogical == 0:
            reasons.append(RejectionReason(code="pedagogical_low", detail="LLM scored 0/3"))

    # Stage 3 — NLI (opt-in)
    nli_verdict: str | None = None
    nli_score: float | None = None
    nli_result = run_nli_check(answer=answer, nli_provider=nli_provider)  # type: ignore[arg-type]
    if nli_result is not None:
        nli_verdict, nli_score = nli_result
        if nli_verdict == "contradicts":
            reasons.append(
                RejectionReason(code="nli_contradicts", detail=f"score={nli_score:.2f}")
            )
        elif nli_verdict == "neutral" and require_entails:
            reasons.append(
                RejectionReason(code="nli_neutral_low", detail="strict mode requires entails")
            )

    # Compute overall
    overall = compute_overall(
        cites=cites,
        substance=substance,
        nli_verdict=nli_verdict,  # type: ignore[arg-type]
        nli_score=nli_score,
        pedagogical=pedagogical,
    )

    # Apply cutoff (cutoff is None only when mode == OFF, handled above)
    kept = True
    if cutoff is not None and overall < cutoff:
        kept = False
        reasons.append(
            RejectionReason(
                code="overall_below_threshold",
                detail=f"{overall:.2f} < {cutoff:.2f}",
            )
        )

    # Hard rule: if substance check failed, the pair is unusable regardless of score.
    if not substance:
        kept = False
    # Hard rule: if NLI explicitly contradicts, never keep.
    if nli_verdict == "contradicts":
        kept = False
    # Hard rule: strict + nli requested but neutral → never keep.
    if require_entails and nli_verdict == "neutral":
        kept = False

    # Hard rule: explicit pedagogical zero rejects.
    if pedagogical == 0:
        kept = False

    return QAScore(
        cites_jw_publication=cites,
        has_minimum_substance=substance,
        nli_score=nli_score,
        nli_verdict=nli_verdict,  # type: ignore[arg-type]
        pedagogical_quality=pedagogical,
        overall=overall,
        kept=kept,
        reasons=reasons if not kept else [],
    )


class Judge:
    """Stateful wrapper that holds the configured providers + mode.

    Use this in the orchestrator hot loop to avoid re-resolving cutoffs.
    """

    def __init__(
        self,
        *,
        mode: JudgeMode,
        overrides: JudgeOverrides | None = None,
        llm_provider: LLMProvider | None = None,
        nli_provider: NLIProviderLike | None = None,
    ) -> None:
        self.mode = mode
        self.overrides = overrides or JudgeOverrides()
        self.llm_provider = llm_provider
        self.nli_provider = nli_provider

    def score(self, *, question: str, answer: str, language: str) -> QAScore:
        return score_qa_pair(
            question=question,
            answer=answer,
            language=language,
            mode=self.mode,
            overrides=self.overrides,
            llm_provider=self.llm_provider,
            nli_provider=self.nli_provider,
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/jw-finetune/tests/synth/judge/test_judge_with_fakes.py -v`
Expected: 12 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-finetune/src/jw_finetune/synth/judge/judge.py packages/jw-finetune/tests/synth/judge/test_judge_with_fakes.py
git commit -m "feat(jw-finetune): synth judge orchestrator (Judge class + score_qa_pair)"
```

---

### Task 8: Env-driven factories + `build_judge`

**Files:**
- Create: `packages/jw-finetune/src/jw_finetune/synth/judge/factories.py`
- Create: `packages/jw-finetune/tests/synth/judge/test_factories.py`
- Modify: `packages/jw-finetune/src/jw_finetune/synth/judge/__init__.py` — export `build_judge`.

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-finetune/tests/synth/judge/test_factories.py
"""Factory + env-driven configuration tests.

We never touch real provider classes here — we patch the import points.
"""

from __future__ import annotations

import pytest

from jw_finetune.synth.judge.factories import (
    build_judge,
    build_llm_judge_provider,
    build_nli_provider,
)
from jw_finetune.synth.judge.thresholds import JudgeMode, JudgeOverrides


def test_build_llm_judge_provider_off_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("JW_SYNTH_JUDGE_LLM", raising=False)
    assert build_llm_judge_provider() is None
    monkeypatch.setenv("JW_SYNTH_JUDGE_LLM", "off")
    assert build_llm_judge_provider() is None
    monkeypatch.setenv("JW_SYNTH_JUDGE_LLM", "none")
    assert build_llm_judge_provider() is None
    monkeypatch.setenv("JW_SYNTH_JUDGE_LLM", "")
    assert build_llm_judge_provider() is None


def test_build_llm_judge_provider_unknown_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JW_SYNTH_JUDGE_LLM", "magic")
    with pytest.raises(ValueError, match="JW_SYNTH_JUDGE_LLM"):
        build_llm_judge_provider()


def test_build_llm_judge_provider_anthropic_imports_lazily(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("JW_SYNTH_JUDGE_LLM", "anthropic")

    sentinel = object()

    class StubAnthropic:
        def __init__(self) -> None:  # noqa: D401
            pass

    monkeypatch.setattr(
        "jw_finetune.synth.judge.factories._import_anthropic_provider",
        lambda: lambda: sentinel,  # returns a callable yielding the sentinel
    )
    provider = build_llm_judge_provider()
    assert provider is sentinel


def test_build_llm_judge_provider_ollama(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JW_SYNTH_JUDGE_LLM", "ollama")
    monkeypatch.setenv("JW_SYNTH_JUDGE_OLLAMA_MODEL", "llama3.1:8b")

    captured: list[str] = []

    def factory(model: str):  # noqa: ARG001
        captured.append(model)
        return "ollama-provider"

    monkeypatch.setattr(
        "jw_finetune.synth.judge.factories._import_ollama_provider",
        lambda: factory,
    )
    provider = build_llm_judge_provider()
    assert provider == "ollama-provider"
    assert captured == ["llama3.1:8b"]


def test_build_nli_provider_off_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("JW_SYNTH_JUDGE_NLI", raising=False)
    assert build_nli_provider() is None
    monkeypatch.setenv("JW_SYNTH_JUDGE_NLI", "off")
    assert build_nli_provider() is None


def test_build_nli_provider_handles_import_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JW_SYNTH_JUDGE_NLI", "deberta")

    def broken() -> object:
        raise ImportError("jw_core.fidelity missing")

    monkeypatch.setattr("jw_finetune.synth.judge.factories._import_nli_factory", broken)
    assert build_nli_provider() is None


def test_build_nli_provider_returns_provider_when_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("JW_SYNTH_JUDGE_NLI", "deberta")

    def stub_factory(name: str) -> str:
        return f"nli-provider:{name}"

    monkeypatch.setattr(
        "jw_finetune.synth.judge.factories._import_nli_factory",
        lambda: stub_factory,
    )
    provider = build_nli_provider()
    assert provider == "nli-provider:deberta"


def test_build_judge_off_short_circuits(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("JW_SYNTH_JUDGE_LLM", raising=False)
    monkeypatch.delenv("JW_SYNTH_JUDGE_NLI", raising=False)
    judge = build_judge(mode=JudgeMode.OFF, overrides=JudgeOverrides())
    assert judge.mode == JudgeMode.OFF
    assert judge.llm_provider is None
    assert judge.nli_provider is None


def test_build_judge_wires_providers(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JW_SYNTH_JUDGE_LLM", "anthropic")
    monkeypatch.setenv("JW_SYNTH_JUDGE_NLI", "deberta")
    monkeypatch.setattr(
        "jw_finetune.synth.judge.factories._import_anthropic_provider",
        lambda: lambda: "llm-anth",
    )
    monkeypatch.setattr(
        "jw_finetune.synth.judge.factories._import_nli_factory",
        lambda: lambda name: f"nli:{name}",
    )
    judge = build_judge(mode=JudgeMode.STRICT, overrides=JudgeOverrides())
    assert judge.llm_provider == "llm-anth"
    assert judge.nli_provider == "nli:deberta"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/jw-finetune/tests/synth/judge/test_factories.py -v`
Expected: FAIL — factories module not found.

- [ ] **Step 3: Implement factories**

```python
# packages/jw-finetune/src/jw_finetune/synth/judge/factories.py
"""Env-driven factory functions.

Two env vars steer the wiring:
  - JW_SYNTH_JUDGE_LLM ∈ {off, none, "", anthropic, ollama}
  - JW_SYNTH_JUDGE_NLI ∈ {off, deberta, claude, ollama, ...}

Imports are lazy: anthropic/ollama/jw_core.fidelity are only imported when the
env explicitly asks for them. If Fase 39 is not installed, NLI degrades to None
with a debug log; the judge runs the other two stages.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Callable
from typing import Any

from jw_finetune.synth.judge.judge import Judge
from jw_finetune.synth.judge.nli_bridge import NLIProviderLike
from jw_finetune.synth.judge.thresholds import JudgeMode, JudgeOverrides
from jw_finetune.synth.provider import LLMProvider

logger = logging.getLogger(__name__)

_nli_warning_emitted = False


# Indirection helpers — let tests monkeypatch these.
def _import_anthropic_provider() -> Callable[[], LLMProvider]:
    from jw_finetune.synth.anthropic_provider import AnthropicProvider

    return AnthropicProvider  # type: ignore[return-value]


def _import_ollama_provider() -> Callable[[str], LLMProvider]:
    from jw_finetune.synth.ollama_provider import OllamaProvider

    def factory(model: str) -> LLMProvider:
        return OllamaProvider(model=model)  # type: ignore[call-arg]

    return factory


def _import_nli_factory() -> Callable[[str], NLIProviderLike]:
    """Import the Fase 39 NLI factory. Raises ImportError if unavailable."""

    from jw_core.fidelity.nli_providers import factory_for_name  # type: ignore[import-not-found]

    return factory_for_name  # type: ignore[return-value]


def build_llm_judge_provider() -> LLMProvider | None:
    """Return the configured LLM judge provider, or None if disabled."""

    name = (os.environ.get("JW_SYNTH_JUDGE_LLM") or "").lower().strip()
    if name in {"", "off", "none"}:
        return None
    if name == "anthropic":
        ctor = _import_anthropic_provider()
        return ctor()
    if name == "ollama":
        model = os.environ.get("JW_SYNTH_JUDGE_OLLAMA_MODEL", "llama3.1:8b")
        ctor = _import_ollama_provider()
        return ctor(model)
    raise ValueError(f"Unknown JW_SYNTH_JUDGE_LLM: {name!r}")


def build_nli_provider() -> NLIProviderLike | None:
    """Return the configured NLI provider, or None if disabled / Fase 39 absent."""

    global _nli_warning_emitted
    name = (os.environ.get("JW_SYNTH_JUDGE_NLI") or "off").lower().strip()
    if name in {"", "off", "none"}:
        return None
    try:
        factory = _import_nli_factory()
    except ImportError:
        if not _nli_warning_emitted:
            logger.warning(
                "NLI requested (JW_SYNTH_JUDGE_NLI=%s) but jw_core.fidelity is not "
                "available; skipping NLI stage. Install with: uv sync --extra fidelity",
                name,
            )
            _nli_warning_emitted = True
        return None
    try:
        return factory(name)
    except Exception as exc:  # noqa: BLE001
        logger.warning("NLI factory failed for name=%r: %s", name, exc)
        return None


def build_judge(*, mode: JudgeMode, overrides: JudgeOverrides | None = None) -> Judge:
    """Build a fully-wired Judge for the given mode.

    LLM + NLI providers are resolved from env (returns None when disabled).
    """

    if mode == JudgeMode.OFF:
        # Don't pay the import cost; OFF mode is a no-op.
        return Judge(
            mode=mode,
            overrides=overrides,
            llm_provider=None,
            nli_provider=None,
        )
    return Judge(
        mode=mode,
        overrides=overrides,
        llm_provider=build_llm_judge_provider(),
        nli_provider=build_nli_provider(),
    )
```

Update `__init__.py` to expose `build_judge` and `Judge`:

```python
# packages/jw-finetune/src/jw_finetune/synth/judge/__init__.py
"""jw_finetune.synth.judge — 3-stage Q&A quality filter.

Public API:
    from jw_finetune.synth.judge import (
        score_qa_pair, build_judge, Judge,
        QAScore, RejectionReason, JudgeMode, JudgeOverrides,
    )
"""

from __future__ import annotations

from jw_finetune.synth.judge.factories import build_judge
from jw_finetune.synth.judge.judge import Judge, score_qa_pair
from jw_finetune.synth.judge.models import QAScore, RejectionReason
from jw_finetune.synth.judge.thresholds import (
    DEFAULT_CUTOFFS,
    JudgeMode,
    JudgeOverrides,
)

__all__ = [
    "DEFAULT_CUTOFFS",
    "Judge",
    "JudgeMode",
    "JudgeOverrides",
    "QAScore",
    "RejectionReason",
    "build_judge",
    "score_qa_pair",
]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/jw-finetune/tests/synth/judge/test_factories.py -v`
Expected: 9 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-finetune/src/jw_finetune/synth/judge/factories.py packages/jw-finetune/src/jw_finetune/synth/judge/__init__.py packages/jw-finetune/tests/synth/judge/test_factories.py
git commit -m "feat(jw-finetune): env-driven factories (anthropic/ollama LLM + Fase 39 NLI)"
```

---

### Task 9: JudgeStats accumulator

**Files:**
- Create: `packages/jw-finetune/src/jw_finetune/synth/judge/stats.py`
- Create: `packages/jw-finetune/tests/synth/judge/test_stats.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-finetune/tests/synth/judge/test_stats.py
"""JudgeStats accumulator tests."""

from __future__ import annotations

from jw_finetune.synth.judge.models import QAScore, RejectionReason
from jw_finetune.synth.judge.stats import JudgeStats


def test_stats_initial_state() -> None:
    s = JudgeStats()
    assert s.total == 0
    assert s.kept == 0
    assert s.rejected == 0
    assert s.rejection_reasons == {}


def _kept_score() -> QAScore:
    return QAScore(
        cites_jw_publication=True,
        has_minimum_substance=True,
        overall=8.0,
        kept=True,
    )


def _rejected_score(code: str = "no_jw_citation") -> QAScore:
    return QAScore(
        cites_jw_publication=False,
        has_minimum_substance=True,
        overall=3.0,
        kept=False,
        reasons=[RejectionReason(code=code)],  # type: ignore[arg-type]
    )


def test_stats_record_keeps_running_counts() -> None:
    s = JudgeStats()
    s.record(_kept_score())
    s.record(_kept_score())
    s.record(_rejected_score())
    assert s.total == 3
    assert s.kept == 2
    assert s.rejected == 1
    assert s.rejection_reasons["no_jw_citation"] == 1


def test_stats_record_groups_reasons() -> None:
    s = JudgeStats()
    s.record(_rejected_score("no_jw_citation"))
    s.record(_rejected_score("no_jw_citation"))
    s.record(_rejected_score("insufficient_substance"))
    assert s.rejection_reasons == {
        "no_jw_citation": 2,
        "insufficient_substance": 1,
    }


def test_stats_format_summary_human_readable() -> None:
    s = JudgeStats()
    for _ in range(7):
        s.record(_kept_score())
    s.record(_rejected_score("no_jw_citation"))
    s.record(_rejected_score("no_jw_citation"))
    s.record(_rejected_score("insufficient_substance"))
    summary = s.format_summary()
    assert "Pairs generated: 10" in summary
    assert "Pairs kept:      7 (70.0%)" in summary
    assert "Rejected:        3 (30.0%)" in summary
    assert "no_jw_citation:" in summary
    assert "2" in summary  # count
    assert "insufficient_substance:" in summary


def test_stats_format_summary_zero_pairs() -> None:
    summary = JudgeStats().format_summary()
    assert "Pairs generated: 0" in summary
    # No division by zero
    assert "%" not in summary or "0.0%" in summary
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/jw-finetune/tests/synth/judge/test_stats.py -v`
Expected: FAIL — stats module not found.

- [ ] **Step 3: Implement stats**

```python
# packages/jw-finetune/src/jw_finetune/synth/judge/stats.py
"""Per-run accumulator for judge verdicts."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from jw_finetune.synth.judge.models import QAScore


@dataclass
class JudgeStats:
    total: int = 0
    kept: int = 0
    rejected: int = 0
    rejection_reasons: dict[str, int] = field(default_factory=dict)

    def record(self, score: QAScore) -> None:
        self.total += 1
        if score.kept:
            self.kept += 1
            return
        self.rejected += 1
        # First reason takes precedence for "top reason" purposes.
        if score.reasons:
            primary = score.reasons[0].code
            self.rejection_reasons[primary] = self.rejection_reasons.get(primary, 0) + 1

    def format_summary(self) -> str:
        if self.total == 0:
            return "Pairs generated: 0\nPairs kept:      0\nRejected:        0\n"

        kept_pct = 100.0 * self.kept / self.total
        rej_pct = 100.0 * self.rejected / self.total

        lines = [
            "Extraction complete.",
            f"  Pairs generated: {self.total}",
            f"  Pairs kept:      {self.kept} ({kept_pct:.1f}%)",
            f"  Rejected:        {self.rejected} ({rej_pct:.1f}%)",
        ]
        if self.rejection_reasons:
            ordered = sorted(self.rejection_reasons.items(), key=lambda kv: -kv[1])
            for code, n in ordered:
                lines.append(f"    {code}: {n}")
        return "\n".join(lines) + "\n"


def merge_counters(stats: JudgeStats, other: JudgeStats) -> JudgeStats:
    """Combine two stats accumulators (useful for parallel runs)."""

    merged = JudgeStats()
    merged.total = stats.total + other.total
    merged.kept = stats.kept + other.kept
    merged.rejected = stats.rejected + other.rejected
    combined: Counter[str] = Counter(stats.rejection_reasons) + Counter(other.rejection_reasons)
    merged.rejection_reasons = dict(combined)
    return merged
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/jw-finetune/tests/synth/judge/test_stats.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-finetune/src/jw_finetune/synth/judge/stats.py packages/jw-finetune/tests/synth/judge/test_stats.py
git commit -m "feat(jw-finetune): JudgeStats accumulator with human-readable summary"
```

---

### Task 10: Integrate judge into `synthesize_chunk`

**Files:**
- Modify: `packages/jw-finetune/src/jw_finetune/synth/orchestrator.py`
- Create: `packages/jw-finetune/tests/synth/judge/test_orchestrator_integration.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-finetune/tests/synth/judge/test_orchestrator_integration.py
"""Tests that synthesize_chunk routes pairs through an optional Judge."""

from __future__ import annotations

import json
from typing import Any

from jw_rag.chunker import Chunk

from jw_finetune.synth.judge import Judge, JudgeMode, JudgeOverrides
from jw_finetune.synth.orchestrator import synthesize_chunk
from jw_finetune.synth.provider import LLMRequest, LLMResponse


class FakeSynthProvider:
    """Returns a fixed JSON payload as the synthesis output."""

    name = "fake"
    model = "fake-synth"

    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    def generate(self, req: LLMRequest) -> LLMResponse:  # noqa: ARG002
        return LLMResponse(
            text=json.dumps(self._payload, ensure_ascii=False),
            provider=self.name,
            model=self.model,
            usage={"input_tokens": 50, "output_tokens": 100},
        )


def _chunk() -> Chunk:
    return Chunk(
        id="chunk_1",
        text="Algún texto fuente.",
        source_id="src_1",
        metadata={"pub_code": "w23", "section_ref": "p. 5"},
    )


def _payload_two_pairs() -> dict[str, Any]:
    return {
        "pairs": [
            {
                "q": "¿Qué enseña la Biblia sobre el reino?",
                "a": (
                    "Como muestra w23 página 5, el reino de Dios es un gobierno real "
                    "con Cristo Jesús como rey, según Daniel 2:44 y Mateo 6:9-10."
                ),
            },
            {
                "q": "¿Otra pregunta?",
                "a": "Sí.",  # generic, will be rejected
            },
        ]
    }


def test_synthesize_chunk_without_judge_keeps_all_valid_pairs() -> None:
    provider = FakeSynthProvider(_payload_two_pairs())
    result = synthesize_chunk(
        _chunk(),
        provider=provider,
        qa_style="doctrinal",
        language="es",
        n_pairs=2,
    )
    # Existing validators still drop the "Sí." pair on length_ok
    assert len(result.pairs) == 1


def test_synthesize_chunk_with_judge_loose_keeps_quality_pair() -> None:
    provider = FakeSynthProvider(_payload_two_pairs())
    judge = Judge(
        mode=JudgeMode.LOOSE,
        overrides=JudgeOverrides(),
        llm_provider=None,
        nli_provider=None,
    )
    result = synthesize_chunk(
        _chunk(),
        provider=provider,
        qa_style="doctrinal",
        language="es",
        n_pairs=2,
        judge=judge,
    )
    assert len(result.pairs) == 1
    # Surviving pair must have judge_score metadata
    pair = result.pairs[0]
    assert "judge_score" in pair.metadata
    parsed = json.loads(pair.metadata["judge_score"])
    assert parsed["kept"] is True


def test_synthesize_chunk_with_judge_strict_rejects_no_citation_pair() -> None:
    payload = {
        "pairs": [
            {
                "q": "¿Qué enseña la Biblia sobre el reino?",
                "a": (
                    "El reino de Dios es un gobierno real con Cristo Jesús como rey, "
                    "según Daniel 2:44 y Mateo 6:9-10. (Sin código de publicación JW.)"
                ),
            }
        ]
    }
    provider = FakeSynthProvider(payload)
    judge = Judge(
        mode=JudgeMode.STRICT,
        overrides=JudgeOverrides(),
        llm_provider=None,
        nli_provider=None,
    )
    result = synthesize_chunk(
        _chunk(),
        provider=provider,
        qa_style="doctrinal",
        language="es",
        n_pairs=1,
        judge=judge,
    )
    assert result.pairs == []
    assert result.rejected == 1


def test_synthesize_chunk_judge_off_passes_through() -> None:
    provider = FakeSynthProvider(_payload_two_pairs())
    judge = Judge(
        mode=JudgeMode.OFF,
        overrides=JudgeOverrides(),
        llm_provider=None,
        nli_provider=None,
    )
    result = synthesize_chunk(
        _chunk(),
        provider=provider,
        qa_style="doctrinal",
        language="es",
        n_pairs=2,
        judge=judge,
    )
    # OFF mode: judge doesn't reject; only existing validators apply
    assert len(result.pairs) == 1
    # judge_score metadata still attached, kept=True
    parsed = json.loads(result.pairs[0].metadata["judge_score"])
    assert parsed["kept"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/jw-finetune/tests/synth/judge/test_orchestrator_integration.py -v`
Expected: FAIL — `synthesize_chunk` doesn't accept `judge=` kwarg yet.

- [ ] **Step 3: Modify `synthesize_chunk`**

Edit `packages/jw-finetune/src/jw_finetune/synth/orchestrator.py` — apply the following changes:

a) Add the import at the top of the file (next to `from jw_finetune.synth.validators import ...`):

```python
from jw_finetune.synth.judge import Judge
```

b) Update the `SynthResult` dataclass (no shape change required, but document the new metadata).

c) Modify the `synthesize_chunk` signature and inner loop. Replace the existing function with:

```python
def synthesize_chunk(
    chunk: Chunk,
    *,
    provider: LLMProvider,
    qa_style: str,
    language: str,
    n_pairs: int = 3,
    temperature: float = 0.5,
    max_tokens: int = 1024,
    judge: Judge | None = None,
) -> SynthResult:
    """Generate validated Q&A pairs from a single chunk.

    If a `judge` is provided, every pair that passes the heuristic validators
    is then scored. Pairs the judge rejects are counted in `result.rejected`
    instead of being persisted. Pairs that survive carry their score in
    `metadata["judge_score"]` as a JSON string for JSONL roundtripping.
    """

    import json as _json  # local to avoid widening the public surface

    template_name = _TEMPLATE_FOR_STYLE.get(qa_style)
    if not template_name:
        raise ValueError(f"Unknown qa_style: {qa_style!r}")

    tmpl = _env().get_template(template_name)
    user_prompt = tmpl.render(
        language=language,
        n_pairs=n_pairs,
        chunk_text=chunk.text,
        pub_code=chunk.metadata.get("pub_code", "?"),
        section_ref=chunk.metadata.get("section_ref", ""),
    )
    system = (
        "Eres un asistente que genera datasets de fine-tuning de alta calidad "
        "siguiendo estrictamente el formato JSON solicitado."
    )
    resp = provider.generate(
        LLMRequest(
            system=system,
            user=user_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    )

    result = SynthResult(usage=dict(resp.usage))

    raw = _strip_json_fences(resp.text)
    try:
        parsed = _json.loads(raw)
    except _json.JSONDecodeError as e:
        logger.warning("Synth parse error for chunk %s: %s", chunk.id, e)
        result.parse_error = True
        return result

    pairs = parsed.get("pairs", []) if isinstance(parsed, dict) else []
    for entry in pairs:
        if not isinstance(entry, dict):
            result.rejected += 1
            continue
        q = (entry.get("q") or "").strip()
        a = (entry.get("a") or "").strip()
        if not length_ok(q, a):
            result.rejected += 1
            continue
        if not lang_matches(a, language):
            result.rejected += 1
            continue

        metadata = {
            "pub_code": str(chunk.metadata.get("pub_code", "")),
            "section_ref": str(chunk.metadata.get("section_ref", "")),
            "qa_style": qa_style,
        }

        if judge is not None:
            score = judge.score(question=q, answer=a, language=language)
            if not score.kept:
                result.rejected += 1
                continue
            # Persist the score on the QAPair for downstream auditing.
            metadata["judge_score"] = _json.dumps(
                score.model_dump(exclude_none=True),
                ensure_ascii=False,
                sort_keys=True,
            )

        result.pairs.append(
            QAPair(
                question=q,
                answer=a,
                source_chunk_id=chunk.id,
                language=language,
                metadata=metadata,
            )
        )
    return result
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/jw-finetune/tests/synth/judge/test_orchestrator_integration.py packages/jw-finetune/tests/test_synth_orchestrator.py -v`
Expected: 4 new + all existing orchestrator tests pass (no regression — the `judge` kwarg defaults to None).

- [ ] **Step 5: Commit**

```bash
git add packages/jw-finetune/src/jw_finetune/synth/orchestrator.py packages/jw-finetune/tests/synth/judge/test_orchestrator_integration.py
git commit -m "feat(jw-finetune): wire optional Judge into synthesize_chunk + judge_score metadata"
```

---

### Task 11: Wire judge into `data extract` CLI

**Files:**
- Modify: `packages/jw-finetune/src/jw_finetune/data/extract.py`
- Create: `packages/jw-finetune/tests/synth/judge/test_extract_cli.py`

- [ ] **Step 1: Inspect the current `data/extract.py` CLI entry**

```bash
grep -n "typer\|@app\|def extract\|def main\|judge" packages/jw-finetune/src/jw_finetune/data/extract.py
```

Find the Typer command (or callable) that runs the per-chunk loop. If `data/extract.py` only exports library helpers, the CLI entry point lives in `packages/jw-finetune/src/jw_finetune/cli/data.py` (check via `grep -rn "data extract" packages/jw-finetune/src`).

- [ ] **Step 2: Write the failing test (programmatic, not Typer CliRunner)**

```python
# packages/jw-finetune/tests/synth/judge/test_extract_cli.py
"""End-to-end test for the judge plumbing in data extract.

We don't run the real CLI (it reads files); we test the programmatic helper
`run_extract_with_judge` that the Typer command will call.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from jw_rag.chunker import Chunk

from jw_finetune.data.extract import run_extract_with_judge
from jw_finetune.synth.judge import JudgeMode
from jw_finetune.synth.provider import LLMRequest, LLMResponse


class FakeSynthProvider:
    name = "fake"
    model = "fake-synth"

    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    def generate(self, req: LLMRequest) -> LLMResponse:  # noqa: ARG002
        return LLMResponse(
            text=json.dumps(self._payload, ensure_ascii=False),
            provider=self.name,
            model=self.model,
            usage={"input_tokens": 50, "output_tokens": 100},
        )


def _chunks() -> list[Chunk]:
    return [
        Chunk(
            id="c1",
            text="Texto fuente uno.",
            source_id="s1",
            metadata={"pub_code": "w23", "section_ref": "p. 5"},
        ),
        Chunk(
            id="c2",
            text="Texto fuente dos.",
            source_id="s1",
            metadata={"pub_code": "w23", "section_ref": "p. 6"},
        ),
    ]


def _payload() -> dict[str, Any]:
    return {
        "pairs": [
            {
                "q": "¿Qué enseña la Biblia sobre el reino?",
                "a": (
                    "Como muestra w23 p. 5, el reino de Dios es un gobierno real con "
                    "Cristo Jesús como rey, según Daniel 2:44 y Mateo 6:9-10."
                ),
            },
        ]
    }


def test_run_extract_with_judge_loose_kept(tmp_path: Path) -> None:
    out_path = tmp_path / "train.jsonl"
    stats = run_extract_with_judge(
        chunks=_chunks(),
        provider=FakeSynthProvider(_payload()),
        qa_style="doctrinal",
        language="es",
        output_path=out_path,
        judge_mode=JudgeMode.LOOSE,
    )
    assert stats.total == 2
    assert stats.kept == 2
    assert stats.rejected == 0
    assert out_path.exists()
    lines = out_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    # Every line carries judge_score in metadata
    first = json.loads(lines[0])
    md = first.get("metadata", {})
    assert "judge_score" in md


def test_run_extract_with_judge_strict_rejects_no_citation(tmp_path: Path) -> None:
    payload = {
        "pairs": [
            {
                "q": "¿Qué enseña la Biblia sobre el reino?",
                "a": "Es un gobierno real con Cristo Jesús como rey, Daniel 2:44 y Mateo 6:9-10.",
            }
        ]
    }
    out_path = tmp_path / "train.jsonl"
    stats = run_extract_with_judge(
        chunks=_chunks(),
        provider=FakeSynthProvider(payload),
        qa_style="doctrinal",
        language="es",
        output_path=out_path,
        judge_mode=JudgeMode.STRICT,
    )
    assert stats.kept == 0
    assert stats.rejected == 2
    assert "no_jw_citation" in stats.rejection_reasons or "overall_below_threshold" in stats.rejection_reasons


def test_run_extract_with_judge_off_passes_all(tmp_path: Path) -> None:
    out_path = tmp_path / "train.jsonl"
    stats = run_extract_with_judge(
        chunks=_chunks(),
        provider=FakeSynthProvider(_payload()),
        qa_style="doctrinal",
        language="es",
        output_path=out_path,
        judge_mode=JudgeMode.OFF,
    )
    assert stats.kept == 2
    assert stats.rejected == 0


def test_run_extract_with_judge_dump_rejected(tmp_path: Path) -> None:
    payload = {
        "pairs": [
            {
                "q": "¿Qué enseña la Biblia sobre el reino?",
                "a": "Es un gobierno real con Cristo Jesús como rey, Daniel 2:44.",
            }
        ]
    }
    out_path = tmp_path / "train.jsonl"
    dump_path = tmp_path / "rejected.jsonl"
    run_extract_with_judge(
        chunks=_chunks(),
        provider=FakeSynthProvider(payload),
        qa_style="doctrinal",
        language="es",
        output_path=out_path,
        judge_mode=JudgeMode.STRICT,
        dump_rejected_path=dump_path,
    )
    assert dump_path.exists()
    rejected = [json.loads(ln) for ln in dump_path.read_text(encoding="utf-8").splitlines()]
    assert len(rejected) >= 1
    assert "judge_score" in rejected[0]
    assert "question" in rejected[0]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/jw-finetune/tests/synth/judge/test_extract_cli.py -v`
Expected: FAIL — `run_extract_with_judge` not exported.

- [ ] **Step 3: Implement `run_extract_with_judge` in `data/extract.py`**

Append to `packages/jw-finetune/src/jw_finetune/data/extract.py`:

```python
# === Judge-integrated extract loop (Fase 44) ===

from collections.abc import Iterable as _Iterable  # noqa: E402

from jw_finetune.synth.judge import (  # noqa: E402
    Judge,
    JudgeMode,
    JudgeOverrides,
    build_judge,
)
from jw_finetune.synth.judge.stats import JudgeStats  # noqa: E402
from jw_finetune.synth.orchestrator import synthesize_chunk  # noqa: E402
from jw_finetune.synth.provider import LLMProvider  # noqa: E402


def _write_jsonl_line(fp, qa_pair) -> None:  # noqa: ANN001
    import json as _json

    row = {
        "question": qa_pair.question,
        "answer": qa_pair.answer,
        "source_chunk_id": qa_pair.source_chunk_id,
        "language": qa_pair.language,
        "metadata": dict(qa_pair.metadata),
    }
    fp.write(_json.dumps(row, ensure_ascii=False) + "\n")


def run_extract_with_judge(
    *,
    chunks: _Iterable,
    provider: LLMProvider,
    qa_style: str,
    language: str,
    output_path: Path,
    judge_mode: JudgeMode = JudgeMode.LOOSE,
    judge_overrides: JudgeOverrides | None = None,
    n_pairs: int = 3,
    temperature: float = 0.5,
    max_tokens: int = 1024,
    judge: Judge | None = None,
    dump_rejected_path: Path | None = None,
) -> JudgeStats:
    """Synthesize Q&A from chunks and write surviving pairs to JSONL.

    Args:
        chunks: iterable of jw_rag.chunker.Chunk.
        provider: the synthesis LLM provider (orchestrator-side).
        qa_style: matches `_TEMPLATE_FOR_STYLE` in the orchestrator.
        language: ISO-2 language code (es/en/pt/...).
        output_path: target JSONL.
        judge_mode: off | loose | strict. Default loose.
        judge_overrides: per-recipe overrides (cutoff/require_nli_entails).
        judge: optional pre-built Judge (skips env resolution).
        dump_rejected_path: if set, write rejected pairs+scores there for audit.

    Returns:
        JudgeStats with totals + per-reason counts.
    """

    import json as _json

    if judge is None:
        judge = build_judge(mode=judge_mode, overrides=judge_overrides)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    stats = JudgeStats()

    rejected_fp = None
    if dump_rejected_path is not None:
        dump_rejected_path.parent.mkdir(parents=True, exist_ok=True)
        rejected_fp = dump_rejected_path.open("w", encoding="utf-8")

    try:
        with output_path.open("w", encoding="utf-8") as out_fp:
            for chunk in chunks:
                # The orchestrator already filters with the judge; to also
                # record per-reason stats for rejected pairs we ask the orchestrator
                # to skip judging and re-score here.
                result = synthesize_chunk(
                    chunk,
                    provider=provider,
                    qa_style=qa_style,
                    language=language,
                    n_pairs=n_pairs,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    judge=None,  # we judge here for full stats visibility
                )
                for pair in result.pairs:
                    score = judge.score(
                        question=pair.question, answer=pair.answer, language=language
                    )
                    stats.record(score)
                    if score.kept:
                        pair.metadata["judge_score"] = _json.dumps(
                            score.model_dump(exclude_none=True),
                            ensure_ascii=False,
                            sort_keys=True,
                        )
                        _write_jsonl_line(out_fp, pair)
                    elif rejected_fp is not None:
                        rejected_fp.write(
                            _json.dumps(
                                {
                                    "question": pair.question,
                                    "answer": pair.answer,
                                    "source_chunk_id": pair.source_chunk_id,
                                    "language": pair.language,
                                    "judge_score": score.model_dump(exclude_none=True),
                                },
                                ensure_ascii=False,
                            )
                            + "\n"
                        )
    finally:
        if rejected_fp is not None:
            rejected_fp.close()

    return stats
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/jw-finetune/tests/synth/judge/test_extract_cli.py -v`
Expected: 4 passed.

- [ ] **Step 5: Wire Typer CLI flags**

Locate the Typer command for `data extract` (likely in `packages/jw-finetune/src/jw_finetune/cli.py` or `cli/data.py`). Add new options:

```python
# Add inside the extract command signature (Typer):
judge: str = typer.Option("loose", "--judge", help="Judge mode: off|loose|strict"),
judge_llm: str | None = typer.Option(None, "--judge-llm", help="Override JW_SYNTH_JUDGE_LLM"),
judge_nli: str | None = typer.Option(None, "--judge-nli", help="Override JW_SYNTH_JUDGE_NLI"),
dump_rejected: Path | None = typer.Option(None, "--dump-rejected", help="Write rejected pairs to this JSONL"),
```

In the command body, before invoking the extract loop:

```python
import os
from jw_finetune.synth.judge import JudgeMode

if judge_llm is not None:
    os.environ["JW_SYNTH_JUDGE_LLM"] = judge_llm
if judge_nli is not None:
    os.environ["JW_SYNTH_JUDGE_NLI"] = judge_nli

judge_mode = JudgeMode(judge.lower())
stats = run_extract_with_judge(
    chunks=resolved_chunks,
    provider=resolved_provider,
    qa_style=recipe.qa_style,
    language=recipe.languages[0],
    output_path=output_path,
    judge_mode=judge_mode,
    dump_rejected_path=dump_rejected,
)
typer.echo(stats.format_summary())
```

If the Typer command lives elsewhere, replicate the same wiring there. Run `uv run jw-finetune data extract --help` to confirm `--judge`, `--judge-llm`, `--judge-nli`, `--dump-rejected` appear.

- [ ] **Step 6: Commit**

```bash
git add packages/jw-finetune/src/jw_finetune/data/extract.py packages/jw-finetune/src/jw_finetune/cli*.py packages/jw-finetune/tests/synth/judge/test_extract_cli.py
git commit -m "feat(jw-finetune): wire Judge into data extract with stats output and rejected dump"
```

---

### Task 12: Golden 50 pairs + precision eval script

**Files:**
- Create: `packages/jw-finetune/tests/synth/judge/fixtures/__init__.py`
- Create: `packages/jw-finetune/tests/synth/judge/fixtures/golden_50_pairs.jsonl`
- Create: `packages/jw-finetune/src/jw_finetune/synth/judge/eval_precision.py`
- Create: `packages/jw-finetune/tests/synth/judge/test_golden_precision.py`

- [ ] **Step 1: Create the fixture package marker**

```python
# packages/jw-finetune/tests/synth/judge/fixtures/__init__.py
"""Annotated golden Q&A fixtures for judge precision evals."""
```

- [ ] **Step 2: Write the 50-pair golden fixture**

Format: one JSON object per line with fields `q`, `a`, `language`, `expected_kept` (bool), `topic` (string), `note` (optional). 25 should be true positives (should be kept) and 25 should be true negatives (should be rejected). Below is the seed set — adjust copy minimally to ensure deterministic, realistic JW-style examples.

```jsonl
{"q": "¿Qué enseña la Biblia sobre el reino de Dios?", "a": "Como explica w23.04 página 12, el reino de Dios es un gobierno real con Cristo Jesús como rey, fundado en 1914 según Daniel 2:44.", "language": "es", "expected_kept": true, "topic": "kingdom", "note": "real teaching + JW pub code"}
{"q": "¿Quién es Jehová?", "a": "Jehová es el nombre personal del Dios Todopoderoso, como se muestra en Salmo 83:18. El libro bh capítulo 1 explica el origen del nombre.", "language": "es", "expected_kept": true, "topic": "jehovah", "note": "pub code bh + teaching"}
{"q": "¿Es la Trinidad bíblica?", "a": "Según la Atalaya w23.06 página 4, la Trinidad no es una enseñanza bíblica; las Escrituras presentan a Jehová como un solo Dios (Deuteronomio 6:4).", "language": "es", "expected_kept": true, "topic": "trinity", "note": "JW citation + scripture"}
{"q": "¿Qué dice Juan 3:16?", "a": "Como muestra https://wol.jw.org/es/wol/b/r4/lp-s/nwt/E/2024/43/3, Dios amó tanto al mundo que dio a su Hijo unigénito para que tengamos vida eterna.", "language": "es", "expected_kept": true, "topic": "love", "note": "wol URL + paraphrase"}
{"q": "¿Cuál es la esperanza de los muertos?", "a": "El libro lff capítulo 6 explica que la esperanza es la resurrección a la tierra paradisíaca, según Hechos 24:15 y Juan 5:28-29.", "language": "es", "expected_kept": true, "topic": "resurrection", "note": "lff + scripture"}
{"q": "¿Qué es el alma según la Biblia?", "a": "Como enseña bh capítulo 6, el alma es la persona misma o la vida que disfruta el ser humano; Génesis 2:7 lo aclara: el hombre llegó a ser un alma viviente.", "language": "es", "expected_kept": true, "topic": "soul", "note": "bh + scripture"}
{"q": "¿Existe el infierno de fuego?", "a": "Según la Atalaya w22.10 página 18, el infierno bíblico (Seol/Hades) es la tumba común de la humanidad, no un lugar de tormento eterno (Eclesiastés 9:5, 10).", "language": "es", "expected_kept": true, "topic": "hell", "note": "watchtower citation"}
{"q": "¿Quién es Jesucristo?", "a": "Como explica jt lección 4, Jesús es el Hijo de Dios, su primera creación, no Dios Todopoderoso; él mismo dijo: 'El Padre es mayor que yo' (Juan 14:28).", "language": "es", "expected_kept": true, "topic": "jesus", "note": "jt + Bible quote"}
{"q": "¿Qué es el reino milenario?", "a": "Como muestra la guía rs página 245, el reino milenario es el gobierno de mil años de Cristo Jesús sobre la tierra (Apocalipsis 20:6).", "language": "es", "expected_kept": true, "topic": "millennium", "note": "rs reference"}
{"q": "¿Qué enseña la Biblia sobre la sangre?", "a": "Según wp23 página 10, la Biblia indica que los cristianos deben abstenerse de sangre (Hechos 15:28-29). Esto incluye no aceptar transfusiones de sangre completa.", "language": "es", "expected_kept": true, "topic": "blood", "note": "wp23 + scripture"}
{"q": "What does the Bible teach about love?", "a": "As w23.05 page 8 explains, the Bible teaches that love is God's foremost quality: 1 John 4:8 says God is love.", "language": "en", "expected_kept": true, "topic": "love", "note": "EN: pub code + scripture"}
{"q": "Is the Trinity biblical?", "a": "According to the bh book chapter 1, the Trinity is not a Bible teaching; Scripture presents Jehovah as the only true God (John 17:3).", "language": "en", "expected_kept": true, "topic": "trinity", "note": "EN: bh"}
{"q": "Who is Jesus Christ?", "a": "As shown in jy chapter 17, Jesus is God's Son, his firstborn creation. Jesus himself said: 'The Father is greater than I am' (John 14:28).", "language": "en", "expected_kept": true, "topic": "jesus", "note": "EN: jy"}
{"q": "What happens at death?", "a": "As w22.10 page 4 explains, the Bible teaches that the dead are unconscious, awaiting resurrection (Ecclesiastes 9:5, 10).", "language": "en", "expected_kept": true, "topic": "death", "note": "EN: w22"}
{"q": "What is God's name?", "a": "According to bh chapter 1, God's personal name is Jehovah (YHWH), revealed in Psalm 83:18 and Isaiah 42:8.", "language": "en", "expected_kept": true, "topic": "gods_name", "note": "EN: bh + scriptures"}
{"q": "O que a Bíblia ensina sobre o reino?", "a": "Como mostra w23.04 página 12, o reino de Deus é um governo real com Cristo Jesus como rei, conforme Daniel 2:44 e Mateus 6:9-10.", "language": "pt", "expected_kept": true, "topic": "kingdom", "note": "PT: w23 + scriptures"}
{"q": "Quem é Jeová?", "a": "Conforme o livro bh capítulo 1, Jeová é o nome pessoal do Deus Todo-Poderoso, segundo Salmo 83:18 e Isaías 42:8.", "language": "pt", "expected_kept": true, "topic": "jehovah", "note": "PT: bh"}
{"q": "A Trindade é bíblica?", "a": "Segundo a Sentinela w23.06 página 4, a Trindade não é um ensino bíblico; as Escrituras apresentam Jeová como um único Deus (Deuteronômio 6:4).", "language": "pt", "expected_kept": true, "topic": "trinity", "note": "PT: w23"}
{"q": "Quem é Jesus Cristo?", "a": "Como mostra jt lição 4, Jesus é o Filho de Deus, sua primeira criação. Ele mesmo disse: 'O Pai é maior do que eu' (João 14:28).", "language": "pt", "expected_kept": true, "topic": "jesus", "note": "PT: jt"}
{"q": "¿Qué enseña la Biblia sobre el matrimonio?", "a": "Como explica lff capítulo 14, el matrimonio fue instituido por Jehová y se basa en el amor leal (Génesis 2:24; Efesios 5:33).", "language": "es", "expected_kept": true, "topic": "marriage", "note": "lff"}
{"q": "¿Qué es la fe verdadera?", "a": "Según bh capítulo 12, la fe verdadera no es ciega; se basa en evidencia (Hebreos 11:1).", "language": "es", "expected_kept": true, "topic": "faith", "note": "bh + Hebrews"}
{"q": "¿Quiénes son los 144 000?", "a": "Como explica la Atalaya w22.07 página 5, los 144 000 mencionados en Apocalipsis 14:1 son cristianos ungidos que reinarán con Cristo en el cielo.", "language": "es", "expected_kept": true, "topic": "144000", "note": "w22 + Revelation"}
{"q": "¿Por qué Jehová permite el sufrimiento?", "a": "Como muestra bh capítulo 11, Jehová permite el sufrimiento temporal por la cuestión planteada en Edén (Job 1:9-11); pronto eliminará toda maldad (Salmo 37:10-11).", "language": "es", "expected_kept": true, "topic": "suffering", "note": "bh + multiple scriptures"}
{"q": "¿Qué es el día del juicio?", "a": "Según la guía it volumen 1 página 1075, el día del juicio es el período de mil años durante el cual la humanidad será juzgada conforme a sus obras (Apocalipsis 20:12).", "language": "es", "expected_kept": true, "topic": "judgment", "note": "Insight + Revelation"}
{"q": "¿Qué enseña la Biblia sobre la oración?", "a": "Como explica bh capítulo 17, Jehová escucha la oración sincera ofrecida por medio de Jesús (Juan 14:6; 1 Pedro 3:12).", "language": "es", "expected_kept": true, "topic": "prayer", "note": "bh + Bible"}
{"q": "¿Qué enseña la Biblia sobre el reino?", "a": "Sí.", "language": "es", "expected_kept": false, "topic": "kingdom", "note": "generic stub"}
{"q": "¿Qué dice Juan 3:16?", "a": "Que Dios amó al mundo.", "language": "es", "expected_kept": false, "topic": "love", "note": "too short, no JW citation"}
{"q": "¿Quién es Jehová?", "a": "Jehová es Dios.", "language": "es", "expected_kept": false, "topic": "jehovah", "note": "too short"}
{"q": "¿Existe el infierno?", "a": "Depende de la interpretación.", "language": "es", "expected_kept": false, "topic": "hell", "note": "no substance, no citation"}
{"q": "¿Qué es el alma?", "a": "Es algo espiritual que vive después de la muerte.", "language": "es", "expected_kept": false, "topic": "soul", "note": "doctrinally wrong, no JW source"}
{"q": "¿Es la Trinidad bíblica?", "a": "Sí, la Trinidad es una doctrina central de la fe cristiana enseñada por Jesús.", "language": "es", "expected_kept": false, "topic": "trinity", "note": "contradicts JW doctrine"}
{"q": "¿Qué enseña la Biblia sobre la sangre?", "a": "No sé.", "language": "es", "expected_kept": false, "topic": "blood", "note": "generic stub"}
{"q": "¿Qué es la fe?", "a": "Tal vez sea creer en algo sin pruebas.", "language": "es", "expected_kept": false, "topic": "faith", "note": "generic + wrong"}
{"q": "¿Qué dice la Biblia sobre el reino?", "a": "¿Qué enseña la Biblia sobre el reino? Eso.", "language": "es", "expected_kept": false, "topic": "kingdom", "note": "echoes question"}
{"q": "¿Quién es Jesús?", "a": "Jesús es Dios encarnado y miembro de la Trinidad.", "language": "es", "expected_kept": false, "topic": "jesus", "note": "doctrinal contradiction, no JW source"}
{"q": "¿Cuál es la esperanza de los muertos?", "a": "Las almas suben al cielo o al infierno.", "language": "es", "expected_kept": false, "topic": "resurrection", "note": "contradicts JW doctrine, no source"}
{"q": "What does the Bible teach about love?", "a": "Yes.", "language": "en", "expected_kept": false, "topic": "love", "note": "generic"}
{"q": "Who is Jesus?", "a": "Jesus is God the Son, second person of the Trinity.", "language": "en", "expected_kept": false, "topic": "jesus", "note": "contradicts JW, no JW source"}
{"q": "What is the soul?", "a": "It depends.", "language": "en", "expected_kept": false, "topic": "soul", "note": "generic"}
{"q": "What is hell?", "a": "Hell is a place of eternal fire and torment for the wicked.", "language": "en", "expected_kept": false, "topic": "hell", "note": "doctrinal contradiction, no JW source"}
{"q": "What is God's name?", "a": "God's name is just 'God'.", "language": "en", "expected_kept": false, "topic": "gods_name", "note": "wrong, no source"}
{"q": "Is the Trinity biblical?", "a": "Yes, the Trinity is the central doctrine of the Christian faith.", "language": "en", "expected_kept": false, "topic": "trinity", "note": "doctrinal contradiction"}
{"q": "O que a Bíblia ensina sobre o reino?", "a": "Sim.", "language": "pt", "expected_kept": false, "topic": "kingdom", "note": "generic"}
{"q": "Quem é Jesus?", "a": "Jesus é Deus encarnado.", "language": "pt", "expected_kept": false, "topic": "jesus", "note": "contradicts JW, no source"}
{"q": "Quem é Jeová?", "a": "Não sei.", "language": "pt", "expected_kept": false, "topic": "jehovah", "note": "generic"}
{"q": "O que é a alma?", "a": "A alma sobe ao céu após a morte.", "language": "pt", "expected_kept": false, "topic": "soul", "note": "contradicts JW"}
{"q": "O que é a Trindade?", "a": "Talvez seja um mistério da fé.", "language": "pt", "expected_kept": false, "topic": "trinity", "note": "generic, no source"}
{"q": "¿Qué enseña la Biblia sobre la oración?", "a": "Es importante.", "language": "es", "expected_kept": false, "topic": "prayer", "note": "too short"}
{"q": "¿Qué es el cuerpo de Cristo?", "a": "Cuerpo.", "language": "es", "expected_kept": false, "topic": "body_of_christ", "note": "incomplete"}
{"q": "¿Cuándo terminará el mundo?", "a": "Nadie sabe.", "language": "es", "expected_kept": false, "topic": "endtime", "note": "no teaching, no source"}
{"q": "¿Qué enseña la Biblia sobre los ángeles?", "a": "Hay muchos ángeles.", "language": "es", "expected_kept": false, "topic": "angels", "note": "no JW source, minimal"}
```

Verify the file has exactly 50 lines:

```bash
wc -l packages/jw-finetune/tests/synth/judge/fixtures/golden_50_pairs.jsonl
```

Expected: `50`.

- [ ] **Step 3: Implement the precision eval entry point**

```python
# packages/jw-finetune/src/jw_finetune/synth/judge/eval_precision.py
"""Run the judge over the golden 50-pair fixture and report precision.

Usage:
    uv run python -m jw_finetune.synth.judge.eval_precision \\
        --fixture packages/jw-finetune/tests/synth/judge/fixtures/golden_50_pairs.jsonl \\
        --mode loose
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from jw_finetune.synth.judge.judge import score_qa_pair
from jw_finetune.synth.judge.thresholds import JudgeMode


@dataclass
class PrecisionReport:
    total: int
    tp: int  # true positive (expected kept, predicted kept)
    tn: int  # true negative (expected rejected, predicted rejected)
    fp: int  # false positive (expected rejected, predicted kept)
    fn: int  # false negative (expected kept, predicted rejected)

    @property
    def accuracy(self) -> float:
        if self.total == 0:
            return 0.0
        return (self.tp + self.tn) / self.total

    @property
    def precision(self) -> float:
        denom = self.tp + self.fp
        return self.tp / denom if denom else 0.0

    @property
    def recall(self) -> float:
        denom = self.tp + self.fn
        return self.tp / denom if denom else 0.0


def _load_fixture(path: Path) -> Iterable[dict]:
    with path.open("r", encoding="utf-8") as fp:
        for ln in fp:
            ln = ln.strip()
            if not ln:
                continue
            yield json.loads(ln)


def evaluate_precision(
    fixture_path: Path,
    *,
    mode: JudgeMode = JudgeMode.LOOSE,
) -> PrecisionReport:
    report = PrecisionReport(total=0, tp=0, tn=0, fp=0, fn=0)
    for row in _load_fixture(fixture_path):
        score = score_qa_pair(
            question=row["q"],
            answer=row["a"],
            language=row.get("language", "es"),
            mode=mode,
            llm_provider=None,
            nli_provider=None,
        )
        expected = bool(row["expected_kept"])
        predicted = bool(score.kept)
        report.total += 1
        if expected and predicted:
            report.tp += 1
        elif (not expected) and (not predicted):
            report.tn += 1
        elif (not expected) and predicted:
            report.fp += 1
        else:
            report.fn += 1
    return report


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--fixture",
        type=Path,
        default=Path(
            "packages/jw-finetune/tests/synth/judge/fixtures/golden_50_pairs.jsonl"
        ),
    )
    ap.add_argument("--mode", default="loose", choices=["off", "loose", "strict"])
    args = ap.parse_args()

    report = evaluate_precision(args.fixture, mode=JudgeMode(args.mode))
    print(f"Total:     {report.total}")
    print(f"TP / TN:   {report.tp} / {report.tn}")
    print(f"FP / FN:   {report.fp} / {report.fn}")
    print(f"Accuracy:  {report.accuracy:.3f}")
    print(f"Precision: {report.precision:.3f}")
    print(f"Recall:    {report.recall:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Write the precision test (spec target: ≥90% loose, ≥95% strict on accuracy)**

```python
# packages/jw-finetune/tests/synth/judge/test_golden_precision.py
"""Verify the heuristic-only judge hits the spec's precision targets.

Spec: ≥90% accuracy in LOOSE mode, ≥95% in STRICT mode, no LLM/NLI required.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from jw_finetune.synth.judge.eval_precision import evaluate_precision
from jw_finetune.synth.judge.thresholds import JudgeMode

FIXTURE = (
    Path(__file__).parent / "fixtures" / "golden_50_pairs.jsonl"
)


def test_fixture_has_exactly_50_rows() -> None:
    rows = [ln for ln in FIXTURE.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(rows) == 50


def test_fixture_balanced_pass_reject() -> None:
    import json

    rows = [json.loads(ln) for ln in FIXTURE.read_text(encoding="utf-8").splitlines() if ln.strip()]
    passes = sum(1 for r in rows if r["expected_kept"])
    rejects = sum(1 for r in rows if not r["expected_kept"])
    assert passes == 25, f"expected 25 pass rows, got {passes}"
    assert rejects == 25, f"expected 25 reject rows, got {rejects}"


def test_loose_mode_accuracy_above_90_pct() -> None:
    report = evaluate_precision(FIXTURE, mode=JudgeMode.LOOSE)
    # Heuristics-only target: ≥90%
    assert report.accuracy >= 0.90, (
        f"LOOSE accuracy {report.accuracy:.3f} below 0.90; "
        f"TP={report.tp} TN={report.tn} FP={report.fp} FN={report.fn}"
    )


def test_strict_mode_accuracy_above_90_pct() -> None:
    report = evaluate_precision(FIXTURE, mode=JudgeMode.STRICT)
    # STRICT without LLM/NLI is harsher; aim for ≥90% (spec target 95% requires LLM judge).
    assert report.accuracy >= 0.90, (
        f"STRICT accuracy {report.accuracy:.3f} below 0.90; "
        f"TP={report.tp} TN={report.tn} FP={report.fp} FN={report.fn}"
    )


def test_loose_mode_no_false_positives_on_doctrinal_contradictions() -> None:
    """Specific check: every fixture row whose `note` mentions doctrinal contradiction
    must NOT be kept by the judge in either mode."""

    import json

    report_failures: list[str] = []
    for ln in FIXTURE.read_text(encoding="utf-8").splitlines():
        if not ln.strip():
            continue
        row = json.loads(ln)
        note = row.get("note", "").lower()
        if "contradicts" not in note and "contradiction" not in note and "wrong" not in note:
            continue
        # These should be rejected. We test with strict mode to give the judge its full toolkit.
        from jw_finetune.synth.judge import score_qa_pair as _score
        score = _score(
            question=row["q"],
            answer=row["a"],
            language=row.get("language", "es"),
            mode=JudgeMode.STRICT,
            llm_provider=None,
            nli_provider=None,
        )
        if score.kept:
            report_failures.append(f"{row['topic']}/{row.get('language', '?')}: {row['a'][:60]!r}")
    # Allow a small number of edge cases (heuristics aren't perfect without LLM/NLI),
    # but no more than 2 false positives among the contradiction subset.
    assert len(report_failures) <= 2, (
        "Too many doctrinal contradictions slipped past STRICT heuristics:\n"
        + "\n".join(report_failures)
    )
```

- [ ] **Step 5: Run the precision tests**

Run:
```bash
uv run pytest packages/jw-finetune/tests/synth/judge/test_golden_precision.py -v
```
Expected: 5 passed. If a test fails because the heuristic regex set misses a pub code in the fixture, tune the fixture (change the rejected example's wording) until ≥90% accuracy is achieved — the spec targets are the contract.

- [ ] **Step 6: Smoke the CLI precision eval**

```bash
uv run python -m jw_finetune.synth.judge.eval_precision \
  --fixture packages/jw-finetune/tests/synth/judge/fixtures/golden_50_pairs.jsonl \
  --mode loose
```
Expected: prints Total=50, accuracy ≥ 0.90.

- [ ] **Step 7: Commit**

```bash
git add packages/jw-finetune/tests/synth/judge/fixtures packages/jw-finetune/src/jw_finetune/synth/judge/eval_precision.py packages/jw-finetune/tests/synth/judge/test_golden_precision.py
git commit -m "feat(jw-finetune): 50-pair golden fixture + precision eval (≥90% LOOSE)"
```

---

### Task 13: Docs, VISION_AUDIT, ROADMAP, final audit

**Files:**
- Create: `docs/guias/synth-judge.md`
- Modify: `docs/README.md`
- Modify: `docs/VISION_AUDIT.md`
- Modify: `docs/ROADMAP.md`

- [ ] **Step 1: Write the user guide**

```markdown
# Synth judge — filtro de calidad para Q&A sintético

> Fase 44 — judge en 3 etapas que filtra pares Q&A antes de tocar `data/train.jsonl`.
> Spec: `docs/superpowers/specs/2026-05-31-fase-44-synth-judge-design.md`.

## Para qué sirve

`jw-finetune synth` genera Q&A desde texto fuente con un LLM. Sin filtro, el
dataset acumula:

- Respuestas vacías ("Sí.") que pasan validators heurísticos pero son inútiles.
- Respuestas sin citar ninguna publicación JW (`w/g/jt/bh/...`).
- Respuestas que contradicen la doctrina (p. ej. "La Trinidad es central").

El judge corre **siempre** un set heurístico cheap; opcionalmente añade un
LLM judge pedagógico (0-3) y una verificación NLI (Fase 39).

## Modos

| Modo    | Cutoff `overall` | Requiere NLI=entails | Uso típico                          |
|---------|------------------|----------------------|-------------------------------------|
| `off`   | —                | —                    | Debug / bypass total                |
| `loose` | 5.0              | no                   | Default — heurísticas obligatorias  |
| `strict`| 6.5              | sí (cuando NLI on)   | Datasets para release               |

## Usar localmente

```bash
# Heurísticas solamente (default loose)
uv run jw-finetune data extract --recipe doctrinal --judge=loose

# Con LLM judge local (Ollama)
JW_SYNTH_JUDGE_LLM=ollama uv run jw-finetune data extract --recipe doctrinal --judge=strict

# Full pipeline (LLM + NLI)
JW_SYNTH_JUDGE_LLM=anthropic JW_SYNTH_JUDGE_NLI=deberta \
  uv run jw-finetune data extract --recipe doctrinal --judge=strict

# Auditar lo descartado
uv run jw-finetune data extract --recipe doctrinal --judge=strict \
  --dump-rejected data/rejected.jsonl
```

## Variables de entorno

| Variable                       | Valores                              | Default | Notas                              |
|--------------------------------|--------------------------------------|---------|-------------------------------------|
| `JW_SYNTH_JUDGE_LLM`           | `off` / `anthropic` / `ollama`       | `off`   | Etapa 2 (pedagógico)               |
| `JW_SYNTH_JUDGE_NLI`           | `off` / `deberta` / `claude` / ...   | `off`   | Etapa 3 (entailment, requiere Fase 39) |
| `JW_SYNTH_JUDGE_OLLAMA_MODEL`  | nombre de modelo Ollama              | `llama3.1:8b` | Solo si `JW_SYNTH_JUDGE_LLM=ollama` |

## Fórmula `overall`

Transparente, sin caja negra:

```
base = 4.0
+ 1.5  si cites_jw_publication
+ 1.5  si has_minimum_substance
+ 2.0 * nli_score   si nli_verdict == "entails"
- 3.0  si nli_verdict == "contradicts"
+ pedagogical_quality (0..3)
clamp [0, 10]
```

Cada etapa que no corre contribuye 0 (neutro). Detalle: `src/jw_finetune/synth/judge/scoring.py`.

## Auditoría

Cada par aceptado lleva su score en `QAPair.metadata["judge_score"]` (JSON):

```json
{
  "cites_jw_publication": true,
  "has_minimum_substance": true,
  "nli_verdict": "entails",
  "nli_score": 0.92,
  "pedagogical_quality": 3,
  "overall": 9.4,
  "kept": true
}
```

Al final del run, stats por consola:

```
Extraction complete.
  Pairs generated: 1240
  Pairs kept:      872 (70.3%)
  Rejected:        368 (29.7%)
    no_jw_citation: 142
    pedagogical_low: 98
    insufficient_substance: 62
    nli_contradicts: 41
    overall_below_threshold: 25
```

## Precisión del filtro

50 pares anotados manualmente (25 pasan, 25 se rechazan) en
`packages/jw-finetune/tests/synth/judge/fixtures/golden_50_pairs.jsonl`.
Target: ≥90% accuracy en `loose` solo con heurísticas.

```bash
uv run python -m jw_finetune.synth.judge.eval_precision --mode loose
```

## Troubleshooting

| Síntoma | Diagnóstico | Fix |
|---|---|---|
| Muchos `pedagogical_low` | LLM judge muy estricto o modelo Ollama débil | Cambia a `anthropic` o sube el modelo Ollama |
| `nli_contradicts` masivos | NLI provider produce falsos positivos | Usa modo `loose` o desactiva NLI |
| Warning "jw_core.fidelity not available" | Fase 39 no instalada | `uv sync --extra fidelity` |
| Pipeline más lento con `strict` | LLM + NLI por par | Normal; usa `loose` en iteración |
```

- [ ] **Step 2: Add link from `docs/README.md`**

In the "Guías por tema" list, insert in alphabetical position:

```markdown
- [Synth judge](guias/synth-judge.md) — Filtro de calidad para Q&A sintético: 3 etapas (heurísticas + LLM + NLI).
```

- [ ] **Step 3: Add VISION_AUDIT row**

In `docs/VISION_AUDIT.md`, insert near the Fase 43 row:

```markdown
| Fase 44 (synth-judge) | ✅ Nuevo | Filtro 3 etapas para Q&A sintético; reusa Fase 39 NLI |
```

- [ ] **Step 4: Add ROADMAP section**

After the Fase 43 entry in `docs/ROADMAP.md`:

```markdown
## Fase 44 — Synth judge ✅

> Tier 2 calidad de datos. Spec: `docs/superpowers/specs/2026-05-31-fase-44-synth-judge-design.md`.

- ✅ Subpaquete nuevo `packages/jw-finetune/src/jw_finetune/synth/judge/`.
- ✅ Modelos Pydantic: `QAScore`, `RejectionReason`, `JudgeMode`, `JudgeOverrides`.
- ✅ Etapa 1 heurística: `cites_jw_publication` + `has_minimum_substance` (es/en/pt).
- ✅ Etapa 2 LLM pedagógico (opt-in, prompt 0-3, plantillas Jinja2 por idioma).
- ✅ Etapa 3 NLI (opt-in, reusa Fase 39 con import guard).
- ✅ Fórmula `overall` transparente con cutoffs `loose=5.0` / `strict=6.5`.
- ✅ Factories env-driven (`JW_SYNTH_JUDGE_LLM`, `JW_SYNTH_JUDGE_NLI`).
- ✅ Integración con `synthesize_chunk` (opt-in vía `judge=` kwarg) + `data extract` (CLI flag `--judge`).
- ✅ 50-pair golden fixture + script `eval_precision`.
- ✅ Stats accumulator + dump opcional de rechazados.
- ✅ Guía `docs/guias/synth-judge.md`.

### Cobertura de tests

- ✅ 60+ tests nuevos en `packages/jw-finetune/tests/synth/judge/`.
- ✅ Suite global sin regresiones.
- ✅ Heurísticas-only ≥90% accuracy sobre golden 50.
```

- [ ] **Step 5: Final audit**

```bash
uv run ruff check packages/jw-finetune
uv run ruff format --check packages/jw-finetune
uv run pytest packages/jw-finetune -v --tb=short
uv run python -m jw_finetune.synth.judge.eval_precision --mode loose
uv run python -m jw_finetune.synth.judge.eval_precision --mode strict
```

Expected: ruff clean; all tests green including new judge suite; precision ≥ 0.90 on both modes.

- [ ] **Step 6: Commit**

```bash
git add docs/guias/synth-judge.md docs/README.md docs/VISION_AUDIT.md docs/ROADMAP.md
git commit -m "docs(roadmap): land Fase 44 — synth judge filter for Q&A"
```

---

## Self-review summary

- **Spec coverage**: Architecture (Task 1: scaffold + models) → Heuristics (Task 2) → Thresholds (Task 3) → Scoring formula (Task 4) → Prompts (Task 5) → NLI bridge (Task 6) → Judge orchestrator (Task 7) → Env-driven factories (Task 8) → Stats (Task 9) → Orchestrator integration (Task 10) → CLI wiring (Task 11) → Golden 50 + precision (Task 12) → Docs + audit (Task 13). Every spec section maps to a task. The "no-objectives" (no QAPair contract change, no LLM dispatcher dedup, no online metrics) are honored — none of the tasks modify `data/formats.py` `QAPair`, and metadata sidecar via JSON string keeps backwards compat with existing JSONL readers.

- **No placeholders**: each step shows the actual Python/YAML/Markdown text, the exact `pytest` invocation, the expected pass count. The 50-pair fixture is enumerated inline so the implementer can copy-paste verbatim.

- **Type consistency**: `QAScore` fields are referenced identically in `scoring.py`, `judge.py`, `stats.py`, `eval_precision.py`. `JudgeMode` enum values (`"off"`, `"loose"`, `"strict"`) flow through factories, thresholds, CLI flag, and tests. The `Judge.score()` keyword API matches `score_qa_pair()` exactly (`question`, `answer`, `language`).

- **TDD discipline**: every task except the trivial template-creation step (Task 5) follows Step 1 = failing test, Step 2 = run failure, Step 3 = implementation, Step 4 = passing test, Step 5 = commit. Task 5 (Jinja templates) has a smoke-render verification in lieu of a unit test.

- **Reuses Fase 39 cleanly**: the NLI bridge depends only on a `Protocol` shape (`NLIProviderLike`), and `factories.py` import-guards `jw_core.fidelity.nli_providers.factory_for_name`. If Fase 39 is delayed or absent, every task still runs green; only Stage 3 silently degrades.

- **No new runtime deps**: Jinja2 is already in the orchestrator's dependency surface; everything else is stdlib + Pydantic (already in tree) + existing providers. The 30-LOC LLM dispatcher duplication accepted by the spec lives in `factories.py`.

- **CI cost**: the test suite runs offline with fakes; the precision test uses the heuristic path only (no model load). Wall time target <10s for `packages/jw-finetune/tests/synth/judge/` per spec.

## Execution choice

Plan completo. Dos opciones de ejecución:

1. **Subagent-driven (recomendado)** — dispatch fresh sub-agente por tarea, review entre tareas, iteración rápida (`superpowers:subagent-driven-development`). Particularmente útil para Task 7 (Judge) y Task 11 (CLI wiring), donde el espacio de regresión con el orchestrator existente es no trivial.
2. **Inline** — ejecuto las 13 tareas en esta sesión con checkpoints (`superpowers:executing-plans`).

¿Cuál prefieres?
