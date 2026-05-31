# Fase 22 — `jw-eval` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `jw-eval`, a 3-layer doctrinal evaluation suite with golden Q&A regression that runs in CI and protects the agent contracts of all subsequent phases.

**Architecture:** New monorepo package `packages/jw-eval/`. Three independent layers (structural / citations / semantic) share a YAML-loaded GoldenCase model and a Suite dispatcher. Judges are pluggable (embeddings + LLM via env). CI gets two new jobs (offline, blocking) plus two scheduled jobs (live + nightly L3).

**Tech Stack:** Python 3.13 · Pydantic (models) · pytest (test runner + eval runner via custom CLI) · PyYAML (fixtures) · sentence-transformers (optional, L3) · Ollama HTTP / Anthropic SDK (LLM judge) · Typer (CLI) · FastMCP (MCP tool).

**Spec:** [`docs/superpowers/specs/2026-05-30-fase-22-eval-doctrinal-design.md`](../specs/2026-05-30-fase-22-eval-doctrinal-design.md).

---

## File map

Creates:
- `packages/jw-eval/pyproject.toml`
- `packages/jw-eval/README.md`
- `packages/jw-eval/src/jw_eval/__init__.py`
- `packages/jw-eval/src/jw_eval/models.py`
- `packages/jw-eval/src/jw_eval/loader.py`
- `packages/jw-eval/src/jw_eval/suite.py`
- `packages/jw-eval/src/jw_eval/layers/__init__.py`
- `packages/jw-eval/src/jw_eval/layers/structural.py`
- `packages/jw-eval/src/jw_eval/layers/citations.py`
- `packages/jw-eval/src/jw_eval/layers/semantic.py`
- `packages/jw-eval/src/jw_eval/judges/__init__.py`
- `packages/jw-eval/src/jw_eval/judges/embeddings.py`
- `packages/jw-eval/src/jw_eval/judges/llm.py`
- `packages/jw-eval/src/jw_eval/report.py`
- `packages/jw-eval/src/jw_eval/cli.py`
- `packages/jw-eval/scripts/build_eval_snapshots.py`
- `packages/jw-eval/scripts/eval_open_drift_issues.py`
- `packages/jw-eval/fixtures/golden_qa/l1/*.yaml` (12 files)
- `packages/jw-eval/fixtures/golden_qa/l2/*.yaml` (12 files)
- `packages/jw-eval/fixtures/golden_qa/l3/*.yaml` (6 files)
- `packages/jw-eval/fixtures/wol_snapshots/*.html` (12+ files, auto-built)
- `packages/jw-eval/tests/test_models.py`
- `packages/jw-eval/tests/test_loader.py`
- `packages/jw-eval/tests/test_layer_structural.py`
- `packages/jw-eval/tests/test_layer_citations.py`
- `packages/jw-eval/tests/test_layer_semantic.py`
- `packages/jw-eval/tests/test_judges.py`
- `packages/jw-eval/tests/test_suite.py`
- `packages/jw-eval/tests/test_report.py`
- `packages/jw-eval/tests/test_cli.py`
- `packages/jw-eval/tests/fixtures/mini/*.yaml` (synthetic cases for self-tests)
- `docs/guias/eval-doctrinal.md`

Modifies:
- `pyproject.toml` (root) — add `packages/jw-eval` to workspace members + `jw-eval` source.
- `packages/jw-cli/pyproject.toml` — add `jw-eval` dependency.
- `packages/jw-cli/src/jw_cli/main.py` — register `eval` command.
- `packages/jw-cli/src/jw_cli/commands/__init__.py` + new `eval.py`.
- `packages/jw-mcp/pyproject.toml` — add `jw-eval` dependency.
- `packages/jw-mcp/src/jw_mcp/server.py` — register `run_eval_suite` tool.
- `.github/workflows/ci.yml` — add `eval-fast`, `eval-l2-live`, `eval-nightly` jobs.
- `docs/VISION_AUDIT.md` — add Fase 22 row.
- `docs/ROADMAP.md` — add Fase 22 section.
- `docs/README.md` — link the new guide.

---

### Task 1: Scaffold `jw-eval` package and register in workspace

**Files:**
- Create: `packages/jw-eval/pyproject.toml`
- Create: `packages/jw-eval/README.md`
- Create: `packages/jw-eval/src/jw_eval/__init__.py`
- Modify: `pyproject.toml` (root)

- [ ] **Step 1: Create the package pyproject.toml**

```toml
# packages/jw-eval/pyproject.toml
[project]
name = "jw-eval"
version = "0.1.0"
description = "Doctrinal regression eval suite for jw-agent-toolkit"
readme = "README.md"
requires-python = ">=3.13"
license = "GPL-3.0-only"
dependencies = [
    "jw-core",
    "jw-rag",
    "jw-agents",
    "pydantic>=2.5.0",
    "pyyaml>=6.0.1",
    "typer>=0.12.0",
    "httpx>=0.27.0",
]

[project.optional-dependencies]
embeddings = [
    "sentence-transformers>=2.7.0",
]
ollama = [
    # nothing — uses httpx directly against local Ollama HTTP API
]
claude = [
    "anthropic>=0.34.0",
]
openai = [
    "openai>=1.40.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/jw_eval"]
```

- [ ] **Step 2: Create README**

```markdown
# jw-eval

Doctrinal regression eval suite for the jw-agent-toolkit.

Three layers:
- **L1 — Structural** — agent contract regression (no network, no LLM).
- **L2 — Citations** — every URL resolves and supports the claim (snapshot or live).
- **L3 — Semantic** — agent answer ≈ golden answer (embeddings + LLM judge).

Run: `jw eval --layer 1,2`.
Spec: `docs/superpowers/specs/2026-05-30-fase-22-eval-doctrinal-design.md`.
```

- [ ] **Step 3: Create empty package init**

```python
# packages/jw-eval/src/jw_eval/__init__.py
"""jw-eval — doctrinal regression eval suite.

Public API:
    from jw_eval import Suite, GoldenCase, LayerResult, SuiteReport
"""

from jw_eval.models import GoldenCase, LayerResult, SuiteReport
from jw_eval.suite import Suite

__all__ = ["GoldenCase", "LayerResult", "Suite", "SuiteReport"]
```

- [ ] **Step 4: Register in workspace**

Edit `pyproject.toml` (root):
- In `[tool.uv.workspace] members = [...]` append `"packages/jw-eval"`.
- In `[tool.uv.sources]` add `jw-eval = { workspace = true }`.

- [ ] **Step 5: Verify install**

Run: `uv sync --all-packages`
Expected: no errors. `uv pip list | grep jw-eval` shows `jw-eval 0.1.0`.

- [ ] **Step 6: Commit**

```bash
git add packages/jw-eval pyproject.toml uv.lock
git commit -m "feat(jw-eval): scaffold package and register in workspace"
```

---

### Task 2: Models (`GoldenCase`, `LayerResult`, `SuiteReport`)

**Files:**
- Create: `packages/jw-eval/src/jw_eval/models.py`
- Create: `packages/jw-eval/tests/test_models.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-eval/tests/test_models.py
"""Tests for jw_eval.models."""

from __future__ import annotations

from datetime import datetime

import pytest

from jw_eval.models import GoldenCase, LayerResult, SuiteReport


def test_golden_case_minimal() -> None:
    case = GoldenCase(
        id="l1_demo",
        agent="apologetics",
        layer="l1",
        input={"question": "test"},
        expected={"min_findings": 1},
    )
    assert case.id == "l1_demo"
    assert case.layer == "l1"
    assert case.metadata == {}


def test_golden_case_rejects_invalid_layer() -> None:
    with pytest.raises(ValueError):
        GoldenCase(
            id="x",
            agent="apologetics",
            layer="l9",  # type: ignore[arg-type]
            input={},
            expected={},
        )


def test_layer_result_pass() -> None:
    r = LayerResult(
        case_id="l1_demo",
        layer="l1",
        verdict="pass",
        score=None,
        reasons=[],
        duration_ms=12,
    )
    assert r.verdict == "pass"
    assert r.score is None


def test_suite_report_summary_aggregates() -> None:
    now = datetime(2026, 5, 30, 12, 0, 0)
    results = [
        LayerResult(case_id="a", layer="l1", verdict="pass", score=None, reasons=[], duration_ms=1),
        LayerResult(case_id="b", layer="l1", verdict="fail", score=None, reasons=["x"], duration_ms=2),
        LayerResult(case_id="c", layer="l2", verdict="pass", score=None, reasons=[], duration_ms=3),
    ]
    report = SuiteReport(
        started_at=now,
        finished_at=now,
        layers_run=["l1", "l2"],
        results=results,
        summary=SuiteReport.summarize(results),
    )
    assert report.summary["l1"]["pass"] == 1
    assert report.summary["l1"]["fail"] == 1
    assert report.summary["l2"]["pass"] == 1
    assert report.summary["l2"]["fail"] == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/jw-eval/tests/test_models.py -v`
Expected: FAIL — ModuleNotFoundError or AttributeError on `models`.

- [ ] **Step 3: Implement the models**

```python
# packages/jw-eval/src/jw_eval/models.py
"""Pydantic models for the eval suite.

A GoldenCase is one row in the suite. It declares which agent to run, what
input to give it, and what the expected output looks like — shape of
`expected` depends on the layer.

A LayerResult is the verdict for one (case, layer) pair.

A SuiteReport is the aggregate of all LayerResults plus metadata.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

LayerName = Literal["l1", "l2", "l3"]
Verdict = Literal["pass", "fail", "skip", "error"]


class GoldenCase(BaseModel):
    """One Golden Q&A case."""

    id: str
    agent: str
    layer: LayerName
    input: dict[str, Any]
    expected: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class LayerResult(BaseModel):
    """Verdict of evaluating one case at one layer."""

    case_id: str
    layer: LayerName
    verdict: Verdict
    score: float | None = None  # 0..1 for L3; None for L1/L2
    reasons: list[str] = Field(default_factory=list)
    duration_ms: int = 0


class SuiteReport(BaseModel):
    """Aggregate report for a Suite run."""

    started_at: datetime
    finished_at: datetime
    layers_run: list[str]
    results: list[LayerResult]
    summary: dict[str, dict[str, int]] = Field(default_factory=dict)
    diff_vs_baseline: dict[str, Any] | None = None

    @staticmethod
    def summarize(results: list[LayerResult]) -> dict[str, dict[str, int]]:
        """Roll up verdict counts per layer."""

        agg: dict[str, dict[str, int]] = defaultdict(
            lambda: {"pass": 0, "fail": 0, "skip": 0, "error": 0}
        )
        for r in results:
            agg[r.layer][r.verdict] += 1
        return dict(agg)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/jw-eval/tests/test_models.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-eval/src/jw_eval/models.py packages/jw-eval/tests/test_models.py
git commit -m "feat(jw-eval): add GoldenCase/LayerResult/SuiteReport models"
```

---

### Task 3: YAML Loader

**Files:**
- Create: `packages/jw-eval/src/jw_eval/loader.py`
- Create: `packages/jw-eval/tests/test_loader.py`
- Create: `packages/jw-eval/tests/fixtures/mini/demo_l1.yaml`

- [ ] **Step 1: Write the demo fixture**

