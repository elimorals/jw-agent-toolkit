from __future__ import annotations

from jw_core.data.life_disclaimers import (
    DISCLAIMERS,
    ELDERS_REDIRECTS,
    get_disclaimer,
    get_elders_redirect,
)


def test_disclaimer_has_three_languages() -> None:
    assert get_disclaimer("general", "en")
    assert get_disclaimer("general", "es")
    assert get_disclaimer("general", "pt")


def test_disclaimer_general_and_sensitive_share_text() -> None:
    assert get_disclaimer("general", "es") == get_disclaimer("sensitive", "es")


def test_disclaimer_unknown_lang_falls_back_to_english() -> None:
    text = get_disclaimer("general", "fr")
    assert "Watchtower" in text or "published" in text.lower()


def test_elders_redirect_sensitive_only() -> None:
    for lang in ("en", "es", "pt"):
        redirect = get_elders_redirect(lang)
        assert (
            "elders" in redirect.lower()
            or "ancianos" in redirect.lower()
            or "anciaos" in redirect.lower()
            or "ancião" in redirect.lower()
            or "anciao" in redirect.lower()
        )


def test_elders_redirect_falls_back_to_english() -> None:
    text = get_elders_redirect("xx")
    assert text == get_elders_redirect("en")


def test_no_redirect_mentions_medical_professional_by_role() -> None:
    """Pastoral boundary: redirect must not push to therapists/doctors.

    Coherent with the design — agent stays inside the spiritual
    chain (family, elders), not the medical system.
    """
    forbidden = [
        "therapist",
        "psychologist",
        "psychiatrist",
        "doctor",
        "terapeuta",
        "psicologo",
        "psiquiatra",
        "medico",
    ]
    for lang in ("en", "es", "pt"):
        text = get_elders_redirect(lang).lower()
        for word in forbidden:
            assert word not in text, f"{lang}: redirect must not name {word!r}"


def test_no_disclaimer_mentions_medical_professional() -> None:
    forbidden = ["therapist", "psychologist", "terapeuta", "psicologo"]
    for fam in ("general", "sensitive"):
        for lang in ("en", "es", "pt"):
            text = get_disclaimer(fam, lang).lower()
            for word in forbidden:
                assert word not in text


def test_dicts_exported() -> None:
    assert DISCLAIMERS
    assert ELDERS_REDIRECTS
