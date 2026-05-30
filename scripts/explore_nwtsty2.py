"""Second exploration: figure out verse↔study-note association + cross-ref panel format."""
from pathlib import Path
from bs4 import BeautifulSoup
import asyncio
import httpx

html = Path('packages/jw-core/tests/fixtures/nwtsty_john3.html').read_text()
soup = BeautifulSoup(html, 'lxml')

print("=" * 70)
print("ALL VERSE SPANS — count and order")
print("=" * 70)
verses = soup.find_all('span', class_='v')
print(f"  total .v spans: {len(verses)}")
# Group by verse id pattern v{book}-{ch}-{verse}-{instance}
import re
by_verse = {}
for v in verses:
    vid = v.get('id', '')
    m = re.match(r'v(\d+)-(\d+)-(\d+)-(\d+)', vid)
    if m:
        book, ch, vnum, inst = m.groups()
        key = (int(book), int(ch), int(vnum))
        by_verse.setdefault(key, []).append(v)
print(f"  unique (book, ch, verse) tuples: {len(by_verse)}")
print(f"  first 3 verses: {list(by_verse)[:3]}")
# Verse 1 first instance
key = (43, 3, 1)
if key in by_verse:
    v = by_verse[key][0]
    text = v.get_text(' ', strip=True)
    print(f"\n  Verse 43:3:1 text:\n    {text[:200]!r}")

print()
print("=" * 70)
print("STUDY NOTES — find verse association via header above each group")
print("=" * 70)
# Maybe there's a parent or sibling with the verse number
groups = soup.select('div.studyNoteGroup')
for grp in groups[:5]:
    # Headword
    note = grp.find('li', class_='studyNote')
    if not note:
        continue
    head = note.find('strong')
    headword = head.get_text(strip=True) if head else "?"
    # Walk ancestors looking for verse hint
    parent = grp
    verse_hint = None
    for _ in range(5):
        parent = parent.parent
        if not parent:
            break
        if 'id' in parent.attrs and parent['id'].startswith('chapter'):
            verse_hint = parent['id']
            break
    print(f"  headword={headword!r:<30}  parent_chapter_id={verse_hint}")

print()
print("=" * 70)
print("STUDY NOTES position 1..N — try to map to verses by appearance order")
print("=" * 70)
# Build verse → text map and try to match each headword to verse text
verse_text = {}
for (book, ch, vnum), spans in by_verse.items():
    verse_text[vnum] = " ".join(s.get_text(' ', strip=True) for s in spans).lower()

note_to_verse = []
for grp in groups[:15]:
    note = grp.find('li', class_='studyNote')
    if not note:
        continue
    head = note.find('strong')
    if not head:
        continue
    headword = head.get_text(strip=True).rstrip(':').lower()
    # Look up first verse number that contains this headword
    found = None
    for vnum, txt in sorted(verse_text.items()):
        if headword in txt:
            found = vnum
            break
    note_to_verse.append((headword[:40], found))

for hw, v in note_to_verse[:15]:
    print(f"  v={v}  headword={hw!r}")

print()
print("=" * 70)
print("CROSS-REF PANEL — what does the /bc/ URL return?")
print("=" * 70)
# Sample one inline cross-ref URL and see its response
ref_url = "https://wol.jw.org/en/wol/bc/r1/lp-e/1001070147/77"

async def fetch_xref(url):
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True,
                                 headers={"User-Agent": "Mozilla/5.0"}) as c:
        r = await c.get(url)
        return r.status_code, r.text[:1500]

status, body = asyncio.run(fetch_xref(ref_url))
print(f"  GET {ref_url}")
print(f"  status: {status}")
print(f"  body[:1500]:")
print(body)