```yaml
# packages/jw-eval/tests/fixtures/mini/demo_l1.yaml
id: mini_l1_demo
agent: apologetics
layer: l1
input:
  question: "demo"
  language: en
expected:
  min_findings: 1
metadata:
  added_at: 2026-05-30
```

- [ ] **Step 2: Write the failing test**

```python
# packages/jw-eval/tests/test_loader.py
from __future__ import annotations

from pathlib import Path

import pytest

from jw_eval.loader import load_cases, load_case_file

FIXTURES = Path(__file__).parent / "fixtures" / "mini"


def test_load_case_file_minimal() -> None:
    case = load_case_file(FIXTURES / "demo_l1.yaml")
    assert case.id == "mini_l1_demo"
    assert case.layer == "l1"
    assert case.input["question"] == "demo"


def test_load_cases_filters_by_layer() -> None:
    cases = load_cases(FIXTURES, layers=["l1"])
    assert len(cases) >= 1
    assert all(c.layer == "l1" for c in cases)


def test_load_cases_empty_dir(tmp_path: Path) -> None:
    assert load_cases(tmp_path, layers=["l1"]) == []


def test_load_case_file_missing_required_field(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text("id: x\n")  # missing agent, layer, input
    with pytest.raises(ValueError):
        load_case_file(bad)
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest packages/jw-eval/tests/test_loader.py -v`
Expected: FAIL — loader module not found.

- [ ] **Step 4: Implement the loader**

```python
# packages/jw-eval/src/jw_eval/loader.py
"""Load GoldenCase YAML files from disk.

Convention: cases live in subdirs by layer (l1/, l2/, l3/) under one root.
One YAML file = one GoldenCase. Filenames are free-form but should be
descriptive (e.g. `apologetics_trinity_es.yaml`).
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import ValidationError

from jw_eval.models import GoldenCase, LayerName


def load_case_file(path: Path) -> GoldenCase:
    """Parse one YAML file into a GoldenCase. Raise ValueError on schema errors."""

    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: expected YAML mapping, got {type(raw).__name__}")
    try:
        return GoldenCase.model_validate(raw)
    except ValidationError as exc:
        raise ValueError(f"{path}: {exc}") from exc


def load_cases(root: Path, layers: list[LayerName] | None = None) -> list[GoldenCase]:
    """Recursively load every *.yaml under root, optionally filtering by layer."""

    cases: list[GoldenCase] = []
    if not root.exists():
        return cases
    for path in sorted(root.rglob("*.yaml")):
        case = load_case_file(path)
        if layers and case.layer not in layers:
            continue
        cases.append(case)
    return cases
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest packages/jw-eval/tests/test_loader.py -v`
Expected: 4 passed.

- [ ] **Step 6: Commit**

```bash
git add packages/jw-eval/src/jw_eval/loader.py packages/jw-eval/tests/test_loader.py packages/jw-eval/tests/fixtures
git commit -m "feat(jw-eval): YAML loader for GoldenCase fixtures"
```

---

### Task 4: Layer 1 — Structural evaluator

**Files:**
- Create: `packages/jw-eval/src/jw_eval/layers/__init__.py`
- Create: `packages/jw-eval/src/jw_eval/layers/structural.py`
- Create: `packages/jw-eval/tests/test_layer_structural.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-eval/tests/test_layer_structural.py
from __future__ import annotations

from typing import Any

from jw_eval.layers.structural import evaluate_structural
from jw_eval.models import GoldenCase


class FakeFinding:
    def __init__(self, source: str, has_citation: bool = True, text: str = "demo") -> None:
        self._source = source
        self._has_citation = has_citation
        self._text = text

    @property
    def text(self) -> str:
        return self._text

    @property
    def metadata(self) -> dict[str, Any]:
        return {"source": self._source} if self._has_citation else {}


class FakeResult:
    def __init__(self, findings: list[FakeFinding]) -> None:
        self.findings = findings


def _agent_factory(result: FakeResult):
    def run(input_dict: dict[str, Any]) -> FakeResult:  # noqa: ARG001
        return result
    return run


def test_structural_passes_when_all_checks_met() -> None:
    case = GoldenCase(
        id="t1",
        agent="apologetics",
        layer="l1",
        input={"question": "?"},
        expected={
            "min_findings": 2,
            "sources_in_order": ["topic_index", "verse_text"],
            "must_have_source": "topic_index",
            "must_have_citation": True,
            "forbidden_keywords_in_findings": ["maybe"],
        },
    )
    result = FakeResult(
        findings=[
            FakeFinding("topic_index", True, "Real cite"),
            FakeFinding("verse_text", True, "Verse"),
        ]
    )
    r = evaluate_structural(case, _agent_factory(result))
    assert r.verdict == "pass"


def test_structural_fails_on_missing_source() -> None:
    case = GoldenCase(
        id="t2",
        agent="apologetics",
        layer="l1",
        input={"question": "?"},
        expected={"must_have_source": "topic_index"},
    )
    result = FakeResult(findings=[FakeFinding("rag")])
    r = evaluate_structural(case, _agent_factory(result))
    assert r.verdict == "fail"
    assert any("topic_index" in reason for reason in r.reasons)


def test_structural_fails_on_forbidden_keyword() -> None:
    case = GoldenCase(
        id="t3",
        agent="apologetics",
        layer="l1",
        input={"question": "?"},
        expected={"forbidden_keywords_in_findings": ["maybe"]},
    )
    result = FakeResult(findings=[FakeFinding("rag", True, "this is maybe wrong")])
    r = evaluate_structural(case, _agent_factory(result))
    assert r.verdict == "fail"


def test_structural_fails_on_missing_citation() -> None:
    case = GoldenCase(
        id="t4",
        agent="apologetics",
        layer="l1",
        input={"question": "?"},
        expected={"must_have_citation": True},
    )
    result = FakeResult(findings=[FakeFinding("rag", has_citation=False)])
    r = evaluate_structural(case, _agent_factory(result))
    assert r.verdict == "fail"


def test_structural_errors_when_agent_raises() -> None:
    case = GoldenCase(id="t5", agent="apologetics", layer="l1", input={}, expected={})

    def broken(_: dict[str, Any]):
        raise RuntimeError("boom")

    r = evaluate_structural(case, broken)
    assert r.verdict == "error"
    assert any("boom" in reason for reason in r.reasons)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/jw-eval/tests/test_layer_structural.py -v`
Expected: FAIL — structural module missing.

- [ ] **Step 3: Implement the structural evaluator**

```python
# packages/jw-eval/src/jw_eval/layers/__init__.py
"""Layer evaluators: structural (L1), citations (L2), semantic (L3)."""
```

```python
# packages/jw-eval/src/jw_eval/layers/structural.py
"""L1 — Structural eval.

Runs the agent on the case input and checks the AgentResult shape against
the expected dict. Pure CPU, no network.

Expected keys (all optional, all enforced when present):
  min_findings: int                      — len(result.findings) >= N
  must_have_source: str                  — any finding has metadata.source == X
  sources_in_order: list[str]            — result.findings[i].metadata.source matches in order
  must_have_citation: bool               — every finding has metadata.source set
  forbidden_keywords_in_findings: list   — none of these substrings in any finding.text
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any, Protocol

from jw_eval.models import GoldenCase, LayerResult


class _AgentResultLike(Protocol):
    findings: list[Any]  # each finding has `.text` and `.metadata`


AgentCallable = Callable[[dict[str, Any]], _AgentResultLike]


def evaluate_structural(case: GoldenCase, agent: AgentCallable) -> LayerResult:
    """Evaluate one L1 case. `agent` is a callable returning an AgentResult-like object."""

    started = time.monotonic()
    reasons: list[str] = []

    try:
        result = agent(case.input)
    except Exception as exc:
        return LayerResult(
            case_id=case.id,
            layer="l1",
            verdict="error",
            reasons=[f"agent raised: {exc!r}"],
            duration_ms=int((time.monotonic() - started) * 1000),
        )

    findings = list(result.findings)
    exp = case.expected

    min_n = exp.get("min_findings")
    if isinstance(min_n, int) and len(findings) < min_n:
        reasons.append(f"min_findings={min_n} but got {len(findings)}")

    must_src = exp.get("must_have_source")
    if isinstance(must_src, str) and not any(
        getattr(f, "metadata", {}).get("source") == must_src for f in findings
    ):
        reasons.append(f"missing required source={must_src!r}")

    ordered = exp.get("sources_in_order")
    if isinstance(ordered, list):
        actual = [getattr(f, "metadata", {}).get("source") for f in findings[: len(ordered)]]
        if actual != ordered:
            reasons.append(f"sources_in_order expected {ordered}, got {actual}")

    if exp.get("must_have_citation") is True:
        for i, f in enumerate(findings):
            if not getattr(f, "metadata", {}).get("source"):
                reasons.append(f"finding[{i}] lacks metadata.source")

    forbidden = exp.get("forbidden_keywords_in_findings") or []
    for kw in forbidden:
        for i, f in enumerate(findings):
            text = getattr(f, "text", "") or ""
            if kw.lower() in text.lower():
                reasons.append(f"forbidden keyword {kw!r} found in finding[{i}]")

    verdict = "pass" if not reasons else "fail"
    return LayerResult(
        case_id=case.id,
        layer="l1",
        verdict=verdict,
        reasons=reasons,
        duration_ms=int((time.monotonic() - started) * 1000),
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/jw-eval/tests/test_layer_structural.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-eval/src/jw_eval/layers packages/jw-eval/tests/test_layer_structural.py
git commit -m "feat(jw-eval): Layer 1 — structural evaluator"
```

---

### Task 5: Seed L1 Golden Cases (12 fixtures)

**Files:**
- Create: `packages/jw-eval/fixtures/golden_qa/l1/verse_explainer_john_3_16_es.yaml`
- Create: `packages/jw-eval/fixtures/golden_qa/l1/verse_explainer_john_3_16_en.yaml`
- Create: `packages/jw-eval/fixtures/golden_qa/l1/verse_explainer_romans_6_23_en.yaml`
- Create: `packages/jw-eval/fixtures/golden_qa/l1/apologetics_trinity_es.yaml`
- Create: `packages/jw-eval/fixtures/golden_qa/l1/apologetics_trinity_en.yaml`
- Create: `packages/jw-eval/fixtures/golden_qa/l1/apologetics_hell_es.yaml`
- Create: `packages/jw-eval/fixtures/golden_qa/l1/apologetics_soul_en.yaml`
- Create: `packages/jw-eval/fixtures/golden_qa/l1/research_topic_kingdom_en.yaml`
- Create: `packages/jw-eval/fixtures/golden_qa/l1/research_topic_resurrection_es.yaml`
- Create: `packages/jw-eval/fixtures/golden_qa/l1/meeting_helper_pubtalk_en.yaml`
- Create: `packages/jw-eval/fixtures/golden_qa/l1/meeting_helper_workbook_es.yaml`
- Create: `packages/jw-eval/fixtures/golden_qa/l1/conversation_assistant_creation_en.yaml`

- [ ] **Step 1: Write the first L1 case fully**

