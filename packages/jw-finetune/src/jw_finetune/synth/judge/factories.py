"""Env-driven factory functions.

Two env vars steer the wiring:
  - JW_SYNTH_JUDGE_LLM in {off, none, "", anthropic, ollama}
  - JW_SYNTH_JUDGE_NLI in {off, deberta, claude, ollama, ...}

Imports are lazy: anthropic/ollama/jw_core.fidelity are only imported when the
env explicitly asks for them. If Fase 39 is not installed, NLI degrades to
None with a warning; the judge runs the other two stages.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Callable

from jw_finetune.synth.judge.judge import Judge
from jw_finetune.synth.judge.nli_bridge import NLIProviderLike
from jw_finetune.synth.judge.thresholds import JudgeMode, JudgeOverrides
from jw_finetune.synth.provider import LLMProvider

logger = logging.getLogger(__name__)

_nli_warning_emitted = False


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
    """Return the configured NLI provider, or None if disabled / unavailable."""

    global _nli_warning_emitted
    name = (os.environ.get("JW_SYNTH_JUDGE_NLI") or "off").lower().strip()
    if name in {"", "off", "none"}:
        return None
    try:
        factory = _import_nli_factory()
    except ImportError:
        if not _nli_warning_emitted:
            logger.warning(
                "NLI requested (JW_SYNTH_JUDGE_NLI=%s) but jw_core.fidelity is "
                "not available; skipping NLI stage.",
                name,
            )
            _nli_warning_emitted = True
        return None
    try:
        return factory(name)
    except Exception as exc:
        logger.warning("NLI factory failed for name=%r: %s", name, exc)
        return None


def build_judge(
    *, mode: JudgeMode, overrides: JudgeOverrides | None = None
) -> Judge:
    """Build a fully-wired Judge for the given mode."""

    if mode == JudgeMode.OFF:
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
