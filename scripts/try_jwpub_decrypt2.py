"""Try many AES key derivation variants on JWPUB Content."""
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

with zipfile.ZipFile(PUB) as outer:
    manifest = json.loads(outer.read("manifest.json"))
    inner_bytes = outer.read("contents")

manifest_hash_hex = manifest["hash"]
manifest_hash_bytes = bytes.fromhex(manifest_hash_hex)
pub_hash_hex = manifest["publication"]["hash"]
pub_hash_bytes = bytes.fromhex(pub_hash_hex)

with zipfile.ZipFile(io.BytesIO(inner_bytes)) as inner:
    db_name = next(n for n in inner.namelist() if n.endswith(".db"))
    db_bytes = inner.read(db_name)
Path("/tmp/inspect.db").write_bytes(db_bytes)

conn = sqlite3.connect("/tmp/inspect.db")
conn.row_factory = sqlite3.Row
docs = conn.execute(
    "SELECT DocumentId, MepsDocumentId, MepsLanguageIndex, Title, ContentLength, Content "
    "FROM Document ORDER BY DocumentId LIMIT 5"
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


variants_global: list[tuple[str, bytes, bytes]] = []

# Try many derivations of (key, iv) from manifest_hash + pub_hash combos
seed_variants = {
    "manifest_hash_bytes": manifest_hash_bytes,
    "sha256(manifest_hash_bytes)": hashlib.sha256(manifest_hash_bytes).digest(),
    "sha256(manifest_hash_hex)": hashlib.sha256(manifest_hash_hex.encode()).digest(),
    "sha256(pub_hash_bytes)": hashlib.sha256(pub_hash_bytes).digest(),
    "sha256(pub_hash_hex)": hashlib.sha256(pub_hash_hex.encode()).digest(),
    "sha256(manifest_hash + pub_hash)": hashlib.sha256(manifest_hash_bytes + pub_hash_bytes).digest(),
    "sha256(pub_hash + manifest_hash)": hashlib.sha256(pub_hash_bytes + manifest_hash_bytes).digest(),
}

for label, seed in seed_variants.items():
    if len(seed) < 32:
        continue
    variants_global.append((f"global {label} [:16] / [16:32]", seed[:16], seed[16:32]))

# Best-effort scan
print("=" * 70)
print("Global-key strategies")
print("=" * 70)
sample_first = None
for label, key, iv in variants_global:
    ok = 0
    sample = None
    for d in docs:
        r = try_decrypt(key, iv, d["Content"])
        if r:
            ok += 1
            if not sample:
                sample = r
    print(f"  {label:<55} ok={ok}/5")
    if ok > 0 and not sample_first:
        sample_first = sample

if sample_first:
    print(f"\n  sample[:200] = {sample_first[:200]!r}")
    quit()

# Per-document strategies
print()
print("=" * 70)
print("Per-document key strategies (meps_id endian + order combos)")
print("=" * 70)

best_label = None
best_sample = None
best_count = 0

for endian_label, endian in [("LE", "little"), ("BE", "big")]:
    for size in (4, 8):
        for order in ("meps_first", "manifest_first"):
            ok = 0
            sample = None
            label_done = False
            for d in docs:
                meps_bytes = int(d["MepsDocumentId"]).to_bytes(size, endian)
                if order == "meps_first":
                    seed_input = meps_bytes + manifest_hash_bytes
                else:
                    seed_input = manifest_hash_bytes + meps_bytes
                seed = hashlib.sha256(seed_input).digest()
                r = try_decrypt(seed[:16], seed[16:32], d["Content"])
                if r:
                    ok += 1
                    if not sample:
                        sample = r
            label = f"meps_{endian_label}{size}_{order}"
            print(f"  {label:<35} ok={ok}/5")
            if ok > best_count:
                best_count = ok
                best_label = label
                best_sample = sample

if best_sample:
    print(f"\n=== WINNER: {best_label}  ok={best_count}/5 ===")
    print(f"sample[:300] = {best_sample[:300].decode('utf-8', errors='replace')!r}")
else:
    print("\n=== No per-doc variant worked. ===")
    print("\nMaybe ALL 5 documents have Content length not divisible by 16?")
    for d in docs:
        print(f"  doc={d['DocumentId']}  len(Content)={len(d['Content'])}  %16={len(d['Content']) % 16}")