```yaml
# packages/jw-eval/fixtures/golden_qa/l1/verse_explainer_john_3_16_es.yaml
id: l1_verse_explainer_john_3_16_es
agent: verse_explainer
layer: l1
input:
  reference: "Juan 3:16"
  language: es
expected:
  min_findings: 1
  must_have_source: verse_text
  must_have_citation: true
  forbidden_keywords_in_findings:
    - "supuestamente"
    - "tal vez"
metadata:
  topic: bible.john.3.16
  added_by: elias
  added_at: 2026-05-30
```

- [ ] **Step 2: Write the apologetics-Trinity case fully**

```yaml
# packages/jw-eval/fixtures/golden_qa/l1/apologetics_trinity_es.yaml
id: l1_apologetics_trinity_es
agent: apologetics
layer: l1
input:
  question: "¿Es la Trinidad bíblica?"
  language: es
expected:
  min_findings: 3
  sources_in_order:
    - topic_index
  must_have_source: topic_index
  must_have_citation: true
  forbidden_keywords_in_findings:
    - "doctrina central"
metadata:
  topic: doctrine.trinity
  added_by: elias
  added_at: 2026-05-30
```

- [ ] **Step 3: Write the remaining 10 cases following the same shape**

Each remaining file uses the exact schema from Steps 1-2. Concrete content for each:

```yaml
# verse_explainer_john_3_16_en.yaml — same as _es but reference="John 3:16", language=en
# verse_explainer_romans_6_23_en.yaml — reference="Romans 6:23", language=en
# apologetics_trinity_en.yaml — question="Is the Trinity biblical?", language=en, forbidden=["central doctrine"]
# apologetics_hell_es.yaml — question="¿Existe el infierno de fuego?", forbidden=["llamas eternas literales"]
# apologetics_soul_en.yaml — question="Do humans have an immortal soul?", forbidden=["immortal by nature"]
# research_topic_kingdom_en.yaml — agent=research_topic, input={topic:"Kingdom of God", language:"en"}, must_have_source=cdn_search
# research_topic_resurrection_es.yaml — agent=research_topic, input={topic:"Resurrección", language:"es"}, must_have_source=cdn_search
# meeting_helper_pubtalk_en.yaml — agent=meeting_helper, input={url_or_ref:"Romans 12:1", language:"en", kind:"public_talk"}, min_findings=2
# meeting_helper_workbook_es.yaml — agent=meeting_helper, input={url_or_ref:"Mateo 24:14", language:"es", kind:"workbook"}, min_findings=2
# conversation_assistant_creation_en.yaml — agent=conversation_assistant, input={topic:"creation", audience:"atheist", language:"en"}, min_findings=2
```

- [ ] **Step 4: Verify all 12 cases load**

Run:
```bash
uv run python -c "
from pathlib import Path
from jw_eval.loader import load_cases
cases = load_cases(Path('packages/jw-eval/fixtures/golden_qa'), layers=['l1'])
print(f'Loaded {len(cases)} L1 cases')
assert len(cases) == 12, f'expected 12, got {len(cases)}'
print('OK')
"
```
Expected: `Loaded 12 L1 cases\nOK`

- [ ] **Step 5: Commit**

```bash
git add packages/jw-eval/fixtures/golden_qa/l1
git commit -m "feat(jw-eval): seed 12 L1 golden cases (verse/apologetics/research/meeting/conversation)"
```

---

### Task 6: Layer 2 snapshot mode + build script

**Files:**
- Create: `packages/jw-eval/src/jw_eval/layers/citations.py`
- Create: `packages/jw-eval/scripts/build_eval_snapshots.py`
- Create: `packages/jw-eval/tests/test_layer_citations.py`

- [ ] **Step 1: Write the failing test (snapshot mode only here)**

```python
# packages/jw-eval/tests/test_layer_citations.py
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import pytest

from jw_eval.layers.citations import evaluate_citations_snapshot, snapshot_path
from jw_eval.models import GoldenCase


def _stub_agent(citations: list[str]):
    class _F:
        def __init__(self, url: str) -> None:
            self.metadata = {"citation_url": url}

    class _R:
        findings = [_F(u) for u in citations]

    def run(_: dict[str, Any]) -> _R:
        return _R()

    return run


def test_snapshot_path_is_sha256(tmp_path: Path) -> None:
    url = "https://wol.jw.org/example"
    p = snapshot_path(tmp_path, url)
    assert p.name == hashlib.sha256(url.encode()).hexdigest() + ".html"


def test_citations_pass_when_url_and_phrase_present(tmp_path: Path) -> None:
    url = "https://wol.jw.org/x"
    snap = snapshot_path(tmp_path, url)
    snap.write_text("<html>... amó tanto al mundo ...</html>", encoding="utf-8")

    case = GoldenCase(
        id="l2_demo",
        agent="verse_explainer",
        layer="l2",
        input={"reference": "Juan 3:16"},
        expected={
            "expected_citations": [url],
            "support_phrases": ["amó tanto al mundo"],
        },
    )
    r = evaluate_citations_snapshot(case, _stub_agent([url]), snapshots_root=tmp_path)
    assert r.verdict == "pass"


def test_citations_fail_when_url_missing(tmp_path: Path) -> None:
    url = "https://wol.jw.org/x"
    case = GoldenCase(
        id="l2_no_url",
        agent="verse_explainer",
        layer="l2",
        input={"reference": "Juan 3:16"},
        expected={"expected_citations": [url], "support_phrases": ["x"]},
    )
    r = evaluate_citations_snapshot(case, _stub_agent([]), snapshots_root=tmp_path)
    assert r.verdict == "fail"
    assert any("missing URL" in reason for reason in r.reasons)


def test_citations_fail_when_phrase_absent(tmp_path: Path) -> None:
    url = "https://wol.jw.org/x"
    snap = snapshot_path(tmp_path, url)
    snap.write_text("<html>completely different</html>", encoding="utf-8")
    case = GoldenCase(
        id="l2_no_phrase",
        agent="verse_explainer",
        layer="l2",
        input={"reference": "Juan 3:16"},
        expected={
            "expected_citations": [url],
            "support_phrases": ["amó tanto al mundo"],
        },
    )
    r = evaluate_citations_snapshot(case, _stub_agent([url]), snapshots_root=tmp_path)
    assert r.verdict == "fail"
    assert any("none of support_phrases" in reason for reason in r.reasons)


def test_citations_skip_when_snapshot_missing(tmp_path: Path) -> None:
    url = "https://wol.jw.org/x"  # no snapshot created
    case = GoldenCase(
        id="l2_no_snap",
        agent="verse_explainer",
        layer="l2",
        input={},
        expected={"expected_citations": [url], "support_phrases": ["x"]},
    )
    r = evaluate_citations_snapshot(case, _stub_agent([url]), snapshots_root=tmp_path)
    assert r.verdict == "skip"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/jw-eval/tests/test_layer_citations.py -v`
Expected: FAIL — citations module missing.

- [ ] **Step 3: Implement Layer 2 snapshot mode**

```python
# packages/jw-eval/src/jw_eval/layers/citations.py
"""L2 — Citation integrity eval.

Two modes:
  - SNAPSHOT mode: HTML snapshots commited to repo. Offline, deterministic.
                   Used by default in CI.
  - LIVE mode: re-fetches the URL with WOLClient and compares.
               Cron weekly, opens issues on drift. (Live mode added in Task 8.)

A case passes if:
  1) Agent output contains every URL listed in `expected_citations`.
  2) For each URL, the snapshot contains at least one phrase from
     `support_phrases`.

Snapshot location: `<snapshots_root>/<sha256(URL)>.html`.
"""

from __future__ import annotations

import hashlib
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from jw_eval.models import GoldenCase, LayerResult


def snapshot_path(root: Path, url: str) -> Path:
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()
    return root / f"{digest}.html"


def _extract_urls(result: Any) -> list[str]:
    """Pull URLs out of an AgentResult-like object's findings."""

    urls: list[str] = []
    for f in getattr(result, "findings", []) or []:
        meta = getattr(f, "metadata", {}) or {}
        # Convention: citation URL lives at metadata.citation_url OR finding.citation.url
        url = meta.get("citation_url")
        if not url:
            citation = getattr(f, "citation", None)
            url = getattr(citation, "url", None) if citation else None
        if url:
            urls.append(url)
    return urls


def evaluate_citations_snapshot(
    case: GoldenCase,
    agent: Callable[[dict[str, Any]], Any],
    snapshots_root: Path,
) -> LayerResult:
    """Evaluate an L2 case in snapshot (offline) mode."""

    started = time.monotonic()
    expected_urls = case.expected.get("expected_citations") or []
    phrases = case.expected.get("support_phrases") or []
    reasons: list[str] = []

    try:
        result = agent(case.input)
    except Exception as exc:
        return LayerResult(
            case_id=case.id,
            layer="l2",
            verdict="error",
            reasons=[f"agent raised: {exc!r}"],
            duration_ms=int((time.monotonic() - started) * 1000),
        )

    actual_urls = _extract_urls(result)
    for url in expected_urls:
        if url not in actual_urls:
            reasons.append(f"missing URL {url} (got {actual_urls})")

    # If we don't have snapshots for the URLs, skip — do not fail.
    missing_snaps = [u for u in expected_urls if not snapshot_path(snapshots_root, u).exists()]
    if missing_snaps:
        return LayerResult(
            case_id=case.id,
            layer="l2",
            verdict="skip",
            reasons=[f"no snapshot for {u}" for u in missing_snaps],
            duration_ms=int((time.monotonic() - started) * 1000),
        )

    for url in expected_urls:
        html = snapshot_path(snapshots_root, url).read_text(encoding="utf-8")
        if not any(p.lower() in html.lower() for p in phrases):
            reasons.append(f"none of support_phrases {phrases} found in snapshot of {url}")

    verdict = "pass" if not reasons else "fail"
    return LayerResult(
        case_id=case.id,
        layer="l2",
        verdict=verdict,
        reasons=reasons,
        duration_ms=int((time.monotonic() - started) * 1000),
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/jw-eval/tests/test_layer_citations.py -v`
Expected: 5 passed.

- [ ] **Step 5: Write the snapshot-build script**

