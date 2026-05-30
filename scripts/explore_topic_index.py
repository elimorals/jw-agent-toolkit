"""Inspect Pub Index fixtures to design parsers."""
from pathlib import Path
from bs4 import BeautifulSoup, Tag

FIXTURES = Path("packages/jw-core/tests/fixtures")


def explore(name: str) -> None:
    print("\n" + "=" * 70)
    print(f"{name}")
    print("=" * 70)
    html = (FIXTURES / name).read_text()
    soup = BeautifulSoup(html, "lxml")

    title_el = soup.select_one("h1") or soup.find("title")
    print(f"  title: {title_el.get_text(strip=True) if title_el else '(none)'}")

    # Article container
    art = soup.find("article", id="article")
    if not art:
        print("  no <article id='article'> — abort")
        return

    # Most frequent class names inside the article
    from collections import Counter
    classes: list[str] = []
    for el in art.find_all(class_=True):
        cls = el.get("class") or []
        classes.extend(cls)
    print("  top 15 classes in article:")
    for c, n in Counter(classes).most_common(15):
        print(f"    {n:>5}  {c}")

    # Look at the first 8 anchor hrefs as a sample
    print(f"\n  first 12 internal anchors in article:")
    for a in art.find_all("a", href=True)[:12]:
        href = a.get("href", "")
        text = a.get_text(" ", strip=True)[:60]
        print(f"    {text!r:<62}  →  {href}")


for n in ("wt_pub_index_home.html", "wt_pub_index_trinity.html", "wt_research_guide.html"):
    explore(n)
