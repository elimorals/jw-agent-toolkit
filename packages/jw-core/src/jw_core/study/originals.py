"""Original-language analysis — Strong's loader + built-in core entries.

Two layers:

  1. **Built-in core catalog** (`_BUILT_IN_ENTRIES`): 7 high-value entries
     for apologetics (`Jehovah`, `elohim`, `nephesh`, `sheol`, `hadēs`,
     `kyrios`, `psychē`).

  2. **External dump loader** (`load_strong_json`, `load_strong_dir`):
     reads Brown-Driver-Briggs (Hebrew) and Thayer's (Greek) JSON dumps
     in the open-format used by `morphgnt/Open-Greek-NewTestament` and
     `openscriptures/strongs`. Drop a `strong.json` in
     `~/.jw-agent-toolkit/strongs/` and the loader picks it up.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class StrongEntry:
    strong_number: str  # 'G5590' (Greek 5590), 'H7585' (Hebrew 7585)
    transliteration: str
    original: str  # actual Greek/Hebrew, when known
    glosses: dict[str, list[str]]  # per-language glosses
    short_definition: dict[str, str] = field(default_factory=dict)
    long_definition: dict[str, str] = field(default_factory=dict)
    examples: list[str] = field(default_factory=list)  # verse refs

    def gloss_for(self, language: str) -> list[str]:
        return self.glosses.get(language, self.glosses.get("en", []))


_BUILT_IN_ENTRIES: dict[str, StrongEntry] = {
    "G5590": StrongEntry(
        strong_number="G5590",
        transliteration="psychē",
        original="ψυχή",
        glosses={
            "en": ["breath", "life", "soul (mortal)"],
            "es": ["aliento", "vida", "alma (mortal)"],
            "pt": ["fôlego", "vida", "alma (mortal)"],
        },
        short_definition={
            "en": "The animating principle of a living creature; the person himself.",
            "es": "El principio que anima a una criatura viviente; la persona misma.",
            "pt": "O princípio que anima uma criatura viva; a própria pessoa.",
        },
        examples=["Matthew 10:28", "Acts 2:27", "Revelation 16:3"],
    ),
    "H5315": StrongEntry(
        strong_number="H5315",
        transliteration="nephesh",
        original="נֶפֶשׁ",
        glosses={
            "en": ["soul", "creature", "person", "breath"],
            "es": ["alma", "criatura", "persona", "aliento"],
            "pt": ["alma", "criatura", "pessoa", "fôlego"],
        },
        short_definition={
            "en": "The breathing creature — the very being, not a separable spirit.",
            "es": "La criatura que respira — el ser mismo, no un espíritu separable.",
            "pt": "A criatura que respira — o próprio ser, não um espírito separável.",
        },
        examples=["Genesis 2:7", "Leviticus 17:11", "Ezekiel 18:4"],
    ),
    "H7585": StrongEntry(
        strong_number="H7585",
        transliteration="sheol",
        original="שְׁאוֹל",
        glosses={
            "en": ["grave", "pit", "common abode of the dead"],
            "es": ["sepultura", "fosa", "lugar común de los muertos"],
            "pt": ["sepultura", "cova", "lugar comum dos mortos"],
        },
        examples=["Ecclesiastes 9:10", "Psalm 16:10", "Isaiah 38:18"],
    ),
    "G86": StrongEntry(
        strong_number="G86",
        transliteration="hadēs",
        original="ᾅδης",
        glosses={
            "en": ["grave", "place of the dead"],
            "es": ["sepulcro", "lugar de los muertos"],
            "pt": ["sepulcro", "lugar dos mortos"],
        },
        examples=["Acts 2:27", "Revelation 20:13"],
    ),
    "G2962": StrongEntry(
        strong_number="G2962",
        transliteration="kyrios",
        original="κύριος",
        glosses={
            "en": ["lord", "master", "owner"],
            "es": ["señor", "amo", "dueño"],
            "pt": ["senhor", "amo", "dono"],
        },
        examples=["Matthew 22:44", "Luke 6:46"],
    ),
    "H430": StrongEntry(
        strong_number="H430",
        transliteration="elohim",
        original="אֱלֹהִים",
        glosses={
            "en": ["God", "gods", "judges", "the divine ones"],
            "es": ["Dios", "dioses", "jueces", "seres divinos"],
            "pt": ["Deus", "deuses", "juízes", "seres divinos"],
        },
        examples=["Genesis 1:1", "Psalm 82:6"],
    ),
    "H3068": StrongEntry(
        strong_number="H3068",
        transliteration="YHWH",
        original="יְהוָה",
        glosses={
            "en": ["Jehovah (the personal name of God)"],
            "es": ["Jehová (el nombre personal de Dios)"],
            "pt": ["Jeová (o nome pessoal de Deus)"],
        },
        examples=["Exodus 3:15", "Psalm 83:18"],
    ),
}


def get_strong_entry(strong_number: str) -> StrongEntry | None:
    """Return the catalog entry for a Strong's number (case-insensitive)."""
    return _BUILT_IN_ENTRIES.get(strong_number.upper())