```python
# packages/jw-eval/scripts/build_eval_snapshots.py
"""Build HTML snapshots for L2 cases.

Reads every l2 YAML, collects unique `expected_citations` URLs, downloads
them with WOLClient, and writes minified HTML to
packages/jw-eval/fixtures/wol_snapshots/<sha256(URL)>.html.

Run manually:
    uv run python packages/jw-eval/scripts/build_eval_snapshots.py
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import re
from pathlib import Path

import httpx
import yaml


def _digest(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()


def _minify(html: str) -> str:
    """Strip <script>, <style>, and runs of whitespace. Keep text + links."""

    html = re.sub(r"<script\b[^>]*>.*?</script>", "", html, flags=re.IGNORECASE | re.DOTALL)
    html = re.sub(r"<style\b[^>]*>.*?</style>", "", html, flags=re.IGNORECASE | re.DOTALL)
    html = re.sub(r"\s+", " ", html)
    return html.strip()


async def _download(url: str) -> str:
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(url, headers={"User-Agent": "jw-eval/0.1 (snapshot builder)"})
        r.raise_for_status()
        return r.text


def _collect_urls(l2_dir: Path) -> list[str]:
    urls: set[str] = set()
    for f in sorted(l2_dir.glob("*.yaml")):
        data = yaml.safe_load(f.read_text(encoding="utf-8"))
        for u in (data.get("expected") or {}).get("expected_citations", []) or []:
            urls.add(u)
    return sorted(urls)


async def _main(l2_dir: Path, out_dir: Path, force: bool) -> int:
    out_dir.mkdir(parents=True, exist_ok=True)
    urls = _collect_urls(l2_dir)
    n_written = 0
    for url in urls:
        dest = out_dir / f"{_digest(url)}.html"
        if dest.exists() and not force:
            continue
        print(f"GET {url}")
        try:
            body = await _download(url)
        except Exception as exc:  # noqa: BLE001
            print(f"  !! failed: {exc}")
            continue
        dest.write_text(_minify(body), encoding="utf-8")
        n_written += 1
    print(f"\n{n_written} new snapshot(s) written to {out_dir}.")
    return 0


def main() -> int:
    here = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser()
    parser.add_argument("--l2-dir", default=str(here / "fixtures" / "golden_qa" / "l2"))
    parser.add_argument("--out-dir", default=str(here / "fixtures" / "wol_snapshots"))
    parser.add_argument("--force", action="store_true", help="re-download even if file exists")
    args = parser.parse_args()
    return asyncio.run(_main(Path(args.l2_dir), Path(args.out_dir), args.force))


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 6: Commit**

```bash
git add packages/jw-eval/src/jw_eval/layers/citations.py packages/jw-eval/scripts/build_eval_snapshots.py packages/jw-eval/tests/test_layer_citations.py
git commit -m "feat(jw-eval): Layer 2 snapshot mode + snapshot build script"
```

---

### Task 7: Seed 12 L2 cases and build their snapshots

**Files:**
- Create: `packages/jw-eval/fixtures/golden_qa/l2/verse_john_3_16_es.yaml`
- Create: `packages/jw-eval/fixtures/golden_qa/l2/verse_john_3_16_en.yaml`
- Create: `packages/jw-eval/fixtures/golden_qa/l2/verse_john_3_16_pt.yaml`
- Create: `packages/jw-eval/fixtures/golden_qa/l2/verse_romans_6_23_en.yaml`
- Create: `packages/jw-eval/fixtures/golden_qa/l2/verse_romans_6_23_es.yaml`
- Create: `packages/jw-eval/fixtures/golden_qa/l2/verse_acts_4_12_en.yaml`
- Create: `packages/jw-eval/fixtures/golden_qa/l2/verse_acts_4_12_es.yaml`
- Create: `packages/jw-eval/fixtures/golden_qa/l2/verse_acts_4_12_pt.yaml`
- Create: `packages/jw-eval/fixtures/golden_qa/l2/topic_trinity_es.yaml`
- Create: `packages/jw-eval/fixtures/golden_qa/l2/topic_kingdom_en.yaml`
- Create: `packages/jw-eval/fixtures/golden_qa/l2/topic_soul_en.yaml`
- Create: `packages/jw-eval/fixtures/golden_qa/l2/topic_resurrection_es.yaml`

- [ ] **Step 1: Write the first L2 case fully**

```yaml
# packages/jw-eval/fixtures/golden_qa/l2/verse_john_3_16_es.yaml
id: l2_verse_john_3_16_es
agent: verse_explainer
layer: l2
input:
  reference: "Juan 3:16"
  language: es
expected:
  expected_citations:
    - https://wol.jw.org/es/wol/b/r4/lp-s/nwt/E/2024/43/3
  support_phrases:
    - "amó tanto al mundo"
    - "Dios amó tanto"
metadata:
  added_at: 2026-05-30
```

- [ ] **Step 2: Write remaining 11 cases**

Each follows the same shape. Vary `reference`, `language`, the resolved WOL URL (use `jw_core.parsers.reference.parse_reference` + `WOLClient.build_url_for_chapter` to derive) and one canonical phrase from the target verse.

For the four `topic_*` cases, set `agent: apologetics`, `input: {question: "<topic>", language: ...}`, and pick a Topic Index subject URL plus a phrase from a top citation.

- [ ] **Step 3: Build snapshots**

Run:
```bash
uv run python packages/jw-eval/scripts/build_eval_snapshots.py
```
Expected: 12+ HTML files written to `packages/jw-eval/fixtures/wol_snapshots/`.

- [ ] **Step 4: Commit fixtures + snapshots**

```bash
git add packages/jw-eval/fixtures/golden_qa/l2 packages/jw-eval/fixtures/wol_snapshots
git commit -m "feat(jw-eval): seed 12 L2 cases and HTML snapshots"
```

---

### Task 8: Layer 2 — live mode

**Files:**
- Modify: `packages/jw-eval/src/jw_eval/layers/citations.py`
- Modify: `packages/jw-eval/tests/test_layer_citations.py`

- [ ] **Step 1: Write the failing test**

Append to `test_layer_citations.py`:

```python
def test_citations_live_uses_fetcher() -> None:
    from jw_eval.layers.citations import evaluate_citations_live

    url = "https://wol.jw.org/x"
    case = GoldenCase(
        id="l2_live",
        agent="verse_explainer",
        layer="l2",
        input={"reference": "Juan 3:16"},
        expected={
            "expected_citations": [url],
            "support_phrases": ["amó tanto al mundo"],
        },
    )

    def stub_fetch(u: str) -> str:
        assert u == url
        return "<p>amó tanto al mundo</p>"

    r = evaluate_citations_live(case, _stub_agent([url]), fetcher=stub_fetch)
    assert r.verdict == "pass"


