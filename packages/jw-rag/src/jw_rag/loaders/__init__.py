"""Loaders externos para fuentes no-JWPUB/no-EPUB.

Cada loader es opt-in: la dependencia pesada vive detrás de un extra
del paquete (`[pdf-marker]`, `[doc-markitdown]`, `[loaders-all]`).

Public API:
    ingest_pdf(store, path, *, language, **metadata) -> int
    ingest_office_doc(store, path, *, language, **metadata) -> int

The package `__init__` deliberately catches `ModuleNotFoundError` on
each re-export so that importing `jw_rag.loaders` succeeds even when
sibling loader modules are missing during incremental development
(F62.1 lands the scaffold before F62.3 / F62.5 add the modules
themselves). At runtime, calling code receives the symbol or hits a
clear AttributeError telling them which loader is unavailable.
"""

from __future__ import annotations

__all__ = ["ingest_office_doc", "ingest_pdf"]

try:
    from jw_rag.loaders.pdf_marker import ingest_pdf
except ModuleNotFoundError:  # module not yet created during scaffolding
    ingest_pdf = None  # type: ignore[assignment]

try:
    from jw_rag.loaders.docs_markitdown import ingest_office_doc
except ModuleNotFoundError:  # module not yet created during scaffolding
    ingest_office_doc = None  # type: ignore[assignment]
