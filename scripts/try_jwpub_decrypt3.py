"""Brute-force more AES-256 + IV combos before pivoting to EPUB."""
from __future__ import annotations
import hashlib
import io
import itertools
import json
import sqlite3
import zipfile
import zlib
from pathlib import Path

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

PUB = Path("data/jwpub_test/ti_E.jwpub")
with zipfile.ZipFile(PUB) as outer:
    manifest = json.loads(outer.read("manifest.json"))
    inner_bytes = outer.read("contents")

mh_hex = manifest["hash"]
mh_bytes = bytes.fromhex(mh_hex)
ph_hex = manifest["publication"]["hash"]
ph_bytes = bytes.fromhex(ph_hex)

with zipfile.ZipFile(io.BytesIO(inner_bytes)) as inner:
    db_name = next(n for n in inner.namelist() if n.endswith(".db"))
    db_bytes = inner.read(db_name)
Path("/tmp/inspect.db").write_bytes(db_bytes)

conn = sqlite3.connect("/tmp/inspect.db")
conn.row_factory = sqlite3.Row
docs = conn.execute(
    "SELECT DocumentId, MepsDocumentId, MepsLanguageIndex, Content "
    "FROM Document ORDER BY DocumentId LIMIT 3"
).fetchall()
conn.close()


def try_decrypt(key: bytes, iv: bytes, ct: bytes) -> bytes | None:
    if len(ct) % 16 != 0:
        return None
    try:
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
        d = cipher.decryptor()
        pt = d.update(ct) + d.finalize()
        if pt and 1 <= pt[-1] <= 16 and pt[-pt[-1]:] == bytes([pt[-1]]) * pt[-1]:
            pt = pt[:-pt[-1]]
        return zlib.decompress(pt)
    except Exception:
        return None


candidates_key: list[tuple[str, bytes]] = [
    ("manifest_hash_bytes[0:32]", mh_bytes),  # 32-byte AES-256 key
    ("manifest_hash_bytes[0:16]", mh_bytes[:16]),  # AES-128
    ("sha256(manifest_hash_hex_str)[:32]", hashlib.sha256(mh_hex.encode()).digest()),
    ("sha256(manifest_hash_bytes)[:32]", hashlib.sha256(mh_bytes).digest()),
    ("sha256(ti)[:32]", hashlib.sha256(b"ti").digest()),
]


def gen_iv_candidates(d) -> list[tuple[str, bytes]]:
    meps = d["MepsDocumentId"]
    lang = d["MepsLanguageIndex"]
    return [
        ("zeros", b"\x00" * 16),
        ("manifest_hash[16:32]", mh_bytes[16:32]),
        ("manifest_hash[0:16]", mh_bytes[:16]),
        ("sha256(str(meps))[:16]", hashlib.sha256(str(meps).encode()).digest()[:16]),
        ("sha256(meps_LE4)[:16]", hashlib.sha256(meps.to_bytes(4, 'little')).digest()[:16]),
        ("sha256(meps_BE4)[:16]", hashlib.sha256(meps.to_bytes(4, 'big')).digest()[:16]),
        ("sha256(meps_LE8)[:16]", hashlib.sha256(meps.to_bytes(8, 'little')).digest()[:16]),
        ("sha256(str(meps)+manifest_hash)[:16]",
         hashlib.sha256((str(meps) + mh_hex).encode()).digest()[:16]),
        ("sha256(manifest_hash+str(meps))[:16]",
         hashlib.sha256((mh_hex + str(meps)).encode()).digest()[:16]),
        ("sha256(meps_LE4 + manifest_hash)[:16]",
         hashlib.sha256(meps.to_bytes(4, 'little') + mh_bytes).digest()[:16]),
        ("sha256(manifest_hash + meps_LE4)[:16]",
         hashlib.sha256(mh_bytes + meps.to_bytes(4, 'little')).digest()[:16]),
        ("sha256(lang)[:16]",
         hashlib.sha256(str(lang).encode()).digest()[:16]),
    ]


win_count = 0
for k_label, k in candidates_key:
    for iv_label_pat in [name for name, _ in gen_iv_candidates(docs[0])]:
        # For each candidate IV builder, check on doc 0
        d = docs[0]
        all_ivs = dict(gen_iv_candidates(d))
        iv = all_ivs[iv_label_pat]
        r = try_decrypt(k, iv, d["Content"])
        if r:
            print(f"  WIN  key={k_label}  iv={iv_label_pat}  sample={r[:80]!r}")
            win_count += 1

if win_count == 0:
    print("No combination worked. Time to pivot to EPUB.")
else:
    print(f"Found {win_count} working combinations.")