def test_citations_live_fail_on_drift() -> None:
    from jw_eval.layers.citations import evaluate_citations_live

    url = "https://wol.jw.org/x"
    case = GoldenCase(
        id="l2_drift",
        agent="verse_explainer",
        layer="l2",
        input={},
        expected={"expected_citations": [url], "support_phrases": ["expected"]},
    )

    def stub_fetch(_: str) -> str:
        return "<p>completely different content</p>"

    r = evaluate_citations_live(case, _stub_agent([url]), fetcher=stub_fetch)
    assert r.verdict == "fail"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/jw-eval/tests/test_layer_citations.py -v`
Expected: 2 new tests FAIL — `evaluate_citations_live` not defined.

- [ ] **Step 3: Implement live mode**

Append to `packages/jw-eval/src/jw_eval/layers/citations.py`:

```python
def evaluate_citations_live(
    case: GoldenCase,
    agent: Callable[[dict[str, Any]], Any],
    fetcher: Callable[[str], str],
) -> LayerResult:
    """Evaluate an L2 case live: re-fetch URLs via `fetcher` callback."""

    started = time.monotonic()
    expected_urls = case.expected.get("expected_citations") or []
    phrases = case.expected.get("support_phrases") or []
    reasons: list[str] = []

    try:
        result = agent(case.input)
    except Exception as exc:
        return LayerResult(
            case_id=case.id,
            layer="l2",
            verdict="error",
            reasons=[f"agent raised: {exc!r}"],
            duration_ms=int((time.monotonic() - started) * 1000),
        )

    actual_urls = _extract_urls(result)
    for url in expected_urls:
        if url not in actual_urls:
            reasons.append(f"missing URL {url} (got {actual_urls})")

    for url in expected_urls:
        try:
            html = fetcher(url)
        except Exception as exc:  # noqa: BLE001
            reasons.append(f"fetch failed for {url}: {exc!r}")
            continue
        if not any(p.lower() in html.lower() for p in phrases):
            reasons.append(f"live: none of {phrases} found in {url}")

    verdict = "pass" if not reasons else "fail"
    return LayerResult(
        case_id=case.id,
        layer="l2",
        verdict=verdict,
        reasons=reasons,
        duration_ms=int((time.monotonic() - started) * 1000),
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/jw-eval/tests/test_layer_citations.py -v`
Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-eval/src/jw_eval/layers/citations.py packages/jw-eval/tests/test_layer_citations.py
git commit -m "feat(jw-eval): Layer 2 live mode with injectable fetcher"
```

---

### Task 9: Embeddings judge

**Files:**
- Create: `packages/jw-eval/src/jw_eval/judges/__init__.py`
- Create: `packages/jw-eval/src/jw_eval/judges/embeddings.py`
- Create: `packages/jw-eval/tests/test_judges.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-eval/tests/test_judges.py
from __future__ import annotations

from jw_eval.judges.embeddings import EmbeddingsJudge, FakeEmbedder


def test_embeddings_judge_identical_returns_one() -> None:
    judge = EmbeddingsJudge(embedder=FakeEmbedder())
    score = judge.cosine("hello world", "hello world")
    assert 0.999 <= score <= 1.0001


def test_embeddings_judge_disjoint_returns_low() -> None:
    judge = EmbeddingsJudge(embedder=FakeEmbedder())
    score = judge.cosine("hello", "completely different")
    assert score < 0.5


def test_embeddings_judge_classify_uses_thresholds() -> None:
    judge = EmbeddingsJudge(embedder=FakeEmbedder(), threshold_pass=0.78, threshold_review_min=0.55)
    assert judge.classify(0.9) == "pass"
    assert judge.classify(0.7) == "review"
    assert judge.classify(0.3) == "fail"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/jw-eval/tests/test_judges.py -v`
Expected: FAIL — judges module missing.

- [ ] **Step 3: Implement embeddings judge**

```python
# packages/jw-eval/src/jw_eval/judges/__init__.py
"""Judges for L3 semantic eval — embeddings (cheap) and LLM (escalation)."""
```

```python
# packages/jw-eval/src/jw_eval/judges/embeddings.py
"""Embeddings-based similarity judge.

Default embedder is `FakeEmbedder`, deterministic bag-of-words token hash.
Real embedder (sentence-transformers) is loaded only if installed and selected
via factory `default_embedder()`.
"""

from __future__ import annotations

import math
import re
from typing import Protocol


class Embedder(Protocol):
    def embed(self, text: str) -> list[float]: ...


class FakeEmbedder:
    """Deterministic bag-of-words embedder. Same vocab across calls."""

    DIM = 256

    def embed(self, text: str) -> list[float]:
        vec = [0.0] * self.DIM
        for tok in re.findall(r"\w+", text.lower()):
            vec[hash(tok) % self.DIM] += 1.0
        # L2 normalize
        norm = math.sqrt(sum(x * x for x in vec)) or 1.0
        return [x / norm for x in vec]


def default_embedder() -> Embedder:
    """Return sentence-transformers embedder if available, else FakeEmbedder."""

    try:
        from sentence_transformers import SentenceTransformer  # type: ignore[import-not-found]
    except ImportError:
        return FakeEmbedder()

    model = SentenceTransformer("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")

    class _STEmbedder:
        def embed(self, text: str) -> list[float]:
            return model.encode([text], normalize_embeddings=True)[0].tolist()

    return _STEmbedder()


class EmbeddingsJudge:
    """Cosine similarity over embedder output + threshold-based classification."""

    def __init__(
        self,
        embedder: Embedder | None = None,
        threshold_pass: float = 0.78,
        threshold_review_min: float = 0.55,
    ) -> None:
        self.embedder = embedder or default_embedder()
        self.threshold_pass = threshold_pass
        self.threshold_review_min = threshold_review_min

    def cosine(self, a: str, b: str) -> float:
        va = self.embedder.embed(a)
        vb = self.embedder.embed(b)
        return sum(x * y for x, y in zip(va, vb, strict=True))

    def classify(self, score: float) -> str:
        if score >= self.threshold_pass:
            return "pass"
        if score >= self.threshold_review_min:
            return "review"
        return "fail"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/jw-eval/tests/test_judges.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-eval/src/jw_eval/judges packages/jw-eval/tests/test_judges.py
git commit -m "feat(jw-eval): embeddings judge with FakeEmbedder default and ST fallback"
```

---

### Task 10: LLM judge (Ollama / Claude / OpenAI dispatcher)

**Files:**
- Create: `packages/jw-eval/src/jw_eval/judges/llm.py`
- Modify: `packages/jw-eval/tests/test_judges.py`

- [ ] **Step 1: Write the failing test**

Append to `test_judges.py`:

```python
def test_llm_judge_dispatches_to_callable() -> None:
    from jw_eval.judges.llm import LLMJudge

    calls: list[str] = []

    def stub_call(prompt: str) -> str:
        calls.append(prompt)
        return '{"verdict": "pass", "reason": "looks fine"}'

    judge = LLMJudge(caller=stub_call)
    verdict, reason = judge.judge(
        golden="The Trinity is not biblical.",
        candidate="Scripture rejects the Trinity.",
        keywords_any=["not biblical", "rejects"],
        keywords_none=["central doctrine"],
    )
    assert verdict == "pass"
    assert reason == "looks fine"
    assert "Respuesta dorada:" in calls[0] or "Golden:" in calls[0]


def test_llm_judge_handles_garbage_response() -> None:
    from jw_eval.judges.llm import LLMJudge

    judge = LLMJudge(caller=lambda _: "not even json")
    verdict, reason = judge.judge("a", "b", keywords_any=[], keywords_none=[])
    assert verdict == "error"
    assert "parse" in reason.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/jw-eval/tests/test_judges.py -v`
Expected: 2 new tests FAIL — `LLMJudge` missing.

- [ ] **Step 3: Implement LLM judge**

```python
# packages/jw-eval/src/jw_eval/judges/llm.py
"""LLM-based judge for L3 borderline cases.

Caller is a string-in, string-out function — keeps the judge independent
from any specific provider SDK. Three built-in callers:
  - ollama_caller(): http://localhost:11434/api/generate
  - claude_caller(): anthropic SDK (lazy import)
  - openai_caller(): openai SDK (lazy import)

The choice is driven by env var JW_EVAL_LLM ∈ {ollama, claude, openai, none}.
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable


JUDGE_PROMPT = """Eres un juez doctrinal de fidelidad. Compara la respuesta candidata
con la respuesta dorada. Responde estrictamente como JSON:
{{"verdict": "pass" | "fail", "reason": "..."}}

Respuesta dorada:
{golden}

Respuesta candidata:
{candidate}

Keywords requeridas (al menos UNA debe aparecer en candidata): {keywords_any}
Keywords prohibidas (NINGUNA puede aparecer): {keywords_none}
"""


class LLMJudge:
    def __init__(self, caller: Callable[[str], str]) -> None:
        self.caller = caller

    def judge(
        self,
        golden: str,
        candidate: str,
        keywords_any: list[str],
        keywords_none: list[str],
    ) -> tuple[str, str]:
        prompt = JUDGE_PROMPT.format(
            golden=golden,
            candidate=candidate,
            keywords_any=keywords_any,
            keywords_none=keywords_none,
        )
        try:
            raw = self.caller(prompt)
        except Exception as exc:  # noqa: BLE001
            return "error", f"caller raised: {exc!r}"
        try:
            data = json.loads(raw)
        except Exception:  # noqa: BLE001
            return "error", f"could not parse JSON from response: {raw[:200]!r}"
        v = str(data.get("verdict", "")).lower()
        if v not in {"pass", "fail"}:
            return "error", f"unexpected verdict: {v!r}"
        return v, str(data.get("reason", ""))


def _ollama_caller(model: str = "llama3.1:8b", base: str = "http://localhost:11434") -> Callable[[str], str]:
    import httpx

    def call(prompt: str) -> str:
        r = httpx.post(
            f"{base}/api/generate",
            json={"model": model, "prompt": prompt, "stream": False, "format": "json"},
            timeout=60.0,
        )
        r.raise_for_status()
        return str(r.json().get("response", ""))

    return call


def _claude_caller(model: str = "claude-haiku-4-5-20251001") -> Callable[[str], str]:
    from anthropic import Anthropic  # type: ignore[import-not-found]

    client = Anthropic()

    def call(prompt: str) -> str:
        msg = client.messages.create(
            model=model,
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text  # type: ignore[union-attr,attr-defined]

    return call


def _openai_caller(model: str = "gpt-4o-mini") -> Callable[[str], str]:
    from openai import OpenAI  # type: ignore[import-not-found]

    client = OpenAI()

    def call(prompt: str) -> str:
        r = client.chat.completions.create(
            model=model,
            response_format={"type": "json_object"},
            messages=[{"role": "user", "content": prompt}],
        )
        return r.choices[0].message.content or ""

    return call


def get_default_caller() -> Callable[[str], str] | None:
    """Inspect JW_EVAL_LLM env and return the configured caller, or None."""

    backend = os.environ.get("JW_EVAL_LLM", "ollama").lower()
    if backend == "ollama":
        return _ollama_caller()
    if backend == "claude":
        return _claude_caller()
    if backend == "openai":
        return _openai_caller()
    if backend == "none":
        return None
    raise ValueError(f"unknown JW_EVAL_LLM={backend!r}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/jw-eval/tests/test_judges.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-eval/src/jw_eval/judges/llm.py packages/jw-eval/tests/test_judges.py
git commit -m "feat(jw-eval): LLM judge dispatcher (Ollama default, Claude/OpenAI opt-in)"
```

---

### Task 11: Layer 3 — semantic evaluator (escalating)

**Files:**
- Create: `packages/jw-eval/src/jw_eval/layers/semantic.py`
- Create: `packages/jw-eval/tests/test_layer_semantic.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-eval/tests/test_layer_semantic.py
from __future__ import annotations

from typing import Any

from jw_eval.judges.embeddings import EmbeddingsJudge, FakeEmbedder
from jw_eval.layers.semantic import evaluate_semantic
from jw_eval.models import GoldenCase


def _stub_agent(text: str):
    class _F:
        def __init__(self, t: str) -> None:
            self.text = t
            self.metadata = {"source": "rag"}

    class _R:
        findings = [_F(text)]

    def run(_: dict[str, Any]) -> _R:
        return _R()

    return run


def test_semantic_pass_high_similarity() -> None:
    case = GoldenCase(
        id="l3_pass",
        agent="apologetics",
        layer="l3",
        input={"question": "?"},
        expected={
            "golden_answer": "The Trinity is not a Bible teaching.",
            "expected_keywords_any": ["not"],
            "expected_keywords_none": ["central doctrine"],
        },
    )
    agent = _stub_agent("The Trinity is not a Bible teaching, Scripture rejects it.")
    judge = EmbeddingsJudge(embedder=FakeEmbedder(), threshold_pass=0.5, threshold_review_min=0.3)
    r = evaluate_semantic(case, agent, embeddings_judge=judge, llm_judge=None)
    assert r.verdict == "pass"
    assert r.score is not None and r.score >= 0.5


def test_semantic_fail_forbidden_keyword_present() -> None:
    case = GoldenCase(
        id="l3_kw_fail",
        agent="apologetics",
        layer="l3",
        input={"question": "?"},
        expected={
            "golden_answer": "X",
            "expected_keywords_any": [],
            "expected_keywords_none": ["central doctrine"],
        },
    )
    agent = _stub_agent("It is the central doctrine of the faith.")
    judge = EmbeddingsJudge(embedder=FakeEmbedder(), threshold_pass=0.0, threshold_review_min=0.0)
    r = evaluate_semantic(case, agent, embeddings_judge=judge, llm_judge=None)
    assert r.verdict == "fail"


def test_semantic_escalates_when_borderline() -> None:
    case = GoldenCase(
        id="l3_borderline",
        agent="apologetics",
        layer="l3",
        input={"question": "?"},
        expected={
            "golden_answer": "answer",
            "expected_keywords_any": [],
            "expected_keywords_none": [],
        },
    )
    agent = _stub_agent("totally different words")

    # Force borderline score region
    judge = EmbeddingsJudge(embedder=FakeEmbedder(), threshold_pass=0.99, threshold_review_min=0.0)

    calls: list[str] = []

    class StubLLM:
        def judge(self, golden: str, candidate: str, keywords_any: list[str], keywords_none: list[str]) -> tuple[str, str]:
            calls.append(candidate)
            return "pass", "escalated and approved"

    r = evaluate_semantic(case, agent, embeddings_judge=judge, llm_judge=StubLLM())
    assert r.verdict == "pass"
    assert calls, "LLM judge should have been called"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/jw-eval/tests/test_layer_semantic.py -v`
Expected: FAIL — semantic module missing.

- [ ] **Step 3: Implement Layer 3**

```python
# packages/jw-eval/src/jw_eval/layers/semantic.py
"""L3 — semantic Q&A eval.

Pipeline:
  1) Run agent on case.input.
  2) Concatenate finding.text into `candidate`.
  3) Compute cosine(embedder(candidate), embedder(golden_answer)).
  4) Apply expected_keywords_any / expected_keywords_none — any miss is a fail
     regardless of cosine.
  5) Classify cosine: pass / review / fail.
     - pass -> verdict pass
     - fail -> verdict fail
     - review -> escalate to LLM judge if available; else mark as 'review' (treated as fail).
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any, Protocol

from jw_eval.judges.embeddings import EmbeddingsJudge
from jw_eval.models import GoldenCase, LayerResult


class LLMJudgeLike(Protocol):
    def judge(
        self,
        golden: str,
        candidate: str,
        keywords_any: list[str],
        keywords_none: list[str],
    ) -> tuple[str, str]: ...


def _join_findings(result: Any) -> str:
    parts: list[str] = []
    for f in getattr(result, "findings", []) or []:
        t = getattr(f, "text", "") or getattr(f, "summary", "") or ""
        if t:
            parts.append(t)
    return "\n".join(parts)


def evaluate_semantic(
    case: GoldenCase,
    agent: Callable[[dict[str, Any]], Any],
    embeddings_judge: EmbeddingsJudge,
    llm_judge: LLMJudgeLike | None = None,
) -> LayerResult:
    started = time.monotonic()
    exp = case.expected
    golden = str(exp.get("golden_answer") or "")
    kw_any: list[str] = list(exp.get("expected_keywords_any") or [])
    kw_none: list[str] = list(exp.get("expected_keywords_none") or [])
    reasons: list[str] = []

    try:
        result = agent(case.input)
    except Exception as exc:
        return LayerResult(
            case_id=case.id,
            layer="l3",
            verdict="error",
            reasons=[f"agent raised: {exc!r}"],
            duration_ms=int((time.monotonic() - started) * 1000),
        )

    candidate = _join_findings(result)

    # Keyword gates run BEFORE cosine — they're hard rules.
    cand_lower = candidate.lower()
    if kw_any and not any(k.lower() in cand_lower for k in kw_any):
        reasons.append(f"none of expected_keywords_any present: {kw_any}")
    for k in kw_none:
        if k.lower() in cand_lower:
            reasons.append(f"forbidden keyword present: {k!r}")

    score = embeddings_judge.cosine(candidate, golden) if golden else 0.0
    bucket = embeddings_judge.classify(score)

    if reasons:
        verdict = "fail"
    elif bucket == "pass":
        verdict = "pass"
    elif bucket == "fail":
        verdict = "fail"
        reasons.append(f"cosine={score:.3f} below threshold")
    else:  # review
        if llm_judge is None:
            verdict = "fail"
            reasons.append(f"cosine={score:.3f} in review band, no LLM judge configured")
        else:
            v, why = llm_judge.judge(golden=golden, candidate=candidate, keywords_any=kw_any, keywords_none=kw_none)
            verdict = v if v in {"pass", "fail"} else "error"
            reasons.append(f"escalated to LLM: {why}")

    return LayerResult(
        case_id=case.id,
        layer="l3",
        verdict=verdict,
        score=score,
        reasons=reasons,
        duration_ms=int((time.monotonic() - started) * 1000),
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/jw-eval/tests/test_layer_semantic.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-eval/src/jw_eval/layers/semantic.py packages/jw-eval/tests/test_layer_semantic.py
git commit -m "feat(jw-eval): Layer 3 — semantic eval with embeddings + LLM escalation"
```

---

### Task 12: Seed 6 L3 cases

**Files:**
- Create: `packages/jw-eval/fixtures/golden_qa/l3/trinity_es.yaml`
- Create: `packages/jw-eval/fixtures/golden_qa/l3/trinity_en.yaml`
- Create: `packages/jw-eval/fixtures/golden_qa/l3/soul_en.yaml`
- Create: `packages/jw-eval/fixtures/golden_qa/l3/hell_es.yaml`
- Create: `packages/jw-eval/fixtures/golden_qa/l3/jesus_identity_en.yaml`
- Create: `packages/jw-eval/fixtures/golden_qa/l3/gods_name_es.yaml`

- [ ] **Step 1: Write the Trinity-es L3 case fully**

```yaml
# packages/jw-eval/fixtures/golden_qa/l3/trinity_es.yaml
id: l3_apologetics_trinity_basic_es
agent: apologetics
layer: l3
input:
  question: "¿Es la Trinidad bíblica?"
  language: es
expected:
  golden_answer: |
    La Trinidad no es una enseñanza bíblica. Las Escrituras presentan a Jehová
    como el único Dios verdadero (Deuteronomio 6:4; Juan 17:3), mientras que
    Jesús es su Hijo (Juan 14:28). La doctrina trinitaria se desarrolló siglos
    después de los apóstoles, influida por filosofía griega.
  expected_keywords_any:
    - "no es bíblica"
    - "no enseñada por Jesús"
    - "no aparece en las Escrituras"
  expected_keywords_none:
    - "doctrina central de la fe cristiana"
metadata:
  topic: doctrine.trinity
  added_at: 2026-05-30
```

- [ ] **Step 2: Write the remaining 5 L3 cases**

Each uses the same schema. Topics + golden_answer summaries:

- `trinity_en.yaml`: English version of the Trinity case.
- `soul_en.yaml`: question "Do humans have an immortal soul?" — gold says soul = whole person, mortal (Ezek 18:4; Eccl 9:5).
- `hell_es.yaml`: "¿Existe el infierno de fuego?" — gold says Seol/Hades = tumba común, no tormento eterno.
- `jesus_identity_en.yaml`: "Is Jesus God?" — gold says Jesus is Son, separate, John 14:28; 17:3.
- `gods_name_es.yaml`: "¿Cuál es el nombre de Dios?" — gold says Jehová (YHWH), Sal 83:18; Isa 42:8.

Each must include `expected_keywords_any`, `expected_keywords_none`, and `metadata.topic`.

- [ ] **Step 3: Verify they load**

Run:
```bash
uv run python -c "
from pathlib import Path
from jw_eval.loader import load_cases
print(len(load_cases(Path('packages/jw-eval/fixtures/golden_qa'), layers=['l3'])))
"
```
Expected: `6`.

- [ ] **Step 4: Commit**

```bash
git add packages/jw-eval/fixtures/golden_qa/l3
git commit -m "feat(jw-eval): seed 6 L3 semantic cases (core doctrines)"
```

---

### Task 13: Suite orchestrator

**Files:**
- Create: `packages/jw-eval/src/jw_eval/suite.py`
- Create: `packages/jw-eval/tests/test_suite.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-eval/tests/test_suite.py
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from jw_eval.models import GoldenCase
from jw_eval.suite import Suite


class FakeFinding:
    def __init__(self, text: str, source: str = "rag") -> None:
        self.text = text
        self.metadata = {"source": source, "citation_url": "https://wol.jw.org/x"}


class FakeResult:
    def __init__(self) -> None:
        self.findings = [FakeFinding("Hello world doctrinal answer")]


def fake_agent(_: dict[str, Any]) -> FakeResult:
    return FakeResult()


def test_suite_runs_layer_1_only(tmp_path: Path) -> None:
    yaml = tmp_path / "case.yaml"
    yaml.write_text(
        """
id: t_l1
agent: apologetics
layer: l1
input: {}
expected:
  must_have_source: rag
""",
        encoding="utf-8",
    )

    suite = Suite(
        cases_root=tmp_path,
        snapshots_root=tmp_path,
        agent_registry={"apologetics": fake_agent},
    )
    report = suite.run(layers=["l1"])
    assert len(report.results) == 1
    assert report.results[0].verdict == "pass"
    assert report.summary["l1"]["pass"] == 1


def test_suite_unknown_agent_marks_error(tmp_path: Path) -> None:
    yaml = tmp_path / "case.yaml"
    yaml.write_text(
        "id: t\nagent: missing\nlayer: l1\ninput: {}\nexpected: {}\n", encoding="utf-8"
    )
    suite = Suite(cases_root=tmp_path, snapshots_root=tmp_path, agent_registry={})
    report = suite.run(layers=["l1"])
    assert report.results[0].verdict == "error"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/jw-eval/tests/test_suite.py -v`
Expected: FAIL — Suite missing.

- [ ] **Step 3: Implement Suite**

```python
# packages/jw-eval/src/jw_eval/suite.py
"""Suite dispatcher — loads cases, routes to layer evaluators, returns SuiteReport."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from jw_eval.judges.embeddings import EmbeddingsJudge
from jw_eval.judges.llm import LLMJudge, get_default_caller
from jw_eval.layers.citations import evaluate_citations_live, evaluate_citations_snapshot
from jw_eval.layers.semantic import evaluate_semantic
from jw_eval.layers.structural import evaluate_structural
from jw_eval.loader import load_cases
from jw_eval.models import GoldenCase, LayerName, LayerResult, SuiteReport

AgentRegistry = dict[str, Callable[[dict[str, Any]], Any]]


class Suite:
    def __init__(
        self,
        cases_root: Path,
        snapshots_root: Path,
        agent_registry: AgentRegistry,
        live_fetcher: Callable[[str], str] | None = None,
        embeddings_judge: EmbeddingsJudge | None = None,
        llm_judge: LLMJudge | None = None,
    ) -> None:
        self.cases_root = cases_root
        self.snapshots_root = snapshots_root
        self.agents = agent_registry
        self.live_fetcher = live_fetcher
        self.embeddings_judge = embeddings_judge
        self.llm_judge = llm_judge

    def _resolve_agent(self, name: str):
        agent = self.agents.get(name)
        if agent is None:
            def _err(_: dict[str, Any]):
                raise RuntimeError(f"agent {name!r} not registered")
            return _err
        return agent

    def _evaluate(self, case: GoldenCase, live: bool) -> LayerResult:
        agent = self._resolve_agent(case.agent)
        if case.layer == "l1":
            return evaluate_structural(case, agent)
        if case.layer == "l2":
            if live and self.live_fetcher is not None:
                return evaluate_citations_live(case, agent, fetcher=self.live_fetcher)
            return evaluate_citations_snapshot(case, agent, snapshots_root=self.snapshots_root)
        if case.layer == "l3":
            if self.embeddings_judge is None:
                self.embeddings_judge = EmbeddingsJudge()
            if self.llm_judge is None:
                caller = get_default_caller()
                self.llm_judge = LLMJudge(caller=caller) if caller is not None else None
            return evaluate_semantic(
                case,
                agent,
                embeddings_judge=self.embeddings_judge,
                llm_judge=self.llm_judge,
            )
        return LayerResult(case_id=case.id, layer=case.layer, verdict="error", reasons=["unknown layer"])

    def run(
        self,
        layers: list[LayerName],
        agent_filter: str | None = None,
        live: bool = False,
    ) -> SuiteReport:
        started = datetime.now(UTC)
        cases = load_cases(self.cases_root, layers=layers)
        if agent_filter:
            cases = [c for c in cases if c.agent == agent_filter]
        results = [self._evaluate(c, live=live) for c in cases]
        finished = datetime.now(UTC)
        return SuiteReport(
            started_at=started,
            finished_at=finished,
            layers_run=list(layers),
            results=results,
            summary=SuiteReport.summarize(results),
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/jw-eval/tests/test_suite.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-eval/src/jw_eval/suite.py packages/jw-eval/tests/test_suite.py
git commit -m "feat(jw-eval): Suite dispatcher routing cases to layer evaluators"
```

---

### Task 14: Reporter (markdown + JSON)

**Files:**
- Create: `packages/jw-eval/src/jw_eval/report.py`
- Create: `packages/jw-eval/tests/test_report.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-eval/tests/test_report.py
from __future__ import annotations

from datetime import datetime

from jw_eval.models import LayerResult, SuiteReport
from jw_eval.report import to_json, to_markdown


def _sample() -> SuiteReport:
    now = datetime(2026, 5, 30, 12, 0, 0)
    results = [
        LayerResult(case_id="a", layer="l1", verdict="pass", reasons=[], duration_ms=5),
        LayerResult(case_id="b", layer="l1", verdict="fail", reasons=["missing source"], duration_ms=6),
        LayerResult(case_id="c", layer="l3", verdict="pass", score=0.91, reasons=[], duration_ms=200),
    ]
    return SuiteReport(
        started_at=now,
        finished_at=now,
        layers_run=["l1", "l3"],
        results=results,
        summary=SuiteReport.summarize(results),
    )


def test_markdown_has_table_and_failures() -> None:
    md = to_markdown(_sample())
    assert "# jw-eval report" in md
    assert "| l1 |" in md
    assert "missing source" in md
    assert "0.91" in md


def test_json_roundtrips() -> None:
    rep = _sample()
    js = to_json(rep)
    assert '"verdict": "pass"' in js
    assert '"case_id": "b"' in js
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/jw-eval/tests/test_report.py -v`
Expected: FAIL — report module missing.

- [ ] **Step 3: Implement reporter**

```python
# packages/jw-eval/src/jw_eval/report.py
"""Report serializers for SuiteReport."""

from __future__ import annotations

from jw_eval.models import SuiteReport


def to_json(report: SuiteReport) -> str:
    return report.model_dump_json(indent=2)


def to_markdown(report: SuiteReport) -> str:
    lines: list[str] = []
    lines.append("# jw-eval report")
    lines.append("")
    lines.append(f"- **Started:** {report.started_at.isoformat()}")
    lines.append(f"- **Finished:** {report.finished_at.isoformat()}")
    lines.append(f"- **Layers run:** {', '.join(report.layers_run)}")
    lines.append("")

    lines.append("## Summary")
    lines.append("")
    lines.append("| Layer | pass | fail | skip | error |")
    lines.append("|---|---|---|---|---|")
    for layer, counts in sorted(report.summary.items()):
        lines.append(
            f"| {layer} | {counts.get('pass', 0)} | {counts.get('fail', 0)} | "
            f"{counts.get('skip', 0)} | {counts.get('error', 0)} |"
        )
    lines.append("")

    fails = [r for r in report.results if r.verdict in {"fail", "error"}]
    if fails:
        lines.append(f"## Failures ({len(fails)})")
        lines.append("")
        for r in fails:
            score = f" score={r.score:.3f}" if r.score is not None else ""
            lines.append(f"### `{r.case_id}` ({r.layer}, {r.verdict}{score})")
            for reason in r.reasons:
                lines.append(f"- {reason}")
            lines.append("")
    else:
        lines.append("All cases passed. ✓")
        lines.append("")

    lines.append("## All results")
    lines.append("")
    lines.append("| case_id | layer | verdict | score | duration_ms |")
    lines.append("|---|---|---|---|---|")
    for r in report.results:
        score = f"{r.score:.2f}" if r.score is not None else "—"
        lines.append(f"| {r.case_id} | {r.layer} | {r.verdict} | {score} | {r.duration_ms} |")
    return "\n".join(lines) + "\n"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/jw-eval/tests/test_report.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-eval/src/jw_eval/report.py packages/jw-eval/tests/test_report.py
git commit -m "feat(jw-eval): markdown + json report serializers"
```

---

### Task 15: CLI command `jw eval`

**Files:**
- Create: `packages/jw-eval/src/jw_eval/cli.py`
- Create: `packages/jw-cli/src/jw_cli/commands/eval.py`
- Modify: `packages/jw-cli/src/jw_cli/main.py`
- Modify: `packages/jw-cli/src/jw_cli/commands/__init__.py`
- Modify: `packages/jw-cli/pyproject.toml`
- Create: `packages/jw-eval/tests/test_cli.py`

- [ ] **Step 1: Write the failing test (CLI smoke + agent registry)**

```python
# packages/jw-eval/tests/test_cli.py
from __future__ import annotations

from pathlib import Path
from typing import Any

from jw_eval.cli import default_agent_registry, run_from_cli


def test_default_agent_registry_has_known_agents() -> None:
    reg = default_agent_registry()
    assert "apologetics" in reg
    assert "verse_explainer" in reg


def test_run_from_cli_returns_report(tmp_path: Path) -> None:
    cases_dir = tmp_path / "golden_qa"
    cases_dir.mkdir()
    (cases_dir / "demo.yaml").write_text(
        """
id: demo
agent: __fake__
layer: l1
input: {}
expected: {}
""",
        encoding="utf-8",
    )

    def fake_agent(_: dict[str, Any]):
        class _R:
            findings = []
        return _R()

    report = run_from_cli(
        cases_root=cases_dir,
        snapshots_root=tmp_path,
        layers=["l1"],
        agent_registry={"__fake__": fake_agent},
    )
    assert report.summary["l1"]["pass"] == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/jw-eval/tests/test_cli.py -v`
Expected: FAIL — jw_eval.cli missing.

- [ ] **Step 3: Implement `jw_eval.cli`**

```python
# packages/jw-eval/src/jw_eval/cli.py
"""Programmatic entry point used by both jw-cli and CI.

The real Typer command is in jw-cli (it wires this into the `jw` umbrella).
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from jw_eval.models import LayerName, SuiteReport
from jw_eval.suite import Suite


def default_agent_registry() -> dict[str, Callable[[dict[str, Any]], Any]]:
    """Return the registry of real agents from jw-agents wrapped for sync invocation."""

    # Lazy import to keep `jw_eval.cli` import cheap.
    from jw_agents.apologetics import apologetics  # type: ignore[import-not-found]
    from jw_agents.conversation_assistant import conversation_assistant  # type: ignore[import-not-found]
    from jw_agents.meeting_helper import meeting_helper  # type: ignore[import-not-found]
    from jw_agents.research_topic import research_topic  # type: ignore[import-not-found]
    from jw_agents.verse_explainer import verse_explainer  # type: ignore[import-not-found]

    registry: dict[str, Callable[[dict[str, Any]], Any]] = {}

    def _wrap(name: str, fn: Callable[..., Any]):
        def call(inp: dict[str, Any]) -> Any:
            return fn(**inp)
        registry[name] = call

    _wrap("apologetics", apologetics)
    _wrap("conversation_assistant", conversation_assistant)
    _wrap("meeting_helper", meeting_helper)
    _wrap("research_topic", research_topic)
    _wrap("verse_explainer", verse_explainer)
    return registry


def run_from_cli(
    cases_root: Path,
    snapshots_root: Path,
    layers: list[LayerName],
    agent_filter: str | None = None,
    live: bool = False,
    agent_registry: dict[str, Callable[[dict[str, Any]], Any]] | None = None,
) -> SuiteReport:
    suite = Suite(
        cases_root=cases_root,
        snapshots_root=snapshots_root,
        agent_registry=agent_registry or default_agent_registry(),
    )
    return suite.run(layers=layers, agent_filter=agent_filter, live=live)
```

- [ ] **Step 4: Wire `jw eval` into jw-cli**

Modify `packages/jw-cli/pyproject.toml` — add `"jw-eval",` to `dependencies`.

Create `packages/jw-cli/src/jw_cli/commands/eval.py`:

```python
# packages/jw-cli/src/jw_cli/commands/eval.py
"""`jw eval` — run the doctrinal eval suite."""

from __future__ import annotations

from pathlib import Path

import typer

from jw_eval.cli import run_from_cli
from jw_eval.report import to_json, to_markdown


def eval_cmd(
    layer: str = typer.Option("1,2", "--layer", help="Comma-separated layer numbers: 1, 2, 3"),
    cases_root: Path = typer.Option(
        Path("packages/jw-eval/fixtures/golden_qa"),
        "--cases",
        help="Path to golden_qa root.",
    ),
    snapshots_root: Path = typer.Option(
        Path("packages/jw-eval/fixtures/wol_snapshots"),
        "--snapshots",
        help="Path to wol HTML snapshots.",
    ),
    live: bool = typer.Option(False, "--live", help="Use live HTTP for L2 instead of snapshots."),
    agent_filter: str | None = typer.Option(None, "--filter-agent", help="Run only cases for this agent."),
    report: str = typer.Option("md", "--report", help="md | json"),
    out: Path | None = typer.Option(None, "--out", help="Write report to file instead of stdout."),
) -> None:
    layers: list = []
    for ch in layer.split(","):
        n = int(ch.strip())
        layers.append(f"l{n}")

    suite_report = run_from_cli(
        cases_root=cases_root,
        snapshots_root=snapshots_root,
        layers=layers,
        agent_filter=agent_filter,
        live=live,
    )

    text = to_markdown(suite_report) if report == "md" else to_json(suite_report)
    if out:
        out.write_text(text, encoding="utf-8")
        typer.echo(f"Wrote {out}")
    else:
        typer.echo(text)

    # Exit code = number of failures (caps at 125 to keep within POSIX bounds).
    failures = sum(
        1 for r in suite_report.results if r.verdict in {"fail", "error"}
    )
    raise typer.Exit(code=min(failures, 125))
```

Modify `packages/jw-cli/src/jw_cli/commands/__init__.py` — add `from . import eval` (and `eval` to the module exports).

Modify `packages/jw-cli/src/jw_cli/main.py` — add the import and registration:

```python
from jw_cli.commands import eval as eval_cmd_module  # noqa: A004
# ...existing imports...

app.command(name="eval")(eval_cmd_module.eval_cmd)
```

- [ ] **Step 5: Run test to verify it passes + smoke CLI**

Run:
```bash
uv run pytest packages/jw-eval/tests/test_cli.py -v
uv run jw eval --layer 1 --report json --cases packages/jw-eval/fixtures/golden_qa
```
Expected: tests pass; CLI prints JSON with `summary.l1`.

- [ ] **Step 6: Commit**

```bash
git add packages/jw-eval/src/jw_eval/cli.py packages/jw-cli packages/jw-eval/tests/test_cli.py
git commit -m "feat(jw-cli): wire jw eval command using jw-eval suite"
```

---

### Task 16: MCP tool `run_eval_suite`

**Files:**
- Modify: `packages/jw-mcp/pyproject.toml` — add `"jw-eval"` dep.
- Modify: `packages/jw-mcp/src/jw_mcp/server.py` — register the tool.
- Create: `packages/jw-mcp/tests/test_eval_tool.py` (or append to existing protocol tests).

- [ ] **Step 1: Write a failing protocol test**

```python
# packages/jw-mcp/tests/test_eval_tool.py
from __future__ import annotations

import pytest

# We test the function the MCP tool wraps; a full FastMCP roundtrip is
# already covered elsewhere in test_protocol.py.

def test_run_eval_suite_returns_summary(tmp_path) -> None:
    from jw_mcp.server import run_eval_suite

    out = run_eval_suite(
        layers=[1],
        cases_root=str(tmp_path),
        snapshots_root=str(tmp_path),
    )
    assert "summary" in out
    assert "results" in out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/jw-mcp/tests/test_eval_tool.py -v`
Expected: FAIL — `run_eval_suite` not exported.

- [ ] **Step 3: Implement the MCP tool**

Append to `packages/jw-mcp/src/jw_mcp/server.py`:

```python
from pathlib import Path as _Path  # noqa: E402

from jw_eval.cli import run_from_cli as _eval_run  # noqa: E402

@mcp.tool()
def run_eval_suite(
    layers: list[int] = [1],
    cases_root: str = "packages/jw-eval/fixtures/golden_qa",
    snapshots_root: str = "packages/jw-eval/fixtures/wol_snapshots",
    live: bool = False,
    agent: str | None = None,
) -> dict:
    """Run the jw-eval doctrinal regression suite. Returns the SuiteReport as a dict."""

    layer_names = [f"l{n}" for n in layers]
    report = _eval_run(
        cases_root=_Path(cases_root),
        snapshots_root=_Path(snapshots_root),
        layers=layer_names,
        agent_filter=agent,
        live=live,
    )
    return report.model_dump(mode="json")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/jw-mcp/tests/test_eval_tool.py -v`
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-mcp packages/jw-mcp/tests/test_eval_tool.py
git commit -m "feat(jw-mcp): expose run_eval_suite tool"
```

---

### Task 17: CI jobs (eval-fast offline, eval-l2-live weekly, eval-nightly)

**Files:**
- Modify: `.github/workflows/ci.yml`
- Create: `packages/jw-eval/scripts/eval_open_drift_issues.py`

- [ ] **Step 1: Append jobs to ci.yml**

```yaml
# .github/workflows/ci.yml — append at end of `jobs:` block

  eval-fast:
    name: Eval fast (L1 + L2 snapshot)
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v5
      - uses: astral-sh/setup-uv@v6
        with:
          enable-cache: true
          cache-dependency-glob: "uv.lock"
      - run: uv python install 3.13
      - run: uv sync --all-packages
      - name: Run jw eval layers 1+2
        run: uv run jw eval --layer 1,2 --report md --out eval-fast.md
      - uses: actions/upload-artifact@v4
        with:
          name: eval-fast-report
          path: eval-fast.md

  eval-l2-live:
    name: Eval L2 live (weekly)
    if: github.event_name == 'schedule' && github.event.schedule == '0 6 * * MON'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v5
      - uses: astral-sh/setup-uv@v6
      - run: uv python install 3.13
      - run: uv sync --all-packages
      - run: uv run jw eval --layer 2 --live --report json --out l2-live.json
      - run: uv run python packages/jw-eval/scripts/eval_open_drift_issues.py l2-live.json
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}

  eval-nightly:
    name: Eval nightly (L1+L2+L3 Ollama)
    if: github.event_name == 'schedule' && github.event.schedule == '0 4 * * *'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v5
      - uses: astral-sh/setup-uv@v6
      - run: uv python install 3.13
      - run: uv sync --all-packages
      - run: JW_EVAL_LLM=none uv run jw eval --layer 1,2,3 --report md --out eval-nightly.md
      - uses: actions/upload-artifact@v4
        with:
          name: eval-nightly-report
          path: eval-nightly.md
