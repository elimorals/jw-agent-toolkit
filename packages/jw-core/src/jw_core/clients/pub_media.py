"""Client for b.jw-cdn.org/apis/pub-media/GETPUBMEDIALINKS.

Returns the file inventory for a publication: PDF/EPUB/JWPUB/MP3 in every
language the publication is available in. Useful for offline downloads
(Bible PDF, Watchtower EPUB, books as JWPUB).

Endpoint shape:
  GET ?output=json
      &pub={pub_code}         e.g. 'fg' (Good News brochure), 'nwt' (NWT)
      &langwritten={lang}     JW code, e.g. 'E', 'S'
      &issue={issue}          optional — for magazines (yyyymm)
      &booknum={bible_book}   optional — for Bible books (1-66)
      &fileformat={fmt}       optional — PDF, EPUB, JWPUB, MP3, RTF
      &alllangs={bool}        if true, return all language variants

Authentication: none required.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import httpx
from pydantic import BaseModel, Field

from jw_core.cache import DiskCache
from jw_core.clients._polite import politely_get
from jw_core.telemetry import Telemetry
from jw_core.throttle import Throttler

logger = logging.getLogger(__name__)

PUB_MEDIA_URL = "https://b.jw-cdn.org/apis/pub-media/GETPUBMEDIALINKS"

VALID_FORMATS = {"PDF", "EPUB", "JWPUB", "MP3", "RTF", "BRL"}


class PubMediaError(RuntimeError):
    pass


class PubMediaFile(BaseModel):
    """One downloadable file from GETPUBMEDIALINKS."""

    url: str
    filename: str = Field(default="")
    title: str = Field(default="")
    language: str = Field(default="", description="JW code of the file's language")
    file_format: str = Field(default="", description="PDF, EPUB, JWPUB, MP3, ...")
    size_bytes: int = Field(default=0)
    checksum: str = Field(default="")
    bible_book: int | None = Field(default=None, description="0 = all, 1..66 = book")
    track: int | None = None
    duration_s: int | None = Field(default=None, description="For audio/video")
    mime_type: str = Field(default="")

    @classmethod
    def from_api(cls, language: str, fmt: str, data: dict[str, Any]) -> PubMediaFile:
        file_meta = data.get("file", {}) or {}
        return cls(
            url=file_meta.get("url", ""),
            filename=file_meta.get("url", "").rsplit("/", 1)[-1],
            title=data.get("title", ""),
            language=language,
            file_format=fmt,
            size_bytes=int(data.get("filesize", 0) or 0),
            checksum=file_meta.get("checksum", ""),
            bible_book=data.get("booknum"),
            track=data.get("track"),
            duration_s=int(data.get("duration", 0) or 0) or None,
            mime_type=data.get("mimetype", ""),
        )


class Publication(BaseModel):
    """A publication descriptor with all available files."""

    pub_code: str
    pub_name: str = Field(default="")
    files: list[PubMediaFile] = Field(default_factory=list)

    def files_by_format(self, fmt: str) -> list[PubMediaFile]:
        return [f for f in self.files if f.file_format.upper() == fmt.upper()]

    def files_by_language(self, lang_code: str) -> list[PubMediaFile]:
        return [f for f in self.files if f.language == lang_code]


class PubMediaClient:
    """Async client for GETPUBMEDIALINKS."""

    def __init__(
        self,
        http: httpx.AsyncClient | None = None,
        *,
        throttler: Throttler | None = None,
        cache: DiskCache | None = None,
        telemetry: Telemetry | None = None,
    ) -> None:
        self._http = http or httpx.AsyncClient(timeout=60.0, follow_redirects=True)
        self._owns_http = http is None
        self._throttler = throttler
        self._cache = cache
        self._telemetry = telemetry

    async def get_publication(
        self,
        pub_code: str,
        *,
        language: str = "E",
        issue: int | None = None,
        bible_book: int | None = None,
        file_format: str | None = None,
        all_languages: bool = False,
    ) -> Publication:
        """Fetch the file inventory for a publication.

        Raises PubMediaError on 404 (publication not found) or other HTTP errors.
        """
        if file_format and file_format.upper() not in VALID_FORMATS:
            raise ValueError(f"file_format must be one of {sorted(VALID_FORMATS)} or None")
        params: dict[str, Any] = {
            "output": "json",
            "pub": pub_code,
            "langwritten": language,
        }
        if issue is not None:
            params["issue"] = issue
        if bible_book is not None:
            if not 0 <= bible_book <= 66:
                raise ValueError("bible_book must be 0..66 (0 = all)")
            params["booknum"] = bible_book
        if file_format:
            params["fileformat"] = file_format.upper()
        if all_languages:
            params["alllangs"] = 1

        try:
            resp = await politely_get(
                self._http,
                PUB_MEDIA_URL,
                params=params,
                throttler=self._throttler,
                cache=self._cache,
                telemetry=self._telemetry,
                endpoint_id="pub_media.get_publication",
                record_json_shape=True,
                cache_ttl_seconds=86400.0,  # publication catalogs change slowly
            )
            if resp.status_code == 404:
                raise PubMediaError(f"Publication not found: pub={pub_code!r} lang={language!r}")
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPError as e:
            raise PubMediaError(f"GETPUBMEDIALINKS failed: {e}") from e

        files = self._extract_files(data)
        return Publication(
            pub_code=pub_code,
            pub_name=data.get("pubName", ""),
            files=files,
        )

    @staticmethod
    def _extract_files(data: dict[str, Any]) -> list[PubMediaFile]:
        files: list[PubMediaFile] = []
        languages_block = data.get("files", {}) or {}
        for lang_code, by_format in languages_block.items():
            if not isinstance(by_format, dict):
                continue
            for fmt, file_list in by_format.items():
                if not isinstance(file_list, list):
                    continue
                for entry in file_list:
                    if isinstance(entry, dict):
                        files.append(PubMediaFile.from_api(lang_code, fmt, entry))
        return files

    async def download(
        self,
        file: PubMediaFile,
        dest: Path | str,
        *,
        chunk_size: int = 64 * 1024,
    ) -> Path:
        """Stream-download a single file to `dest`. Returns the final path."""
        dest_path = Path(dest)
        if dest_path.is_dir():
            dest_path = dest_path / (file.filename or "download.bin")
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            async with self._http.stream("GET", file.url) as resp:
                resp.raise_for_status()
                with dest_path.open("wb") as fp:
                    async for chunk in resp.aiter_bytes(chunk_size):
                        fp.write(chunk)
        except httpx.HTTPError as e:
            raise PubMediaError(f"Download failed for {file.url}: {e}") from e
        return dest_path

    def cache_stats(self) -> dict[str, int] | None:
        return self._cache.stats() if self._cache is not None else None

    async def aclose(self) -> None:
        if self._owns_http:
            await self._http.aclose()
