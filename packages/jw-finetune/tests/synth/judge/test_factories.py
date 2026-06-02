"""Factory + env-driven configuration tests.

We never touch real provider classes here — we patch the import points.
"""

from __future__ import annotations

import pytest
from jw_finetune.synth.judge import factories
from jw_finetune.synth.judge.factories import (
    build_judge,
    build_llm_judge_provider,
    build_nli_provider,
)
from jw_finetune.synth.judge.thresholds import JudgeMode, JudgeOverrides


@pytest.fixture(autouse=True)
def _reset_nli_warning() -> None:
    factories._nli_warning_emitted = False


def test_build_llm_judge_provider_off_returns_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("JW_SYNTH_JUDGE_LLM", raising=False)
    assert build_llm_judge_provider() is None
    monkeypatch.setenv("JW_SYNTH_JUDGE_LLM", "off")
    assert build_llm_judge_provider() is None
    monkeypatch.setenv("JW_SYNTH_JUDGE_LLM", "none")
    assert build_llm_judge_provider() is None
    monkeypatch.setenv("JW_SYNTH_JUDGE_LLM", "")
    assert build_llm_judge_provider() is None


def test_build_llm_judge_provider_unknown_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("JW_SYNTH_JUDGE_LLM", "magic")
    with pytest.raises(ValueError, match="JW_SYNTH_JUDGE_LLM"):
        build_llm_judge_provider()


def test_build_llm_judge_provider_anthropic_imports_lazily(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("JW_SYNTH_JUDGE_LLM", "anthropic")
    sentinel = object()
    monkeypatch.setattr(
        "jw_finetune.synth.judge.factories._import_anthropic_provider",
        lambda: lambda: sentinel,
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


def test_build_nli_provider_off_returns_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("JW_SYNTH_JUDGE_NLI", raising=False)
    assert build_nli_provider() is None
    monkeypatch.setenv("JW_SYNTH_JUDGE_NLI", "off")
    assert build_nli_provider() is None


def test_build_nli_provider_handles_import_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("JW_SYNTH_JUDGE_NLI", "deberta")

    def broken() -> object:
        raise ImportError("jw_core.fidelity missing")

    monkeypatch.setattr(
        "jw_finetune.synth.judge.factories._import_nli_factory", broken
    )
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
