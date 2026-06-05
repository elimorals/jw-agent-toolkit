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
    apologetics as apologetics_module,
)
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
from jw_cli.commands import (
    eval as eval_module,
)
from jw_cli.commands import (
    export as export_module,
)
from jw_cli.commands import (
    gen as gen_module,
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
from jw_brain.cli import brain_app
from jw_cli.commands.chunker_bench import chunker_bench_cmd
from jw_cli.commands.constrained import constrained_app
from jw_cli.commands.create_agent import create_agent_cmd
from jw_cli.commands.image import image_app
from jw_cli.commands.omnilingual import omnilingual_app
from jw_cli.commands.plugins import app as plugins_app
from jw_cli.commands.provenance import provenance_app
from jw_cli.commands.rag import rag_app

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
app.add_typer(jwpub.jwpub_app, name="jwpub")
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
app.add_typer(rag_app, name="rag")
app.add_typer(gen_module.gen_app, name="gen")
app.command(name="export")(export_module.export_cmd)
app.command(name="life")(life.life_cmd)
app.command(name="eval")(eval_module.eval_cmd)
app.command(name="say")(say.say_cmd)
app.command(name="transcribe")(transcribe.transcribe_cmd)
from jw_cli.commands.library import library_app
from jw_cli.commands.translate import translate_cmd

app.command(name="translate", help="Translate preserving Bible refs (F54.2, NLLB-200).")(translate_cmd)
app.add_typer(library_app, name="library", help="JW Library backup IO (F54.3).")
app.add_typer(constrained_app, name="constrained")
app.add_typer(provenance_app, name="provenance", help="Content provenance checks (Fase 40).")
app.add_typer(plugins_app, name="plugins", help="Manage community plugins (Fase 41).")
app.add_typer(brain_app, name="brain", help="Second-brain (Fase 49).")
app.add_typer(omnilingual_app, name="omnilingual", help="Omnilingual ASR worker venv (Fase 53).")
from jw_agents.tracing.viewer import app as _trace_app

app.add_typer(_trace_app, name="trace", help="Inspect agent traces (Fase 43).")
from jw_cli.commands.versification import versification_app

app.add_typer(
    versification_app,
    name="versification",
    help="Map Bible refs between numbering traditions (Fase 46).",
)
app.command(name="chunker-bench", help="Benchmark chunker variants (Fase 45).")(chunker_bench_cmd)
app.command(
    name="create-agent",
    help="Scaffold a new plugin (delegates to create-jw-agent — Fase 42).",
    context_settings={"allow_extra_args": True, "ignore_unknown_options": True},
)(create_agent_cmd)
app.command(name="apologetics")(apologetics_module.apologetics_cmd)

# F64 — `jw audio transcribe` (diarización + bible-refs)
from jw_cli.commands.audio import audio_app

app.add_typer(audio_app, name="audio", help="Audio: transcripción + diarización (Fase 64).")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
