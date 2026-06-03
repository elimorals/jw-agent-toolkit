"""Translation providers — pluggable backends for `jw_core.translation`.

Each provider takes a (masked) source string + source/target language codes
and returns the translated text with `<<REF:i>>` tokens preserved. The
caller is responsible for the mask/restore dance via `jw_core.translation`.

Providers (F53):
  - `nllb` — Meta NLLB-200 (200 languages, CC-BY-NC-4.0). Local, CTranslate2
    INT8 backend, Mac M-series + CUDA. Strong on low-resource.

Router (F54.1): `get_translation_provider()` picks based on commercial-safety
and language pair. Pass `commercial=True` to skip CC-BY-NC providers.
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod


class TranslationProvider(ABC):
    name: str
    is_commercial_safe: bool = True

    @abstractmethod
    def is_available(self) -> bool:
        """True iff the provider can serve requests right now."""

    @abstractmethod
    def supports_language_pair(self, source: str, target: str) -> bool:
        """True iff (source, target) is a known route."""

    @abstractmethod
    def translate(self, text: str, *, source: str, target: str) -> str:
        """Translate `text` from `source` to `target`."""


# ── F54.1 router ────────────────────────────────────────────────────────


class TranslationError(RuntimeError):
    """Raised when no provider can serve a request."""


def _all_providers() -> list[type[TranslationProvider]]:
    """Lazy-import all providers so optional deps don't crash at import."""
    from jw_core.translation_providers.nllb import NLLBProvider

    return [NLLBProvider]


DEFAULT_TRANSLATION_CHAIN: list[str] = ["nllb-200"]


def get_translation_provider(
    name: str | None = None,
    *,
    source: str | None = None,
    target: str | None = None,
    commercial: bool = False,
) -> TranslationProvider:
    """Return an available translation provider.

    Resolution:
      1. Explicit `name`.
      2. `JW_TRANSLATION_PROVIDER` env var.
      3. By `(source, target)` pair: prefer commercial-safe if `commercial=True`.
      4. DEFAULT_TRANSLATION_CHAIN — first available wins.

    `commercial=True` filters out CC-BY-NC providers (NLLB). Pass it when
    the caller is producing output for paid distribution.
    """
    classes = _all_providers()
    requested = name or os.getenv("JW_TRANSLATION_PROVIDER")
    if requested:
        for cls in classes:
            if cls.name == requested:
                inst = cls()
                if not inst.is_available():
                    raise TranslationError(f"Provider {requested!r} not available.")
                if commercial and not inst.is_commercial_safe:
                    raise TranslationError(
                        f"Provider {requested!r} is non-commercial (CC-BY-NC). "
                        f"Pass `commercial=False` or pick a different provider."
                    )
                return inst
        raise TranslationError(f"Unknown translation provider {requested!r}.")

    for entry_name in DEFAULT_TRANSLATION_CHAIN:
        for cls in classes:
            if cls.name != entry_name:
                continue
            inst = cls()
            if commercial and not inst.is_commercial_safe:
                continue
            if source and target and not inst.supports_language_pair(source, target):
                continue
            if inst.is_available():
                return inst

    raise TranslationError(
        "No translation provider available. Install NLLB: "
        "`uv add 'jw-core[translation-nllb]'` (CC-BY-NC, non-commercial)."
    )


def list_translation_providers() -> list[dict[str, object]]:
    out = []
    for cls in _all_providers():
        inst = cls()
        out.append(
            {
                "name": cls.name,
                "available": inst.is_available(),
                "commercial_safe": inst.is_commercial_safe,
            }
        )
    return out
