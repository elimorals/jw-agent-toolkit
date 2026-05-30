"""Telegram adapter using `python-telegram-bot` (optional install).

Usage:

    from jw_mcp.bots import build_telegram_handler

    handler = build_telegram_handler()
    # Plug into python-telegram-bot's Application.add_handler(...)

We don't start the polling loop here — the user runs `Application.run_polling()`
in their own entry point to keep this module free of long-running side effects.
"""

from __future__ import annotations

from typing import Any

from jw_mcp.bots.protocols import BotMessage, dispatch_message


class _TelegramResponder:
    def __init__(self, update: Any, context: Any) -> None:
        self.update = update
        self.context = context

    async def send(self, text: str) -> None:
        await self.update.message.reply_text(text)

    async def typing(self) -> None:
        try:
            await self.context.bot.send_chat_action(
                chat_id=self.update.effective_chat.id, action="typing"
            )
        except Exception:
            pass


async def _handle(update: Any, context: Any) -> None:
    text = (update.message.text or "").strip() if update.message else ""
    if not text:
        return
    language = "en"
    if update.effective_user and update.effective_user.language_code:
        language = update.effective_user.language_code.split("-")[0]
    msg = BotMessage(
        text=text,
        language=language,
        sender_id=str(update.effective_user.id if update.effective_user else ""),
        platform="telegram",
    )
    responder = _TelegramResponder(update, context)
    await dispatch_message(msg, responder)


def build_telegram_handler() -> Any:
    """Construct a Message handler that the user wires to `Application`."""
    try:
        from telegram.ext import MessageHandler, filters
    except ImportError as e:  # pragma: no cover
        raise ImportError(
            "`python-telegram-bot>=21` is required. `pip install python-telegram-bot`"
        ) from e
    return MessageHandler(filters.TEXT & ~filters.COMMAND | filters.COMMAND, _handle)
