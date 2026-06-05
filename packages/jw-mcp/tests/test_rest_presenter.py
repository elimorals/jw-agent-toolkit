"""F57 — REST endpoints para presenter."""

from __future__ import annotations

from datetime import date

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("starlette")

from httpx import ASGITransport, AsyncClient  # noqa: E402
from jw_meeting_media.models import (  # noqa: E402
    MeetingItem,
    MeetingKind,
    MeetingProgram,
    MeetingSection,
)


@pytest.fixture()
def app_with_program(tmp_path, monkeypatch):
    import jw_mcp.rest_api as rest_api

    monkeypatch.setattr(rest_api, "_storage_singleton", None)
    monkeypatch.setattr(
        rest_api,
        "_meetings_root",
        lambda: tmp_path / "meetings",
    )
    storage = rest_api._storage()
    program = MeetingProgram(
        language="es",
        week_start=date(2026, 6, 1),
        kind=MeetingKind.MIDWEEK,
        sections=[
            MeetingSection(
                section_id="s1",
                title="t",
                items=[
                    MeetingItem(
                        item_id="i1",
                        title="x",
                        position=1,
                        bible_refs=[],
                        media_refs=[],
                    ),
                ],
            ),
        ],
        source_url="x",
    )
    storage.save_program(program)
    return rest_api.app


@pytest.fixture()
def app_with_multi_item_program(tmp_path, monkeypatch):
    """Programa con 3 items para tests de reorder / jump."""
    import jw_mcp.rest_api as rest_api

    monkeypatch.setattr(rest_api, "_storage_singleton", None)
    monkeypatch.setattr(
        rest_api,
        "_meetings_root",
        lambda: tmp_path / "meetings",
    )
    storage = rest_api._storage()
    program = MeetingProgram(
        language="es",
        week_start=date(2026, 6, 1),
        kind=MeetingKind.MIDWEEK,
        sections=[
            MeetingSection(
                section_id="s1",
                title="t",
                items=[
                    MeetingItem(
                        item_id=f"i{j}",
                        title=f"Item {j}",
                        position=j,
                        bible_refs=[],
                        media_refs=[],
                    )
                    for j in range(1, 4)
                ],
            ),
        ],
        source_url="x",
    )
    storage.save_program(program)
    return rest_api.app


@pytest.mark.asyncio
async def test_create_session_returns_id(app_with_program):
    async with AsyncClient(
        transport=ASGITransport(app=app_with_program),
        base_url="http://test",
    ) as ac:
        resp = await ac.post(
            "/presenter/sessions",
            params={"language": "es", "year": 2026, "week": 23, "kind": "midweek"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "session_id" in data


@pytest.mark.asyncio
async def test_play_pause_cycle(app_with_program):
    async with AsyncClient(
        transport=ASGITransport(app=app_with_program), base_url="http://test"
    ) as ac:
        sid = (
            await ac.post(
                "/presenter/sessions",
                params={"language": "es", "year": 2026, "week": 23},
            )
        ).json()["session_id"]
        await ac.post(f"/presenter/sessions/{sid}/play")
        state = (await ac.get(f"/presenter/sessions/{sid}/state")).json()
        assert state["playing"] is True
        await ac.post(f"/presenter/sessions/{sid}/pause")
        state = (await ac.get(f"/presenter/sessions/{sid}/state")).json()
        assert state["playing"] is False


@pytest.mark.asyncio
async def test_unknown_program_returns_404(app_with_program):
    async with AsyncClient(
        transport=ASGITransport(app=app_with_program), base_url="http://test"
    ) as ac:
        resp = await ac.post(
            "/presenter/sessions",
            params={"language": "es", "year": 1999, "week": 1, "kind": "midweek"},
        )
        assert resp.status_code == 404


# ── F57.14: drag-drop endpoints ────────────────────────────────────────


@pytest.mark.asyncio
async def test_reorder_endpoint_swaps_queue(app_with_multi_item_program):
    async with AsyncClient(
        transport=ASGITransport(app=app_with_multi_item_program),
        base_url="http://test",
    ) as ac:
        sid = (
            await ac.post(
                "/presenter/sessions",
                params={"language": "es", "year": 2026, "week": 23},
            )
        ).json()["session_id"]
        before = (await ac.get(f"/presenter/sessions/{sid}/state")).json()
        moved_title = before["queue"][2]["title"]
        resp = await ac.post(
            f"/presenter/sessions/{sid}/reorder",
            json={"from_index": 2, "to_index": 0},
        )
        assert resp.status_code == 200
        assert resp.json() == {"ok": True}
        after = (await ac.get(f"/presenter/sessions/{sid}/state")).json()
        assert after["queue"][0]["title"] == moved_title


@pytest.mark.asyncio
async def test_add_endpoint_appends_external_file(app_with_multi_item_program):
    async with AsyncClient(
        transport=ASGITransport(app=app_with_multi_item_program),
        base_url="http://test",
    ) as ac:
        sid = (
            await ac.post(
                "/presenter/sessions",
                params={"language": "es", "year": 2026, "week": 23},
            )
        ).json()["session_id"]
        resp = await ac.post(
            f"/presenter/sessions/{sid}/add",
            json={
                "title": "ad-hoc.jpg",
                "local_path": "/tmp/foo.jpg",
                "kind": "image",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["queue_size"] == 4
        state = (await ac.get(f"/presenter/sessions/{sid}/state")).json()
        assert state["queue"][-1]["title"] == "ad-hoc.jpg"
        assert state["queue"][-1]["media_refs"][0]["local_path"] == "/tmp/foo.jpg"


@pytest.mark.asyncio
async def test_jump_endpoint_sets_cursor(app_with_multi_item_program):
    async with AsyncClient(
        transport=ASGITransport(app=app_with_multi_item_program),
        base_url="http://test",
    ) as ac:
        sid = (
            await ac.post(
                "/presenter/sessions",
                params={"language": "es", "year": 2026, "week": 23},
            )
        ).json()["session_id"]
        resp = await ac.post(
            f"/presenter/sessions/{sid}/jump", params={"index": 2}
        )
        assert resp.status_code == 200
        state = (await ac.get(f"/presenter/sessions/{sid}/state")).json()
        assert state["cursor"] == 2

        # out-of-range → 400
        bad = await ac.post(
            f"/presenter/sessions/{sid}/jump", params={"index": 99}
        )
        assert bad.status_code == 400
