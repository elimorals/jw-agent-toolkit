"""student_part_helper agent — compose a student-part script.

Inputs:
    kind: one of {bible_reading, starting_conversation, return_visit, bible_study}
    topic_or_ref: a Bible reference, a free topic phrase, or "this week"
    language: en/es/pt (others fall back to en for the template body)
    oratory_point: optional 1..50; if None we use point_of_the_month(today)
    audience: default/new/religious/atheist (others fall back to 'default')

Output: AgentResult with exactly 4 findings (opening/body/transition/close)
        and metadata describing what was applied.

No LLM, no network unless topic_or_ref == 'this week' and a WOLClient is
passed in. Idempotent for fixed `today`.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from jw_core.clients.wol import WOLClient
from jw_core.data.books import BOOKS
from jw_core.data.oratory_points import (
    OratoryPoint,
    brief,
    get_point,
    key_phrase,
    point_of_the_month,
    points_applicable_to,
)
from jw_core.data.student_parts_templates import (
    find_template,
    time_target_seconds_for,
)
from jw_core.models import BibleRef
from jw_core.parsers.reference import parse_reference

from jw_agents.base import AgentResult, Citation, Finding

_KNOWN_KINDS = {
    "bible_reading",
    "starting_conversation",
    "return_visit",
    "bible_study",
}
_KNOWN_AUDIENCES = {"default", "new", "religious", "atheist"}
_TEMPLATE_LANGS = {"en", "es", "pt"}


async def student_part_helper(
    kind: str,
    topic_or_ref: str,
    *,
    language: str = "en",
    oratory_point: int | None = None,
    audience: str = "default",
    wol: WOLClient | None = None,
    today: date | None = None,
) -> AgentResult:
    """Compose a 4-section script for a student assignment."""
    result = AgentResult(query=topic_or_ref, agent_name="student_part_helper")
    today = today or date.today()
    result.metadata["language"] = language
    result.metadata["kind"] = kind
    result.metadata["audience"] = audience

    if kind not in _KNOWN_KINDS:
        result.warnings.append(f"Unknown kind {kind!r}; expected one of {sorted(_KNOWN_KINDS)}")
        return result

    # 1. Resolve oratory point.
    point = _resolve_oratory_point(oratory_point, today, kind, result)

    # 2. Resolve audience (fall back if unknown).
    audience_used = audience if audience in _KNOWN_AUDIENCES else "default"
    if audience_used != audience:
        result.warnings.append(
            f"Audience {audience!r} unsupported; using 'default'."
        )
    result.metadata["audience_used"] = audience_used

    # 3. Resolve scripture / topic / 'this week'.
    verse_display, verse_url, topic_label = await _resolve_topic(
        topic_or_ref, language, kind, wol, today, result,
    )

    # 4. Pick template.
    tpl = find_template(kind, audience_used, language)
    template_lang_used = tpl.language
    result.metadata["template_language_used"] = template_lang_used

    # 5. Build placeholders.
    placeholders = _build_placeholders(
        verse_display=verse_display,
        topic=topic_label,
        point=point,
        language=language,
        kind=kind,
        result=result,
    )

    # 6. Render the 4 sections into Findings.
    for section_name, raw in (
        ("opening", tpl.opening),
        ("body", tpl.body),
        ("transition", tpl.transition),
        ("close", tpl.close),
    ):
        text = _safe_format(raw, placeholders)
        citation = (
            Citation(url=verse_url, title=verse_display, kind="verse")
            if verse_url
            else Citation(url="", title=topic_label or topic_or_ref, kind="topic_anchor")
        )
        result.findings.append(
            Finding(
                summary=f"{kind} · {section_name}",
                excerpt=text,
                citation=citation,
                metadata={
                    "source": "student_part_template",
                    "section": section_name,
                },
            )
        )

    # 7. Final metadata.
    result.metadata["time_target_seconds"] = time_target_seconds_for(kind)
    result.metadata["oratory_point_applied"] = {
        "number": point.number,
        "key_phrase": key_phrase(point, language),
        "category": point.category,
    }
    if topic_label:
        result.metadata["topic"] = topic_label

    return result


# ── helpers ─────────────────────────────────────────────────────────────


def _resolve_oratory_point(
    explicit: int | None,
    today: date,
    kind: str,
    result: AgentResult,
) -> OratoryPoint:
    if explicit is not None:
        try:
            point = get_point(explicit)
        except ValueError as exc:
            result.warnings.append(str(exc))
            point = point_of_the_month(today)
    else:
        point = point_of_the_month(today)

    if kind not in point.applies_to:
        applicable = ", ".join(str(p.number) for p in points_applicable_to(kind)[:5])
        result.warnings.append(
            f"Oratory point {point.number} does not naturally apply to {kind!r}; "
            f"consider one of: {applicable}…"
        )
    return point


async def _resolve_topic(
    topic_or_ref: str,
    language: str,
    kind: str,
    wol: WOLClient | None,
    today: date,
    result: AgentResult,
) -> tuple[str, str, str]:
    """Return (verse_display, verse_url, topic_label).

    - If `topic_or_ref` parses as a reference: returns the reference's display
      and WOL URL; topic_label is "".
    - If it is exactly 'this week' (case-insensitive): tries the workbook
      scraper; on success returns the matching assignment's reference; on
      failure or no `wol`, returns ("", "", topic_or_ref) with a warning.
    - Otherwise: ("", "", topic_or_ref).
    """
    if topic_or_ref.strip().lower() == "this week":
        if wol is None:
            result.warnings.append(
                "'this week' requires a WOLClient (workbook scraper) — using free topic instead."
            )
            return ("", "", topic_or_ref)
        # Lazy import to keep workbook off the import path of every consumer.
        try:
            from jw_agents.workbook_helper import workbook_helper  # type: ignore[import-not-found]
        except Exception as exc:  # noqa: BLE001
            result.warnings.append(f"workbook_helper unavailable: {exc!r}")
            return ("", "", topic_or_ref)
        try:
            wb = await workbook_helper(today.isoformat(), language=language, wol=wol)
        except Exception as exc:  # noqa: BLE001
            result.warnings.append(f"workbook fetch failed: {exc!r}")
            return ("", "", topic_or_ref)
        # Find the first assignment that matches `kind` in the workbook output.
        for f in wb.findings:
            if f.metadata.get("kind") == kind and f.metadata.get("reference"):
                ref = parse_reference(str(f.metadata["reference"]))
                if ref is not None:
                    return (ref.display(), ref.wol_url(lang=language), "")
        result.warnings.append(
            f"workbook did not contain an assignment of kind={kind!r} for this week."
        )
        return ("", "", topic_or_ref)

    ref = parse_reference(topic_or_ref)
    if ref is not None:
        display = _localized_display(ref, language)
        result.metadata["resolved_reference"] = display
        return (display, ref.wol_url(lang=language), "")
    return ("", "", topic_or_ref)


def _localized_display(ref: BibleRef, language: str) -> str:
    """Render `ref` using the preferred book name for `language`.

    Falls back to the canonical English name when the language is not in
    the book's name table.
    """
    name = ref.book_canonical
    for entry in BOOKS:
        if entry["num"] == ref.book_num:
            names = entry["names"].get(language) or entry["names"].get("en")
            if names:
                name = names[0]
            break
    out = f"{name} {ref.chapter}"
    if ref.verse_start:
        out += f":{ref.verse_range}"
    return out


def _build_placeholders(
    *,
    verse_display: str,
    topic: str,
    point: OratoryPoint,
    language: str,
    kind: str,
    result: AgentResult,
) -> dict[str, str]:
    # `verse_display` falls back to `topic` so templates always render.
    display = verse_display or topic or "—"
    return {
        "verse_display": display,
        "verse_text": "",          # filled only when wol fetch was done; v1: empty.
        "topic": topic or "—",
        "oratory_phrase": key_phrase(point, language),
        "oratory_brief": brief(point, language),
        # return_visit-specific
        "prior_seed": result.metadata.get("prior_seed", "your last comment"),
        "next_visit_hook": result.metadata.get("next_visit_hook", "the next thought"),
        # bible_study-specific
        "paragraph": result.metadata.get("paragraph", "1"),
        "next_paragraph": result.metadata.get("next_paragraph", "2"),
        "focus": result.metadata.get("focus", topic or "the lesson"),
    }


def _safe_format(template: str, placeholders: dict[str, str]) -> str:
    """str.format that tolerates missing keys by leaving the literal placeholder."""

    class _Defaulter(dict):
        def __missing__(self, key: str) -> str:  # noqa: D401
            return "{" + key + "}"

    return template.format_map(_Defaulter(placeholders))


# Re-export for convenience.
__all__ = ["student_part_helper"]
