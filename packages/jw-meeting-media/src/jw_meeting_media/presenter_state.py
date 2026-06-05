"""PresenterManager: gestiona sesiones de presenter activas.

Sesiones in-memory (no persisten). Una sesión = una ventana Tauri
mostrando media de un programa. Múltiples sesiones simultáneas
soportadas (ej. para multi-congregación).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from jw_meeting_media.models import MeetingProgram, PresenterSession


class PresenterManager:
    def __init__(self) -> None:
        self._sessions: dict[str, PresenterSession] = {}

    def create_session(self, *, program: MeetingProgram) -> str:
        sid = str(uuid.uuid4())
        queue = [item for sec in program.sections for item in sec.items]
        self._sessions[sid] = PresenterSession(
            session_id=sid,
            program_url=program.source_url,
            queue=queue,
            cursor=0,
            playing=False,
            started_at=datetime.now(timezone.utc).isoformat(),
        )
        return sid

    def get_state(self, session_id: str) -> PresenterSession:
        if session_id not in self._sessions:
            raise KeyError(f"unknown session: {session_id}")
        return self._sessions[session_id]

    def list_sessions(self) -> list[str]:
        return list(self._sessions.keys())

    def play(self, session_id: str) -> None:
        self.get_state(session_id).playing = True

    def pause(self, session_id: str) -> None:
        self.get_state(session_id).playing = False

    def next_(self, session_id: str) -> None:
        state = self.get_state(session_id)
        if state.cursor + 1 < len(state.queue):
            state.cursor += 1

    def prev(self, session_id: str) -> None:
        state = self.get_state(session_id)
        if state.cursor > 0:
            state.cursor -= 1

    def stop(self, session_id: str) -> None:
        state = self.get_state(session_id)
        state.cursor = 0
        state.playing = False

    def destroy(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)
