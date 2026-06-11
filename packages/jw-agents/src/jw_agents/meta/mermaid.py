"""Mermaid flowchart export for OrchestrationPlan (Fase 65 post-MVP)."""

from __future__ import annotations

from jw_agents.meta.models import OrchestrationPlan, OrchestrationResult


def _sanitize_label(text: str, *, max_len: int = 40) -> str:
    """Make a string safe inside a Mermaid node label."""
    cleaned = text.replace('"', "'").replace("\n", " ").strip()
    if len(cleaned) > max_len:
        cleaned = cleaned[: max_len - 1] + "…"
    return cleaned


def plan_to_mermaid(plan: OrchestrationPlan) -> str:
    """Render `plan` as a Mermaid `flowchart TD` definition.

    Each step is a node with `id["tool\\nrationale"]`; `depends_on` edges
    become `dep --> step`. Root nodes (no deps) also receive an implicit
    edge from a synthetic `start` node so the graph stays connected
    when viewed in mermaid.live.
    """

    lines: list[str] = ["flowchart TD"]
    title = _sanitize_label(plan.goal, max_len=60)
    lines.append(f'    start(("{title}"))')

    for step in plan.steps:
        tool = _sanitize_label(step.tool)
        rationale = _sanitize_label(step.rationale, max_len=60)
        if rationale:
            label = f"{tool}<br/>{rationale}"
        else:
            label = tool
        lines.append(f'    {step.id}["{label}"]')
        if not step.depends_on:
            lines.append(f"    start --> {step.id}")
        for dep in step.depends_on:
            lines.append(f"    {dep} --> {step.id}")

    return "\n".join(lines)


def result_to_mermaid(result: OrchestrationResult) -> str:
    """Same as `plan_to_mermaid` but colors steps by status.

    Failed / skipped steps get a red `:::error` class; OK steps get the
    default. Useful to visualize post-execution outcome.
    """

    plan = result.plan
    by_id = {r.step_id: r for r in result.step_results}

    lines = plan_to_mermaid(plan).splitlines()
    lines.append("")
    lines.append("    classDef error fill:#f99,stroke:#a00,color:#000;")
    lines.append("    classDef ok fill:#9f9,stroke:#0a0,color:#000;")

    for step in plan.steps:
        sr = by_id.get(step.id)
        if sr is None:
            continue
        klass = "error" if sr.error else "ok"
        lines.append(f"    class {step.id} {klass};")

    return "\n".join(lines)
