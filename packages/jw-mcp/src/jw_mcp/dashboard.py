"""Dashboard — single-page web view over the toolkit state.

Mounted alongside the REST API:

    uv pip install fastapi uvicorn
    .venv/bin/uvicorn jw_mcp.rest_api:app --port 8765
    open http://localhost:8765/dashboard

Shows:
  - Cache stats (DiskCache size, hit ratio if exposed)
  - RAG store: total chunks, sample sources
  - Upcoming calendar events
  - Profile + memory summary
  - TTS providers available
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from jw_core.audio.tts import list_tts_providers
from jw_core.calendar.events import upcoming_for_user
from jw_core.calendar.memorial import countdown_to_memorial
from jw_core.personalization.memory import load_memory_for_user
from jw_core.personalization.profile import UserProfileStore

router = APIRouter()


def _safe_int(n: int) -> str:
    return str(n) if n > 0 else "—"


def _section(title: str, body: str) -> str:
    return f'<section class="card"><h2>{title}</h2>{body}</section>'


def _ul(items: list[str]) -> str:
    if not items:
        return "<p class='muted'>No data.</p>"
    return "<ul>" + "".join(f"<li>{i}</li>" for i in items) + "</ul>"


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard() -> str:
    # Profile
    with UserProfileStore() as ps:
        profile = ps.get("default")
    profile_lines = [
        f"<strong>Language:</strong> {profile.language}",
        f"<strong>Tone:</strong> {profile.tone}",
        f"<strong>Assignments:</strong> {', '.join(profile.assignments) or '—'}",
        f"<strong>Interests:</strong> {', '.join(profile.interests) or '—'}",
    ]

    # Memory
    memories = load_memory_for_user("default", limit=5)
    memory_items = [f"[{m.kind}] {m.text[:60]}" for m in memories]

    # Calendar
    today = date.today()
    upcoming = upcoming_for_user(horizon_days=90, today=today)
    cal_items = [f"{e.start_iso} · {e.kind} · {e.title}" for e in upcoming[:8]]
    memorial = countdown_to_memorial(today=today)
    cal_lead = (
        f"<p><strong>Memorial:</strong> {memorial['memorial_iso']} ({memorial['days_remaining']} days remaining)</p>"
    )

    # TTS providers
    tts_items = [
        f"{p['name']} — {'available' if p['available'] else 'not installed'} ({', '.join(p['languages'][:5])})"
        for p in list_tts_providers()
    ]

    body = (
        _section("Profile", _ul(profile_lines))
        + _section("Recent memory", _ul(memory_items))
        + _section("Upcoming events", cal_lead + _ul(cal_items))
        + _section("TTS engines", _ul(tts_items))
    )
    return _PAGE.format(body=body, today=today.isoformat())


_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>jw-agent-toolkit dashboard</title>
  <style>
    body {{ font-family: -apple-system, system-ui, sans-serif; max-width: 860px;
           margin: 2rem auto; padding: 0 1rem; color: #2b2b2b; background: #fafafa; }}
    h1 {{ font-size: 1.5rem; }}
    .card {{ background: #fff; border: 1px solid #e0e0e0; border-radius: 8px;
             margin: 1rem 0; padding: 1rem; }}
    h2 {{ font-size: 1.05rem; margin-top: 0; color: #1a4d7a; }}
    ul {{ padding-left: 1.25rem; }}
    .muted {{ color: #888; }}
    .footer {{ color: #888; font-size: 0.8rem; text-align: center;
              margin: 1rem 0; }}
  </style>
</head>
<body>
  <h1>jw-agent-toolkit · {today}</h1>
  {body}
  <p class="footer">All data stays on this device.</p>
</body>
</html>
"""
