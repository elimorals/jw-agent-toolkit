"""Markdown export for a SparSession transcript (Fase 66 post-MVP)."""

from __future__ import annotations

from jw_agents.spar.models import SparSession


def to_markdown(session: SparSession) -> str:
    """Render a `SparSession` as a self-contained Markdown transcript."""

    p = session.persona
    lines: list[str] = [
        f"# Sparring session - {p.display_name}",
        "",
        f"- **session_id**: `{session.session_id}`",
        f"- **persona**: `{p.key}` ({p.display_name}, tone={p.tone})",
        f"- **language**: `{session.language}`",
        f"- **started_at**: {session.started_at}",
        f"- **closed**: {session.closed}",
        "",
        "> PRÁCTICA - esto NO es una visita real.",
        "",
        "## Turnos",
        "",
    ]

    pairs = zip(
        session.user_turns, session.persona_turns, strict=False
    )
    for idx, (user, persona) in enumerate(pairs):
        lines.append(f"### Turno {idx + 1}")
        lines.append("")
        lines.append(f"**Visitante**: {user.text}")
        lines.append("")
        lines.append(f"**{p.display_name}**: {persona.reply}")
        if persona.hidden_doubts:
            lines.append("")
            lines.append("Dudas internas (no expresadas):")
            for d in persona.hidden_doubts:
                lines.append(f"- {d}")
        lines.append("")

    if len(session.persona_turns) > len(session.user_turns):
        # Stray persona turns (shouldn't happen) -> render anyway
        for extra in session.persona_turns[len(session.user_turns) :]:
            lines.append("**Persona (extra)**: " + extra.reply)
            lines.append("")

    if session.feedback:
        lines.append("## Feedback")
        lines.append("")
        for fb in session.feedback:
            lines.append(
                f"- Turno {fb.user_turn_index + 1}: "
                f"citation={fb.citation_quality} nli={fb.nli_verdict}"
                + (
                    f" - sugerencia: {fb.suggested_phrasing}"
                    if fb.suggested_phrasing
                    else ""
                )
            )
        lines.append("")

    if session.score_summary:
        lines.append("## Score summary")
        lines.append("")
        for k, v in session.score_summary.items():
            lines.append(f"- **{k}**: {v}")
        lines.append("")

    return "\n".join(lines)
