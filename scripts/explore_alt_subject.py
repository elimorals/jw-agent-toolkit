"""Inspect the 'Religions, Customs, and Beliefs' subject page to find its format."""
from pathlib import Path
from bs4 import BeautifulSoup
from collections import Counter

html = Path("packages/jw-core/tests/fixtures/wt_pub_index_alt_1204387.html").read_text()
soup = BeautifulSoup(html, "lxml")
article = soup.find("article", id="article")

print("title:", (article.find("h1") or article.find("p", class_="st")).get_text(" ", strip=True))
print()

print("=" * 70)
print("Paragraph-level classes (top 15)")
print("=" * 70)
classes: list[str] = []
for p in article.find_all(["p", "div"], class_=True):
    classes.extend(p.get("class", []))
for c, n in Counter(classes).most_common(15):
    print(f"  {n:>5}  {c}")

print()
print("=" * 70)
print("First 12 direct child <p> elements in order")
print("=" * 70)
for i, p in enumerate(article.find_all("p")[:15], 1):
    cls = " ".join(p.get("class") or []) or "(none)"
    txt = p.get_text(" ", strip=True)[:100]
    n_anchors = len(p.find_all("a"))
    print(f"  {i:>3}. <p class={cls}>  anchors={n_anchors}  text={txt!r}")

print()
print("=" * 70)
print("Anchor classes seen on this page")
print("=" * 70)
a_classes: Counter[str] = Counter()
for a in article.find_all("a"):
    cls = " ".join(a.get("class") or [])
    a_classes[cls or "(no class)"] += 1
for cls, n in a_classes.most_common():
    print(f"  {n:>5}  {cls!r}")

print()
print("=" * 70)
print("Sample anchors on this page")
print("=" * 70)
for a in article.find_all("a")[:15]:
    text = a.get_text(" ", strip=True)[:50]
    href = a.get("href", "")[:70]
    cls = a.get("class") or []
    print(f"  class={cls!s:<15}  text={text!r:<52}  href={href}")
