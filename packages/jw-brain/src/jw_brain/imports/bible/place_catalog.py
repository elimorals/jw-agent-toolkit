"""Catálogo curado de geocoordenadas para lugares bíblicos.

Coordinates from public-domain sources (Wikipedia, Bible Atlas projects).
Eras_active follows the JW chronology established in `period_catalog.py`.

Schema agnostic to BibleKgPlace — this module exposes a separate
PlaceGeoData dataclass used by the loader to enrich BibleKgPlace.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from jw_brain.imports.bible.models import EraSlug


@dataclass(frozen=True)
class PlaceGeoData:
    slug: str
    region: str
    modern_name: str
    latitude: float
    longitude: float
    eras_active: tuple[EraSlug, ...] = field(default_factory=tuple)


ALL_PLACES: tuple[PlaceGeoData, ...] = (
    PlaceGeoData(
        slug="jerusalem",
        region="Judea",
        modern_name="Jerusalem (Yerushalayim / Al-Quds)",
        latitude=31.7784,
        longitude=35.2356,
        eras_active=(
            "united_kingdom", "divided_kingdom", "babylonian_exile",
            "persian_era", "hellenistic_era", "roman_era", "early_christian_era",
        ),
    ),
    PlaceGeoData(
        slug="babylon",
        region="Mesopotamia",
        modern_name="Hillah (Iraq)",
        latitude=32.5422,
        longitude=44.4205,
        eras_active=("divided_kingdom", "babylonian_exile", "persian_era"),
    ),
    PlaceGeoData(
        slug="babylonia",
        region="Mesopotamia",
        modern_name="Southern Iraq",
        latitude=32.5,
        longitude=44.5,
        eras_active=("divided_kingdom", "babylonian_exile", "persian_era"),
    ),
    PlaceGeoData(
        slug="egypt",
        region="Northeast Africa",
        modern_name="Egypt",
        latitude=26.8206,
        longitude=30.8025,
        eras_active=(
            "patriarchal", "egyptian_exile", "judges", "united_kingdom",
            "divided_kingdom", "babylonian_exile", "persian_era",
            "hellenistic_era", "roman_era", "early_christian_era",
        ),
    ),
    PlaceGeoData(
        slug="canaan",
        region="Levant",
        modern_name="Israel / Palestine / Lebanon",
        latitude=31.5,
        longitude=35.0,
        eras_active=("patriarchal", "judges"),
    ),
    PlaceGeoData(
        slug="israel",
        region="Levant",
        modern_name="Israel",
        latitude=31.0461,
        longitude=34.8516,
        eras_active=(
            "united_kingdom", "divided_kingdom", "babylonian_exile",
            "persian_era", "hellenistic_era", "roman_era", "early_christian_era",
        ),
    ),
    PlaceGeoData(
        slug="judah",
        region="Southern Levant",
        modern_name="Southern Israel",
        latitude=31.3,
        longitude=35.0,
        eras_active=("united_kingdom", "divided_kingdom", "babylonian_exile"),
    ),
    PlaceGeoData(
        slug="samaria",
        region="Central Levant",
        modern_name="Sebastia (West Bank)",
        latitude=32.2767,
        longitude=35.1928,
        eras_active=("divided_kingdom", "roman_era", "early_christian_era"),
    ),
    PlaceGeoData(
        slug="galilee",
        region="Northern Levant",
        modern_name="Galilee region (Israel)",
        latitude=32.8,
        longitude=35.5,
        eras_active=("roman_era", "early_christian_era"),
    ),
    PlaceGeoData(
        slug="judea",
        region="Southern Levant",
        modern_name="Judea (West Bank / Israel)",
        latitude=31.5,
        longitude=35.1,
        eras_active=("hellenistic_era", "roman_era", "early_christian_era"),
    ),
    PlaceGeoData(
        slug="nazareth",
        region="Galilee",
        modern_name="Nazareth (Nāṣira)",
        latitude=32.7022,
        longitude=35.2972,
        eras_active=("roman_era", "early_christian_era"),
    ),
    PlaceGeoData(
        slug="bethlehem",
        region="Judea",
        modern_name="Bethlehem (Bayt Laḥm)",
        latitude=31.7054,
        longitude=35.2024,
        eras_active=("united_kingdom", "divided_kingdom", "roman_era", "early_christian_era"),
    ),
    PlaceGeoData(
        slug="rome",
        region="Italia",
        modern_name="Rome (Italy)",
        latitude=41.9028,
        longitude=12.4964,
        eras_active=("roman_era", "early_christian_era"),
    ),
    PlaceGeoData(
        slug="athens",
        region="Greece",
        modern_name="Athens (Greece)",
        latitude=37.9838,
        longitude=23.7275,
        eras_active=("hellenistic_era", "roman_era", "early_christian_era"),
    ),
    PlaceGeoData(
        slug="ephesus",
        region="Asia Minor",
        modern_name="Selçuk (Turkey, ruins)",
        latitude=37.9419,
        longitude=27.3416,
        eras_active=("hellenistic_era", "roman_era", "early_christian_era"),
    ),
    PlaceGeoData(
        slug="antioch",
        region="Syria",
        modern_name="Antakya (Turkey)",
        latitude=36.2024,
        longitude=36.1606,
        eras_active=("hellenistic_era", "roman_era", "early_christian_era"),
    ),
)

_BY_SLUG: dict[str, PlaceGeoData] = {p.slug: p for p in ALL_PLACES}


def get_place_geodata(slug: str) -> PlaceGeoData | None:
    return _BY_SLUG.get(slug)
