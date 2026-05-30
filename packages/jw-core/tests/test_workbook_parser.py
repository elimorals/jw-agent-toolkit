"""Smoke tests for the workbook + Watchtower study parsers."""

from __future__ import annotations

from datetime import date

from jw_core.parsers.watchtower_study import parse_watchtower_study
from jw_core.parsers.workbook import (
    parse_workbook_week,
    watchtower_study_pub_code_for_date,
    workbook_pub_code_for_date,
)

WORKBOOK_HTML = """
<html><body>
  <article>
    <h1>PROVERBS 1-3</h1>
    <p>Song 38</p>
    <h2>Treasures From God's Word</h2>
    <h3>'Trust in Jehovah With All Your Heart' (10 min)</h3>
    <p>Discuss Pr 3:5-6. Highlight the practical application.</p>
    <h2>Apply Yourself to the Field Ministry</h2>
    <h3>Initial Call: Video (3 min)</h3>
    <p>Show the video and reset.</p>
    <h2>Living as Christians</h2>
    <h3>Congregation Bible Study (30 min)</h3>
    <p>jy chapter 110, paragraphs 1-7.</p>
    <p>Song 90 and closing prayer.</p>
  </article>
</body></html>
"""

WT_HTML = """
<html><body>
  <article id="article">
    <h1>How Joy Helps Us Endure</h1>
    <p class="themeScrp">'The joy of Jehovah is your stronghold.' — Nehemiah 8:10.</p>
    <p class="lead">Joy is not optional for Christians; it is a gift from Jehovah.</p>
    <p data-pid="1">1. Joy is one of the fruitages of God's spirit. <a class="b" href="#">Galatians 5:22</a></p>
    <p class="qu">What is joy, and how does it differ from happiness?</p>
    <p data-pid="2">2. Endurance becomes lighter when joy is present.</p>
    <p class="qu">How does joy strengthen our endurance?</p>
  </article>
</body></html>
"""


def test_workbook_code_helpers() -> None:
    assert workbook_pub_code_for_date(date(2026, 3, 15)) == "mwb26.03"
    # April → still March issue (bimonthly).
    assert workbook_pub_code_for_date(date(2026, 4, 10)) == "mwb26.03"
    # Watchtower studied today was printed two months earlier.
    assert watchtower_study_pub_code_for_date(date(2026, 5, 1)) == "w26.03"
    # Year rollover.
    assert watchtower_study_pub_code_for_date(date(2026, 1, 5)) == "w25.11"


def test_workbook_parser_extracts_sections() -> None:
    week = parse_workbook_week(
        WORKBOOK_HTML,
        pub_code="mwb26.03",
        language="en",
        source_url="https://wol.jw.org/x",
    )
    assert week.bible_reading == "PROVERBS 1-3"
    assert week.song_opening == 38
    names = [s.name for s in week.sections]
    assert "treasures" in names
    assert "apply_yourself" in names
    assert "living_as_christians" in names
    treasures = week.section("treasures")
    assert treasures is not None
    assert treasures.assignments
    first = treasures.assignments[0]
    assert first.minutes == 10
    assert "Pr 3:5-6" in first.body


def test_watchtower_parser_extracts_paragraphs() -> None:
    study = parse_watchtower_study(WT_HTML, pub_code="w26.03", language="en")
    assert study.title.lower().startswith("how joy")
    assert study.theme_scripture.startswith("'The joy")
    nums = [p.number for p in study.paragraphs]
    assert 1 in nums and 2 in nums
    p1 = next(p for p in study.paragraphs if p.number == 1)
    assert "Galatians 5:22" in p1.scripture_refs
    assert any("joy" in q.lower() for q in p1.questions)


def test_comment_synthesis() -> None:
    from jw_agents.workbook_helper import synthesize_comments

    study = parse_watchtower_study(WT_HTML, pub_code="w26.03", language="en")
    p1 = study.paragraphs[0]
    comments = synthesize_comments(p1, study=study, language="en", max_comments=2)
    assert len(comments) == 2
    assert all(c.script for c in comments)
    assert comments[0].angle == "main_point"
