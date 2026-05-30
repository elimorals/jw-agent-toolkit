"""Find a robust anchor for verse-to-study-note mapping."""
from pathlib import Path
import re
from bs4 import BeautifulSoup, Tag

html = Path('packages/jw-core/tests/fixtures/nwtsty_john3.html').read_text()
soup = BeautifulSoup(html, 'lxml')

print("=" * 70)
print("1. studyNoteGroup → does it have its own id or data-* with verse?")
print("=" * 70)
for grp in soup.select('div.studyNoteGroup')[:5]:
    print(f"  attrs: {dict(grp.attrs)}")

print()
print("=" * 70)
print("2. Anchors INSIDE the study note that link back to a verse")
print("=" * 70)
for li in soup.find_all('li', class_='studyNote')[:6]:
    head = li.find('strong')
    headword = head.get_text(strip=True).rstrip(':') if head else "?"
    # Look for any link with 'v=' or 'verse' in href
    links = li.find_all('a', href=True)
    verse_link = None
    for a in links:
        href = a.get('href', '')
        if 'v=' in href or re.search(r'/\d+/\d+/\d+', href):
            verse_link = href
            break
    print(f"  {headword[:35]:<37} first_link_with_verse={verse_link!r}")

print()
print("=" * 70)
print("3. WALK parents — does any ancestor have data-pid or id encoding verse?")
print("=" * 70)
for li in soup.find_all('li', class_='studyNote')[:5]:
    head = li.find('strong')
    headword = head.get_text(strip=True).rstrip(':') if head else "?"
    chain = []
    parent = li.parent
    for _ in range(6):
        if not parent:
            break
        chain.append(f"{parent.name}[{parent.get('class', '')!r}]")
        if parent.get('id') or parent.get('data-rsid') or parent.get('data-pid'):
            chain.append(f"  → id={parent.get('id')} data-rsid={parent.get('data-rsid')} data-pid={parent.get('data-pid')}")
        parent = parent.parent
    print(f"  {headword[:30]:<32}  parents: " + " > ".join(chain[:4]))

print()
print("=" * 70)
print("4. Search for OTHER attributes on studyNote li")
print("=" * 70)
for li in soup.find_all('li', class_='studyNote')[:6]:
    attrs = dict(li.attrs)
    # remove class
    attrs.pop('class', None)
    head = li.find('strong')
    headword = head.get_text(strip=True).rstrip(':') if head else "?"
    print(f"  {headword[:30]:<32}  attrs={attrs}")
    # Look inside for any data-* attrs
    for el in li.find_all(True):
        for k in el.attrs:
            if k.startswith('data-') and k != 'data-pid':
                print(f"      child {el.name}: {k}={el.attrs[k]!r}")
                break
        else:
            continue
        break

print()
print("=" * 70)
print("5. Are study notes RENDERED next to verse anchors in DOM order?")
print("=" * 70)
# Find each verse's position and study note positions
els_in_order = []
for el in soup.find_all(['span', 'li']):
    if el.name == 'span' and 'v' in (el.get('class') or []):
        m = re.match(r'v(\d+)-(\d+)-(\d+)-1', el.get('id', ''))  # only first instance
        if m:
            els_in_order.append(('verse', int(m.group(3)), el.sourceline if hasattr(el, 'sourceline') else 0))
    elif el.name == 'li' and 'studyNote' in (el.get('class') or []):
        head = el.find('strong')
        hw = head.get_text(strip=True).rstrip(':') if head else "?"
        els_in_order.append(('note', hw[:30], el.sourceline if hasattr(el, 'sourceline') else 0))

print(f"  Total interleaved elements (first 25):")
for kind, ident, line in els_in_order[:25]:
    print(f"    {kind:<6}  {ident!s:<35}  line={line}")
