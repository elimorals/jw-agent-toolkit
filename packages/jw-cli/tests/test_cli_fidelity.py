"""Tests for the ``--fidelity`` flag on the new ``jw apologetics`` CLI command.

The real apologetics agent makes live HTTP calls to wol.jw.org; we patch it
with a deterministic stub via monkeypatch on the imported symbol inside
``jw_cli.commands.apologetics``.

This is the minimum surface that demonstrates the wiring: the spec lists
four agent commands (apologetics / verse-explainer / research / meeting)
but the repo's CLI only ships ``apologetics`` as an agent-wrapping command
today. Each of the remaining three has an existing jw-agents module but
no corresponding ``jw_cli/commands/`` shim yet — adding them is mechanical
and follows this same pattern.
"""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from jw_agents.base import AgentResult, Citation, Finding
from jw_cli.main import app


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


@pytest.fixture()
def patch_apologetics(monkeypatch):
    async def fake(*args, **kwargs):  # noqa: ARG001
        return _stub_result()

    import jw_cli.commands.apologetics as mod

    monkeypatch.setattr(mod, "apologetics", fake)


def test_apologetics_fidelity_off_skips_wrapping(patch_apologetics) -> None:
    runner = CliRunner()
    res = runner.invoke(app, ["apologetics", "question?", "--fidelity", "off"])
    assert res.exit_code == 0
    # When off, no nli_* metadata in stdout
    assert "nli_verdict" not in res.stdout


def test_apologetics_fidelity_warn_adds_metadata(patch_apologetics) -> None:
    runner = CliRunner()
    res = runner.invoke(app, ["apologetics", "question?", "--fidelity", "warn"])
    assert res.exit_code == 0
    assert "nli_verdict" in res.stdout


def test_apologetics_fidelity_reject_drops_bad_findings(patch_apologetics) -> None:
    runner = CliRunner()
    res = runner.invoke(app, ["apologetics", "question?", "--fidelity", "reject"])
    assert res.exit_code == 0
    # FakeNLI on this excerpt detects asymmetric negation → contradicts → reject
    assert "Rejected finding" in res.stdout or '"findings": []' in res.stdout


def test_apologetics_fidelity_invalid_value_exits_nonzero(patch_apologetics) -> None:
    runner = CliRunner()
    res = runner.invoke(app, ["apologetics", "question?", "--fidelity", "bogus"])
    assert res.exit_code != 0


def test_apologetics_default_fidelity_is_warn(patch_apologetics) -> None:
    """Default --fidelity is warn — no flag means NLI metadata is present."""
    runner = CliRunner()
    res = runner.invoke(app, ["apologetics", "question?"])
    assert res.exit_code == 0
    assert "nli_verdict" in res.stdout
    assert '"nli_on_fail": "warn"' in res.stdout
