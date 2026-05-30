"""Integrations with third-party JW apps / file formats.

Each submodule wraps one external surface:

  - `jw_library` → deep links to the official "JW Library" desktop/mobile app
    via the `jwlibrary:///finder?...` URL scheme (the only stable, officially-
    registered automation hook the app exposes).
  - `jw_library_local` → opt-in, read-only inspection of the app's installed
    library on the user's filesystem (Windows only; macOS sandbox blocks it).

These integrations never call jw.org over the network; they either build a
local URL or read a local file. Internet-facing code stays in
`jw_core.clients`.
"""

from __future__ import annotations

from jw_core.integrations.jw_library import (
    JWLibraryError,
    VerseRange,
    build_bible_url,
    build_bible_urls,
    build_publication_url,
    build_url_for_ref,
    detect_platform,
    open_jw_library,
)
from jw_core.integrations.jw_library_local import (
    ENV_OPT_IN as JW_LIBRARY_LOCAL_OPT_IN_ENV,
)
from jw_core.integrations.jw_library_local import (
    LocalInspectionResult,
    MacOSFullDiskAccessError,
    check_macos_full_disk_access,
    inspect_local_jw_library,
    read_macos_userdata,
)
from jw_core.integrations.jw_library_sync import (
    SyncReport,
    sync_backup_to_rag,
)
from jw_core.integrations.markdown import (
    ConversionStats,
    LinkifyResult,
    convert_jw_links_in_text,
    convert_jwpub_bible_url,
    convert_jwpub_publication_url,
    linkify_markdown,
    parse_jwlibrary_url,
    render_markdown_link,
    render_verse_block,
)
from jw_core.integrations.meps_catalog import (
    CatalogDocument,
    CatalogPublication,
    MepsCatalog,
)

__all__ = [
    "CatalogDocument",
    "CatalogPublication",
    "ConversionStats",
    "JWLibraryError",
    "JW_LIBRARY_LOCAL_OPT_IN_ENV",
    "LinkifyResult",
    "LocalInspectionResult",
    "MacOSFullDiskAccessError",
    "MepsCatalog",
    "SyncReport",
    "VerseRange",
    "build_bible_url",
    "build_bible_urls",
    "build_publication_url",
    "build_url_for_ref",
    "check_macos_full_disk_access",
    "convert_jw_links_in_text",
    "convert_jwpub_bible_url",
    "convert_jwpub_publication_url",
    "detect_platform",
    "inspect_local_jw_library",
    "linkify_markdown",
    "open_jw_library",
    "parse_jwlibrary_url",
    "read_macos_userdata",
    "render_markdown_link",
    "render_verse_block",
    "sync_backup_to_rag",
]
