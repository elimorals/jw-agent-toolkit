"""WhatsApp adapter (via Meta Cloud API).

We don't ship a full bot server — the user typically deploys this behind
a webhook (FastAPI / Cloudflare Worker / etc.). What we provide is the
RESPONDER + `dispatch_message` glue.

Usage from a FastAPI webhook:

    from fastapi import FastAPI, Request
    from jw_mcp.bots import BotMessage, build_whatsapp_responder, dispatch_message

    app = FastAPI()

    @app.post("/whatsapp/webhook")
    async def whatsapp_webhook(request: Request):
        payload = await request.json()
        # ...parse payload['entry'][...] into text + sender id...
        responder = build_whatsapp_responder(phone_id="...", access_token="...", to=sender)
        await dispatch_message(BotMessage(text=text, language="en", platform="whatsapp"), responder)
        return {"ok": True}
"""

from __future__ import annotations

import logging

import httpx

logger = logging.getLogger(__name__)

_API_URL = "https://graph.facebook.com/v20.0/{phone_id}/messages"


class _WhatsAppResponder:
    def __init__(self, *, phone_id: str, access_token: str, to: str, http: httpx.AsyncClient | None = None) -> None:
        self.phone_id = phone_id
        self.access_token = access_token
        self.to = to
        self._http = http or httpx.AsyncClient(timeout=20.0)
        self._owns_http = http is None

    async def send(self, text: str) -> None:
        try:
            await self._http.post(
                _API_URL.format(phone_id=self.phone_id),
                headers={"Authorization": f"Bearer {self.access_token}"},
                json={
                    "messaging_product": "whatsapp",
                    "to": self.to,
                    "type": "text",
                    "text": {"body": text[:4090]},
                },
            )
        except Exception as e:  # pragma: no cover - network only
            logger.warning(f"WhatsApp send failed: {e}")

    async def typing(self) -> None:
        # WhatsApp Cloud API doesn't expose a typing-indicator endpoint; no-op.
        return None

    async def aclose(self) -> None:
        if self._owns_http:
            await self._http.aclose()


def build_whatsapp_responder(*, phone_id: str, access_token: str, to: str) -> _WhatsAppResponder:
    """Construct a responder bound to a single conversation."""
    return _WhatsAppResponder(phone_id=phone_id, access_token=access_token, to=to)
