"""F58.14 — catálogo expandido de cabezales bíblicos.

Verifica que el catálogo built-in expandido tiene cobertura mínima del
canon bíblico común y que no hay overlap persona/lugar problemático.
"""

from __future__ import annotations

from jw_brain.imports.bible.expanded_headwords import (
    EXPANDED_PERSON_HEADWORDS,
    EXPANDED_PLACE_HEADWORDS,
)


# ── Tamaños mínimos ─────────────────────────────────────────────────────────


def test_expanded_persons_size() -> None:
    """Al menos 150 personas en el catálogo expandido."""
    assert len(EXPANDED_PERSON_HEADWORDS) >= 150


def test_expanded_places_size() -> None:
    """Al menos 100 lugares en el catálogo expandido."""
    assert len(EXPANDED_PLACE_HEADWORDS) >= 100


# ── Cobertura de figuras clave ─────────────────────────────────────────────


def test_patriarchs_present() -> None:
    """Patriarcas mayores en ES y EN."""
    expected = {
        "abraham", "isaac", "jacob", "josé", "joseph",
        "noé", "noah", "moisés", "moses",
    }
    for name in expected:
        assert name in EXPANDED_PERSON_HEADWORDS, f"missing person: {name}"


def test_kings_present() -> None:
    """Reyes principales de Israel y Judá."""
    expected = {
        "david", "salomón", "solomon", "saúl", "saul",
        "ezequías", "hezekiah", "josías", "josiah",
        "acab", "ahab", "jezabel", "jezebel",
    }
    for name in expected:
        assert name in EXPANDED_PERSON_HEADWORDS, f"missing king: {name}"


def test_major_prophets_present() -> None:
    """Profetas mayores y menores en ES y EN."""
    expected = {
        "isaías", "isaiah", "jeremías", "jeremiah",
        "ezequiel", "ezekiel", "daniel",
        "elías", "elijah", "eliseo", "elisha",
        "oseas", "hosea", "amós", "amos",
        "jonás", "jonah", "miqueas", "micah",
        "habacuc", "habakkuk", "malaquías", "malachi",
    }
    for name in expected:
        assert name in EXPANDED_PERSON_HEADWORDS, f"missing prophet: {name}"


def test_nt_figures_present() -> None:
    """Apóstoles y figuras clave del NT en ES y EN."""
    expected = {
        "jesús", "jesus", "cristo", "christ",
        "pedro", "peter", "pablo", "paul",
        "juan", "john", "mateo", "matthew",
        "marcos", "mark", "lucas", "luke",
        "maría", "mary", "esteban", "stephen",
        "cornelio", "cornelius", "bernabé", "barnabas",
        "timoteo", "timothy", "tito", "titus",
    }
    for name in expected:
        assert name in EXPANDED_PERSON_HEADWORDS, f"missing NT person: {name}"


def test_key_places_present() -> None:
    """Lugares mayores del AT/NT en ES y EN."""
    expected = {
        "jerusalén", "jerusalem", "belén", "bethlehem",
        "babilonia", "babylon", "egipto", "egypt",
        "roma", "rome", "atenas", "athens",
        "nazaret", "nazareth", "antioquía", "antioch",
        "damasco", "damascus", "cesarea", "caesarea",
        "éfeso", "ephesus", "corinto", "corinth",
        "siloh", "shiloh", "hebrón", "hebron",
        "jericó", "jericho", "sinaí", "sinai",
    }
    for name in expected:
        assert name in EXPANDED_PLACE_HEADWORDS, f"missing place: {name}"


def test_revelation_cities_present() -> None:
    """Las 7 iglesias de Apocalipsis."""
    expected = {
        "éfeso", "ephesus", "esmirna", "smyrna",
        "pérgamo", "pergamum", "tiatira", "thyatira",
        "sardis", "filadelfia", "philadelphia", "laodicea",
    }
    for name in expected:
        assert name in EXPANDED_PLACE_HEADWORDS, f"missing rev city: {name}"


# ── Integridad ──────────────────────────────────────────────────────────────


def test_no_duplicates_across_person_place() -> None:
    """Un nombre dado debe ser o persona o lugar, no ambos.

    Casos como "judá" (patriarca vs región) están registrados como persona
    por defecto — el catálogo place declara variantes específicas
    ("tierra de israel") cuando es relevante. Permitimos overlaps mínimos
    pero documentamos para evitar drift.
    """
    overlap = EXPANDED_PERSON_HEADWORDS & EXPANDED_PLACE_HEADWORDS
    assert overlap == set(), f"unexpected overlap: {sorted(overlap)}"


def test_all_lowercase() -> None:
    """Todas las entradas deben estar normalizadas a lowercase."""
    for name in EXPANDED_PERSON_HEADWORDS:
        assert name == name.lower(), f"non-lowercase person: {name!r}"
    for name in EXPANDED_PLACE_HEADWORDS:
        assert name == name.lower(), f"non-lowercase place: {name!r}"


def test_no_whitespace_padding() -> None:
    """No debe haber whitespace al inicio/final (se compara con .strip())."""
    for name in EXPANDED_PERSON_HEADWORDS:
        assert name == name.strip(), f"padded person: {name!r}"
    for name in EXPANDED_PLACE_HEADWORDS:
        assert name == name.strip(), f"padded place: {name!r}"
