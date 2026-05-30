"""Live validation of the Module 1 pipeline against jw.org.

Run:
    chflags nohidden .venv/lib/python3.13/site-packages/editable_impl_jw_*.pth
    .venv/bin/python scripts/live_test_phase11.py
"""

from __future__ import annotations

import asyncio
from datetime import date

from jw_agents.workbook_helper import workbook_helper


async def main() -> None:
    print("\n=== Probing real jw.org (workbook + WT) ===\n")
    target = date(2024, 5, 13)  # Monday in the May-June 2024 workbook
    result = await workbook_helper(
        target_date=target.isoformat(),
        language="en",
        include_watchtower=True,
        include_comments=True,
        comments_per_paragraph=1,
    )
    print(f"week_of: {result.metadata.get('week_of')}")
    print(f"workbook_issue: {result.metadata.get('workbook_issue')}")
    print(f"watchtower_issue: {result.metadata.get('watchtower_issue')}")
    print(f"warnings: {result.warnings}")
    print(f"finding count: {len(result.findings)}")
    print("\nFirst 8 findings:")
    for f in result.findings[:8]:
        print(f"  • [{f.metadata.get('source','')}] {f.summary[:80]}")
    print("\nSection breakdown:")
    sections = [f for f in result.findings if f.metadata.get("source") == "workbook_week"]
    assignments = [f for f in result.findings if f.metadata.get("source") == "workbook_assignment"]
    print(f"  week findings={len(sections)} assignments={len(assignments)}")


if __name__ == "__main__":
    asyncio.run(main())
