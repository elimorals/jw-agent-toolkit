"""``jw versification`` — map a reference between numbering traditions.

Three subcommands:
  map      <ref> --from nwt --to masoretic     show the mapped coordinate
  explain  <ref> --from nwt --to masoretic     human-readable explanation
  list     [--book Joel]                       list catalog discrepancies
"""

from __future__ import annotations

import typer
from jw_core.parsers.reference import parse_reference
from jw_core.versification import explain as _explain
from jw_core.versification import load_catalog, to_canonical
from jw_core.versification.models import Tradition

versification_app = typer.Typer(
    help="Map Bible references between numbering traditions (Fase 46).",
    no_args_is_help=True,
)


def _parse_or_die(ref: str) -> tuple[str, int, int, int, int | None]:
    parsed = parse_reference(ref)
    if parsed is None:
        raise typer.BadParameter(f"could not parse reference: {ref!r}")
    return (
        parsed.book_canonical,
        parsed.book_num,
        parsed.chapter,
        parsed.verse_start or 1,
        parsed.verse_end,
    )


@versification_app.command("map")
def map_cmd(
    ref: str = typer.Argument(..., help="Bible reference, e.g. 'Joel 2:28'."),
    from_tradition: Tradition = typer.Option(
        "nwt", "--from", help="Source tradition."
    ),
    to_tradition: Tradition = typer.Option(
        ..., "--to", help="Target tradition."
    ),
) -> None:
    """Print the mapped coordinate plus a one-line rationale."""

    book, book_num, chapter, verse_start, verse_end = _parse_or_die(ref)
    result = to_canonical(
        book=book,
        book_num=book_num,
        chapter=chapter,
        verse_start=verse_start,
        verse_end=verse_end,
        from_tradition=from_tradition,
        to_tradition=to_tradition,
    )
    end = (
        f"-{result.coord.verse_end}"
        if result.coord.verse_end is not None
        and result.coord.verse_end != result.coord.verse_start
        else ""
    )
    typer.echo(
        f"{result.ref_book} {result.coord.chapter}:"
        f"{result.coord.verse_start}{end} ({to_tradition})"
    )
    if result.rationale:
        typer.echo(result.rationale)


@versification_app.command("explain")
def explain_cmd(
    ref: str = typer.Argument(..., help="Bible reference, e.g. 'Psalm 51:1'."),
    from_tradition: Tradition = typer.Option("nwt", "--from"),
    to_tradition: Tradition = typer.Option(..., "--to"),
    language: str = typer.Option("en", "--lang", help="en|es|pt"),
) -> None:
    """Print the trilingual explanation for the discrepancy (if any)."""

    book, book_num, chapter, verse_start, verse_end = _parse_or_die(ref)
    out = _explain(
        book=book,
        book_num=book_num,
        chapter=chapter,
        verse_start=verse_start,
        verse_end=verse_end,
        from_tradition=from_tradition,
        to_tradition=to_tradition,
        language=language,  # type: ignore[arg-type]
    )
    typer.echo(out if out else "(no discrepancy — identical reference)")


@versification_app.command("list")
def list_cmd(
    book: str | None = typer.Option(
        None, "--book", help="Filter by canonical book name."
    ),
) -> None:
    """List catalog entries, optionally filtered by book."""

    catalog = load_catalog()
    if book:
        catalog = [e for e in catalog if e.book.lower() == book.lower()]
    typer.echo(f"{len(catalog)} entries")
    for e in catalog:
        nwt = e.nwt
        typer.echo(
            f"  {e.book} {nwt.chapter}:{nwt.verse_start}"
            + (f"-{nwt.verse_end}" if nwt.verse_end else "")
            + f"  [{e.issue}]"
        )
