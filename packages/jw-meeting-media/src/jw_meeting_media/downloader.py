"""Downloader con cache local y verificación sha256.

Path scheme: <cache_root>/<lang>/<year>/<week>/<basename>
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from urllib.parse import urlparse

import httpx

from jw_meeting_media.models import MediaRef


class Downloader:
    def __init__(
        self,
        *,
        cache_root: Path,
        http: httpx.AsyncClient | None = None,
    ):
        self._cache_root = Path(cache_root)
        self._cache_root.mkdir(parents=True, exist_ok=True)
        self._http = http
        self._owned = http is None
        if self._owned:
            self._http = httpx.AsyncClient(
                follow_redirects=True,
                timeout=120,
                headers={"User-Agent": "jw-agent-toolkit/F57"},
            )

    async def download(
        self,
        ref: MediaRef,
        *,
        language: str,
        year: int,
        week: int,
    ) -> Path:
        if not ref.url.startswith("http"):
            raise ValueError(f"ref has no http url: {ref}")
        target_dir = self._cache_root / language / str(year) / str(week)
        target_dir.mkdir(parents=True, exist_ok=True)
        name = self._filename_for(ref)
        target = target_dir / name

        if target.exists() and self._is_valid(target, ref.sha256):
            return target

        assert self._http is not None
        resp = await self._http.get(ref.url)
        resp.raise_for_status()
        content = resp.content

        if ref.sha256:
            actual = hashlib.sha256(content).hexdigest()
            if actual != ref.sha256:
                raise RuntimeError(
                    f"sha256 mismatch for {ref.url}: expected {ref.sha256}, got {actual}"
                )

        target.write_bytes(content)
        return target

    def _filename_for(self, ref: MediaRef) -> str:
        name = Path(urlparse(ref.url).path).name
        if name:
            return name
        if ref.sha256:
            return f"{ref.sha256[:16]}.bin"
        return "media.bin"

    def _is_valid(self, path: Path, expected_sha: str | None) -> bool:
        if expected_sha is None:
            return True
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        return actual == expected_sha

    async def aclose(self) -> None:
        if self._owned and self._http is not None:
            await self._http.aclose()
