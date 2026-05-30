# Infraestructura operacional (Módulo 10 — Fase 15)

> Cubre el ítem #10 de [VISION.md](../VISION.md): logging estructurado, REST API sobre MCP, bots de Telegram/WhatsApp, esqueleto para dashboard.

## Logging estructurado

`jw_core/observability/logging_setup.py`:

```python
from jw_core.observability import configure_logging, get_logger, log_event

configure_logging(level="INFO", fmt="json")  # o "text"
log = get_logger("jw.mcp.request")
log_event(log, "request_received", endpoint="/api/v1/verse", duration_ms=12)
```

Resultado en `fmt="json"`:
```json
{"ts": "2026-05-30T10:00:00", "level": "INFO", "logger": "jw.mcp.request",
 "msg": "request_received", "endpoint": "/api/v1/verse", "duration_ms": 12}
```

**Env vars:**
- `JW_LOG_LEVEL=DEBUG|INFO|WARNING|ERROR`
- `JW_LOG_FORMAT=text|json`

Listo para ingesta en Loki, Datadog, CloudWatch, etc.

## REST API sobre MCP

`packages/jw-mcp/src/jw_mcp/rest_api.py` — FastAPI app exponiendo los agentes core:

```bash
uv pip install fastapi uvicorn
uv run uvicorn jw_mcp.rest_api:app --host 0.0.0.0 --port 8765
```

**Endpoints (todos POST JSON salvo `/healthz`):**

| Path | Body | Devuelve |
|---|---|---|
| `GET /healthz` | — | `{"status": "ok"}` |
| `/api/v1/verse` | `{book_num, chapter, verse, language}` | Texto del versículo + WOL URL |
| `/api/v1/daily` | `{language, date?}` | Texto diario |
| `/api/v1/search` | `{query, language, limit, filter_type}` | Resultados CDN |
| `/api/v1/apologetics` | `{question, language}` | AgentResult |
| `/api/v1/workbook` | `{date?, language}` | Programa semanal |
| `/api/v1/conversation` | `{text, language}` | Respuesta a objeción |

CORS abierto (cualquier origen) — para producción, restringe `allow_origins`.

## Bots

Tres archivos en `packages/jw-mcp/src/jw_mcp/bots/`:

- `protocols.py` — `BotMessage`, `BotResponder` Protocol, `dispatch_message(msg, responder)`.
- `telegram_adapter.py` — `build_telegram_handler()` para `python-telegram-bot`.
- `whatsapp_adapter.py` — `build_whatsapp_responder(phone_id, access_token, to)` para Cloud API.

### Comandos slash soportados

```
/verse <ref>         — texto + URL canónica
/daily [YYYY-MM-DD]  — texto diario
/search <query>      — top 3 resultados con URLs
/apologetics <q>     — respuesta a objeción
/workbook [date]     — programa semanal de reunión
/quote <texto>       — búsqueda inversa de cita
/help                — ayuda
```

Mensajes que no son comandos son tratados como una objeción (`conversation_assistant`).

### Ejemplo Telegram (60 líneas para arrancar)

```python
# bot.py
from telegram.ext import Application
from jw_mcp.bots import build_telegram_handler

app = Application.builder().token("YOUR_BOT_TOKEN").build()
app.add_handler(build_telegram_handler())
app.run_polling()
```

### Ejemplo WhatsApp (Meta Cloud API + FastAPI webhook)

```python
from fastapi import FastAPI, Request
from jw_mcp.bots import BotMessage, build_whatsapp_responder, dispatch_message

api = FastAPI()

@api.post("/whatsapp/webhook")
async def webhook(request: Request):
    payload = await request.json()
    # ... extrae text + sender_id desde payload['entry'][0]['changes'] ...
    text, sender_id = extract(payload)
    responder = build_whatsapp_responder(
        phone_id="123",
        access_token="EAAB...",
        to=sender_id,
    )
    await dispatch_message(
        BotMessage(text=text, language="en", sender_id=sender_id, platform="whatsapp"),
        responder,
    )
    return {"ok": True}
```

## Privacidad

- El REST API y bots **no persisten** mensajes por defecto. El usuario controla el storage (revisita tracker, notes, etc.) que esté ya en SQLite local.
- Para producción, agregar middleware de rate-limiting y autenticación (token bearer) antes del despliegue público.

## Tests

- `packages/jw-core/tests/test_observability_module.py` — 4 tests (json/text formatters, env-var override, extra fields).
- `packages/jw-mcp/tests/test_bots_module.py` — 5 tests (help text, summarizer, responder protocol).

```bash
uv run pytest packages/jw-core/tests/test_observability_module.py packages/jw-mcp/tests/test_bots_module.py -v
```

## Cómo extender

- **Dashboard web:** Streamlit o Vite + un backend que monte `rest_api.app` como sub-app FastAPI.
- **Telegram con persistencia:** middleware `dispatch_message` para grabar conversación en `RevisitStore`.
- **Multi-tenant API:** anteceder un middleware `X-Tenant-ID` y separar caches/DBs por tenant.

## Pendiente

- App de escritorio Tauri (VISION 10) — `tauri` wrapping React + el REST API.
- Sync multi-dispositivo E2E (Módulo 11).
- Publicación de `jw-core` a PyPI (Fase 9 pendiente operacional).
