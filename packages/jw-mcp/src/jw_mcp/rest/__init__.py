"""REST sub-routers for jw-mcp (Fase 71 post-MVP onwards).

Routers live in submodules and are intentionally NOT auto-mounted on the
global app. Callers wire them explicitly so a deployment can opt-out:

    from jw_mcp.rest.book_camera import router as book_camera_router
    app.include_router(book_camera_router)
"""

from __future__ import annotations

__all__: list[str] = []
