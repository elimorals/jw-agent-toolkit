"""MediaResolver: dado un MediaRef abstracto, devuelve un MediaRef con
url directa lista para descargar.

Reusa PubMediaClient (F2) cuando hay pub_code+track, sino pass-through.
"""

from __future__ import annotations

from typing import Any

from jw_meeting_media.models import MediaKind, MediaRef


class MediaResolver:
    """Resuelve refs abstractas a URLs directas usando PubMediaClient si hace falta.

    El cliente PubMediaClient inyectado puede ser el real (F2) o un mock con
    `get_publication(pub=..., track=..., language=...)` retornando un dict con
    estructura `{"files": {lang: {"MP4"|"M4V"|"MP3": [{...}]}}}`.
    """

    def __init__(self, pub_media_client: Any | None = None):
        self._pub = pub_media_client

    async def resolve(self, ref: MediaRef) -> MediaRef:
        if ref.url and ref.url.startswith("http"):
            return ref  # ya resuelto

        if ref.kind == MediaKind.VIDEO and ref.pub_code and ref.track is not None:
            return await self._resolve_video_pubmedia(ref)

        if ref.kind == MediaKind.AUDIO and ref.pub_code and ref.track is not None:
            return await self._resolve_audio_pubmedia(ref)

        # JWPUB / EXTERNAL: la URL viene tal cual; opcionalmente HEAD para validar
        return ref

    async def _resolve_video_pubmedia(self, ref: MediaRef) -> MediaRef:
        response = await self._call_pub(ref, formats=("MP4", "M4V"))
        chosen = self._pick_format(response, ref.language or "es", ("MP4", "M4V"))
        if chosen is None:
            return ref
        return ref.model_copy(
            update={
                "url": chosen.get("file", {}).get("url", ""),
                "sha256": chosen.get("checksum"),
                "duration_seconds": chosen.get("duration"),
            }
        )

    async def _resolve_audio_pubmedia(self, ref: MediaRef) -> MediaRef:
        response = await self._call_pub(ref, formats=("MP3",))
        chosen = self._pick_format(response, ref.language or "es", ("MP3",))
        if chosen is None:
            return ref
        return ref.model_copy(
            update={
                "url": chosen.get("file", {}).get("url", ""),
                "sha256": chosen.get("checksum"),
            }
        )

    async def _call_pub(self, ref: MediaRef, *, formats: tuple[str, ...]) -> dict:
        if self._pub is None:
            from jw_core.clients.pub_media import PubMediaClient

            self._pub = PubMediaClient()
        result = await self._pub.get_publication(
            pub=ref.pub_code,
            track=ref.track,
            language=ref.language or "es",
        )
        # Acepta dict crudo o objeto Publication (model_dump)
        if hasattr(result, "model_dump"):
            return result.model_dump()
        return result or {}

    @staticmethod
    def _pick_format(
        response: dict, language: str, formats: tuple[str, ...]
    ) -> dict | None:
        files = (response or {}).get("files", {}).get(language, {})
        if not isinstance(files, dict):
            return None
        for fmt in formats:
            entries = files.get(fmt)
            if entries:
                return entries[0]
        return None
