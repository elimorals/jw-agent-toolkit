"""JWPUB parser — metadata + full text decryption (Phase 5.5).

Structure of a JWPUB file:
    outer ZIP:
        manifest.json
        contents       ← inner ZIP
    inner ZIP:
        {symbol}_{lang}.db    ← SQLite with Document table
        images/*.jpg

The `Document.Content` blob is zlib-compressed then AES-128-CBC encrypted.
The key/IV is derived from the publication's identity (language index,
symbol, year, issue number), NOT from the manifest hash. Algorithm
discovered in `gokusander/jwpub-toolkit` (MIT-licensed).

Algorithm (`_compute_key_iv`):
  1. pub_string = f"{meps_language_index}_{symbol}_{year}" (+ "_{issue}" if non-zero)
  2. digest = SHA-256(pub_string)
  3. material = digest XOR `_XOR_KEY` (fixed 32-byte JW magic constant)
  4. key = material[:16]   (AES-128 key)
     iv  = material[16:32]  (CBC IV)
  5. plaintext = zlib_inflate(AES-128-CBC-decrypt(content_blob))

For full-text indexing, both `parse_jwpub()` (returns text) and
`ingest_jwpub()` (chunks + embeds into the RAG store) are now available.
"""

from __future__ import annotations

import hashlib
import io
import json
import sqlite3
import tempfile
import zipfile
import zlib
from pathlib import Path

from bs4 import BeautifulSoup
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from jw_core.models import JwpubDocument, JwpubMetadata

# Fixed XOR constant used by JW to derive per-publication keys. Discovered
# by `gokusander/jwpub-toolkit` (MIT) by inspecting JW Library binaries.
_XOR_KEY = bytes.fromhex(
    "11cbb5587e32846d4c26790c633da289f66fe5842a3a585ce1bc3a294af5ada7"
)


class JwpubError(RuntimeError):
    pass


# ── Public API ──────────────────────────────────────────────────────────

def parse_jwpub_metadata(path: Path | str) -> JwpubMetadata:
    """Return readable metadata + document TOC, WITHOUT decryption.

    Cheap because we don't touch the encrypted blobs. Use this when you
    just need the chapter list / page numbers / paragraph counts. For full
    text, call `parse_jwpub()` instead.
    """
    return _parse(path, decrypt_text=False)


def parse_jwpub(path: Path | str) -> JwpubMetadata:
    """Open a JWPUB and decrypt every document's Content blob.

    Each returned `JwpubDocument` carries the decrypted XHTML in `.text`
    and the extracted plain-text paragraphs in `.paragraphs`. Raises
    `JwpubError` only on I/O / format problems; documents whose
    individual blob fails to decrypt get `text=""` and the failure is
    skipped silently so a single corrupted row doesn't break the call.
    """
    return _parse(path, decrypt_text=True)


# ── Internals ───────────────────────────────────────────────────────────

def _parse(path: Path | str, *, decrypt_text: bool) -> JwpubMetadata:
    pub_path = Path(path)
    try:
        with zipfile.ZipFile(pub_path) as outer:
            manifest_raw = outer.read("manifest.json")
            inner_bytes = outer.read("contents")
    except (KeyError, zipfile.BadZipFile) as e:
        raise JwpubError(f"{pub_path}: not a valid JWPUB ({e})") from e

    manifest = json.loads(manifest_raw)
    pub_meta = manifest.get("publication", {}) or {}

    language_index = pub_meta.get("language") if isinstance(pub_meta.get("language"), int) else 0
    symbol = pub_meta.get("symbol", "")
    year = pub_meta.get("year")
    issue = pub_meta.get("issueTagNumber") or pub_meta.get("issueNumber") or 0

    key_iv: tuple[bytes, bytes] | None = None
    if decrypt_text and symbol and year:
        key_iv = _compute_key_iv(language_index, symbol, int(year), int(issue))

    docs, decrypted = _read_documents_from_inner(inner_bytes, key_iv)

    return JwpubMetadata(
        title=pub_meta.get("title", ""),
        short_title=pub_meta.get("shortTitle", ""),
        symbol=symbol,
        language_index=language_index,
        publication_type=pub_meta.get("publicationType", ""),
        year=year,
        manifest_hash=manifest.get("hash", ""),
        schema_version=pub_meta.get("schemaVersion", 0),
        document_count=len(docs),
        documents=docs,
        source_path=str(pub_path),
        decrypted_text_available=decrypted,
    )


