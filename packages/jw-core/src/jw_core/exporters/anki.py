"""Anki exporter via genanki.

GUID strategy (stable across re-exports):
    guid = sha256(sheet.title + section.heading + section.body[:200])
This means re-exporting the same StudySheet after a typo fix UPDATES the
existing note in Anki instead of duplicating it. Only meaningful changes
to heading/body produce a new note.

Deck and model IDs are also derived from sheet.title via sha256, so the
same deck always lands in the same place in Anki's tree.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from jw_core.exporters.errors import MissingDependencyError
from jw_core.exporters.ir import CitationIR, StudySection, StudySheet


_MODEL_NAME = "jw-agent-toolkit study sheet"


def export_apkg(
    sheet: StudySheet,
    *,
    out: Path,
    deck_name: str | None = None,
    per_citation_cards: bool = False,
) -> Path:
    """Render `sheet` as an Anki package (.apkg) and write it to `out`."""

    try:
        import genanki  # noqa: PLC0415
    except ImportError as exc:
        raise MissingDependencyError(
            "genanki is required for Anki export. "
            "Install with: pip install 'jw-core[anki]'"
        ) from exc

    deck = build_deck(sheet, deck_name=deck_name, per_citation_cards=per_citation_cards)
    out.parent.mkdir(parents=True, exist_ok=True)
    genanki.Package(deck).write_to_file(str(out))
    return out


def build_deck(
    sheet: StudySheet,
    *,
    deck_name: str | None = None,
    per_citation_cards: bool = False,
):
    """Build (but don't write) the genanki.Deck. Useful for tests."""

    try:
        import genanki  # noqa: PLC0415
    except ImportError as exc:
        raise MissingDependencyError(
            "genanki is required for Anki export."
        ) from exc

    model_id = _id_from(_MODEL_NAME)
    deck_id = _id_from(sheet.title)

    model = genanki.Model(
        model_id=model_id,
        name=_MODEL_NAME,
        fields=[{"name": "Front"}, {"name": "Back"}],
        templates=[
            {
                "name": "card",
                "qfmt": "{{Front}}",
                "afmt": '{{FrontSide}}<hr id="answer">{{Back}}',
            }
        ],
    )

    name = deck_name or sheet.title
    deck = genanki.Deck(deck_id=deck_id, name=name)

    for section in sheet.sections:
        deck.add_note(_section_note(genanki, model, sheet, section))
        if per_citation_cards and len(section.citations) >= 1:
            for cite in section.citations:
                deck.add_note(_citation_note(genanki, model, sheet, section, cite))

    return deck


# ── helpers ──


def _id_from(text: str) -> int:
    """Derive a stable 31-bit positive int ID from text via sha256."""
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big") & 0x7FFFFFFF


def _guid(*parts: str) -> str:
    raw = "|".join(parts).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:32]


def _section_note(genanki, model, sheet: StudySheet, section: StudySection):
    """Build the main note for a section."""

    front = section.heading
    back_parts: list[str] = [section.body.replace("\n", "<br>")]
    if section.excerpt:
        back_parts.append(f"<blockquote>{section.excerpt}</blockquote>")
    if section.citations:
        items = "".join(
            f'<li><a href="{c.url}">{c.short_label or c.title or c.url}</a></li>'
            for c in section.citations
        )
        back_parts.append(f"<ul>{items}</ul>")
    back = "".join(back_parts)

    return genanki.Note(
        model=model,
        fields=[front, back],
        guid=_guid(sheet.title, section.heading, section.body[:200]),
    )


def _citation_note(
    genanki,
    model,
    sheet: StudySheet,
    section: StudySection,
    cite: CitationIR,
):
    """Build an extra note focused on a single citation (when per_citation_cards=True)."""

    front = cite.short_label or cite.title or cite.url
    back = f'{section.heading}<br><a href="{cite.url}">{cite.url}</a>'
    return genanki.Note(
        model=model,
        fields=[front, back],
        guid=_guid(sheet.title, section.heading, "cite", cite.url),
    )
