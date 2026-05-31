"""NLIProvider registry + factory.

Mirrors ``jw_rag.rerank_providers.factory`` so the operational model is
identical to Fase 33: an ordered list of provider instances + env override
+ shared ``JW_PROVIDER_ORDER`` env for target ranking.

Order of resolution:

  1. If ``JW_NLI_PROVIDER`` is set:
       - look up by exact ``provider.name``.
       - if ``is_available()`` → return.
       - if not available → raise RuntimeError (do not silently fall through).
       - if name unknown → raise ValueError.
  2. Else: iterate ``_instantiate_registry()``, return the first ``is_available()``,
     skipping FakeNLI (it's the last-resort floor).
  3. If nothing is available → return FakeNLI.

Registry order (priority): Claude > OpenAI > DeBERTa(mlx) > DeBERTa(nvidia)
> DeBERTa(cpu) > Ollama > FakeNLI.
"""

from __future__ import annotations

import logging
import os

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
    deferred to ``is_available()`` and the first ``evaluate()`` call.
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
    """Find a provider in the registry by exact ``.name`` match."""

    for r in _instantiate_registry():
        if r.name == name:
            return r
    return None


def list_available_nli_providers() -> list[NLIProvider]:
    """Public listing: every available provider EXCEPT fakes.

    Fakes are reachable via explicit ``JW_NLI_PROVIDER=fake-nli`` but never
    surface in the default listing — otherwise the auto-fallback would silently
    use them on hosts that also have real providers.
    """

    order = _provider_order()
    available = [r for r in _instantiate_registry() if r.is_available() and r.name != "fake-nli"]
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
                f"JW_NLI_PROVIDER={env_name!r} not available (target={p.target}, missing deps or env vars)"
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
