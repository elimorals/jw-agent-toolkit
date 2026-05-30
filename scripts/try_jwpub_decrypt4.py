"""Try variations: raw deflate, offset zlib, maybe '-a' doesn't mean AES at all."""
from __future__ import annotations
import io
import json
import sqlite3
import zipfile
import zlib
from pathlib import Path

PUB = Path("data/jwpub_test/ti_E.jwpub")
with zipfile.ZipFile(PUB) as outer:
    inner_bytes = outer.read("contents")

with zipfile.ZipFile(io.BytesIO(inner_bytes)) as inner:
    db_name = next(n for n in inner.namelist() if n.endswith(".db"))
    db_bytes = inner.read(db_name)
Path("/tmp/inspect.db").write_bytes(db_bytes)

conn = sqlite3.connect("/tmp/inspect.db")
content = conn.execute("SELECT Content FROM Document LIMIT 1").fetchone()[0]
declared = conn.execute("SELECT ContentLength FROM Document LIMIT 1").fetchone()[0]
conn.close()

print(f"len(Content) = {len(content)}")
print(f"declared ContentLength = {declared}")
print(f"first 32 hex: {content[:32].hex()}")

# Try various decoder strategies
def try_each(label, fn):
    try:
        r = fn()
        print(f"  ✓ {label}  result len={len(r)}  first={r[:80]!r}")
    except Exception as e:
        print(f"  ✗ {label}  {type(e).__name__}: {e}")

print()
print("Try plain zlib decompression at various offsets:")
for off in (0, 1, 2, 4, 8, 16):
    try_each(f"zlib decompress @ off={off}", lambda o=off: zlib.decompress(content[o:]))

print()
print("Try raw deflate (wbits=-15):")
for off in (0, 1, 2, 4, 8, 16):
    try_each(
        f"raw deflate @ off={off}",
        lambda o=off: zlib.decompress(content[o:], wbits=-15),
    )

print()
print("Try gzip header (wbits=31):")
try_each("gzip", lambda: zlib.decompress(content, wbits=31))

print()
print("Inspect: is there a tag/length prefix?")
# Sometimes formats start with a 4-byte LE length
import struct
candidates = struct.unpack_from("<4I", content[:16])
print(f"  first 4x int32 LE: {candidates}")
candidates = struct.unpack_from(">4I", content[:16])
print(f"  first 4x int32 BE: {candidates}")
