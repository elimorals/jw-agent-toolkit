"""Shared JWPUB crypto primitives: key derivation + AES-128-CBC + zlib.

Extracted from `parsers.jwpub` (Phase 5.5 decryption) so the writer in
`writers.jwpub` (Phase 49) can share the same key-derivation logic with
the parser instead of duplicating the magic XOR constant.

The algorithm is:

    pub_string = f"{meps_language_index}_{symbol}_{year}" (+ "_{issue}" if non-zero)
    digest     = SHA-256(pub_string)
    material   = digest XOR XOR_KEY    (XOR_KEY is JW's fixed 32-byte magic)
    key        = material[:16]
    iv         = material[16:32]

Original algorithm credit: `gokusander/jwpub-toolkit` (MIT, decryption side)
and `darioragusa/html2jwpub` (MIT, encryption side).
"""

from __future__ import annotations

import hashlib
import zlib

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

# Fixed 32-byte XOR constant baked into JW Library binaries. Same constant
# is used by every publication in every language.
XOR_KEY = bytes.fromhex("11cbb5587e32846d4c26790c633da289f66fe5842a3a585ce1bc3a294af5ada7")


def compute_key_iv(
    meps_language_index: int,
    symbol: str,
    year: int,
    issue_tag_number: int = 0,
) -> tuple[bytes, bytes]:
    """Derive the AES-128 key + IV for a publication."""
    parts = [str(meps_language_index), symbol, str(year)]
    if issue_tag_number:
        parts.append(str(issue_tag_number))
    pub_string = "_".join(parts)
    digest = hashlib.sha256(pub_string.encode("utf-8")).digest()
    material = bytes(a ^ b for a, b in zip(digest, XOR_KEY, strict=True))
    return material[:16], material[16:32]


def decrypt_blob(blob: bytes, key: bytes, iv: bytes) -> str:
    """AES-128-CBC decrypt + strip PKCS7 + zlib-inflate + UTF-8 decode."""
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
    decryptor = cipher.decryptor()
    padded = decryptor.update(blob) + decryptor.finalize()
    if padded and 1 <= padded[-1] <= 16 and padded[-padded[-1] :] == bytes([padded[-1]]) * padded[-1]:
        padded = padded[: -padded[-1]]
    inflated = zlib.decompress(padded)
    return inflated.decode("utf-8", errors="replace")


def encrypt_blob(content: str, key: bytes, iv: bytes) -> bytes:
    """UTF-8 encode + zlib-deflate + PKCS7 pad + AES-128-CBC encrypt.

    Inverse of `decrypt_blob`. Output is the exact byte-format JW Library
    expects in `Document.Content` (and friends): the AES-encrypted form of
    a zlib stream (header `78 9c ...` for default compression).
    """
    raw = content.encode("utf-8")
    # zlib.compress emits the same wbits=MAX_WBITS / level=Z_DEFAULT_COMPRESSION
    # stream that the Swift reference uses (`deflateInit2_` with MAX_WBITS, 8,
    # Z_DEFAULT_STRATEGY). The result is byte-for-byte compatible with what
    # JW Library produces and what `decrypt_blob` accepts.
    deflated = zlib.compress(raw)
    pad_len = 16 - (len(deflated) % 16)
    padded = deflated + bytes([pad_len]) * pad_len
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
    encryptor = cipher.encryptor()
    return encryptor.update(padded) + encryptor.finalize()
