"""Verify whether publication codes in the Trinity page are linked (with non-'b' class)."""
from pathlib import Path
from collections import Counter
from bs4 import BeautifulSoup

html = Path("packages/jw-core/tests/fixtures/wt_pub_index_trinity.html").read_text()
soup = BeautifulSoup(html, "lxml")
article = soup.find("article", id="article")

print("=" * 70)
print("1. ALL anchor classes in article + count")
print("=" * 70)
class_count: Counter[str] = Counter()
for a in article.find_all("a"):
    classes = a.get("class") or []
    if classes:
        class_count[" ".join(classes)] += 1
    else:
        class_count["(no class)"] += 1
for cls, n in class_count.most_common(10):
    print(f"  {n:>5}  {cls}")

print()
print("=" * 70)
print("2. Sample anchors WITHOUT class='b' — what do they look like?")
print("=" * 70)
shown = 0
for a in article.find_all("a"):
    classes = a.get("class") or []
    if "b" in classes:
        continue
    text = a.get_text(" ", strip=True)
    href = a.get("href", "")
    if not text:
        continue
    print(f"  text={text!r:<35}  class={classes}  href={href[:60]}")
    shown += 1
    if shown >= 10:
        break

print()
print("=" * 70)
print("3. ANY publication-code-looking anchors? (text like 'g05 4/22 7' or 'w88')")
print("=" * 70)
import re
PUB_CODE_RE = re.compile(r"^\s*[a-z]+\d*\s+\d", re.IGNORECASE)
shown = 0
for a in article.find_all("a"):
    text = a.get_text(" ", strip=True)
    if PUB_CODE_RE.match(text) and shown < 12:
        classes = a.get("class") or []
        href = a.get("href", "")
        print(f"  text={text!r:<25}  class={classes}  href={href[:70]}")
        shown += 1

print()
print("=" * 70)
print("4. Parent paragraph of a publication-code anchor — full HTML")
print("=" * 70)
first_pubcode_anchor = next(
    (a for a in article.find_all("a")
     if PUB_CODE_RE.match(a.get_text(" ", strip=True))),
    None
)
if first_pubcode_anchor:
    parent = first_pubcode_anchor.find_parent("p")
    if parent:
        print(str(parent)[:600])
