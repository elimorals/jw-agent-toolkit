"""Discover and validate language metadata against live jw.org endpoints.

VISION.md Module 8 / Gap 4: confirm `wol_resource` and `lp_tag` values
for the Tier-1 languages. The `wol_resource` integer is non-trivial to
guess and JW has rotated it historically.

Two layers:
  - `validate_jw_code(code)` — quick check via pub-media. Returns True if
    `nwt` exists for that JW code (i.e. JW publishes content there).
  - `discover_wol_resource(iso, candidates=...)` — probes a list of
    `wol.jw.org/{iso}/wol/h/r{N}/{lp_tag}` URLs and returns the first
    200-OK pair. Slow (one network call per candidate).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx

from jw_core.languages import Language, get_language

logger = logging.getLogger(__name__)

PUB_MEDIA_VALIDATE = "https://b.jw-cdn.org/apis/pub-media/GETPUBMEDIALINKS"
WOL_BASE = "https://wol.jw.org"


# Hand-curated probe sets — ordered most-likely-first based on historical
# observation. Update as JW publishes new resources.
DEFAULT_PROBE_CANDIDATES: dict[str, list[int]] = {
    "fr": [30, 31, 40, 41, 32, 42, 43],
    "de": [10, 11, 12, 13, 50, 51],
    "it": [6, 14, 15, 16, 28],
    "ru": [8, 22, 29, 35, 39],
    "ja": [7, 12, 33, 18],
    "ko": [46, 47, 48],
    "zh": [23, 24, 25, 26],
}


@dataclass
class LanguageProbeResult:
    iso: str
    jw_code: str
    pub_media_ok: bool = False
    wol_resource: str = ""
    wol_url_tested: str = ""
    error: str = ""


async def validate_jw_code(jw_code: str, *, http: httpx.AsyncClient | None = None) -> bool:
    """Return True if jw.org publishes NWT in this language."""
    owned = http is None
    http = http or httpx.AsyncClient(timeout=15.0, follow_redirects=True)
    try:
        try:
            resp = await http.get(
                PUB_MEDIA_VALIDATE,
                params={"pub": "nwt", "langwritten": jw_code, "fileformat": "epub", "output": "json"},
                headers={"User-Agent": "jw-agent-toolkit/0.1 (+research)"},
            )
            if resp.status_code != 200:
                return False
            data = resp.json()
            block = data.get("files", {}).get(jw_code, {})
            return bool(block.get("EPUB"))
        except Exception:
            return False
    finally:
        if owned:
            await http.aclose()


async def discover_wol_resource(
    language: Language | str,
    *,
    candidates: list[int] | None = None,
    http: httpx.AsyncClient | None = None,
    timeout: float = 12.0,
) -> LanguageProbeResult:
    """Probe `wol.jw.org` for the resource number that serves `language`.

    Args:
        language: A `Language` instance OR an ISO code we look up.
        candidates: list of resource numbers to try (defaults from
            DEFAULT_PROBE_CANDIDATES).
        http: shared client (optional).
        timeout: per-request timeout (default 12s — WOL responses can be slow).

    Returns:
        `LanguageProbeResult` with `wol_resource` set when a 200 is found,
        else empty string + `error` explaining why.
    """
    if isinstance(language, str):
        language = get_language(language)
    result = LanguageProbeResult(iso=language.iso, jw_code=language.jw_code)

    # Validate pub-media first (cheaper).
    owned = http is None
    http = http or httpx.AsyncClient(timeout=timeout, follow_redirects=True)
    try:
        result.pub_media_ok = await validate_jw_code(language.jw_code, http=http)
        if not result.pub_media_ok:
            result.error = "pub-media reports no NWT for this jw_code"
            return result
        probes = candidates or DEFAULT_PROBE_CANDIDATES.get(language.iso, [])
        for n in probes:
            url = f"{WOL_BASE}/{language.iso}/wol/h/r{n}/{language.lp_tag}"
            result.wol_url_tested = url
            try:
                resp = await http.get(
                    url,
                    headers={"User-Agent": "Mozilla/5.0", "Accept-Language": language.iso},
                )
                if resp.status_code == 200:
                    result.wol_resource = f"r{n}"
                    return result
            except httpx.HTTPError as e:
                logger.debug("wol probe error for r%s: %s", n, e)
        result.error = f"No 200 OK across {len(probes)} candidates"
        return result
    finally:
        if owned:
            await http.aclose()
