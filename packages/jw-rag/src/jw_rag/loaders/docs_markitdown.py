"""Loader Office docs → markdown → chunks usando microsoft/markitdown.

Soporta `.docx`, `.pptx`, `.xlsx`. Otros formatos (`.pdf` via
markitdown) los deja a `pdf_marker.py` porque markitdown's PDF path is
inferior a marker para layout complejo (escaneos JW históricos).

Lazy import como `pdf_marker.py`: el extra `[doc-markitdown]` no es
necesario para importar el módulo, sólo para invocar la función.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from jw_rag.chunkers import get_chunker
from jw_rag.store import VectorStore

SUPPORTED_EXTENSIONS: frozenset[str] = frozenset({".docx", ".pptx", ".xlsx"})


def _file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def ingest_office_doc(
    store: VectorStore,
    doc_path: Path | str,
    *,
    language: str,
    chunker: str | None = None,
    custom_meta: dict[str, Any] | None = None,
) -> int:
    """Ingiere un docx/pptx/xlsx al VectorStore vía markitdown.

    Pipeline igual que `ingest_pdf`: hash → idempotency check → convert
    → split en paragraphs → chunker.chunk → store.add.

    Args:
        store: VectorStore destino.
        doc_path: ruta al .docx / .pptx / .xlsx.
        language: código de idioma a guardar en metadata; no afecta
            la conversión (markitdown es language-agnostic).
        chunker: nombre del chunker (None = default).
        custom_meta: metadata extra a mergear con la del loader.

    Returns:
        int — número de chunks añadidos (0 si ya estaba ingerido).

    Raises:
        ValueError: si la extensión no está en SUPPORTED_EXTENSIONS.
            Se valida ANTES del import de markitdown para que el
            usuario reciba un error útil sin necesidad de instalar
            el extra opcional.
        ModuleNotFoundError: si `markitdown` no está instalado.
    """
    doc_path = Path(doc_path)
    ext = doc_path.suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"unsupported extension {ext!r}; "
            f"supported: {sorted(SUPPORTED_EXTENSIONS)}"
        )

    try:
        from markitdown import MarkItDown
    except ImportError as exc:  # pragma: no cover - depends on opt-in extra
        raise ModuleNotFoundError(
            "markitdown is not installed. Run: uv add 'jw-rag[doc-markitdown]'"
        ) from exc

    file_hash = _file_hash(doc_path)
    source_id = f"doc:{ext.lstrip('.')}:{file_hash[:8]}"
    if store.has_source(source_id):
        return 0

    md = MarkItDown()
    result = md.convert(str(doc_path))
    markdown_text = result.text_content
    paragraphs = [p.strip() for p in markdown_text.split("\n\n") if p.strip()]

    metadata: dict[str, Any] = {
        "source_kind": "office_markitdown",
        "source_format": ext.lstrip("."),
        "source_path": str(doc_path.resolve()),
        "file_hash": file_hash,
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
