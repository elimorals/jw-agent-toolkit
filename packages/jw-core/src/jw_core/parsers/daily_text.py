"""Parser for the daily text on the wol.jw.org homepage.

The WOL 'today' page (/{iso}/wol/h/r1/{lp_tag}) embeds the day's verse,
reference, and a short commentary in a `<div class="todayItem">` (class name
varies by language/version; we look for several known selectors).
"""

from __future__ import annotations

from dataclasses import dataclass

from bs4 import BeautifulSoup


@dataclass
class DailyText:
    date: str  # Display date as shown on the page
    scripture: str  # Reference + verse text
    commentary: str  # Short paragraph following the verse


def parse_daily_text(html: str) -> DailyText | None:
    """Parse the daily text from a WOL 'today' homepage."""
    soup = BeautifulSoup(html, "lxml")
    container = soup.select_one(".todayItem") or soup.select_one(".dailyText") or soup.select_one("article.dailyText")
    if container is None:
        return None

    date_el = container.select_one(".itemHeader") or container.find("h2")
    date = date_el.get_text(" ", strip=True) if date_el else ""

    scripture_el = container.select_one(".themeScrp") or container.select_one("p.themeScrp")
    scripture = scripture_el.get_text(" ", strip=True) if scripture_el else ""

    commentary_el = container.select_one(".sb") or container.select_one("p:not(.themeScrp)")
    commentary = commentary_el.get_text(" ", strip=True) if commentary_el else ""

    if not (scripture or commentary):
        return None
    return DailyText(date=date, scripture=scripture, commentary=commentary)
