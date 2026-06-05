"""Loader PDF → markdown → chunks usando datalab-to/marker.

NO importa `marker` en module-level; lo hace lazy dentro de `ingest_pdf`
para que el monorepo arranque aunque el extra `[pdf-marker]` no esté
instalado (graceful degrade: la función falla con ModuleNotFoundError
con un mensaje claro, no falla en import).

Idempotencia por hash sha256 del contenido del PDF.

Detección de "is JW publication" por substring matching contra
signatures conocidas (Watch Tower, JW.ORG, etc.). El loader nunca
bloquea ingest: simplemente anota `metadata.is_jw=True` para permitir
filtrar al hacer retrieval.
"""

from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path
from typing import Any

from jw_rag.chunkers import get_chunker
from jw_rag.store import VectorStore

_JW_SIGNATURES_RE = re.compile(
    r"(watch\s*tower|jw\.org|atalaya|the\s*watchtower|awake!|despertad!|"
    r"kingdom\s*hall|jehovah'?s\s*witnesses|testigos\s*de\s*jehov[áa])",
    re.IGNORECASE,
)


def _file_hash(path: Path) -> str:
    """SHA-256 of the file's bytes; basis for source_id + idempotency."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _detect_is_jw(markdown_text: str) -> bool:
    return bool(_JW_SIGNATURES_RE.search(markdown_text))


def ingest_pdf(
    store: VectorStore,
    pdf_path: Path | str,
    *,
    language: str,
    chunker: str | None = None,
    custom_meta: dict[str, Any] | None = None,
) -> int:
    """Ingiere un PDF al VectorStore vía marker.

    Pipeline:
        1. Compute sha256 del archivo (para source_id + idempotencia).
        2. Si el store ya tiene chunks con ese source_id → return 0 (no-op).
        3. Llamar marker para producir markdown estructurado.
        4. Split markdown en párrafos.
        5. Detectar firmas JW → set metadata.is_jw.
        6. chunker.chunk(...) + store.add(...).

    Args:
        store: VectorStore destino.
        pdf_path: ruta al PDF.
        language: código de idioma (en/es/pt/E/S/T...) — el loader no
            lo interpreta; lo guarda en metadata para enrutar chunkers
            semánticos F45 downstream.
        chunker: nombre del chunker (None usa el default; ver
            `jw_rag.chunkers.get_chunker`).
        custom_meta: metadata extra a mergear con la del loader.

    Returns:
        int — número de chunks añadidos (0 si ya estaba ingerido).

    Raises:
        ModuleNotFoundError: si `marker-pdf` no está instalado (mensaje
            sugiere `uv add 'jw-rag[pdf-marker]'`).
    """
    try:
        from marker.converters.pdf import PdfConverter
        from marker.models import create_model_dict
        from marker.output import text_from_rendered
    except ImportError as exc:  # pragma: no cover - depends on opt-in extra
        raise ModuleNotFoundError(
            "marker-pdf is not installed. Run: uv add 'jw-rag[pdf-marker]'"
        ) from exc

    pdf_path = Path(pdf_path)
    file_hash = _file_hash(pdf_path)
    source_id = f"pdf:{file_hash[:8]}"

    if store.has_source(source_id):
        return 0

    use_gpu = os.environ.get("JW_MARKER_USE_GPU", "0") == "1"
    use_llm = os.environ.get("JW_MARKER_USE_LLM", "0") == "1"

    converter = PdfConverter(
        artifact_dict=create_model_dict(),
        config={"use_llm": use_llm, "device": "cuda" if use_gpu else "cpu"},
    )
    rendered = converter(str(pdf_path))
    markdown_text, _, _ = _unpack_rendered(text_from_rendered(rendered))

    paragraphs = [p.strip() for p in markdown_text.split("\n\n") if p.strip()]
    is_jw = _detect_is_jw(markdown_text)

    metadata: dict[str, Any] = {
        "source_kind": "pdf_marker",
        "source_path": str(pdf_path.resolve()),
        "file_hash": file_hash,
        "is_jw": is_jw,
        "language": language,
    }
    if custom_meta:
        metadata.update(custom_meta)

    chunker_obj = get_chunker(chunker)
    chunks = chunker_obj.chunk(
        paragraphs,
        source_id,
        metadata=metadata,
    )
    store.add(chunks)
    return len(chunks)


def _unpack_rendered(value: Any) -> tuple[str, Any, Any]:
    """Normalize the return shape of `marker.output.text_from_rendered`.

    Historically marker returns `(text, metadata, images)` (3-tuple) but
    older releases used `(text, images)`. Accept both so the loader
    works against whichever marker-pdf the user has pinned.
    """
    if isinstance(value, tuple):
        if len(value) == 3:
            return value
        if len(value) == 2:
            return value[0], None, value[1]
    return str(value), None, None
