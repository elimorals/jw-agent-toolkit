"""Canonicalization + content hashing for provenance.

Capitalization is preserved on purpose — "Jehová" vs "jehová" carries
doctrinal meaning that we want drift detection to see. HTML must be
stripped by the caller's extractor before hashing.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata

_ZERO_WIDTH = {
    "​",  # ZERO WIDTH SPACE
    "‌",  # ZERO WIDTH NON-JOINER
    "‍",  # ZERO WIDTH JOINER
    "⁠",  # WORD JOINER
    "﻿",  # ZERO WIDTH NO-BREAK SPACE / BOM
}

_WHITESPACE_RUN = re.compile(r"\s+")


def canonicalize_text(text: str) -> str:
    """Normalize text so cosmetic edits don't inflate the content hash.

    Steps:
      1. NFC normalize.
      2. Drop zero-width characters.
      3. Collapse whitespace runs to a single space.
      4. Strip outer whitespace.
    """

    if not text:
        return ""
    nfc = unicodedata.normalize("NFC", text)
    if _ZERO_WIDTH.intersection(nfc):
        nfc = "".join(ch for ch in nfc if ch not in _ZERO_WIDTH)
    collapsed = _WHITESPACE_RUN.sub(" ", nfc)
    return collapsed.strip()


def content_sha256(text: str) -> str:
    """Lowercase-hex sha256 of `canonicalize_text(text)`."""

    canonical = canonicalize_text(text)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
