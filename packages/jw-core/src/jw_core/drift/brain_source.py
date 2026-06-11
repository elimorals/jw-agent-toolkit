"""F49 Second Brain → drift `Chunk` adapter (Fase 72 post-MVP).

Reads `Publication` nodes from any `jw_brain.backends.protocol.GraphBackend`
and produces `Chunk` rows suitable for `analyze_doctrinal_drift`.

The adapter is intentionally *thin*:
- it never imports `jw_brain` at module load (jw-core must not depend
  on jw-brain); callers pass an arbitrary backend object that quacks
  like `list_nodes(node_type=...)`;
- it accepts a `text_extractor` and `embed` callable so that the
  caller decides how to extract searchable text and how to embed it,
  which keeps F33-vs-stub-vs-cached embedders flexible.
"""

from __future__ import annotations

from typing import Any, Callable, Protocol, runtime_checkable

import numpy as np

from jw_core.drift.cluster import Chunk


@runtime_checkable
class _NodeListBackend(Protocol):
    """Subset of GraphBackend we need: just `list_nodes`."""

    def list_nodes(self, *, node_type: str) -> list[dict[str, Any]]: ...


def _default_text(props: dict[str, Any]) -> str:
    return str(
        props.get("text")
        or props.get("summary")
        or props.get("title")
        or ""
    )


_YEAR_FIELDS = ("year", "published_year", "pub_year")


def _default_year(props: dict[str, Any]) -> int | None:
    for key in _YEAR_FIELDS:
        if key in props and props[key] is not None:
            try:
                return int(props[key])
            except (TypeError, ValueError):
                continue
    published_date = props.get("published_date")
    if isinstance(published_date, str) and len(published_date) >= 4:
        head = published_date[:4]
        if head.isdigit():
            return int(head)
    return None


def chunks_from_brain(
    backend: _NodeListBackend,
    *,
    embed: Callable[[str], np.ndarray],
    node_type: str = "Publication",
    text_extractor: Callable[[dict[str, Any]], str] = _default_text,
    year_extractor: Callable[[dict[str, Any]], int | None] = _default_year,
    language: str | None = None,
) -> list[Chunk]:
    """Build drift chunks from a Second Brain backend.

    Skips nodes without enough text or without a usable year. Embeddings
    are L2-normalised so cluster cosine distances are well-defined.
    """

    nodes = backend.list_nodes(node_type=node_type)
    out: list[Chunk] = []
    for node in nodes:
        props = node.get("properties") or {}
        if language is not None:
            node_lang = str(props.get("language") or "").lower()
            if node_lang and node_lang != language.lower():
                continue
        text = text_extractor(props).strip()
        if len(text) < 20:
            continue
        year = year_extractor(props)
        if year is None:
            continue
        emb = np.asarray(embed(text), dtype=np.float32)
        norm = float(np.linalg.norm(emb))
        if norm == 0.0:
            continue
        out.append(
            Chunk(text=text, year=int(year), embedding=emb / norm)
        )
    return out
