"""Detailed exploration of the Trinity subject page to design the parser."""
from pathlib import Path
from bs4 import BeautifulSoup, Tag
import re

html = Path("packages/jw-core/tests/fixtures/wt_pub_index_trinity.html").read_text()
soup = BeautifulSoup(html, "lxml")
article = soup.find("article", id="article")

print("=" * 70)
print("1. PARAGRAPH-LEVEL classes inside article")
print("=" * 70)
for p in article.find_all(["p", "h2", "h3", "h4"], class_=True)[:25]:
    cls = " ".join(p.get("class", []))
    text = p.get_text(" ", strip=True)[:80]
    print(f"  <{p.name} class={cls!r}>  text={text!r}")

print()
print("=" * 70)
print("2. STRUCTURE OF A SUBHEADING + CITATIONS BLOCK")
print("=" * 70)
# Subheadings likely have a distinct class. Look for the immediate children of article.
for el in article.find_all(recursive=False)[:5]:
    print(f"  direct child <{el.name} class={el.get('class')}>")
    for sub in el.find_all(recursive=False)[:5]:
        print(f"    <{sub.name} class={sub.get('class')}>  text[:60]={sub.get_text(' ', strip=True)[:60]!r}")

print()
print("=" * 70)
print("3. CITATION ANCHORS — full attribute dump for the first 6")
print("=" * 70)
for a in article.find_all("a", class_="b")[:6]:
    attrs = {k: v for k, v in a.attrs.items()}
    text = a.get_text(strip=True)
    # parent context
    parent = a.parent
    parent_class = parent.get("class") if parent else None
    print(f"  attrs={attrs}  text={text!r}  parent.class={parent_class}")

print()
print("=" * 70)
print("4. Subheading PRE-context — what wraps a group of citations?")
print("=" * 70)
# Find first citation
first_cit = article.find("a", class_="b")
if first_cit:
    # Walk parents until we find a header-ish container
    chain = []
    parent = first_cit.parent
    for _ in range(8):
        if not parent:
            break
        chain.append((parent.name, parent.get("class"), parent.get("id")))
        parent = parent.parent
    print("  Ancestor chain of first citation:")
    for name, cls, pid in chain:
        print(f"    <{name} class={cls} id={pid}>")

print()
print("=" * 70)
print("5. Find headings/subheadings: any text that ends with ; or is bold near citations")
print("=" * 70)
# Subheadings likely <p class="sg"> or similar (since "su" is subheading?)
for cls in ("sg", "sh", "su", "ss", "sb", "h", "subhead"):
    matches = article.find_all(class_=cls)
    if matches:
        print(f"  class={cls!r}  count={len(matches)}")
        for m in matches[:3]:
            print(f"    text={m.get_text(' ', strip=True)[:80]!r}")

print()
print("=" * 70)
print("6. Walk article: emit each top-level paragraph in order with its class")
print("=" * 70)
content_div = article.find("div", id="content") or article
for i, el in enumerate(content_div.find_all(["p", "h1", "h2", "h3"], recursive=True)[:25], 1):
    cls = " ".join(el.get("class") or [])
    txt = el.get_text(" ", strip=True)[:100]
    print(f"  {i:>3}. <{el.name} class={cls}>  {txt!r}")
