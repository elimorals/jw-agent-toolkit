"""Client for `hub.jw.org` — authenticated meeting + convention locator.

Discovered (live, May 2026): `hub.jw.org/meetings/` is an Angular SPA
backed by an OAuth-protected JSON API. The endpoints we have evidence
for (from the SPA's chunks):

  GET  /meetings/meeting-types
  GET  /meetings/languages?languageGuid={guid}
  GET  /meetings/api/analytics/event-action      (POST, telemetry)
  GET  /meetings/v1/search                       (suspected — needs auth)

Because these require a logged-in jw.org session cookie, this client
takes a `session_cookie` string that the user obtains from their
browser DevTools after signing in at https://hub.jw.org/. We never
attempt to login programmatically (that would be brittle and unsafe).

Usage pattern:

    cookie = os.getenv("JW_HUB_COOKIE")  # paste from browser
    client = JWHubClient(session_cookie=cookie)
    schedules = await client.find_meetings(location="lat,lon")
    conventions = await client.find_conventions(location="lat,lon")

When `session_cookie` is empty, every call raises `HubAuthError` and
the caller should fall back to the public mediator-based discovery
(`jw_agents.convention_discovery`).
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import quote

import httpx

logger = logging.getLogger(__name__)

HUB_BASE = "https://hub.jw.org"
HUB_MEETINGS_BASE = f"{HUB_BASE}/meetings"


class HubError(RuntimeError):
    pass


class HubAuthError(HubError):
    """Raised when no session cookie is configured or the API rejects us."""


@dataclass
class MeetingSchedule:
    """One row from the meetings search.

    Most fields are documented from the SPA's TypeScript interfaces seen
    in the bundle. The hub may return additional fields; we keep them in
    `extras` for forward compatibility.
    """

    congregation_guid: str
    congregation_name: str
    address: str = ""
    city: str = ""
    state: str = ""
    country: str = ""
    coordinates: tuple[float, float] | None = None  # (lat, lon)
    language: str = ""
    meeting_type: str = "meetings"  # 'meetings' | 'conventions' | 'circuitassemblies'
    weekly_midweek: dict[str, str] = field(default_factory=dict)  # {day, time}
    weekly_weekend: dict[str, str] = field(default_factory=dict)
    extras: dict[str, Any] = field(default_factory=dict)


@dataclass
class ConventionEntry:
    """One convention entry — venue + dates + program code."""

    title: str
    program_year: int
    start_date: str = ""  # ISO YYYY-MM-DD
    end_date: str = ""
    venue: str = ""
    city: str = ""
    state: str = ""
    country: str = ""
    languages: list[str] = field(default_factory=list)
    extras: dict[str, Any] = field(default_factory=dict)


class JWHubClient:
    """Authenticated client for hub.jw.org search endpoints."""

    def __init__(
        self,
        *,
        session_cookie: str = "",
        http: httpx.AsyncClient | None = None,
        timeout: float = 20.0,
    ) -> None:
        self._cookie = session_cookie.strip()
        self._http = http or httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=True,
            headers={
                "User-Agent": "jw-agent-toolkit/0.1 (+research)",
                "Accept": "application/json, text/json",
                "Accept-Language": "en;q=0.9",
            },
        )
        self._owns_http = http is None

    @property
    def authenticated(self) -> bool:
        return bool(self._cookie)

    def _require_auth(self) -> None:
        if not self._cookie:
            raise HubAuthError(
                "No session cookie configured. Visit https://hub.jw.org/, sign in, "
                "open DevTools → Application → Cookies, and copy the value of "
                "the `JW_AUTH_SESSION` (or similar) cookie. Pass it as "
                "session_cookie=... or set JW_HUB_COOKIE in the environment."
            )

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        self._require_auth()
        url = f"{HUB_MEETINGS_BASE}{path}" if path.startswith("/") else f"{HUB_MEETINGS_BASE}/{path}"
        headers = {"Cookie": self._cookie, "Accept": "application/json"}
        try:
            resp = await self._http.get(url, params=params, headers=headers)
        except httpx.HTTPError as e:
            raise HubError(f"hub.jw.org request failed: {e}") from e
        ct = resp.headers.get("content-type", "")
        if resp.status_code == 401 or resp.status_code == 403:
            raise HubAuthError(
                f"hub.jw.org returned {resp.status_code}. The session cookie may have expired."
            )
        if "html" in ct.lower() and resp.status_code == 200:
            # SPA wrapper instead of JSON — endpoint missing or auth missing.
            raise HubError(
                f"Endpoint {path!r} returned HTML; the API location may have moved."
            )
        if resp.status_code >= 400:
            raise HubError(f"hub.jw.org {resp.status_code}: {resp.text[:200]}")
        try:
            return resp.json()
        except json.JSONDecodeError as e:
            raise HubError(f"hub.jw.org returned non-JSON: {e}") from e

    async def list_meeting_types(self) -> list[str]:
        data = await self._get("meeting-types")
        if isinstance(data, list):
            return [str(x) for x in data]
        if isinstance(data, dict):
            return list(data.keys())
        return []

    async def find_meetings(
        self,
        *,
        location: str = "",
        language_guid: str = "",
    ) -> list[MeetingSchedule]:
        """Search meetings near a location.

        `location` can be:
          - empty (server returns recommendations / default scope)
          - 'lat,lon'
          - an address string

        Returns parsed `MeetingSchedule` rows.
        """
        params: dict[str, Any] = {
            "q": json.dumps({"meetingType": "meetings", "location": location}),
        }
        if language_guid:
            params["languageGuid"] = language_guid
        # Endpoint candidates — try in order.
        candidates = ["v1/search", "search", "data/search"]
        last_err: Exception | None = None
        for path in candidates:
            try:
                data = await self._get(path, params=params)
                return self._normalize_meetings(data)
            except HubError as e:
                last_err = e
                continue
        if last_err:
            raise last_err
        return []

    async def find_conventions(
        self,
        *,
        location: str = "",
        language_guid: str = "",
    ) -> list[ConventionEntry]:
        params: dict[str, Any] = {
            "q": json.dumps({"meetingType": "conventions", "location": location}),
        }
        if language_guid:
            params["languageGuid"] = language_guid
        candidates = ["v1/search", "search", "data/search"]
        last_err: Exception | None = None
        for path in candidates:
            try:
                data = await self._get(path, params=params)
                return self._normalize_conventions(data)
            except HubError as e:
                last_err = e
                continue
        if last_err:
            raise last_err
        return []

    # ── Normalisers (tolerant of shape changes) ─────────────────────────

    @staticmethod
    def _normalize_meetings(data: Any) -> list[MeetingSchedule]:
        items = data.get("results") if isinstance(data, dict) else data
        if not isinstance(items, list):
            return []
        out: list[MeetingSchedule] = []
        for raw in items:
            if not isinstance(raw, dict):
                continue
            coords = None
            if isinstance(raw.get("coordinates"), list) and len(raw["coordinates"]) == 2:
                try:
                    coords = (float(raw["coordinates"][0]), float(raw["coordinates"][1]))
                except (TypeError, ValueError):
                    coords = None
            out.append(
                MeetingSchedule(
                    congregation_guid=str(raw.get("congregationGuid") or raw.get("id") or ""),
                    congregation_name=str(raw.get("congregationName") or raw.get("name") or ""),
                    address=str(raw.get("address") or ""),
                    city=str(raw.get("city") or ""),
                    state=str(raw.get("state") or raw.get("province") or ""),
                    country=str(raw.get("country") or raw.get("countryCode") or ""),
                    coordinates=coords,
                    language=str(raw.get("language") or raw.get("languageCode") or ""),
                    meeting_type=str(raw.get("meetingType") or "meetings"),
                    weekly_midweek=raw.get("midweekMeeting") or raw.get("weeklyMeeting", {}),
                    weekly_weekend=raw.get("weekendMeeting") or raw.get("publicMeeting", {}),
                    extras=raw,
                )
            )
        return out

    @staticmethod
    def _normalize_conventions(data: Any) -> list[ConventionEntry]:
        items = data.get("results") if isinstance(data, dict) else data
        if not isinstance(items, list):
            return []
        out: list[ConventionEntry] = []
        for raw in items:
            if not isinstance(raw, dict):
                continue
            year_str = raw.get("year") or raw.get("programYear") or "0"
            try:
                year = int(year_str)
            except (TypeError, ValueError):
                year = 0
            out.append(
                ConventionEntry(
                    title=str(raw.get("title") or raw.get("name") or f"Convention {year}"),
                    program_year=year,
                    start_date=str(raw.get("startDate") or ""),
                    end_date=str(raw.get("endDate") or ""),
                    venue=str(raw.get("venue") or raw.get("venueName") or ""),
                    city=str(raw.get("city") or ""),
                    state=str(raw.get("state") or ""),
                    country=str(raw.get("country") or raw.get("countryCode") or ""),
                    languages=list(raw.get("languages") or []),
                    extras=raw,
                )
            )
        return out

    async def aclose(self) -> None:
        if self._owns_http:
            await self._http.aclose()


def hub_url_for_meeting_type(meeting_type: str = "meetings", location: str = "") -> str:
    """Build the SPA URL the user can paste in a browser for visual results."""
    payload = json.dumps({"meetingType": meeting_type, "location": location})
    return f"{HUB_MEETINGS_BASE}/en?q={quote(payload)}"
