"""jw CLI entry point.

Usage:
    jw verse "Juan 3:16"
    jw search "amor" --lang S
    jw daily
    jw languages
    jw download fg --lang E --format EPUB --out ./downloads/
    jw chapter 43 3 --lang en
"""

from __future__ import annotations

import typer

from jw_cli.commands import (
    chapter,
    daily,
    download,
    jwpub,
    languages,
    search,
    topic,
    verse,
)

app = typer.Typer(
    name="jw",
    help="JW.org agentic toolkit — verse lookup, search, daily text, downloads, JWPUB, topics.",
    no_args_is_help=True,
    add_completion=False,
)

# Register subcommands as top-level verbs.
app.command(name="verse")(verse.verse_cmd)
app.command(name="search")(search.search_cmd)
app.command(name="daily")(daily.daily_cmd)
app.command(name="languages")(languages.languages_cmd)
app.command(name="download")(download.download_cmd)
app.command(name="chapter")(chapter.chapter_cmd)
app.command(name="jwpub")(jwpub.jwpub_cmd)
app.command(name="topic")(topic.topic_cmd)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
