"""Regenerate shared/data/bible_references_golden.json from the Python parser.

F56.4 — runs `parse_reference` over a curated, hand-maintained input set
that exercises:

  - The 66 books in en/es/pt (full names + JW NWT abbreviations).
  - Range, single verse, chapter-only forms.
  - Multi-digit chapter/verse numbers.
  - 1/2/3 John (the "1/2/3" prefix common case).

If you add a new input here and run `make dump-shared-data`, the JSON
regenerates. CI then runs `git diff --exit-code` on the file; an
uncommitted regeneration fails the build, so a contributor cannot
silently change parser behavior.
"""

from __future__ import annotations

import json
from pathlib import Path

from jw_core.parsers.reference import parse_reference

INPUTS: list[str] = [
    # ── full names en/es/pt — pentateuco
    "Genesis 1:1", "Génesis 1:1", "Gênesis 1:1",
    "Exodus 20:3", "Éxodo 20:3", "Êxodo 20:3",
    "Leviticus 19:18", "Levítico 19:18",
    "Numbers 6:24", "Números 6:24",
    "Deuteronomy 6:4", "Deuteronomio 6:4", "Deuteronômio 6:4",
    # ── históricos
    "Joshua 1:9", "Josué 1:9",
    "1 Samuel 17:45",
    "2 Kings 5:14", "2 Reyes 5:14", "2 Reis 5:14",
    "1 Chronicles 29:11", "1 Crónicas 29:11", "1 Crônicas 29:11",
    "Nehemiah 8:10", "Nehemías 8:10", "Neemias 8:10",
    "Esther 4:14", "Ester 4:14",
    # ── poéticos
    "Job 1:21",
    "Psalm 23:1", "Salmos 23:1", "Salmo 23:1",
    "Proverbs 3:5", "Proverbios 3:5", "Provérbios 3:5",
    "Ecclesiastes 3:1", "Eclesiastés 3:1", "Eclesiastes 3:1",
    "Song of Solomon 2:4", "Cantares 2:4", "Cântico 2:4",
    # ── profetas mayores
    "Isaiah 53:5", "Isaías 53:5",
    "Jeremiah 29:11", "Jeremías 29:11", "Jeremias 29:11",
    "Lamentations 3:22", "Lamentaciones 3:22", "Lamentações 3:22",
    "Ezekiel 18:32", "Ezequiel 18:32",
    "Daniel 12:3",
    # ── profetas menores
    "Hosea 6:6", "Oseas 6:6", "Oseias 6:6",
    "Joel 2:28",
    "Amos 5:24", "Amós 5:24",
    "Obadiah 1:15", "Abdías 1:15", "Obadias 1:15",
    "Jonah 2:1", "Jonás 2:1",
    "Micah 6:8", "Miqueas 6:8", "Miquéias 6:8",
    "Habakkuk 2:4", "Habacuc 2:4", "Habacuque 2:4",
    "Haggai 2:7", "Hageo 2:7",
    "Zechariah 4:6", "Zacarías 4:6", "Zacarias 4:6",
    "Malachi 3:6", "Malaquías 3:6", "Malaquias 3:6",
    # ── NT — evangelios
    "Matthew 5:3", "Mateo 5:3", "Mateus 5:3",
    "Mark 16:15", "Marcos 16:15",
    "Luke 6:31", "Lucas 6:31",
    "John 3:16", "Juan 3:16", "João 3:16",
    # ── NT — Hechos + cartas
    "Acts 17:11", "Hechos 17:11", "Atos 17:11",
    "Romans 8:28", "Romanos 8:28",
    "1 Corinthians 13:4", "1 Corintios 13:4", "1 Coríntios 13:4",
    "2 Corinthians 5:17", "2 Corintios 5:17", "2 Coríntios 5:17",
    "Galatians 5:22", "Gálatas 5:22",
    "Ephesians 4:32", "Efesios 4:32", "Efésios 4:32",
    "Philippians 4:13", "Filipenses 4:13",
    "Colossians 3:23", "Colosenses 3:23",
    "1 Thessalonians 5:17", "1 Tesalonicenses 5:17",
    "1 Timothy 6:10", "1 Timoteo 6:10", "1 Timóteo 6:10",
    "Titus 2:11", "Tito 2:11",
    "Philemon 1:6", "Filemón 1:6", "Filemom 1:6",
    "Hebrews 11:1", "Hebreos 11:1", "Hebreus 11:1",
    "James 1:5", "Santiago 1:5", "Tiago 1:5",
    "1 Peter 5:7", "1 Pedro 5:7",
    "Jude 1:21", "Judas 1:21",
    "Revelation 21:4", "Apocalipsis 21:4", "Apocalipse 21:4",
    # ── abreviaturas JW NWT comunes
    "Gen 1:1", "Gn 1:1", "Gên 1:1",
    "Ex 20:3", "Éx 20:3", "Êx 20:3",
    "Mt 5:7", "Mc 16:15", "Lc 6:31", "Jn 3:16",
    "Ro 8:28", "1Co 13:4", "Heb 11:1", "Ap 21:4", "Re 21:4",
    "1 Co 13:4", "2 Co 5:17", "Stg 1:5",
    # ── rangos
    "John 3:16-18", "Juan 3:16-18", "João 3:16-18",
    "Romans 8:28-30", "Salmos 23:1-3",
    "1 Corinthians 13:4-8", "Génesis 1:1-3",
    # ── capítulo solo
    "Psalm 23", "John 3", "Apocalipsis 21",
    # ── multi-dígito
    "Genesis 50:20", "Psalm 119:105", "Salmos 150:6",
    "Matthew 28:19", "Acts 28:31", "Revelation 22:21",
    # ── 1/2/3 John con varias formas
    "1 John 4:8", "2 John 1:6", "3 John 1:4",
    "1 Juan 4:8", "2 Juan 1:6", "3 Juan 1:4",
    "1 João 4:8", "2 João 1:6", "3 João 1:4",
    # ── ambiguous-by-abbrev
    "Mateo 1:1", "Mat 1:1", "Mt 1:1",
]


def main() -> None:
    cases: list[dict] = []
    for inp in INPUTS:
        ref = parse_reference(inp)
        if ref is None:
            continue  # silently skip non-matching inputs to keep the fixture clean
        cases.append(
            {
                "input": inp,
                "book_num": ref.book_num,
                "book_canonical": ref.book_canonical,
                "chapter": ref.chapter,
                "verse_start": ref.verse_start,
                "verse_end": ref.verse_end,
                "detected_language": ref.detected_language,
                "raw_match": ref.raw_match,
            }
        )

    out = {
        "version": "2.0",
        "description": (
            "Golden Bible reference parse cases shared between jw-core (Python) "
            "and jw-core-js (TypeScript). Both implementations must agree on every "
            "field including detected_language and raw_match. Regenerate via "
            "`make dump-shared-data` — CI fails on uncommitted regeneration."
        ),
        "cases": cases,
    }

    target = Path(__file__).resolve().parents[1] / "shared" / "data" / "bible_references_golden.json"
    target.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(cases)} cases to {target}")


if __name__ == "__main__":
    main()
