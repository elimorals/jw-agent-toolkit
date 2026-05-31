"""Bible book registry with multi-language names and JW NWT abbreviations.

Book numbering follows the standard 1-66 (Genesis=1, Revelation=66), which
matches `booknum` in jw.org's pub-media API.

Each entry contains:
  - num: canonical book number (1-66)
  - canonical: English name used as canonical key
  - names: per-language list of names. Index [0] = preferred display name,
           remaining entries are alternative spellings / abbreviations the
           parser will recognize.

Languages currently registered:
  - en (English)  — JW code "E"
  - es (Spanish)  — JW code "S"
  - pt (Portuguese) — JW code "T"

Add languages by extending the "names" dict on each book. The parser
auto-rebuilds its index from this registry on import.
"""

from typing import TypedDict


class BookNames(TypedDict, total=False):
    en: list[str]
    es: list[str]
    pt: list[str]
    fr: list[str]
    de: list[str]
    it: list[str]
    ru: list[str]
    ja: list[str]
    ko: list[str]
    zh: list[str]


class BookEntry(TypedDict):
    num: int
    canonical: str
    names: BookNames


BOOKS: list[BookEntry] = [
    # ── Hebrew Scriptures ───────────────────────────────────────────────
    {
        "num": 1,
        "canonical": "Genesis",
        "names": {"en": ["Genesis", "Gen", "Ge"], "es": ["Génesis", "Gé", "Gen"], "pt": ["Gênesis", "Gên", "Gn"]},
    },
    {
        "num": 2,
        "canonical": "Exodus",
        "names": {"en": ["Exodus", "Ex", "Exod"], "es": ["Éxodo", "Éx", "Ex"], "pt": ["Êxodo", "Êxo", "Êx"]},
    },
    {
        "num": 3,
        "canonical": "Leviticus",
        "names": {"en": ["Leviticus", "Lev", "Le"], "es": ["Levítico", "Le", "Lev"], "pt": ["Levítico", "Lev", "Lv"]},
    },
    {
        "num": 4,
        "canonical": "Numbers",
        "names": {"en": ["Numbers", "Num", "Nu"], "es": ["Números", "Nú", "Num"], "pt": ["Números", "Núm", "Nm"]},
    },
    {
        "num": 5,
        "canonical": "Deuteronomy",
        "names": {
            "en": ["Deuteronomy", "Deut", "De"],
            "es": ["Deuteronomio", "Dt", "Deu"],
            "pt": ["Deuteronômio", "Deu", "Dt"],
        },
    },
    {
        "num": 6,
        "canonical": "Joshua",
        "names": {"en": ["Joshua", "Josh", "Jos"], "es": ["Josué", "Jos"], "pt": ["Josué", "Jos"]},
    },
    {
        "num": 7,
        "canonical": "Judges",
        "names": {"en": ["Judges", "Judg", "Jg"], "es": ["Jueces", "Jue", "Jc"], "pt": ["Juízes", "Juí", "Jz"]},
    },
    {"num": 8, "canonical": "Ruth", "names": {"en": ["Ruth", "Ru"], "es": ["Rut", "Ru"], "pt": ["Rute", "Rut", "Rt"]}},
    {
        "num": 9,
        "canonical": "1 Samuel",
        "names": {
            "en": ["1 Samuel", "1 Sam", "1Sa", "1Sam"],
            "es": ["1 Samuel", "1 Sam", "1Sa", "1Sam"],
            "pt": ["1 Samuel", "1 Sam", "1Sa", "1Sm"],
        },
    },
    {
        "num": 10,
        "canonical": "2 Samuel",
        "names": {
            "en": ["2 Samuel", "2 Sam", "2Sa", "2Sam"],
            "es": ["2 Samuel", "2 Sam", "2Sa", "2Sam"],
            "pt": ["2 Samuel", "2 Sam", "2Sa", "2Sm"],
        },
    },
    {
        "num": 11,
        "canonical": "1 Kings",
        "names": {
            "en": ["1 Kings", "1 Ki", "1Ki", "1Kgs"],
            "es": ["1 Reyes", "1 Re", "1Re"],
            "pt": ["1 Reis", "1 Re", "1Re"],
        },
    },
    {
        "num": 12,
        "canonical": "2 Kings",
        "names": {
            "en": ["2 Kings", "2 Ki", "2Ki", "2Kgs"],
            "es": ["2 Reyes", "2 Re", "2Re"],
            "pt": ["2 Reis", "2 Re", "2Re"],
        },
    },
    {
        "num": 13,
        "canonical": "1 Chronicles",
        "names": {
            "en": ["1 Chronicles", "1 Chron", "1Ch", "1Chr"],
            "es": ["1 Crónicas", "1 Cr", "1Cr"],
            "pt": ["1 Crônicas", "1 Crô", "1Cr"],
        },
    },
    {
        "num": 14,
        "canonical": "2 Chronicles",
        "names": {
            "en": ["2 Chronicles", "2 Chron", "2Ch", "2Chr"],
            "es": ["2 Crónicas", "2 Cr", "2Cr"],
            "pt": ["2 Crônicas", "2 Crô", "2Cr"],
        },
    },
    {
        "num": 15,
        "canonical": "Ezra",
        "names": {"en": ["Ezra", "Ezr"], "es": ["Esdras", "Esd"], "pt": ["Esdras", "Esd"]},
    },
    {
        "num": 16,
        "canonical": "Nehemiah",
        "names": {"en": ["Nehemiah", "Neh", "Ne"], "es": ["Nehemías", "Ne", "Neh"], "pt": ["Neemias", "Nee", "Ne"]},
    },
    {
        "num": 17,
        "canonical": "Esther",
        "names": {"en": ["Esther", "Esth", "Es"], "es": ["Ester", "Est"], "pt": ["Ester", "Est"]},
    },
    {"num": 18, "canonical": "Job", "names": {"en": ["Job"], "es": ["Job"], "pt": ["Jó", "Job"]}},
    {
        "num": 19,
        "canonical": "Psalms",
        "names": {
            "en": ["Psalms", "Psalm", "Ps", "Psa"],
            "es": ["Salmos", "Salmo", "Sl", "Sal"],
            "pt": ["Salmos", "Salmo", "Sal", "Sl"],
        },
    },
    {
        "num": 20,
        "canonical": "Proverbs",
        "names": {
            "en": ["Proverbs", "Prov", "Pr"],
            "es": ["Proverbios", "Pr", "Prov"],
            "pt": ["Provérbios", "Pro", "Pv"],
        },
    },
    {
        "num": 21,
        "canonical": "Ecclesiastes",
        "names": {
            "en": ["Ecclesiastes", "Eccl", "Ec"],
            "es": ["Eclesiastés", "Ec", "Ecl"],
            "pt": ["Eclesiastes", "Ecl", "Ec"],
        },
    },
    {
        "num": 22,
        "canonical": "Song of Solomon",
        "names": {
            "en": ["Song of Solomon", "Song", "Ca", "SS"],
            "es": ["Cantar de los Cantares", "Cantares", "Can", "Cnt"],
            "pt": ["Cântico de Salomão", "Cântico", "Cân", "Ct"],
        },
    },
    {
        "num": 23,
        "canonical": "Isaiah",
        "names": {"en": ["Isaiah", "Isa", "Is"], "es": ["Isaías", "Is", "Isa"], "pt": ["Isaías", "Isa", "Is"]},
    },
    {
        "num": 24,
        "canonical": "Jeremiah",
        "names": {"en": ["Jeremiah", "Jer"], "es": ["Jeremías", "Jer"], "pt": ["Jeremias", "Jer"]},
    },
    {
        "num": 25,
        "canonical": "Lamentations",
        "names": {
            "en": ["Lamentations", "Lam", "La"],
            "es": ["Lamentaciones", "Lam", "La"],
            "pt": ["Lamentações", "Lam", "Lm"],
        },
    },
    {
        "num": 26,
        "canonical": "Ezekiel",
        "names": {"en": ["Ezekiel", "Ezek", "Eze"], "es": ["Ezequiel", "Eze", "Ez"], "pt": ["Ezequiel", "Eze", "Ez"]},
    },
    {
        "num": 27,
        "canonical": "Daniel",
        "names": {"en": ["Daniel", "Dan", "Da"], "es": ["Daniel", "Dan", "Da"], "pt": ["Daniel", "Dan", "Dn"]},
    },
    {
        "num": 28,
        "canonical": "Hosea",
        "names": {"en": ["Hosea", "Hos", "Ho"], "es": ["Oseas", "Os"], "pt": ["Oseias", "Ose", "Os"]},
    },
    {
        "num": 29,
        "canonical": "Joel",
        "names": {"en": ["Joel", "Joe"], "es": ["Joel", "Joe"], "pt": ["Joel", "Joe", "Jl"]},
    },
    {
        "num": 30,
        "canonical": "Amos",
        "names": {"en": ["Amos", "Am"], "es": ["Amós", "Am"], "pt": ["Amós", "Amo", "Am"]},
    },
    {
        "num": 31,
        "canonical": "Obadiah",
        "names": {"en": ["Obadiah", "Obad", "Ob"], "es": ["Abdías", "Ab"], "pt": ["Obadias", "Oba", "Ob"]},
    },
    {
        "num": 32,
        "canonical": "Jonah",
        "names": {"en": ["Jonah", "Jon"], "es": ["Jonás", "Jon"], "pt": ["Jonas", "Jon"]},
    },
    {
        "num": 33,
        "canonical": "Micah",
        "names": {"en": ["Micah", "Mic", "Mi"], "es": ["Miqueas", "Miq", "Mi"], "pt": ["Miqueias", "Miq", "Mq"]},
    },
    {
        "num": 34,
        "canonical": "Nahum",
        "names": {"en": ["Nahum", "Nah", "Na"], "es": ["Nahúm", "Nah"], "pt": ["Naum", "Nau"]},
    },
    {
        "num": 35,
        "canonical": "Habakkuk",
        "names": {"en": ["Habakkuk", "Hab"], "es": ["Habacuc", "Hab"], "pt": ["Habacuque", "Hab", "Hc"]},
    },
    {
        "num": 36,
        "canonical": "Zephaniah",
        "names": {"en": ["Zephaniah", "Zeph", "Zep"], "es": ["Sofonías", "Sof"], "pt": ["Sofonias", "Sof", "Sf"]},
    },
    {
        "num": 37,
        "canonical": "Haggai",
        "names": {"en": ["Haggai", "Hag"], "es": ["Hageo", "Ag"], "pt": ["Ageu", "Age", "Ag"]},
    },
    {
        "num": 38,
        "canonical": "Zechariah",
        "names": {"en": ["Zechariah", "Zech", "Zec"], "es": ["Zacarías", "Zac"], "pt": ["Zacarias", "Zac", "Zc"]},
    },
    {
        "num": 39,
        "canonical": "Malachi",
        "names": {"en": ["Malachi", "Mal"], "es": ["Malaquías", "Mal"], "pt": ["Malaquias", "Mal", "Ml"]},
    },
    # ── Christian Greek Scriptures ──────────────────────────────────────
    {
        "num": 40,
        "canonical": "Matthew",
        "names": {"en": ["Matthew", "Matt", "Mt"], "es": ["Mateo", "Mt", "Mat"], "pt": ["Mateus", "Mat", "Mt"]},
    },
    {
        "num": 41,
        "canonical": "Mark",
        "names": {"en": ["Mark", "Mr", "Mk"], "es": ["Marcos", "Mr", "Mar"], "pt": ["Marcos", "Mar", "Mc"]},
    },
    {
        "num": 42,
        "canonical": "Luke",
        "names": {"en": ["Luke", "Lu", "Lk"], "es": ["Lucas", "Lu", "Luc"], "pt": ["Lucas", "Luc", "Lc"]},
    },
    {
        "num": 43,
        "canonical": "John",
        "names": {"en": ["John", "Joh", "Jn"], "es": ["Juan", "Jn", "Jua"], "pt": ["João", "Joã", "Jo"]},
    },
    {
        "num": 44,
        "canonical": "Acts",
        "names": {"en": ["Acts", "Ac"], "es": ["Hechos", "Hch", "Hch"], "pt": ["Atos", "At"]},
    },
    {
        "num": 45,
        "canonical": "Romans",
        "names": {"en": ["Romans", "Rom", "Ro"], "es": ["Romanos", "Ro", "Rom"], "pt": ["Romanos", "Rom", "Rm"]},
    },
    {
        "num": 46,
        "canonical": "1 Corinthians",
        "names": {
            "en": ["1 Corinthians", "1 Cor", "1Co", "1Cor"],
            "es": ["1 Corintios", "1 Co", "1Co", "1Cor"],
            "pt": ["1 Coríntios", "1 Co", "1Co", "1Cor"],
        },
    },
    {
        "num": 47,
        "canonical": "2 Corinthians",
        "names": {
            "en": ["2 Corinthians", "2 Cor", "2Co", "2Cor"],
            "es": ["2 Corintios", "2 Co", "2Co", "2Cor"],
            "pt": ["2 Coríntios", "2 Co", "2Co", "2Cor"],
        },
    },
    {
        "num": 48,
        "canonical": "Galatians",
        "names": {"en": ["Galatians", "Gal", "Ga"], "es": ["Gálatas", "Gál", "Ga"], "pt": ["Gálatas", "Gál", "Gl"]},
    },
    {
        "num": 49,
        "canonical": "Ephesians",
        "names": {"en": ["Ephesians", "Eph", "Ep"], "es": ["Efesios", "Ef", "Efe"], "pt": ["Efésios", "Efé", "Ef"]},
    },
    {
        "num": 50,
        "canonical": "Philippians",
        "names": {
            "en": ["Philippians", "Phil", "Php"],
            "es": ["Filipenses", "Flp", "Fil"],
            "pt": ["Filipenses", "Fil", "Fp"],
        },
    },
    {
        "num": 51,
        "canonical": "Colossians",
        "names": {"en": ["Colossians", "Col"], "es": ["Colosenses", "Col"], "pt": ["Colossenses", "Col", "Cl"]},
    },
    {
        "num": 52,
        "canonical": "1 Thessalonians",
        "names": {
            "en": ["1 Thessalonians", "1 Thess", "1Th", "1Thes"],
            "es": ["1 Tesalonicenses", "1 Te", "1Te", "1Tes"],
            "pt": ["1 Tessalonicenses", "1 Te", "1Te", "1Tes"],
        },
    },
    {
        "num": 53,
        "canonical": "2 Thessalonians",
        "names": {
            "en": ["2 Thessalonians", "2 Thess", "2Th", "2Thes"],
            "es": ["2 Tesalonicenses", "2 Te", "2Te", "2Tes"],
            "pt": ["2 Tessalonicenses", "2 Te", "2Te", "2Tes"],
        },
    },
    {
        "num": 54,
        "canonical": "1 Timothy",
        "names": {
            "en": ["1 Timothy", "1 Tim", "1Ti", "1Tim"],
            "es": ["1 Timoteo", "1 Ti", "1Ti", "1Tim"],
            "pt": ["1 Timóteo", "1 Ti", "1Ti", "1Tim"],
        },
    },
    {
        "num": 55,
        "canonical": "2 Timothy",
        "names": {
            "en": ["2 Timothy", "2 Tim", "2Ti", "2Tim"],
            "es": ["2 Timoteo", "2 Ti", "2Ti", "2Tim"],
            "pt": ["2 Timóteo", "2 Ti", "2Ti", "2Tim"],
        },
    },
    {
        "num": 56,
        "canonical": "Titus",
        "names": {"en": ["Titus", "Tit"], "es": ["Tito", "Tit"], "pt": ["Tito", "Tit", "Tt"]},
    },
    {
        "num": 57,
        "canonical": "Philemon",
        "names": {"en": ["Philemon", "Phlm", "Phm"], "es": ["Filemón", "Flm"], "pt": ["Filêmon", "Flm", "Fm"]},
    },
    {
        "num": 58,
        "canonical": "Hebrews",
        "names": {"en": ["Hebrews", "Heb"], "es": ["Hebreos", "Heb"], "pt": ["Hebreus", "Heb", "Hb"]},
    },
    {
        "num": 59,
        "canonical": "James",
        "names": {"en": ["James", "Jas", "Jam"], "es": ["Santiago", "Snt", "Stg"], "pt": ["Tiago", "Tia", "Tg"]},
    },
    {
        "num": 60,
        "canonical": "1 Peter",
        "names": {
            "en": ["1 Peter", "1 Pet", "1Pe", "1Pet"],
            "es": ["1 Pedro", "1 Pe", "1Pe", "1Ped"],
            "pt": ["1 Pedro", "1 Pe", "1Pe", "1Pd"],
        },
    },
    {
        "num": 61,
        "canonical": "2 Peter",
        "names": {
            "en": ["2 Peter", "2 Pet", "2Pe", "2Pet"],
            "es": ["2 Pedro", "2 Pe", "2Pe", "2Ped"],
            "pt": ["2 Pedro", "2 Pe", "2Pe", "2Pd"],
        },
    },
    {
        "num": 62,
        "canonical": "1 John",
        "names": {
            "en": ["1 John", "1 Joh", "1Jo", "1Jn"],
            "es": ["1 Juan", "1 Jn", "1Jn", "1Jua"],
            "pt": ["1 João", "1 Joã", "1Jo"],
        },
    },
    {
        "num": 63,
        "canonical": "2 John",
        "names": {
            "en": ["2 John", "2 Joh", "2Jo", "2Jn"],
            "es": ["2 Juan", "2 Jn", "2Jn", "2Jua"],
            "pt": ["2 João", "2 Joã", "2Jo"],
        },
    },
    {
        "num": 64,
        "canonical": "3 John",
        "names": {
            "en": ["3 John", "3 Joh", "3Jo", "3Jn"],
            "es": ["3 Juan", "3 Jn", "3Jn", "3Jua"],
            "pt": ["3 João", "3 Joã", "3Jo"],
        },
    },
    {
        "num": 65,
        "canonical": "Jude",
        "names": {"en": ["Jude", "Jud"], "es": ["Judas", "Jud"], "pt": ["Judas", "Jud", "Jd"]},
    },
    {
        "num": 66,
        "canonical": "Revelation",
        "names": {
            "en": ["Revelation", "Rev", "Re"],
            "es": ["Apocalipsis", "Ap", "Apo"],
            "pt": ["Apocalipse", "Apo", "Ap"],
        },
    },
]


# Sanity check at import time
assert len(BOOKS) == 66, f"Expected 66 books, got {len(BOOKS)}"
assert [b["num"] for b in BOOKS] == list(range(1, 67)), "Book numbers must be 1..66 in order"

# Tier-1 expansion (Module 8 / Gap 5): merge fr/de/it/ru/ja/ko/zh names.
from jw_core.data.books_tier1 import merge_into as _merge_tier1  # noqa: E402

_merge_tier1(BOOKS)

# Phase 20: merge 17 locales ported from msakowski/obsidian-library-linker.
# Adds rich short/medium/long names + community aliases for cs/hr/da/de/en/fr/
# fi/it/ja/ko/nl/pt-PT/es/tl/ru/vi/bem. Idempotent against the tier-1 merge.
from jw_core.data.book_locales import merge_into_books as _merge_book_locales  # noqa: E402

_merge_book_locales(BOOKS)
