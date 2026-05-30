"""Slide-deck generator from a talk outline.

VISION.md: "Generación de slides/gráficos para discursos".

Two output flavors:

  - `simple` → plain Markdown with `---` separators (works in any
    Markdown viewer or static site generator).
  - `marp`   → Marp-compatible Markdown with directives, so you can
    render with `marp deck.md` to a PDF/PPTX/HTML.

Input is a structured outline — we explicitly keep the LLM out of slide
SYNTHESIS, the LLM just supplies the outline content.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SlideDeck:
    title: str
    subtitle: str = ""
    sections: list[dict[str, object]] = field(default_factory=list)
    theme: str = "default"
    language: str = "en"

    def render(self, fmt: str = "marp") -> str:
        if fmt == "marp":
            return build_marp_deck(self)
        return build_simple_deck(self)


def build_simple_deck(deck: SlideDeck) -> str:
    """Plain Markdown with H1 per slide and `---` between slides."""
    parts: list[str] = []
    # Title slide
    parts.append(f"# {deck.title}")
    if deck.subtitle:
        parts.append(f"\n_{deck.subtitle}_")
    parts.append("\n---\n")
    for section in deck.sections:
        parts.append(_render_section(section, marp=False))
        parts.append("\n---\n")
    return "\n".join(parts).rstrip("- \n")


def build_marp_deck(deck: SlideDeck) -> str:
    """Marp Markdown — paste into a `.md` file and run `marp deck.md`."""
    header = (
        "---\n"
        "marp: true\n"
        f"theme: {deck.theme}\n"
        "paginate: true\n"
        f"lang: {deck.language}\n"
        "---\n\n"
    )
    parts: list[str] = [header]
    parts.append(f"# {deck.title}\n")
    if deck.subtitle:
        parts.append(f"\n{deck.subtitle}\n")
    parts.append("\n---\n\n")
    for section in deck.sections:
        parts.append(_render_section(section, marp=True))
        parts.append("\n---\n\n")
    return "".join(parts).rstrip("- \n")


def _render_section(section: dict[str, object], *, marp: bool) -> str:
    heading = section.get("heading", "")
    bullets = section.get("bullets", []) or []
    citation = section.get("citation", "")
    note = section.get("speaker_note", "")
    out: list[str] = [f"## {heading}\n"]
    for b in bullets:
        out.append(f"- {b}")
    if citation:
        out.append(f"\n_{citation}_")
    if marp and note:
        out.append(f"\n<!-- speaker: {note} -->")
    return "\n".join(out)


def outline_to_deck(
    *,
    title: str,
    subtitle: str = "",
    points: list[dict[str, object]],
    language: str = "en",
    theme: str = "default",
) -> SlideDeck:
    """Convenience: build a `SlideDeck` from an outline (intro / points / conclusion).

    `points` is the list emitted by `public_talk_outline_agent` metadata.
    """
    sections = []
    for p in points:
        sections.append(
            {
                "heading": p.get("heading", ""),
                "bullets": p.get("bullets", []),
                "citation": p.get("citation", ""),
                "speaker_note": p.get("speaker_note", ""),
            }
        )
    return SlideDeck(
        title=title,
        subtitle=subtitle,
        sections=sections,
        language=language,
        theme=theme,
    )
