"""Catálogo curado de geocoordenadas de lugares bíblicos."""
from jw_brain.imports.bible.place_catalog import (
    ALL_PLACES,
    PlaceGeoData,
    get_place_geodata,
)


def test_all_places_have_unique_slugs():
    slugs = [p.slug for p in ALL_PLACES]
    assert len(slugs) == len(set(slugs))


def test_jerusalem_present_with_coords():
    place = get_place_geodata("jerusalem")
    assert place is not None
    assert 31.0 < place.latitude < 32.0  # Jerusalem ~31.78N
    assert 35.0 < place.longitude < 36.0  # ~35.22E
    assert place.region in ("Judea", "Judah", "Israel")


def test_babylon_present_with_coords():
    place = get_place_geodata("babylon")
    assert place is not None
    assert 32.0 < place.latitude < 33.0  # ~32.54N
    assert 44.0 < place.longitude < 45.0  # ~44.42E


def test_modern_names_when_applicable():
    """Ciudades con nombre moderno distinto deben tenerlo."""
    nazareth = get_place_geodata("nazareth")
    if nazareth and nazareth.modern_name:
        assert "Nazareth" in nazareth.modern_name or "Nāṣira" in nazareth.modern_name


def test_eras_active_makes_sense():
    """Bethlehem está activo en united_kingdom (David), divided_kingdom y roman_era (nacimiento Jesús)."""
    place = get_place_geodata("bethlehem")
    assert place is not None
    eras = set(place.eras_active)
    assert "united_kingdom" in eras or "divided_kingdom" in eras
    assert "roman_era" in eras


def test_unknown_returns_none():
    assert get_place_geodata("not_a_place") is None
