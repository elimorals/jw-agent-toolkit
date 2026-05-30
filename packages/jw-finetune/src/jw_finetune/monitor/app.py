"""FastAPI app for the live training dashboard.

Routes:
  GET  /                — dashboard HTML (HTMX-driven)
  GET  /api/metrics     — JSON snapshot of system metrics
  GET  /api/events      — recent buffered events (JSON)
  WS   /ws/events       — live event stream
  GET  /static/*        — static assets
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from jw_finetune.monitor.metrics import collect as collect_metrics
from jw_finetune.monitor.store import EventStore

logger = logging.getLogger(__name__)


def _templates_dir() -> Path:
    return Path(__file__).parent / "templates"


def _static_dir() -> Path:
    return Path(__file__).parent / "static"


def create_app(events_path: Path) -> Any:  # FastAPI not type-imported at top
    """Build a FastAPI app bound to the given events.jsonl path."""
    try:
        from contextlib import asynccontextmanager

        from fastapi import FastAPI, WebSocket, WebSocketDisconnect  # type: ignore[import-not-found]
        from fastapi.responses import HTMLResponse, JSONResponse  # type: ignore[import-not-found]
        from fastapi.staticfiles import StaticFiles  # type: ignore[import-not-found]
    except ImportError as e:
        raise ImportError(
            "fastapi required: install with `--extra monitor`"
        ) from e

    store = EventStore(events_path)

    @asynccontextmanager
    async def lifespan(_app: Any):
        store.start()
        try:
            yield
        finally:
            await store.stop()

    app = FastAPI(title="jw-finetune monitor", lifespan=lifespan)

    @app.get("/", response_class=HTMLResponse)
    async def index() -> str:
        html = (_templates_dir() / "dashboard.html").read_text(encoding="utf-8")
        return html

    @app.get("/api/metrics")
    async def api_metrics() -> Any:
        m = collect_metrics()
        return JSONResponse(m.to_dict())

    @app.get("/api/events")
    async def api_events(limit: int = 200) -> Any:
        evs = list(store.buffer)[-limit:]
        return JSONResponse({"events": evs, "count": len(evs)})

    @app.websocket("/ws/events")
    async def ws_events(ws: WebSocket) -> None:  # pragma: no cover
        await ws.accept()
        try:
            async for ev in store.subscribe():
                await ws.send_text(json.dumps(ev, default=str))
        except WebSocketDisconnect:
            return
        except Exception as e:  # noqa: BLE001
            logger.warning("WS error: %s", e)

    if _static_dir().exists():
        app.mount(
            "/static", StaticFiles(directory=str(_static_dir())), name="static"
        )

    return app


def run(events_path: Path, *, host: str = "127.0.0.1", port: int = 7860) -> None:
    """Block-run the dashboard server."""
    try:
        import uvicorn  # type: ignore[import-not-found]
    except ImportError as e:
        raise ImportError(
            "uvicorn required: install with `--extra monitor`"
        ) from e

    app = create_app(events_path)
    uvicorn.run(app, host=host, port=port, log_level="info")
