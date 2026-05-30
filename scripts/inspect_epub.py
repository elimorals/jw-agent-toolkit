"""Inspect EPUB structure (standard format — should Just Work)."""
import zipfile
from pathlib import Path

EPUB = Path("data/epub_test/bh_E.epub")

print(f"EPUB: {EPUB.name}  {EPUB.stat().st_size:,} bytes")
print("=" * 70)
with zipfile.ZipFile(EPUB) as z:
    print("Files (first 30):")
    for info in z.infolist()[:30]:
        print(f"  {info.file_size:>10,}  {info.filename}")

    print()
    print("META-INF/container.xml:")
    print(z.read("META-INF/container.xml").decode("utf-8")[:500])

    # Find the OPF
    import re
    container = z.read("META-INF/container.xml").decode("utf-8")
    m = re.search(r'full-path="([^"]+)"', container)
    opf_path = m.group(1) if m else None
    print(f"\nOPF path: {opf_path}")

    if opf_path:
        opf = z.read(opf_path).decode("utf-8")
        print(f"\nOPF size: {len(opf):,} chars")
        print("OPF preview (first 1200 chars):")
        print(opf[:1200])
