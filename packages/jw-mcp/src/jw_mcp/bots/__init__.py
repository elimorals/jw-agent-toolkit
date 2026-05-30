"""Bot adapters (Telegram + WhatsApp).

Both adapters share a common `BotResponder` protocol so the same handler
can serve either platform. The actual SDK glue (python-telegram-bot,
heyoo, etc.) lives in their own optional install lines.
"""

from jw_mcp.bots.protocols import BotMessage, BotResponder, dispatch_message
from jw_mcp.bots.telegram_adapter import build_telegram_handler
from jw_mcp.bots.whatsapp_adapter import build_whatsapp_responder

__all__ = [
    "BotMessage",
    "BotResponder",
    "build_telegram_handler",
    "build_whatsapp_responder",
    "dispatch_message",
]
