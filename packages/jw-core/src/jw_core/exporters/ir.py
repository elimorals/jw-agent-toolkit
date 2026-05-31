"""StudySheet — the single intermediate representation consumed by every exporter.

Conversion `AgentResult → StudySheet` happens here and ONLY here. Every
exporter consumes a StudySheet directly, never an AgentResult.

Why a separate IR:
    - Decouples "what to render" from "how to render".
    - Lets us swap the upstream shape (AgentResult, future agents, scraped
      data) without rewriting four exporters.
    - Tests for exporters are fully synthetic (no agent execution needed).
"""

from __future__ import annotations

from typing import Any, TYPE_CHECKING, Literal

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from jw_agents.base import AgentResult

CitationStyle = Literal["inline-paren", "footnote", "bibliography"]

_MAX_TITLE = 80
_MAX_HEADING = 100

_AGENT_SUBTITLES = {
    "apologetics": "Análisis apologético",
    "verse_explainer": "Explicación del versículo",
    "research_topic": "Investigación temática",
    "meeting_helper": "Preparación de reunión",
    "workbook_helper": "Guía de actividad",
    "conversation_assistant": "Asistente de conversación",
    "presentation_builder": "Presentación",
    "public_talk_outline": "Discurso público — bosquejo",
    "reverse_citation_lookup": "Cita inversa",
    "study_conductor": "Conductor del estudio",
    "student_part_helper": "Parte del estudiante",
    "letter_composer": "Composición de carta",
    "life_topics": "Tema de vida",
}


class CitationIR(BaseModel):
    """Citation normalized for every exporter."""

    url: str
    title: str = ""
    kind: str = ""
    short_label: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class StudySection(BaseModel):
    """One section of the study sheet."""

    heading: str
    body: str
    excerpt: str = ""
    citations: list[CitationIR] = Field(default_factory=list)


class StudySheet(BaseModel):
    """Intermediate representation. All exporters consume this."""

    title: str
    subtitle: str = ""
    language: str = "es"
    sections: list[StudySection] = Field(default_factory=list)
    footer_note: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_agent_result(
        cls,
        result: "AgentResult | dict[str, Any]",
        *,
        title: str | None = None,
        language: str | None = None,
        include_citations: bool = True,
    ) -> StudySheet:
        """Single conversion AgentResult (or its dict form) → StudySheet."""

        if isinstance(result, dict):
            data = result
        else:
            data = result.to_dict()

        # ── title ──
        if title:
            final_title = title
        else:
            md_title = data.get("metadata", {}).get("title")
            final_title = md_title or data.get("query", "(sin título)")
        if len(final_title) > _MAX_TITLE:
            final_title = final_title[: _MAX_TITLE - 1].rstrip() + "…"

        # ── subtitle ──
        agent_name = data.get("agent_name", "")
        subtitle = _AGENT_SUBTITLES.get(agent_name, agent_name)

        # ── language ──
        lang = language or data.get("metadata", {}).get("language", "es")

        # ── sections ──
        sections: list[StudySection] = []
        for f in data.get("findings", []):
            summary = (f.get("summary") or "").strip()
            heading = summary.splitlines()[0] if summary else "(sin resumen)"
            if len(heading) > _MAX_HEADING:
                heading = heading[: _MAX_HEADING - 1].rstrip() + "…"

            citations: list[CitationIR] = []
            if include_citations:
                cite_raw = f.get("citation") or {}
                if cite_raw.get("url"):
                    citations.append(_citation_from_dict(cite_raw))

            sections.append(
                StudySection(
                    heading=heading,
                    body=summary,
                    excerpt=(f.get("excerpt") or "").strip(),
                    citations=citations,
                )
            )

        if not sections:
            sections.append(
                StudySection(
                    heading="(sin resultados)",
                    body="El agente no devolvió resultados.",
                )
            )

        # ── footer (warnings + provenance) ──
        warnings = data.get("warnings", []) or []
        footer_parts: list[str] = []
        if warnings:
            footer_parts.append("Advertencias: " + " · ".join(warnings))
        footer_parts.append("Generado por jw-agent-toolkit.")
        footer_note = "\n".join(footer_parts)

        return cls(
            title=final_title,
            subtitle=subtitle,
            language=lang,
            sections=sections,
            footer_note=footer_note,
            metadata=data.get("metadata", {}),
        )


def _citation_from_dict(raw: dict[str, Any]) -> CitationIR:
    """Map a serialized Citation dict to CitationIR, building a short_label."""

    title = (raw.get("title") or "").strip()
    kind = (raw.get("kind") or "").strip()
    meta = raw.get("metadata") or {}

    # Build a compact label. Verses prefer the title (e.g. "Juan 3:16");
    # articles use truncated title; default = URL host + last path segment.
    short = ""
    if kind == "verse" and title:
        short = title
    elif title:
        short = title if len(title) <= 60 else title[:59] + "…"
    else:
        url = raw.get("url", "")
        short = url.rsplit("/", 1)[-1] if url else ""

    return CitationIR(
        url=raw.get("url", ""),
        title=title,
        kind=kind,
        short_label=short,
        metadata=meta,
    )
