"""Loaders externos para fuentes no-JWPUB/no-EPUB.

Cada loader es opt-in: la dependencia pesada vive detrás de un extra
del paquete (`[pdf-marker]`, `[doc-markitdown]`, `[loaders-all]`).

Public API:
    ingest_pdf(store, path, *, language, **metadata) -> int
    ingest_office_doc(store, path, *, language, **metadata) -> int

Imports are deferred to the loader-call site (lazy) so that importing
`jw_rag.loaders` itself does NOT pull `marker` or `markitdown` — they
are only required when the user actually calls the respective function.
"""

from __future__ import annotations

from jw_rag.loaders.docs_markitdown import ingest_office_doc
from jw_rag.loaders.pdf_marker import ingest_pdf

__all__ = ["ingest_office_doc", "ingest_pdf"]
