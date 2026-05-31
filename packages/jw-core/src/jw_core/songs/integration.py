"""Opt-in adapter: enrich a workbook_helper AgentResult with song metadata.

The agent itself (jw_agents.workbook_helper) is NOT modified. Callers
choose whether to wrap its output with this adapter — used by CLI flag
`--with-songs` and by the MCP tool `songs_for_week`.

Idempotent: re-running on an already-enriched result does not duplicate.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from jw_core.songs.registry import get_registry

if TYPE_CHECKING:
    from jw_agents.base import AgentResult


_SLOTS: tuple[str, ...] = ("opening", "middle", "closing")


def enrich_with_songs(result: "AgentResult", language: str = "en") -> "AgentResult":
    """Mutate `result` in place by appending kingdom_song findings.

    Returns the same `result` (for chaining).
    """

    # Local import to avoid a jw_core → jw_agents cycle at module load.
    from jw_agents.base import Citation, Finding

    workbook_finding = _find_workbook_week(result)
    if workbook_finding is None:
        return result

    songs_dict = (workbook_finding.citation.metadata or {}).get("songs") or {}
    if not isinstance(songs_dict, dict):
        result.warnings.append(
            f"enrich_with_songs: songs metadata has unexpected shape {type(songs_dict).__name__}"
        )
        return result

    registry = get_registry(language)
    existing = _existing_song_keys(result)

    for slot in _SLOTS:
        number = songs_dict.get(slot)
        if number is None:
            continue
        if not isinstance(number, int):
            result.warnings.append(
                f"enrich_with_songs: songs[{slot}] is {number!r}, expected int"
            )
            continue
        key = (slot, number)
        if key in existing:
            continue
        song = registry.get(number)
        if song is None:
            result.warnings.append(
                f"enrich_with_songs: song #{number} ({slot}) not in registry for {language!r}"
            )
            continue
        result.findings.append(
            Finding(
                summary=f"Song {number} ({slot}): {song.title}",
                excerpt=song.theme,
                citation=Citation(
                    url=song.canonical_url,
                    title=song.title,
                    kind="kingdom_song",
                    metadata={
                        "number": number,
                        "slot": slot,
                        "scriptures": song.scriptures,
                        "pub_symbol": song.pub_symbol,
                    },
                ),
                metadata={"source": "kingdom_song"},
            )
        )
        existing.add(key)

    return result


def _find_workbook_week(result: "AgentResult") -> Any | None:
    for f in result.findings:
        citation = getattr(f, "citation", None)
        if citation is not None and getattr(citation, "kind", "") == "workbook_week":
            return f
    return None


def _existing_song_keys(result: "AgentResult") -> set[tuple[str, int]]:
    seen: set[tuple[str, int]] = set()
    for f in result.findings:
        citation = getattr(f, "citation", None)
        if citation is None or getattr(citation, "kind", "") != "kingdom_song":
            continue
        meta = citation.metadata or {}
        slot = meta.get("slot")
        number = meta.get("number")
        if isinstance(slot, str) and isinstance(number, int):
            seen.add((slot, number))
    return seen
