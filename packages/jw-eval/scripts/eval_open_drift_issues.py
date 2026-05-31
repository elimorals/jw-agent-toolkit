"""Parse l2-live.json and open GitHub issues for failed cases.

Uses gh CLI through subprocess.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: eval_open_drift_issues.py <report.json>", file=sys.stderr)
        return 2
    data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    drifted = [
        r
        for r in data.get("results", [])
        if r["verdict"] in {"fail", "error"} and r["layer"] == "l2"
    ]
    if not drifted:
        print("No L2 drift detected.")
        return 0
    for r in drifted:
        title = f"[eval/l2 drift] case {r['case_id']}"
        body_lines = [
            f"**Case:** `{r['case_id']}`",
            f"**Verdict:** {r['verdict']}",
            "",
            "## Reasons",
            *[f"- {x}" for x in r.get("reasons", [])],
            "",
            "Refresh snapshot via `uv run python packages/jw-eval/scripts/build_eval_snapshots.py --force`.",
        ]
        try:
            subprocess.run(
                [
                    "gh",
                    "issue",
                    "create",
                    "--title",
                    title,
                    "--label",
                    "link-drift",
                    "--body",
                    "\n".join(body_lines),
                ],
                check=True,
            )
        except subprocess.CalledProcessError as exc:
            print(f"gh issue create failed for {r['case_id']}: {exc}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