def _compute_key_iv(
    meps_language_index: int, symbol: str, year: int, issue_tag_number: int = 0
) -> tuple[bytes, bytes]:
    """Derive the AES-128 key + IV for a publication.

    Algorithm (credit: gokusander/jwpub-toolkit, MIT):
        pub_string = f"{lang}_{symbol}_{year}" (+ "_{issue}" if non-zero)
        material   = SHA-256(pub_string) XOR _XOR_KEY
        key = material[:16]; iv = material[16:32]
    """
    parts = [str(meps_language_index), symbol, str(year)]
    if issue_tag_number:
        parts.append(str(issue_tag_number))
    pub_string = "_".join(parts)
    digest = hashlib.sha256(pub_string.encode("utf-8")).digest()
    material = bytes(a ^ b for a, b in zip(digest, _XOR_KEY))
    return material[:16], material[16:32]


def _decrypt_blob(blob: bytes, key: bytes, iv: bytes) -> str:
    """AES-128-CBC decrypt + strip PKCS7 + zlib-inflate + UTF-8 decode."""
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
    decryptor = cipher.decryptor()
    padded = decryptor.update(blob) + decryptor.finalize()
    # Strip PKCS7 padding.
    if padded and 1 <= padded[-1] <= 16 and padded[-padded[-1]:] == bytes([padded[-1]]) * padded[-1]:
        padded = padded[:-padded[-1]]
    inflated = zlib.decompress(padded)
    return inflated.decode("utf-8", errors="replace")


def _extract_paragraphs(xhtml: str) -> list[str]:
    """Pull plain-text paragraphs out of a decrypted Document.Content blob.

    The blob is JW's internal XHTML — uses `<p data-pid="N">` for the real
    body paragraphs. We strip everything else (page numbers, headers).
    """
    soup = BeautifulSoup(xhtml, "lxml-xml") if xhtml.lstrip().startswith("<?xml") else BeautifulSoup(xhtml, "lxml")
    paragraphs: list[str] = []
    candidates = soup.find_all("p", attrs={"data-pid": True}) or soup.find_all("p")
    for p in candidates:
        text = p.get_text(" ", strip=True)
        if text and len(text) > 4:
            paragraphs.append(text)
    return paragraphs


def _read_documents_from_inner(
    inner_bytes: bytes, key_iv: tuple[bytes, bytes] | None
) -> tuple[list[JwpubDocument], bool]:
    """Read Document rows; decrypt content when `key_iv` is provided.

    Returns (documents, decrypted_text_available) where the bool flag is
    True if at least one blob was successfully decoded (so a failed Trinity
    brochure key wouldn't claim success).
    """
    with zipfile.ZipFile(io.BytesIO(inner_bytes)) as inner:
        db_names = [n for n in inner.namelist() if n.endswith(".db")]
        if not db_names:
            return [], False
        db_bytes = inner.read(db_names[0])

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        tmp.write(db_bytes)
        tmp_path = Path(tmp.name)
    try:
        conn = sqlite3.connect(tmp_path)
        conn.row_factory = sqlite3.Row
        cur = conn.execute(
            """
            SELECT
                DocumentId, MepsDocumentId, Title, TocTitle,
                ChapterNumber, SectionNumber, ParagraphCount,
                FirstPageNumber, LastPageNumber, ContentLength,
                Content
            FROM Document
            ORDER BY DocumentId
            """
        )

        out: list[JwpubDocument] = []
        decrypted_any = False
        for r in cur:
            text = ""
            paragraphs: list[str] = []
            if key_iv is not None and r["Content"]:
                try:
                    text = _decrypt_blob(r["Content"], *key_iv)
                    paragraphs = _extract_paragraphs(text)
                    decrypted_any = True
                except Exception:
                    # Best-effort: a single bad blob shouldn't kill the whole
                    # publication. The metadata side stays intact.
                    text = ""
                    paragraphs = []
            out.append(JwpubDocument(
                document_id=r["DocumentId"],
                meps_document_id=r["MepsDocumentId"],
                title=r["Title"] or "",
                toc_title=r["TocTitle"] or "",
                chapter_number=r["ChapterNumber"],
                section_number=r["SectionNumber"] or 0,
                paragraph_count=r["ParagraphCount"] or 0,
                first_page_number=r["FirstPageNumber"],
                last_page_number=r["LastPageNumber"],
                content_length=r["ContentLength"] or 0,
                text=text,
                paragraphs=paragraphs,
            ))
        conn.close()
        return out, decrypted_any
    finally:
        tmp_path.unlink(missing_ok=True)
