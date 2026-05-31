"""Ingest one page image into the RAG vector store.

Produces one chunk per StructuredBlock with stable `source_id` based on the
SHA-256 of the image path (or contents) plus block index. `bible_ref` blocks
get an extra `parsed_reference` metadata entry when the reference parser
returns a hit.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import TYPE_CHECKING

from jw_core.parsers.reference import parse_reference

from jw_rag.chunker import Chunk

if TYPE_CHECKING:  # avoid hard dep at import time
    from jw_core.vision.vlm import StructuredPage, VLMProvider


def _hash_for_image(image_path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(str(image_path.resolve()).encode("utf-8"))
    if image_path.exists():
        digest.update(image_path.read_bytes())
    return digest.hexdigest()[:16]


def ingest_image(
    store,
    image_path: Path | str,
    *,
    language: str = "en",
    provider: VLMProvider | None = None,
    min_confidence: float | None = None,
) -> int:
    """Ingest one page image. Returns the number of chunks added."""

    if provider is None:
        from jw_core.vision.vlm_providers import get_default_provider

        provider = get_default_provider()

    path = Path(image_path)
    page: StructuredPage = provider.extract_structured(path, language=language)
    img_hash = _hash_for_image(path)

    chunks: list[Chunk] = []
    for i, block in enumerate(page.blocks):
        if min_confidence is not None and block.confidence is not None and block.confidence < min_confidence:
            continue
        metadata: dict[str, object] = {
            "kind": block.kind,
            "lang_hint": block.lang_hint,
            "image_path": str(path),
            "provider": page.provider_name,
            "target": page.target,
            "language_detected": page.language_detected,
            "confidence": block.confidence,
            "bbox": list(block.bbox) if block.bbox else None,
        }
        if block.kind == "bible_ref":
            parsed = parse_reference(block.text)
            if parsed is not None:
                metadata["parsed_reference"] = parsed.model_dump()
        source_id = f"image:{img_hash}:{i}:{block.kind}"
        chunks.append(
            Chunk(
                id=source_id,
                text=block.text,
                source_id=source_id,
                metadata=metadata,
            )
        )

    if chunks:
        store.add(chunks)
    return len(chunks)
