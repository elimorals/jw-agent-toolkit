"""`jw ministry` — door-to-door companion: objections + revisits + lookups.

Subcommands:
    jw ministry objections
    jw ministry answer "Why don't you believe in the Trinity?"
    jw ministry revisit add john1 --name "John" --topic "Trinity" --next 2026-06-04
    jw ministry revisit list
    jw ministry revisit due 2026-06-30
    jw ministry quote "the unity of brotherly love"
"""

from __future__ import annotations

import asyncio
import json

import typer
from jw_agents import (
    Revisit,
    RevisitStore,
    conversation_assistant,
    list_audiences,
    plan_next_visit,
    presentation_builder,
    reverse_citation_lookup,
)
from jw_core.data.objections import list_objections
from rich.console import Console
from rich.table import Table

console = Console()

ministry_app = typer.Typer(name="ministry", help="Ministry helpers: objections, revisits, audience presentations.")
revisit_app = typer.Typer(name="revisit", help="Manage local revisit notes (never synced).")
ministry_app.add_typer(revisit_app)


@ministry_app.command("objections")
def list_objections_cmd(language: str = typer.Option("en", "--lang", "-l")) -> None:
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("key")
    table.add_column("label", overflow="fold")
    table.add_column("topics")
    for o in list_objections(language):
        table.add_row(o["key"], o["label"], ", ".join(o["topic_anchors"]))
    console.print(table)


@ministry_app.command("answer")
def answer_cmd(
    text: str,
    language: str = typer.Option("E", "--lang", "-l"),
    max_subheadings: int = typer.Option(6, "--max"),
) -> None:
    result = asyncio.run(conversation_assistant(text, language=language, max_subheadings=max_subheadings))
    console.print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))


@ministry_app.command("audiences")
def audiences_cmd(language: str = typer.Option("en", "--lang", "-l")) -> None:
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("key")
    table.add_column("label")
    table.add_column("topics", overflow="fold")
    for a in list_audiences(language):
        table.add_row(a["key"], a["label"], ", ".join(a["topics"]))
    console.print(table)


@ministry_app.command("present")
def present_cmd(
    audience: str,
    language: str = typer.Option("E", "--lang", "-l"),
) -> None:
    result = asyncio.run(presentation_builder(audience, language=language))
    console.print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))


@ministry_app.command("quote")
def quote_cmd(
    quote: str,
    language: str = typer.Option("E", "--lang", "-l"),
    top_n: int = typer.Option(8, "--top-n"),
    min_confidence: float = typer.Option(0.4, "--min"),
) -> None:
    result = asyncio.run(reverse_citation_lookup(quote, language=language, top_n=top_n, min_confidence=min_confidence))
    console.print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))


@revisit_app.command("add")
def revisit_add_cmd(
    interest_id: str,
    name: str = typer.Option("(anonymous)", "--name", "-n"),
    language: str = typer.Option("en", "--lang", "-l"),
    topic: str = typer.Option("", "--topic", "-t"),
    notes: str = typer.Option("", "--notes"),
    next: str = typer.Option("", "--next", help="Next visit ISO date"),
) -> None:
    with RevisitStore() as store:
        store.upsert(
            Revisit(
                interest_id=interest_id,
                name_alias=name,
                language=language,
                last_topic=topic,
                notes=notes,
                next_visit_iso=next,
            )
        )
    console.print(f"[green]Saved[/green] revisit [bold]{interest_id}[/bold]")


@revisit_app.command("list")
def revisit_list_cmd(language: str = typer.Option("", "--lang", "-l")) -> None:
    with RevisitStore() as store:
        items = store.list_all(language=language or None)
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("id")
    table.add_column("alias")
    table.add_column("language")
    table.add_column("last topic", overflow="fold")
    table.add_column("next visit")
    for r in items:
        table.add_row(r.interest_id, r.name_alias, r.language, r.last_topic, r.next_visit_iso)
    console.print(table)


@revisit_app.command("due")
def revisit_due_cmd(on_or_before: str) -> None:
    with RevisitStore() as store:
        items = store.due(on_or_before=on_or_before)
    console.print(json.dumps([r.to_row() for r in items], indent=2, ensure_ascii=False))


@revisit_app.command("plan")
def revisit_plan_cmd(interest_id: str, language: str = typer.Option("en", "--lang", "-l")) -> None:
    with RevisitStore() as store:
        rev = store.get(interest_id)
    if rev is None:
        console.print(f"[red]No revisit with id {interest_id!r}[/red]")
        raise typer.Exit(1)
    console.print(json.dumps(plan_next_visit(rev, language=language), indent=2, ensure_ascii=False))


@revisit_app.command("delete")
def revisit_delete_cmd(interest_id: str) -> None:
    with RevisitStore() as store:
        ok = store.delete(interest_id)
    console.print(f"deleted={ok}")
