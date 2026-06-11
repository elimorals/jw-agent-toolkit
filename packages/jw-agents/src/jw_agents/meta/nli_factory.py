"""NLI provider factory for the meta-orchestrator (Fase 65 post-MVP).

Bridges the meta `Critique.evaluate_entailment(*, claim, premise)` shape
to the real F39 `NLIProvider.evaluate(claim, premise, *, language)` API.

Env-driven selection via `JW_META_NLI`:
  - `off` (default) -> no critique NLI (returns None)
  - `auto` / `default` -> use `get_default_nli_provider()` from F39
"""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


class _NLIAdapter:
    """Adapter that exposes `evaluate_entailment` on top of a real F39 NLIProvider.

    The meta `Critique` calls `evaluate_entailment(*, claim, premise)`. The
    real F39 contract is `evaluate(claim, premise, *, language="en")`. This
    adapter normalizes the signature and forwards `language`, falling back
    to "en" if the caller did not pass one.
    """

    def __init__(self, provider: Any, *, language: str = "en") -> None:
        self._provider = provider
        self._language = language

    @property
    def name(self) -> str:
        return getattr(self._provider, "name", "unknown")

    def evaluate_entailment(self, *, claim: str, premise: str) -> Any:
        return self._provider.evaluate(
            claim, premise, language=self._language
        )


def build_nli_from_env(*, language: str = "en") -> Any | None:
    """Construct a critique-compatible NLI adapter from env, or None.

    Returns `None` when:
      - `JW_META_NLI=off` (default)
      - The F39 default provider cannot be resolved
      - Provider declares `is_available() is False` (e.g. missing model)

    Returns an `_NLIAdapter` exposing `evaluate_entailment(*, claim, premise)`
    when the resolved provider reports available.
    """

    mode = os.environ.get("JW_META_NLI", "off").lower()
    if mode in ("", "off", "false", "0", "no"):
        return None

    try:
        from jw_core.fidelity.factory import get_default_nli_provider

        provider = get_default_nli_provider()
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "meta: NLI default provider unavailable (%s); skipping critique NLI.",
            exc,
        )
        return None

    try:
        available = bool(provider.is_available())
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "meta: NLI provider is_available() raised %s; skipping.", exc
        )
        return None

    if not available:
        logger.info(
            "meta: NLI provider %r reports unavailable; skipping critique NLI.",
            getattr(provider, "name", "?"),
        )
        return None

    return _NLIAdapter(provider, language=language)
