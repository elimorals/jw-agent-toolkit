"""Wire-up F33 RAG retriever + F39 NLI for the image-quote verifier (Fase 70 post-MVP).

These factories produce *default* implementations of the `retriever` and
`nli` parameters of `verify_image_quote`. They are loaded lazily so that
`jw_core.verification.image_quote.engine` keeps its tiny default
dependency surface (no `jw_rag`/`transformers` at import time).

Resolution policy:
- `default_rag_retriever()` reads `JW_IMAGE_QUOTE_STORE_PATH`; if set,
  it opens a `jw_rag.VectorStore` and returns a callable retriever.
  Else it returns `None` (engine falls back to "no hits").
- `default_nli()` calls `jw_core.fidelity.get_default_nli_provider()`
  and wraps it in an adapter object exposing the
  `evaluate_entailment(claim=, premise=)` shape the engine expects.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


ENV_STORE_PATH = "JW_IMAGE_QUOTE_STORE_PATH"


@dataclass
class _SimpleHit:
    """Minimal `RAGHit`-shaped record used by the verifier."""

    source_url: str
    source_pub_code: str
    source_text_original: str


def _hit_from_rag(hit: Any) -> _SimpleHit | None:
    chunk = getattr(hit, "chunk", None)
    if chunk is None:
        return None
    text = getattr(chunk, "text", "") or ""
    if not text.strip():
        return None
    meta = getattr(chunk, "metadata", None) or {}
    return _SimpleHit(
        source_url=str(meta.get("source_url") or meta.get("url") or ""),
        source_pub_code=str(
            meta.get("source_pub_code") or meta.get("pub_code") or ""
        ),
        source_text_original=text,
    )


def default_rag_retriever(
    *, top_k: int = 5, store_path: str | None = None
):
    """Return an async callable retriever bound to a `VectorStore`, or None.

    Pass `store_path` explicitly to override the env var.
    """

    path = store_path or os.environ.get(ENV_STORE_PATH, "").strip()
    if not path:
        return None
    try:
        from jw_rag import VectorStore, get_default_embedder
    except ImportError as exc:  # pragma: no cover
        logger.debug("jw_rag not installed: %s", exc)
        return None

    try:
        embedder = get_default_embedder()
        store = VectorStore(path, embedder=embedder)
        if hasattr(store, "load"):
            store.load()
    except Exception as exc:  # noqa: BLE001
        logger.debug("Failed to open RAG store at %s: %s", path, exc)
        return None

    async def _retrieve(query: str) -> list[_SimpleHit]:
        try:
            hits = store.hybrid_search(query, top_k=top_k)
        except Exception as exc:  # noqa: BLE001
            logger.debug("RAG hybrid_search raised: %s", exc)
            return []
        out: list[_SimpleHit] = []
        for h in hits or []:
            simple = _hit_from_rag(h)
            if simple is not None:
                out.append(simple)
        return out

    return _retrieve


class _NLIAdapter:
    """Adapt F39 `NLIProvider.evaluate` → `evaluate_entailment` shape."""

    def __init__(self, provider: Any, *, language: str = "es") -> None:
        self._provider = provider
        self._language = language

    def evaluate_entailment(self, *, claim: str, premise: str) -> Any:
        return self._provider.evaluate(
            claim, premise, language=self._language
        )


def default_nli(language: str = "es"):
    """Return an NLI adapter using the F39 default provider, or None."""

    try:
        from jw_core.fidelity import get_default_nli_provider
    except ImportError as exc:  # pragma: no cover
        logger.debug("jw_core.fidelity not importable: %s", exc)
        return None
    try:
        provider = get_default_nli_provider()
    except Exception as exc:  # noqa: BLE001
        logger.debug("get_default_nli_provider raised: %s", exc)
        return None
    return _NLIAdapter(provider, language=language)


__all__ = [
    "ENV_STORE_PATH",
    "default_nli",
    "default_rag_retriever",
]
