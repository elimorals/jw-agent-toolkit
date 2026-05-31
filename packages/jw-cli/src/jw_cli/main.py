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
    citations,
    daily,
    download,
    jwpub,
    languages,
    life,
    ministry,
    news,
    say,
    search,
    song,
    student,
    study,
    topic,
    transcribe,
    verse,
    workbook,
)
from jw_cli.commands.image import image_app
from jw_cli.commands import (
    eval as eval_module,
)
from jw_cli.commands import (
    export as export_module,
)
from jw_cli.commands import (
    grep as grep_module,
)
from jw_cli.commands import (
    letter as letter_module,
)
from jw_cli.commands import (
    report as report_module,
)

app = typer.Typer(
    name="jw",
    help="JW.org agentic toolkit — verse lookup, search, daily text, downloads, JWPUB, topics.",
    no_args_is_help=True,
    add_completion=False,
)

# Register subcommands as top-level verbs.
app.command(name="verse")(verse.verse_cmd)
app.command(name="letter")(letter_module.letter_cmd)
app.command(name="search")(search.search_cmd)
app.command(name="daily")(daily.daily_cmd)
app.command(name="languages")(languages.languages_cmd)
app.command(name="download")(download.download_cmd)
app.command(name="chapter")(chapter.chapter_cmd)
app.command(name="jwpub")(jwpub.jwpub_cmd)
app.command(name="topic")(topic.topic_cmd)
app.command(name="workbook")(workbook.workbook_command)
app.command(name="student")(student.student_command)
app.command(name="grep", help="Literal concordance search over the local corpus.")(grep_module.grep_cmd)
app.add_typer(ministry.ministry_app, name="ministry")
app.add_typer(song.song_app, name="song")
app.add_typer(citations.citations_app, name="citations")
app.add_typer(study.study_app, name="study")
app.add_typer(news.news_app, name="news")
app.add_typer(report_module.report_app, name="report")
app.add_typer(image_app, name="image")
app.command(name="export")(export_module.export_cmd)
app.command(name="life")(life.life_cmd)
app.command(name="eval")(eval_module.eval_cmd)
app.command(name="say")(say.say_cmd)
app.command(name="transcribe")(transcribe.transcribe_cmd)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
