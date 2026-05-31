"""Report serializers for SuiteReport."""

from __future__ import annotations

from jw_eval.models import SuiteReport


def to_json(report: SuiteReport) -> str:
    return report.model_dump_json(indent=2)


def to_markdown(report: SuiteReport) -> str:
    lines: list[str] = []
    lines.append("# jw-eval report")
    lines.append("")
    lines.append(f"- **Started:** {report.started_at.isoformat()}")
    lines.append(f"- **Finished:** {report.finished_at.isoformat()}")
    lines.append(f"- **Layers run:** {', '.join(report.layers_run)}")
    lines.append("")

    lines.append("## Summary")
    lines.append("")
    lines.append("| Layer | pass | fail | skip | error |")
    lines.append("|---|---|---|---|---|")
    for layer, counts in sorted(report.summary.items()):
        lines.append(
            f"| {layer} | {counts.get('pass', 0)} | {counts.get('fail', 0)} | "
            f"{counts.get('skip', 0)} | {counts.get('error', 0)} |"
        )
    lines.append("")

    fails = [r for r in report.results if r.verdict in {"fail", "error"}]
    if fails:
        lines.append(f"## Failures ({len(fails)})")
        lines.append("")
        for r in fails:
            score = f" score={r.score:.3f}" if r.score is not None else ""
            lines.append(f"### `{r.case_id}` ({r.layer}, {r.verdict}{score})")
            for reason in r.reasons:
                lines.append(f"- {reason}")
            lines.append("")
    else:
        lines.append("All cases passed.")
        lines.append("")

    lines.append("## All results")
    lines.append("")
    lines.append("| case_id | layer | verdict | score | duration_ms |")
    lines.append("|---|---|---|---|---|")
    for r in report.results:
        score = f"{r.score:.2f}" if r.score is not None else "—"
        lines.append(f"| {r.case_id} | {r.layer} | {r.verdict} | {score} | {r.duration_ms} |")
    return "\n".join(lines) + "\n"
