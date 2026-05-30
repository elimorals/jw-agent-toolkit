"""Cross-platform bot dispatcher.

Defines a tiny domain language so Telegram + WhatsApp handlers can share
the same business logic:

  - `BotMessage(text, language, sender_id, platform)` — input
  - `BotResponder` — anything with `.send(text)` and `.typing()`
  - `dispatch_message(msg, responder)` — routes to the appropriate agent

Slash commands handled out-of-the-box:
    /verse <ref>
    /daily [YYYY-MM-DD]
    /search <query>
    /apologetics <question>
    /workbook [YYYY-MM-DD]
    /quote <text>
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from jw_agents.apologetics import apologetics
from jw_agents.conversation_assistant import conversation_assistant
from jw_agents.reverse_citation_lookup import reverse_citation_lookup
from jw_agents.workbook_helper import workbook_helper
from jw_core.clients.cdn import CDNClient
from jw_core.clients.wol import WOLClient
from jw_core.languages import get_language
from jw_core.parsers.daily_text import parse_daily_text
from jw_core.parsers.reference import parse_reference
from jw_core.parsers.verse import get_verse


@dataclass
class BotMessage:
    text: str
    language: str = "en"
    sender_id: str = ""
    platform: str = "unknown"


class BotResponder(Protocol):
    async def send(self, text: str) -> None: ...
    async def typing(self) -> None: ...


async def dispatch_message(
    msg: BotMessage,
    responder: BotResponder,
    *,
    cdn: CDNClient | None = None,
    wol: WOLClient | None = None,
) -> None:
    """Route `msg.text` to the right agent and stream back a response."""
    text = msg.text.strip()
    cmd, _, payload = text.partition(" ")
    cmd = cmd.lower()
    await responder.typing()

    own_clients = cdn is None and wol is None
    cdn = cdn or CDNClient()
    wol = wol or WOLClient()

    try:
        if cmd == "/verse":
            ref = parse_reference(payload) if payload else None
            if ref is None or ref.verse_start is None:
                await responder.send("Use: /verse John 3:16")
                return
            url, html = await wol.get_bible_chapter(ref.book_num, ref.chapter, language=msg.language)
            v = get_verse(html, ref.book_num, ref.chapter, ref.verse_start, language=msg.language)
            if v is None:
                await responder.send(f"Verse not found.\n{url}")
                return
            await responder.send(f"{ref.display()}\n\n{v.text}\n\n{v.wol_url()}")

        elif cmd == "/daily":
            if payload:
                url, html = await wol.get_daily_text_by_date(payload, language=msg.language)
            else:
                url, html = await wol.get_today_homepage(language=msg.language)
            text_obj = parse_daily_text(html)
            if text_obj is None:
                await responder.send(f"Could not parse daily text.\n{url}")
                return
            await responder.send(f"{text_obj.date}\n\n{text_obj.scripture}\n\n{text_obj.commentary}\n\n{url}")

        elif cmd == "/search":
            if not payload:
                await responder.send("Use: /search amor")
                return
            lang = get_language(msg.language)
            data = await cdn.search(payload, language=lang.jw_code, limit=3)
            urls = []
            for r in data.get("results", [])[:3]:
                if isinstance(r, dict):
                    link = (r.get("links") or {}).get("wol")
                    if link:
                        urls.append(f"• {r.get('title', '')}\n  {link}")
            await responder.send("\n\n".join(urls) or "No results.")

        elif cmd == "/apologetics":
            if not payload:
                await responder.send("Use: /apologetics Why don't you celebrate Christmas?")
                return
            result = await apologetics(payload, language=msg.language.upper(), cdn=cdn, wol=wol)
            await responder.send(_summarize_findings(result.findings, max_items=4))

        elif cmd == "/workbook":
            result = await workbook_helper(payload or None, language=msg.language, wol=wol)
            await responder.send(_summarize_findings(result.findings, max_items=6))

        elif cmd == "/quote":
            if not payload:
                await responder.send("Use: /quote <verbatim quote to identify>")
                return
            result = await reverse_citation_lookup(payload, language=msg.language.upper(), cdn=cdn, wol=wol)
            await responder.send(_summarize_findings(result.findings, max_items=3))

        elif cmd in {"/help", "/start"}:
            await responder.send(_HELP_TEXT)

        else:
            # Fallback: treat as a free-form conversation prompt.
            result = await conversation_assistant(text, language=msg.language.upper(), cdn=cdn, wol=wol)
            await responder.send(_summarize_findings(result.findings, max_items=5))
    finally:
        if own_clients:
            await cdn.aclose()
            await wol.aclose()


_HELP_TEXT = (
    "Commands:\n"
    "/verse John 3:16\n"
    "/daily [YYYY-MM-DD]\n"
    "/search <query>\n"
    "/apologetics <question>\n"
    "/workbook [YYYY-MM-DD]\n"
    "/quote <quote text>\n"
)


def _summarize_findings(findings, *, max_items: int) -> str:  # type: ignore[no-untyped-def]
    if not findings:
        return "(no relevant material)"
    parts = []
    for f in findings[:max_items]:
        parts.append(f"• {f.summary}\n  {f.citation.url}".rstrip())
    return "\n\n".join(parts)