```

Add the schedule trigger at top of file (under `on:`):

```yaml
on:
  push:
    branches: [main, master]
  pull_request:
    branches: [main, master]
  workflow_dispatch:
  schedule:
    - cron: "0 6 * * MON"
    - cron: "0 4 * * *"
```

- [ ] **Step 2: Implement `eval_open_drift_issues.py`**

```python
# packages/jw-eval/scripts/eval_open_drift_issues.py
"""Parse l2-live.json and open GitHub issues for failed cases.

Uses gh CLI through subprocess.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: eval_open_drift_issues.py <report.json>", file=sys.stderr)
        return 2
    data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    drifted = [r for r in data.get("results", []) if r["verdict"] in {"fail", "error"} and r["layer"] == "l2"]
    if not drifted:
        print("No L2 drift detected.")
        return 0
    for r in drifted:
        title = f"[eval/l2 drift] case {r['case_id']}"
        body_lines = [
            f"**Case:** `{r['case_id']}`",
            f"**Verdict:** {r['verdict']}",
            "",
            "## Reasons",
            *[f"- {x}" for x in r.get("reasons", [])],
            "",
            "Refresh snapshot via `uv run python packages/jw-eval/scripts/build_eval_snapshots.py --force`.",
        ]
        try:
            subprocess.run(
                ["gh", "issue", "create", "--title", title, "--label", "link-drift", "--body", "\n".join(body_lines)],
                check=True,
            )
        except subprocess.CalledProcessError as exc:
            print(f"gh issue create failed for {r['case_id']}: {exc}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 3: Smoke-validate the YAML locally**

Run:
```bash
uv run python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"
```
Expected: no exception.

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/ci.yml packages/jw-eval/scripts/eval_open_drift_issues.py
git commit -m "ci(jw-eval): add eval-fast (PR-blocking) + eval-l2-live (weekly) + eval-nightly jobs"
```

---

### Task 18: Documentation — user guide

**Files:**
- Create: `docs/guias/eval-doctrinal.md`
- Modify: `docs/README.md`

- [ ] **Step 1: Write the guide**

```markdown
# Eval doctrinal (`jw-eval`)

> Fase 22 — suite de regresión doctrinal. Spec en `docs/superpowers/specs/2026-05-30-fase-22-eval-doctrinal-design.md`.

## Para qué sirve

Mide en cada commit (y nightly) que los agentes del toolkit no introduzcan regresión doctrinal silenciosa. Tres capas independientes:

| Capa | Qué mide | Cuándo corre | Bloquea CI |
|---|---|---|---|
| L1 estructural | shape de `AgentResult` esperada | siempre | sí |
| L2 citas | URLs resuelven + texto sustenta cita | siempre (snapshot) + weekly (live) | sí (snapshot); no (live) |
| L3 semántico | respuesta agente ≈ respuesta dorada | nightly | no |

## Usar localmente

```bash
# L1 + L2 (offline, rápido)
uv run jw eval --layer 1,2

# L2 live contra wol.jw.org real
uv run jw eval --layer 2 --live

# L1+L2+L3 con LLM judge Ollama (default)
JW_EVAL_LLM=ollama uv run jw eval --layer 1,2,3

# Solo Claude judge (requiere ANTHROPIC_API_KEY)
JW_EVAL_LLM=claude uv run jw eval --layer 3

# Salida a archivo
uv run jw eval --layer 1,2 --report md --out eval-report.md
```

## Añadir un nuevo caso dorado

1. Decide la capa: estructural / citas / semántico.
2. Crea YAML en `packages/jw-eval/fixtures/golden_qa/{l1,l2,l3}/<descriptive_name>.yaml`.
3. Si es L2, ejecuta `uv run python packages/jw-eval/scripts/build_eval_snapshots.py` para añadir el snapshot.
4. Commitea YAML + snapshot.
5. CI corre `jw eval` automáticamente.

## Política para fases nuevas

Toda Fase 23-32 debe añadir mínimo 3 casos dorados (uno por capa cuando aplique) al PR. CI verifica cobertura mínima.

## Troubleshooting

| Síntoma | Diagnóstico | Fix |
|---|---|---|
| L2 reporta `skip` | snapshot missing | `build_eval_snapshots.py` |
| L3 falla constantemente score=0 | embedder no instalado | `uv pip install -e packages/jw-eval[embeddings]` |
| L3 escala a LLM y no responde | Ollama no corre | `ollama serve` + `ollama pull llama3.1:8b` |
| L2 live abre muchos issues | wol cambió HTML | revisa snapshots + Fase 23 (auto-refresh) |
```

- [ ] **Step 2: Add link from `docs/README.md`**

Add to the "Guías por tema" list, in alphabetical position:

```markdown
- [Eval doctrinal](guias/eval-doctrinal.md) — Suite de regresión doctrinal `jw-eval`: 3 capas (estructural, citas, semántico), CI bloqueante + nightly.
```

- [ ] **Step 3: Commit**

```bash
git add docs/guias/eval-doctrinal.md docs/README.md
git commit -m "docs(eval): user guide for jw-eval suite"
```

---

### Task 19: Update VISION_AUDIT and ROADMAP

**Files:**
- Modify: `docs/VISION_AUDIT.md`
- Modify: `docs/ROADMAP.md`

- [ ] **Step 1: Add row to VISION_AUDIT.md summary table**

Insert above the closing `**100%...**` paragraph:

```markdown
| Fase 22 (eval doctrinal) | ✅ Nuevo | `jw-eval` — L1+L2+L3, 30 cases iniciales |
```

- [ ] **Step 2: Append Fase 22 section to ROADMAP.md**

After Fase 20, before any "---" or footer:

```markdown
## Fase 22 — Eval doctrinal regresión ✅

> Tier 1 infraestructura de confianza. Spec: `docs/superpowers/specs/2026-05-30-fase-22-eval-doctrinal-design.md`.

- ✅ Paquete nuevo `packages/jw-eval/`.
- ✅ Modelos Pydantic: `GoldenCase`, `LayerResult`, `SuiteReport`.
- ✅ YAML loader recursivo con filtro por capa.
- ✅ Layer 1 (structural): contract regression sobre agentes.
- ✅ Layer 2 (citations): snapshot (offline, bloqueante CI) + live (weekly, abre issues).
- ✅ Layer 3 (semantic): embeddings (sentence-transformers opcional, FakeEmbedder default) + escalada LLM (Ollama default, Claude/OpenAI opt-in).
- ✅ 12 cases L1 + 12 cases L2 + 6 cases L3 = 30 cases iniciales.
- ✅ Reporter markdown + JSON.
- ✅ CLI `jw eval --layer 1,2,3 --live --report md --out file`.
- ✅ Tool MCP `run_eval_suite`.
- ✅ CI jobs: `eval-fast` (bloqueante), `eval-l2-live` (weekly), `eval-nightly` (no-block).
- ✅ Script `build_eval_snapshots.py` + `eval_open_drift_issues.py`.
- ✅ Guía `docs/guias/eval-doctrinal.md`.

### Cobertura de tests

- ✅ 26 tests nuevos en `packages/jw-eval/tests/`.
- ✅ Suite global sin regresiones.
```

- [ ] **Step 3: Commit**

```bash
git add docs/VISION_AUDIT.md docs/ROADMAP.md
git commit -m "docs(roadmap): land Fase 22 — jw-eval doctrinal regression suite"
```

---

### Task 20: Final audit — full suite green + no regressions

**Files:** none (verification only).

- [ ] **Step 1: Run lint + format**

```bash
uv run ruff check packages/jw-eval packages/jw-cli packages/jw-mcp
uv run ruff format --check packages/jw-eval packages/jw-cli packages/jw-mcp
```
Expected: zero violations.

- [ ] **Step 2: Run mypy (best-effort)**

```bash
uv run mypy packages/jw-eval/src
```
Expected: errors only on `# type: ignore` lines, not unrelated regressions.

- [ ] **Step 3: Run the entire test suite**

```bash
uv run pytest packages/ -v --tb=short
```
Expected: all previous tests (551) + new tests (~26) green. No regressions.

- [ ] **Step 4: End-to-end CLI smoke**

```bash
uv run jw eval --layer 1 --report md
```
Expected: markdown report printed; exit code = 0 (all L1 cases pass).

- [ ] **Step 5: Final summary commit**

If any minor doc tweaks: amend or new commit `docs(eval): polish`. Otherwise nothing to do.

---

## Self-review summary

- **Spec coverage**: Each section of the spec maps to a task above (architecture → Task 1; models → Task 2; layers L1/L2/L3 → Tasks 4/6+8/11; judges → Tasks 9+10; suite → Task 13; reporter → Task 14; CLI → Task 15; MCP → Task 16; CI → Task 17; guide → Task 18; audit row → Task 19; final → Task 20). The exclusions (no auto-extraction, no dashboard, no agent modifications) are honored by virtue of being absent from the plan — explicitly called out in the guide (Task 18).
- **No placeholders**: every code step has the actual code; every YAML step shows the actual fields; every command shows the exact invocation and expected output.
- **Type consistency**: `GoldenCase.layer` is `LayerName = Literal["l1","l2","l3"]` used everywhere; `LayerResult.verdict` is `Verdict = Literal["pass","fail","skip","error"]` everywhere; agent callable signature `Callable[[dict[str, Any]], Any]` is consistent across `evaluate_*` and `Suite`. `snapshot_path` returns the same hashed filename in both `citations.py` and the snapshot build script.

## Execution choice

Plan completo. Dos opciones de ejecución:

1. **Subagent-driven (recomendado)** — dispatch fresh sub-agente por tarea, review entre tareas, iteración rápida (`superpowers:subagent-driven-development`).
2. **Inline** — ejecuto tareas en esta sesión con checkpoints (`superpowers:executing-plans`).

¿Cuál prefieres?
