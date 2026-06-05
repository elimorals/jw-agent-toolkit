"""PresenterManager: gestiona sesiones de presenter activas.

Sesiones in-memory (no persisten). Una sesión = una ventana Tauri
mostrando media de un programa. Múltiples sesiones simultáneas
soportadas (ej. para multi-congregación).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

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
            started_at=datetime.now(UTC).isoformat(),
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

    def reorder(self, session_id: str, *, from_index: int, to_index: int) -> None:
        """Mueve un item de la cola; ajusta cursor para que apunte al mismo item.

        Reglas de cursor:
        - Si el cursor apuntaba al item movido → sigue al item (cursor = to_index).
        - Si el item se quitó por encima del cursor y se reinsertó por debajo
          (o viceversa), el cursor se desplaza ±1 para no perder el ítem actual.
        """
        state = self.get_state(session_id)
        if not (0 <= from_index < len(state.queue)):
            raise IndexError(f"from_index {from_index} out of range")
        if not (0 <= to_index < len(state.queue)):
            raise IndexError(f"to_index {to_index} out of range")
        if from_index == to_index:
            return
        item = state.queue.pop(from_index)
        state.queue.insert(to_index, item)
        # Adjust cursor so it tracks the item it pointed to before the move.
        if state.cursor == from_index:
            state.cursor = to_index
        elif from_index < state.cursor <= to_index:
            state.cursor -= 1
        elif to_index <= state.cursor < from_index:
            state.cursor += 1

    def add_item(self, session_id: str, item) -> None:
        """Añade un MeetingItem al final de la cola (no toca cursor)."""
        state = self.get_state(session_id)
        state.queue.append(item)

    def jump_to(self, session_id: str, index: int) -> None:
        """Salta el cursor al índice indicado. Lanza IndexError si out of range."""
        state = self.get_state(session_id)
        if not (0 <= index < len(state.queue)):
            raise IndexError(f"index {index} out of range")
        state.cursor = index
