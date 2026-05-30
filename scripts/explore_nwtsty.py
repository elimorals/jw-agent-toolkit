"""Map study notes / cross-refs to verses by walking the DOM context."""
from pathlib import Path
from bs4 import BeautifulSoup, Tag

html = Path('packages/jw-core/tests/fixtures/nwtsty_john3.html').read_text()
soup = BeautifulSoup(html, 'lxml')

print("=" * 70)
print("STUDY NOTE GROUPS — anchor IDs")
print("=" * 70)
for grp in soup.select('div.studyNoteGroup')[:5]:
    grp_id = grp.get('id', '<no id>')
    notes = grp.find_all('li', class_='studyNote')
    print(f"\n  group id={grp_id!r}  ({len(notes)} notes)")
    for note in notes[:2]:
        nid = note.get('id', '')
        h = note.find('strong')
        head = h.get_text(strip=True) if h else note.get_text(' ', strip=True)[:40]
        print(f"    note id={nid!r}  headword={head!r}")

print()
print("=" * 70)
print("STUDY NOTE FULL ATTRIBUTES + HEAD HTML")
print("=" * 70)
note = soup.find('li', class_='studyNote')
if note:
    attrs = {k: v for k, v in note.attrs.items()}
    print(f"  attrs: {attrs}")
    print(f"\n  HTML head 800 chars:")
    print(str(note)[:800])

print()
print("=" * 70)
print("PARAGRAPHS → verse spans contained")
print("=" * 70)
for p in soup.find_all('p', attrs={'data-pid': True})[:3]:
    verses_in = p.find_all('span', class_='v')
    pids = [v.get('id') for v in verses_in]
    print(f"  <p data-pid={p['data-pid']}>  verses: {pids}")

print()
print("=" * 70)
print("CROSS-REF MARKERS — class='marker' or class='b'?")
print("=" * 70)
markers = soup.find_all('span', class_='marker')[:5]
print(f"  Found {len(markers)} class='marker' spans")
for m in markers:
    parent_a = m.find_parent('a')
    print(f"  m.class={m.get('class')}  text={m.get_text(strip=True)[:30]!r}  parent_href={parent_a.get('href') if parent_a else None}")

print()
print("=" * 70)
print("HOW DO CROSS-REFS HANG OFF A VERSE? — find an a.b inside a verse span")
print("=" * 70)
v = soup.find('span', class_='v')
if v:
    refs = v.find_all('a', class_='b')[:5]
    print(f"  Verse {v.get('id')!r}: {len(refs)} cross-refs inside")
    for r in refs:
        print(f"    href={r.get('href')!r}  text={r.get_text(strip=True)!r}")

print()
print("=" * 70)
print("STUDY NOTE WITH VERSE ID — does the note ID encode the verse?")
print("=" * 70)
for note in soup.find_all('li', class_='studyNote')[:5]:
    print(f"  id={note.get('id')!r}")
