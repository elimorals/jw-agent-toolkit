"""Try AES variants on JWPUB Content blobs until we find the right key derivation."""
from __future__ import annotations
import hashlib
import io
import json
import sqlite3
import zipfile
import zlib
from pathlib import Path

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

PUB = Path("data/jwpub_test/ti_E.jwpub")

# 1. Read manifest + Document table
with zipfile.ZipFile(PUB) as outer:
    manifest = json.loads(outer.read("manifest.json"))
    inner_bytes = outer.read("contents")

manifest_hash_hex = manifest["hash"]  # 64 hex chars
manifest_hash_bytes = bytes.fromhex(manifest_hash_hex)
pub_hash_hex = manifest["publication"]["hash"]  # 40 hex chars (SHA1)
pub_symbol = manifest["publication"]["symbol"]

with zipfile.ZipFile(io.BytesIO(inner_bytes)) as inner:
    db_name = next(n for n in inner.namelist() if n.endswith(".db"))
    db_bytes = inner.read(db_name)
Path("/tmp/inspect.db").write_bytes(db_bytes)

conn = sqlite3.connect("/tmp/inspect.db")
conn.row_factory = sqlite3.Row
docs = conn.execute(
    "SELECT DocumentId, MepsDocumentId, Title, ContentLength, Content "
    "FROM Document ORDER BY DocumentId LIMIT 5"
).fetchall()
conn.close()

print(f"manifest.hash = {manifest_hash_hex}")
print(f"pub.hash      = {pub_hash_hex}")
print(f"pub.symbol    = {pub_symbol}")
print(f"first 5 docs: meps_ids = {[d['MepsDocumentId'] for d in docs]}")
print()


def try_decrypt(key: bytes, iv: bytes, ct: bytes) -> bytes | None:
    """Try AES-CBC decrypt; return plaintext if zlib-decompresses, else None."""
    try:
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
        decryptor = cipher.decryptor()
        pt = decryptor.update(ct) + decryptor.finalize()
        # Strip PKCS7 padding
        if pt and pt[-1] <= 16 and pt[-pt[-1]:] == bytes([pt[-1]]) * pt[-1]:
            pt = pt[:-pt[-1]]
        # Try zlib
        return zlib.decompress(pt)
    except Exception:
        return None


def test_strategy(label: str, key: bytes, iv: bytes) -> bool:
    """Try the strategy across all 5 documents."""
    ok = 0
    sample_text = None
    for d in docs:
        result = try_decrypt(key, iv, d["Content"])
        if result is not None:
            ok += 1
            if sample_text is None:
                sample_text = result[:200]
    print(f"  {label!s:<50} ok={ok}/5")
    if sample_text:
        try:
            decoded = sample_text.decode("utf-8", errors="replace")
            print(f"    sample[:200]: {decoded[:200]!r}")
        except Exception as e:
            print(f"    decode error: {e}")
    return ok > 0


# Strategy 1: AES-128, key = first 16 bytes of manifest_hash_bytes, iv = next 16
test_strategy(
    "manifest_hash[:16] / manifest_hash[16:32]",
    manifest_hash_bytes[:16], manifest_hash_bytes[16:32],
)

# Strategy 2: AES-256 needs 32-byte key. manifest_hash_bytes is 32 bytes
test_strategy(
    "AES-256 key=manifest_hash_bytes  iv=zeros",
    manifest_hash_bytes, b"\x00" * 16,
)

# Strategy 3: sha256(manifest_hash_bytes) split
seed = hashlib.sha256(manifest_hash_bytes).digest()
test_strategy(
    "sha256(manifest_hash_bytes)[:16] / [16:32]",
    seed[:16], seed[16:32],
)

# Strategy 4: sha256(manifest_hash_hex string) split
seed = hashlib.sha256(manifest_hash_hex.encode()).digest()
test_strategy(
    "sha256(manifest_hash_hex_str)[:16] / [16:32]",
    seed[:16], seed[16:32],
)

# Strategy 5: per-doc, sha256(manifest_hash + meps_id) split
print()
print("Per-document keys (sha256(manifest_hash + meps_id)[:16] / [16:32]):")
for d in docs:
    seed = hashlib.sha256(
        manifest_hash_bytes + str(d["MepsDocumentId"]).encode()
    ).digest()
    result = try_decrypt(seed[:16], seed[16:32], d["Content"])
    status = "✓" if result else "✗"
    print(f"  {status}  doc={d['DocumentId']}  meps={d['MepsDocumentId']}")
    if result:
        try:
            print(f"    sample: {result[:120].decode('utf-8', errors='replace')!r}")
        except Exception as e:
            print(f"    decode error: {e}")

print()
print("Alt: SHA1 from pub.hash variants")
pub_hash_bytes = bytes.fromhex(pub_hash_hex)  # 20 bytes
# Hash it to 32 bytes
seed = hashlib.sha256(pub_hash_bytes).digest()
test_strategy(
    "sha256(pub_hash_bytes)[:16] / [16:32]",
    seed[:16], seed[16:32],
)
seed = hashlib.sha256(pub_hash_hex.encode()).digest()
test_strategy(
    "sha256(pub_hash_hex_str)[:16] / [16:32]",
    seed[:16], seed[16:32],
)

print()
print("Alt: db filename based")
db_name_str = db_name
seed = hashlib.sha256(db_name_str.encode()).digest()
test_strategy(
    "sha256(db_filename)[:16] / [16:32]",
    seed[:16], seed[16:32],
)
