"""Loader orquestador del knowledge graph bíblico.

Pipeline procedural (sin LLM):
1. `import_periods()` — itera el catálogo curado `ALL_PERIODS` y emite
   un nodo `Period` por cada entrada.
2. `import_insight(jwpub_path, ...)` — descifra el JWPUB con
   `jw_core.parsers.jwpub.parse_jwpub`, clasifica cada cabezal con
   `InsightParser`, y por cada `InsightEntry`:
     - upsertea un nodo `Person` o `Place` con `BibleKgPerson`/`BibleKgPlace`.
     - parsea `first_mention_href` con `BibleRef.from_wol_url`.
     - upsertea un nodo `Passage` derivado de la BibleRef.
     - upsertea el edge `MENTIONED_IN_PASSAGE` (persona → pasaje) o
       `LOCATED_IN_PASSAGE` (lugar → pasaje).

Todo se emite con provenance fija `source_kind=bible_kg, source_version=f58`
y `license="Watch Tower Bible and Tract Society"`. La idempotencia descansa
en el upsert por `canonical_id` del backend.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from jw_core.models import BibleRef
from jw_core.parsers.jwpub import parse_jwpub

from jw_brain.backends.protocol import GraphBackend
from jw_brain.imports.bible.models import (
    BibleKgPassage,
    BibleKgPerson,
    BibleKgPlace,
    InsightEntry,
)
from jw_brain.imports.bible.parser_insight import InsightParser
from jw_brain.imports.bible.period_catalog import ALL_PERIODS
from jw_brain.imports.bible.place_catalog import get_place_geodata

_PROVENANCE: dict[str, Any] = {
    "source_kind": "bible_kg",
    "source_version": "f58",
    "license": "Watch Tower Bible and Tract Society",
}


@dataclass
class LoaderStats:
    """Resumen agregado de un run del loader.

    Los contadores son monotónicos por llamada (no se resetean entre
    `import_periods` y `import_insight` si el caller reutiliza la
    instancia)."""

    periods_upserted: int = 0
    persons_upserted: int = 0
    places_upserted: int = 0
    passages_upserted: int = 0
    edges_upserted: int = 0
    skipped_unclassified: int = 0
    warnings: list[str] = field(default_factory=list)


def _slugify(s: str) -> str:
    """Lowercase + replace non-alphanumeric con `_`, sin dobles `_`."""
    out: list[str] = []
    prev_us = False
    for ch in s.strip().lower():
        if ch.isalnum():
            out.append(ch)
            prev_us = False
        else:
            if not prev_us:
                out.append("_")
                prev_us = True
    # quita underscores de extremos
    return "".join(out).strip("_")


def _passage_from_bibleref(ref: BibleRef) -> BibleKgPassage:
    """Aplana una `BibleRef` a `BibleKgPassage` para nodo del KG."""
    return BibleKgPassage(
        book_num=ref.book_num,
        chapter=ref.chapter,
        verse_start=ref.verse_start,
        verse_end=ref.verse_end,
    )


class BibleLoader:
    """Orquesta el pipeline bible-KG sobre cualquier `GraphBackend`."""

    def __init__(self, *, backend: GraphBackend) -> None:
        self.backend = backend

    # ── Etapa 1: catálogo de periodos ───────────────────────────────────

    def import_periods(self) -> LoaderStats:
        """Upsertea los 10 periodos cronológicos JW. Idempotente."""
        stats = LoaderStats()
        for period in ALL_PERIODS:
            props: dict[str, Any] = {
                "slug": period.slug,
                "name": period.name,
                "description": period.description,
            }
            if period.start_year_bce is not None:
                props["start_year_bce"] = period.start_year_bce
            if period.end_year_bce is not None:
                props["end_year_bce"] = period.end_year_bce
            if period.end_year_ce is not None:
                props["end_year_ce"] = period.end_year_ce

            self.backend.upsert_node(
                node_type="Period",
                canonical_id=period.canonical_id,
                properties=props,
                provenance=dict(_PROVENANCE),
            )
            stats.periods_upserted += 1
        return stats

    # ── Etapa 2: Insight on the Scriptures ──────────────────────────────

    def import_insight(
        self,
        jwpub_path: Path,
        *,
        symbol: str,
        meps_language: int,
    ) -> LoaderStats:
        """Parsea el JWPUB del Insight y emite Person/Place + Passage + edges."""
        stats = LoaderStats()
        metadata = parse_jwpub(jwpub_path)
        parser = InsightParser(symbol=symbol, meps_language=meps_language)

        for entry in parser.iter_entries(metadata):
            self._process_entry(entry, stats)

        return stats

    # ── helpers ─────────────────────────────────────────────────────────

    def _process_entry(self, entry: InsightEntry, stats: LoaderStats) -> None:
        slug = _slugify(entry.headword)
        if not slug:
            stats.skipped_unclassified += 1
            stats.warnings.append(f"empty slug for headword={entry.headword!r}")
            return

        wol_ref = BibleRef.from_wol_url(entry.first_mention_href) if entry.first_mention_href else None

        if entry.kind == "person":
            person = BibleKgPerson(
                slug=slug,
                name=entry.headword,
                aliases=entry.aliases,
                first_mention_book=wol_ref.book_num if wol_ref else None,
                first_mention_chapter=wol_ref.chapter if wol_ref else None,
                first_mention_verse=wol_ref.verse_start if wol_ref else None,
                description_excerpt=entry.text_excerpt,
            )
            self.backend.upsert_node(
                node_type="Person",
                canonical_id=person.canonical_id,
                properties=person.model_dump(exclude={"slug"}) | {"slug": person.slug},
                provenance=dict(_PROVENANCE),
            )
            stats.persons_upserted += 1
            if wol_ref is not None:
                self._upsert_passage_and_mention(
                    wol_ref,
                    source_canonical_id=person.canonical_id,
                    edge_type="MENTIONED_IN_PASSAGE",
                    stats=stats,
                )
            return

        if entry.kind == "place":
            geodata = get_place_geodata(slug)
            place = BibleKgPlace(
                slug=slug,
                name=entry.headword,
                region=geodata.region if geodata else "",
                modern_name=geodata.modern_name if geodata else "",
                latitude=geodata.latitude if geodata else None,
                longitude=geodata.longitude if geodata else None,
                eras_active=geodata.eras_active if geodata else (),
                source_url=(
                    f"https://wol.jw.org{entry.first_mention_href}"
                    if entry.first_mention_href
                    else ""
                ),
            )
            self.backend.upsert_node(
                node_type="Place",
                canonical_id=place.canonical_id,
                properties=place.model_dump(exclude={"slug"}) | {"slug": place.slug},
                provenance=dict(_PROVENANCE),
            )
            stats.places_upserted += 1
            if wol_ref is not None:
                self._upsert_passage_and_mention(
                    wol_ref,
                    source_canonical_id=place.canonical_id,
                    edge_type="LOCATED_IN_PASSAGE",
                    stats=stats,
                )
            return

        # Defensa: el parser no debería emitir otros kinds, pero si lo hace
        # contamos como skip y emitimos warning.
        stats.skipped_unclassified += 1
        stats.warnings.append(f"unknown kind={entry.kind!r} headword={entry.headword!r}")

    def _upsert_passage_and_mention(
        self,
        wol_ref: BibleRef,
        *,
        source_canonical_id: str,
        edge_type: str,
        stats: LoaderStats,
    ) -> None:
        passage = _passage_from_bibleref(wol_ref)
        passage_props: dict[str, Any] = {
            "book_num": passage.book_num,
            "chapter": passage.chapter,
        }
        if passage.verse_start is not None:
            passage_props["verse_start"] = passage.verse_start
        if passage.verse_end is not None:
            passage_props["verse_end"] = passage.verse_end

        self.backend.upsert_node(
            node_type="Passage",
            canonical_id=passage.canonical_id,
            properties=passage_props,
            provenance=dict(_PROVENANCE),
        )
        stats.passages_upserted += 1

        self.backend.upsert_edge(
            edge_type=edge_type,
            from_node=source_canonical_id,
            to_node=passage.canonical_id,
            properties={},
            provenance=dict(_PROVENANCE),
        )
        stats.edges_upserted += 1
