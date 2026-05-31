"""Tests for the bots subsystem (Module 10) — protocol shape only."""

from __future__ import annotations

import asyncio

from jw_mcp.bots.protocols import (
    _HELP_TEXT,
    BotMessage,
    _summarize_findings,
)


class _CollectingResponder:
    def __init__(self) -> None:
        self.messages: list[str] = []
        self.typed = 0

    async def send(self, text: str) -> None:
        self.messages.append(text)

    async def typing(self) -> None:
        self.typed += 1


def test_bot_message_dataclass_defaults() -> None:
    m = BotMessage(text="hello")
    assert m.language == "en"
    assert m.platform == "unknown"


def test_help_text_includes_commands() -> None:
    for cmd in ("/verse", "/daily", "/search", "/apologetics", "/workbook", "/quote"):
        assert cmd in _HELP_TEXT


def test_summarize_empty_findings() -> None:
    assert _summarize_findings([], max_items=3).startswith("(")


def test_summarize_truncates_to_max() -> None:
    class F:
        def __init__(self, summary: str, url: str) -> None:
            self.summary = summary

            class _C:
                pass

            self.citation = _C()
            self.citation.url = url

    findings = [F(f"item {i}", f"https://x/{i}") for i in range(10)]
    out = _summarize_findings(findings, max_items=3)
    assert out.count("•") == 3


def test_responder_protocol_collects_messages() -> None:
    responder = _CollectingResponder()
    asyncio.run(responder.send("hello"))
    asyncio.run(responder.typing())
    assert responder.messages == ["hello"]
    assert responder.typed == 1
