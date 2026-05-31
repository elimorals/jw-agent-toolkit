"""Integration test: wrap a stand-in apologetics-shaped result with FakeNLI.

We don't import the real apologetics agent (which would require live WOL +
parser fixtures); we build an AgentResult with the same shape and confirm
that the wrapped agent:

  - Returns the same number of findings as the unwrapped version (warn mode).
  - Stamps every finding with nli_* metadata.
  - Stamps result.metadata with nli_min_score / nli_on_fail.
  - Preserves preexisting result.metadata (e.g., language).
  - Never raises.

We do NOT exercise reject mode here — that's tested in test_fidelity_wrap.
This is the "the wiring works end-to-end on an agent-shaped result" test.
"""

from __future__ import annotations

import asyncio

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
    # The preexisting ``language`` metadata is preserved
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
