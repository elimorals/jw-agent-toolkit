# Canonical Versification (Fase 46)

Map a Bible reference between the four numbering traditions the toolkit
recognises: `nwt` (default, matches NWT and KJV), `masoretic` (BHS),
`lxx` (Septuagint), `vulgate`.

## Quick start

```bash
# NWT Joel 2:28 corresponds to BHS Joel 3:1
uv run jw versification map "Joel 2:28" --to masoretic
# -> Joel 3:1-5 (masoretic)
# -> Joel 2:28-32 in the NWT and other Christian Bibles corresponds to Joel 3:1-5...

# Trilingual prose
uv run jw versification explain "Psalms 51:1" --to lxx --lang es

# List the catalog for one book
uv run jw versification list --book Joel
```

## Why this exists

The NWT inherits Christian (Vulgate / KJV) numbering. The Hebrew Masoretic
Text and the Septuagint diverge in about 150 documented points: Psalm
superscriptions counted as verse 0 (BHS) vs verse 1 (NWT), Joel 2:28-32
renumbered as Joel 3:1-5 in BHS, Malachi 4 renumbered as Malachi 3:19-24,
LXX merging Psalms 9 and 10, etc. Without a canonical mapping the
cross-reference finder reports false positives and apologetic Q&A misses
the underlying explanation.

## Programmatic use

```python
from jw_core.versification import to_canonical, explain

result = to_canonical(
    book="Malachi", book_num=39,
    chapter=4, verse_start=1, verse_end=6,
    from_tradition="nwt", to_tradition="masoretic",
)
print(result.coord.chapter, result.coord.verse_start, result.coord.verse_end)
# 3 19 24

print(explain(
    book="Malachi", book_num=39, chapter=4, verse_start=1,
    from_tradition="nwt", to_tradition="masoretic", language="es",
))
```

## Catalog

`packages/jw-core/src/jw_core/data/versification_map.json` ships 30 curated
seed entries covering the most famous discrepancies (Joel, Malachi, Psalm
superscriptions, LXX Psalm 9/10 merge, Daniel 3/4 split, etc.). Every entry
carries:

- A short academic `source` (Tov 2012, BHS apparatus, NETS prefaces, etc.).
- `explanation` in **en / es / pt** — original prose by the maintainer, never
  copied from sources. This keeps the file compatible with GPL-3.0.

## Hard rules

- `to_canonical(ref, from_=t, to_=t)` is identity — no-op.
- A reference with no catalog match returns `is_discrepant=False` and the
  original coordinate.
- Round-trip preserves: forward then backward on a catalog entry yields the
  original (book, chapter, verse range).
- `verse_start = 0` is reserved for BHS/LXX Psalm titles. NWT never has 0.

## Limits (out of scope for v1)

- No Syriac, Coptic, Ethiopic, or Samaritan numbering.
- No textual content — only coordinates. `WOLClient` handles fetching text.
- No LLM-generated explanations. All prose is committed to the JSON.