def list_known_strongs() -> list[dict[str, Any]]:
    return [
        {
            "strong_number": e.strong_number,
            "transliteration": e.transliteration,
            "original": e.original,
            "glosses_en": e.glosses.get("en", []),
        }
        for e in _BUILT_IN_ENTRIES.values()
    ]


def register_strong_dump(entries: list[StrongEntry]) -> None:
    """Add a batch of entries to the in-memory catalog (overrides on conflict)."""
    for entry in entries:
        _BUILT_IN_ENTRIES[entry.strong_number.upper()] = entry


# ── External dump loaders ───────────────────────────────────────────────


_OPENSCRIPTURES_HEB_KEYS = {"strongs_def", "kjv_def", "lemma", "translit"}


def load_strong_json(path: Path | str, *, language: str = "en") -> int:
    """Load a Strong's JSON dump from disk and register every entry.

    Recognized shapes:

    1. `openscriptures/strongs` format — a dict {strong_id: {lemma, translit,
       strongs_def, kjv_def, derivation?, pron?}}.
    2. Compact format — list of dicts with our internal field names.

    Returns the number of entries loaded.
    """
    raw = json.loads(Path(path).expanduser().read_text(encoding="utf-8"))
    entries: list[StrongEntry] = []

    if isinstance(raw, dict):
        # Heuristic: openscriptures style.
        for sid, payload in raw.items():
            if not isinstance(payload, dict):
                continue
            if not _OPENSCRIPTURES_HEB_KEYS & payload.keys():
                continue
            gloss = payload.get("kjv_def") or payload.get("strongs_def") or ""
            translit = payload.get("translit") or payload.get("transliteration") or ""
            original = payload.get("lemma") or payload.get("original") or ""
            short = payload.get("strongs_def") or ""
            entries.append(
                StrongEntry(
                    strong_number=sid.upper(),
                    transliteration=translit,
                    original=original,
                    glosses={language: [g.strip() for g in str(gloss).split(",") if g.strip()][:5]},
                    short_definition={language: short.strip()},
                )
            )
    elif isinstance(raw, list):
        for payload in raw:
            if not isinstance(payload, dict):
                continue
            entries.append(
                StrongEntry(
                    strong_number=str(payload.get("strong_number", "")).upper(),
                    transliteration=payload.get("transliteration", ""),
                    original=payload.get("original", ""),
                    glosses=payload.get("glosses", {}),
                    short_definition=payload.get("short_definition", {}),
                    long_definition=payload.get("long_definition", {}),
                    examples=payload.get("examples", []),
                )
            )
    else:
        raise ValueError(f"Unrecognised Strong's dump shape in {path!r}")
    register_strong_dump(entries)
    return len(entries)


def load_strong_dir(dir_path: Path | str | None = None, *, language: str = "en") -> int:
    """Load every `*.json` in `dir_path` (default `~/.jw-agent-toolkit/strongs/`)."""
    dir_p = (
        Path(dir_path).expanduser()
        if dir_path
        else Path(os.getenv("JW_STRONG_DIR", "~/.jw-agent-toolkit/strongs/")).expanduser()
    )
    if not dir_p.exists():
        return 0
    total = 0
    for f in sorted(dir_p.glob("*.json")):
        try:
            total += load_strong_json(f, language=language)
        except Exception as e:
            logger.warning("Strong's dump %s failed: %s", f.name, e)
    return total


def catalog_size() -> int:
    return len(_BUILT_IN_ENTRIES)
