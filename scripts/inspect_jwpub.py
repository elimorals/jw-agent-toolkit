"""Inspect the internal structure of a JWPUB file (ZIP-of-ZIP + SQLite)."""
import io
import sqlite3
import zipfile
from pathlib import Path

PUB = Path("data/jwpub_test/ti_E.jwpub")
assert PUB.exists(), f"Need to download {PUB} first (run scripts/download_jwpub.py)"

print("=" * 70)
print(f"OUTER ZIP listing  ({PUB.name}, {PUB.stat().st_size:,} bytes)")
print("=" * 70)
with zipfile.ZipFile(PUB) as outer:
    for info in outer.infolist():
        print(f"  {info.file_size:>10,} bytes  {info.filename}")

print()
print("=" * 70)
print("MANIFEST.JSON content")
print("=" * 70)
with zipfile.ZipFile(PUB) as outer:
    manifest = outer.read("manifest.json").decode("utf-8")
    # Pretty print first 1500 chars
    import json
    parsed = json.loads(manifest)
    print(json.dumps(parsed, indent=2)[:1500])

print()
print("=" * 70)
print("INNER ZIP listing")
print("=" * 70)
with zipfile.ZipFile(PUB) as outer:
    # The 'contents' file is the inner ZIP
    inner_bytes = outer.read("contents")
    with zipfile.ZipFile(io.BytesIO(inner_bytes)) as inner:
        for info in inner.infolist():
            print(f"  {info.file_size:>10,} bytes  {info.filename}")

print()
print("=" * 70)
print("SQLite DB inspection")
print("=" * 70)
with zipfile.ZipFile(PUB) as outer:
    inner_bytes = outer.read("contents")
with zipfile.ZipFile(io.BytesIO(inner_bytes)) as inner:
    # Find the .db file
    db_name = next(n for n in inner.namelist() if n.endswith(".db"))
    print(f"  DB file: {db_name}")
    db_bytes = inner.read(db_name)

# Write to a temp file because sqlite3 needs a real path
tmp_db = Path("/tmp/inspect.db")
tmp_db.write_bytes(db_bytes)

conn = sqlite3.connect(tmp_db)
conn.row_factory = sqlite3.Row

print()
print("  Tables:")
for row in conn.execute(
    "SELECT name, sql FROM sqlite_master WHERE type='table' ORDER BY name"
):
    print(f"    - {row['name']}")

print()
print("  Document table sample (first 3 rows, Content truncated):")
cur = conn.execute("SELECT * FROM Document LIMIT 3")
columns = [d[0] for d in cur.description]
print(f"    columns: {columns}")
for row in cur:
    d = dict(row)
    if "Content" in d:
        content = d["Content"]
        d["Content"] = f"<{type(content).__name__}, len={len(content) if content else 0}>"
    print(f"    {d}")

print()
print("  Content raw bytes — first 64 bytes hex + ASCII:")
cur = conn.execute("SELECT Content FROM Document LIMIT 1")
first_content = cur.fetchone()[0]
print(f"    Content type: {type(first_content).__name__}")
print(f"    Length: {len(first_content) if first_content else 0}")
if first_content:
    head = first_content[:64]
    hex_part = " ".join(f"{b:02x}" for b in head)
    ascii_part = "".join(chr(b) if 32 <= b < 127 else "." for b in head)
    print(f"    HEX  : {hex_part}")
    print(f"    ASCII: {ascii_part}")

print()
print("  Check ContentLength vs len(Content)")
for row in conn.execute(
    "SELECT DocumentId, ContentLength, length(Content) AS actual FROM Document LIMIT 5"
):
    print(f"    id={row['DocumentId']}  declared={row['ContentLength']}  actual={row['actual']}")

print()
print("  All columns in Document:")
for col in conn.execute("PRAGMA table_info(Document)").fetchall():
    print(f"    {col}")

conn.close()
