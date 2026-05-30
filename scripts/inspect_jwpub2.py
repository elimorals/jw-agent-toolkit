"""Print the full manifest and look at JWPUB internal hash/key signals."""
import io
import json
import sqlite3
import zipfile
from pathlib import Path

PUB = Path("data/jwpub_test/ti_E.jwpub")

print("=" * 70)
print("FULL MANIFEST.JSON")
print("=" * 70)
with zipfile.ZipFile(PUB) as outer:
    manifest = outer.read("manifest.json").decode("utf-8")
parsed = json.loads(manifest)
print(json.dumps(parsed, indent=2))

print()
print("=" * 70)
print("Hash, publication symbol, mepsId — candidates for key derivation")
print("=" * 70)
print(f"  manifest.hash:     {parsed.get('hash')}")
print(f"  contentFormat:     {parsed.get('contentFormat')}")
pub_meta = parsed.get("publication", {})
print(f"  pub.symbol:        {pub_meta.get('symbol')}")
print(f"  pub.mepsLanguageIndex: {pub_meta.get('mepsLanguageIndex')}")
print(f"  pub.title:         {pub_meta.get('title')}")
print(f"  ALL pub fields:    {list(pub_meta.keys())}")

print()
print("=" * 70)
print("publication.* — look for keys / mepsId")
print("=" * 70)
for k, v in pub_meta.items():
    s = str(v)
    if len(s) < 200:
        print(f"  {k}: {v}")
