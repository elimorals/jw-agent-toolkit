"""NLI Provider Protocol — runtime entailment judgement.

Every provider answers a single question: does ``claim`` semantically
follow from ``premise``? The contract is intentionally narrow:

  - sync function (no async)
  - input: two strings + optional language code
  - output: NLIVerdict (verdict label + 0..1 score + provider name + raw)

Rules (heritage of Fase 33):

  1. No network at import time. Heavy deps (transformers, anthropic, openai)
     are imported lazily inside ``is_available()`` and ``evaluate()``.
  2. ``is_available()`` is cheap — env var checks, package presence, hardware
     detection. Called once per ``get_default_nli_provider()``.
  3. ``evaluate()`` is sync. API-backed providers should wrap their HTTP call
     and block; callers (the @fidelity_wrap decorator) are async-aware and
     can offload to threads.
  4. ``score`` is always in [0, 1], normalized by the provider. DeBERTa
     returns softmax[entailment]; LLMs return JSON ``confidence``.
  5. ``language`` is a hint for LLM providers; transformer NLI models that
     are multilingual ignore it.
"""

from __future__ import annotations

from typing import Literal, Protocol, runtime_checkable

from jw_core.fidelity.verdicts import NLIVerdict

Target = Literal["api", "mlx", "nvidia", "cpu"]


@runtime_checkable
class NLIProvider(Protocol):
    """Canonical NLI provider contract.

    Implementations declare a stable ``name`` (used by ``JW_NLI_PROVIDER`` env
    override) and a ``target`` (used by ``JW_PROVIDER_ORDER`` ranking, shared
    with Fase 33).
    """

    name: str
    target: Target

    def is_available(self) -> bool: ...

    def evaluate(self, claim: str, premise: str, *, language: str = "en") -> NLIVerdict: ...


def evaluate_entailment(
    claim: str,
    premise: str,
    *,
    language: str = "en",
    provider: NLIProvider | None = None,
) -> NLIVerdict:
    """Public helper: evaluate one claim/premise pair.

    Resolves a default provider via ``get_default_nli_provider()`` if none
    is supplied. Used by both ``@fidelity_wrap`` and Fase 44 (``synth-judge``).
    """

    if provider is None:
        from jw_core.fidelity.factory import get_default_nli_provider

        provider = get_default_nli_provider()
    return provider.evaluate(claim, premise, language=language)


__all__ = ["NLIProvider", "Target", "evaluate_entailment"]
