"""Build a synthetic Insight-style JWPUB fixture for deterministic tests.

This script produces `it_mini.jwpub`, a tiny self-contained JWPUB that mimics
the structure of *Insight on the Scriptures* (`it` symbol) just enough for the
F58.7 Insight parser to exercise its heading + WOL-link extraction logic
without needing the real (copyrighted, ~30 MB) publication.

It contains three entries — Abraham, Jerusalem, Moses — each with a single
WOL cross-reference in the body. Their `MepsDocumentId`s are stable so tests
can assert on them.

We reuse `jw_core.writers.jwpub.JwpubBuilder` so the encryption + manifest +
SQLite schema stay in lock-step with `jw_core.parsers.jwpub.parse_jwpub`. If
the parser ever changes its expected layout, both halves move together and
this fixture keeps round-tripping for free.

Run:
    uv run python packages/jw-brain/tests/fixtures/insight_mini/build_fixture.py
"""

from __future__ import annotations

from pathlib import Path

from jw_core.writers.jwpub import JwpubBuilder

# ── Entries ─────────────────────────────────────────────────────────────
# Each entry is one Insight headword. The body XHTML uses the same `<a class="b">`
# pattern WOL produces for Bible cross-references, which is what the F58.7
# Insight parser will pattern-match against.

_ENTRIES: list[tuple[str, str, str]] = [
    (
        "Abraham",
        "/en/wol/b/r1/lp-e/nwtsty/1/11#study=discover&v=1:11:26",
        "Gen. 11:26",
    ),
    (
        "Jerusalem",
        "/en/wol/b/r1/lp-e/nwtsty/10/5#study=discover&v=10:5:6",
        "2 Sam. 5:6",
    ),
    (
        "Moses",
        "/en/wol/b/r1/lp-e/nwtsty/2/2#study=discover&v=2:2:10",
        "Ex. 2:10",
    ),
]


def _build_xhtml(title: str, href: str, label: str) -> str:
    """Return a minimal Insight-style XHTML body for one headword.

    Uses `data-pid` so `_extract_paragraphs` in the JWPUB parser keeps the
    body paragraph (`get_text` heuristic drops `<p>`s without it for most
    publications).
    """
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<article xmlns="http://www.w3.org/1999/xhtml">\n'
        f'  <h1 class="title">{title}</h1>\n'
        f'  <p data-pid="1">'
        f'Definition placeholder for <strong>{title}</strong>. '
        f'See <a class="b" href="{href}">{label}</a>.'
        f'</p>\n'
        "</article>\n"
    )


def main() -> Path:
    out_path = Path(__file__).with_name("it_mini.jwpub")

    builder = JwpubBuilder(
        symbol="it",
        title="Insight on the Scriptures (mini fixture)",
        year=2025,
        meps_language_index=0,  # English
        publication_type="Encyclopedia",
        category="reference",
    )

    # MepsDocumentIds are assigned by JwpubBuilder as 12_000_000 + idx + 1 →
    # 12000001 / 12000002 / 12000003 for the three entries here. The F58.7
    # parser keys on Title, not MepsDocumentId, so the exact ids don't matter
    # for the tests — only that they're stable across rebuilds, which they are.
    for title, href, label in _ENTRIES:
        builder.add_document(title=title, content=_build_xhtml(title, href, label))

    builder.build(out_path)
    size = out_path.stat().st_size
    print(f"Wrote {out_path} ({size} bytes, {len(_ENTRIES)} entries)")
    return out_path


if __name__ == "__main__":
    main()
