"""Verify whether study-note data-pid maps to chapter-body paragraphs that contain verses."""
from pathlib import Path
import re
from bs4 import BeautifulSoup, Tag

html = Path('packages/jw-core/tests/fixtures/nwtsty_john3.html').read_text()
soup = BeautifulSoup(html, 'lxml')

print("=" * 70)
print("1. ALL <p data-pid> in chapter — which contain verses?")
print("=" * 70)

# Build paragraph_id -> [verse numbers]
para_to_verses: dict[str, list[int]] = {}
for p in soup.find_all('p', attrs={'data-pid': True}):
    if not isinstance(p, Tag):
        continue
    pid = p.get('data-pid')
    verses_inside: list[int] = []
    for span in p.find_all('span', class_='v'):
        m = re.match(r'v(\d+)-(\d+)-(\d+)-\d+', span.get('id', ''))
        if m:
            verses_inside.append(int(m.group(3)))
    if verses_inside:
        # Dedup preserving order
        seen = set()
        verses_inside = [v for v in verses_inside if not (v in seen or seen.add(v))]
        para_to_verses[pid] = verses_inside

print(f"  Chapter paragraphs with verses: {len(para_to_verses)}")
for pid, vs in list(para_to_verses.items())[:8]:
    print(f"    data-pid={pid!r:<6} verses={vs}")

print()
print("=" * 70)
print("2. STUDY NOTE inner <p> data-pid values")
print("=" * 70)

notes_data = []
for li in soup.find_all('li', class_='studyNote'):
    if not isinstance(li, Tag):
        continue
    head = li.find('strong')
    headword = head.get_text(strip=True).rstrip(':') if head else "?"
    # Inner <p> with data-pid
    inner_p = li.find('p', attrs={'data-pid': True})
    pid = inner_p.get('data-pid') if inner_p else None
    notes_data.append((headword[:40], pid))

print(f"  Total study notes: {len(notes_data)}")
print(f"  With inner <p data-pid>: {sum(1 for _, p in notes_data if p)}")
print()
for hw, pid in notes_data[:15]:
    chapter_verses = para_to_verses.get(pid, [])
    print(f"    headword={hw!r:<45}  note_pid={pid!r:<6}  chapter_pid_verses={chapter_verses}")

print()
print("=" * 70)
print("3. HYPOTHESIS CHECK: is the inner <p> id same as a chapter para?")
print("=" * 70)
# Maybe study note's data-pid IS the chapter paragraph it annotates.
# For 'Nicodemus' we expect verse 1 → which chapter pid contains v1?
v1_para = next(((pid, vs) for pid, vs in para_to_verses.items() if 1 in vs), None)
print(f"  Chapter para containing v1: {v1_para}")
# What's the Nicodemus note's data-pid?
nicodemus = next((p for h, p in notes_data if h.lower().startswith('nicodemus')), None)
print(f"  Nicodemus note data-pid: {nicodemus}")
print(f"  Match? {v1_para and nicodemus == v1_para[0]}")

# Try a few more
print()
for hw, pid in notes_data[:10]:
    chapter_v = para_to_verses.get(pid, [])
    match_indicator = "✓" if chapter_v else "✗"
    print(f"    {match_indicator}  {hw!r:<45} note_pid={pid!r:<6}  resolves_to_chapter_verses={chapter_v}")
