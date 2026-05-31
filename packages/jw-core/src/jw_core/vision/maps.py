"""Biblical geography catalog — locations + journeys.

VISION.md: "Análisis de mapas bíblicos (geografía): '¿por dónde viajó
Pablo en su segundo viaje?'".

Data is hand-curated from publicly known geography. Coordinates are
approximate; useful for quick LLM grounding and very rough rendering.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import asin, cos, radians, sin, sqrt


@dataclass(frozen=True)
class BiblicalLocation:
    name: str  # canonical English
    aliases: dict[str, str] = field(default_factory=dict)  # language → vernacular
    lat: float = 0.0
    lon: float = 0.0
    region: str = ""

    def localized_name(self, language: str) -> str:
        return self.aliases.get(language, self.name)


# A representative sample. Easy to extend.
_LOCATIONS: dict[str, BiblicalLocation] = {
    "jerusalem": BiblicalLocation(
        name="Jerusalem",
        aliases={"es": "Jerusalén", "pt": "Jerusalém"},
        lat=31.7683,
        lon=35.2137,
        region="Judea",
    ),
    "bethlehem": BiblicalLocation(
        name="Bethlehem",
        aliases={"es": "Belén", "pt": "Belém"},
        lat=31.7054,
        lon=35.2024,
        region="Judea",
    ),
    "antioch": BiblicalLocation(
        name="Antioch (Syria)",
        aliases={"es": "Antioquía", "pt": "Antioquia"},
        lat=36.2021,
        lon=36.1604,
        region="Syria",
    ),
    "ephesus": BiblicalLocation(
        name="Ephesus",
        aliases={"es": "Éfeso", "pt": "Éfeso"},
        lat=37.9495,
        lon=27.3639,
        region="Asia Minor",
    ),
    "corinth": BiblicalLocation(
        name="Corinth",
        aliases={"es": "Corinto", "pt": "Corinto"},
        lat=37.9061,
        lon=22.8783,
        region="Achaia",
    ),
    "athens": BiblicalLocation(
        name="Athens",
        aliases={"es": "Atenas", "pt": "Atenas"},
        lat=37.9838,
        lon=23.7275,
        region="Achaia",
    ),
    "thessalonica": BiblicalLocation(
        name="Thessalonica",
        aliases={"es": "Tesalónica", "pt": "Tessalônica"},
        lat=40.6401,
        lon=22.9444,
        region="Macedonia",
    ),
    "philippi": BiblicalLocation(
        name="Philippi",
        aliases={"es": "Filipos", "pt": "Filipos"},
        lat=41.0136,
        lon=24.2877,
        region="Macedonia",
    ),
    "rome": BiblicalLocation(
        name="Rome",
        aliases={"es": "Roma", "pt": "Roma"},
        lat=41.9028,
        lon=12.4964,
        region="Italy",
    ),
    "babylon": BiblicalLocation(
        name="Babylon",
        aliases={"es": "Babilonia", "pt": "Babilônia"},
        lat=32.5364,
        lon=44.4275,
        region="Mesopotamia",
    ),
}


@dataclass(frozen=True)
class BiblicalJourney:
    key: str
    title: dict[str, str]
    description: dict[str, str]
    waypoints: tuple[str, ...]
    scripture_anchors: tuple[str, ...] = ()


BIBLICAL_JOURNEYS: dict[str, BiblicalJourney] = {
    "paul_2nd": BiblicalJourney(
        key="paul_2nd",
        title={
            "en": "Paul's second missionary journey",
            "es": "Segundo viaje misionero de Pablo",
            "pt": "Segunda viagem missionária de Paulo",
        },
        description={
            "en": "From Antioch through Asia Minor to Macedonia and Achaia.",
            "es": "Desde Antioquía por Asia Menor hasta Macedonia y Acaya.",
            "pt": "De Antioquia, pela Ásia Menor, até a Macedônia e Acaia.",
        },
        waypoints=("antioch", "ephesus", "philippi", "thessalonica", "athens", "corinth"),
        scripture_anchors=("Acts 15:36", "Acts 18:22"),
    ),
    "paul_3rd": BiblicalJourney(
        key="paul_3rd",
        title={
            "en": "Paul's third missionary journey",
            "es": "Tercer viaje misionero de Pablo",
            "pt": "Terceira viagem missionária de Paulo",
        },
        description={
            "en": "Strengthening churches in Asia Minor before sailing to Macedonia and Achaia.",
            "es": "Fortaleciendo iglesias en Asia Menor antes de Macedonia y Acaya.",
            "pt": "Fortalecendo igrejas na Ásia Menor antes da Macedônia e Acaia.",
        },
        waypoints=("antioch", "ephesus", "philippi", "corinth", "jerusalem"),
        scripture_anchors=("Acts 18:23", "Acts 21:17"),
    ),
    "exile_to_babylon": BiblicalJourney(
        key="exile_to_babylon",
        title={
            "en": "Judah's exile to Babylon",
            "es": "Exilio de Judá a Babilonia",
            "pt": "Exílio de Judá para a Babilônia",
        },
        description={
            "en": "Forced march from Jerusalem to Babylon after 607 BCE.",
            "es": "Marcha forzada desde Jerusalén a Babilonia tras 607 a.C.",
            "pt": "Marcha forçada de Jerusalém para a Babilônia após 607 AEC.",
        },
        waypoints=("jerusalem", "babylon"),
        scripture_anchors=("2 Chronicles 36:17-21", "Jeremiah 25:11"),
    ),
}


# ── Lookups ──────────────────────────────────────────────────────────────


def get_journey(key: str, *, language: str = "en") -> dict[str, object] | None:
    journey = BIBLICAL_JOURNEYS.get(key)
    if journey is None:
        return None
    points = [_serialize_loc(_LOCATIONS[w], language) for w in journey.waypoints if w in _LOCATIONS]
    return {
        "key": journey.key,
        "title": journey.title.get(language, journey.title["en"]),
        "description": journey.description.get(language, journey.description["en"]),
        "waypoints": points,
        "scripture_anchors": list(journey.scripture_anchors),
    }


def list_journeys(language: str = "en") -> list[dict[str, str]]:
    return [{"key": j.key, "title": j.title.get(language, j.title["en"])} for j in BIBLICAL_JOURNEYS.values()]


def locations_near(
    location_key: str,
    *,
    radius_km: float = 200,
    language: str = "en",
) -> list[dict[str, object]]:
    """Return all catalog locations within `radius_km` of `location_key`."""
    anchor = _LOCATIONS.get(location_key.lower())
    if anchor is None:
        return []
    out = []
    for key, loc in _LOCATIONS.items():
        if key == location_key.lower():
            continue
        d = _haversine_km(anchor.lat, anchor.lon, loc.lat, loc.lon)
        if d <= radius_km:
            entry = _serialize_loc(loc, language)
            entry["distance_km"] = round(d, 1)
            out.append(entry)
    return sorted(out, key=lambda e: e["distance_km"])


def _serialize_loc(loc: BiblicalLocation, language: str) -> dict[str, object]:
    return {
        "name": loc.localized_name(language),
        "canonical": loc.name,
        "lat": loc.lat,
        "lon": loc.lon,
        "region": loc.region,
    }


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = radians(lat1), radians(lat2)
    d_lat = radians(lat2 - lat1)
    d_lon = radians(lon2 - lon1)
    a = sin(d_lat / 2) ** 2 + cos(p1) * cos(p2) * sin(d_lon / 2) ** 2
    return 2 * r * asin(sqrt(a))
