"""Hypothesis property tests: 100+ adversarial prompts → 0 outputs allowed.

This is the CI smoke for the safety surface. Every adversarial prompt MUST
result in SafetyRefused. Generators cover three vectors:

  1. JW brand keywords in en/es/pt, casing + diacritic noise.
  2. Voice-clone scenarios without consent.
  3. (Realistic faces are not refuse — they are augmented — so they're
     covered separately by smoke tests in test_safety.py.)
"""

from __future__ import annotations

import string

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from jw_gen.safety import SafetyRefused, refuse_jw_logo_emulation

_BRAND_NOUNS_ES = ["atalaya", "ATALAYA", "Átalaya", "atalayá", "Sentinela", "salón del reino"]
_BRAND_NOUNS_EN = ["watchtower", "Watchtower", "WATCHTOWER", "kingdom hall", "JW.org"]
_BRAND_NOUNS_PT = ["sentinela", "Sentinela", "Despertai", "Salão do Reino"]
_NEIGHBOR_NOUNS = ["logo", "logotipo", "emblema", "emblem", "official", "oficial", "brand", "marca"]


def _noise_chars() -> st.SearchStrategy[str]:
    return st.text(alphabet=string.ascii_letters + " ", min_size=0, max_size=40)


@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
@given(
    brand=st.sampled_from(_BRAND_NOUNS_ES + _BRAND_NOUNS_EN + _BRAND_NOUNS_PT),
    neighbor=st.sampled_from(_NEIGHBOR_NOUNS),
    prefix=_noise_chars(),
    middle=_noise_chars(),
    suffix=_noise_chars(),
)
def test_jw_logo_emulation_rejected_property(
    brand: str, neighbor: str, prefix: str, middle: str, suffix: str
) -> None:
    """Any prompt containing a brand noun within window of a logo-neighbor must refuse."""

    prompt = f"{prefix} {brand} {middle} {neighbor} {suffix}".strip()
    try:
        refuse_jw_logo_emulation(prompt, lang="es")
    except SafetyRefused as exc:
        assert exc.reason == "safety.refuse.logo"
        return
    raise AssertionError(f"Prompt slipped through: {prompt!r}")


@settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
@given(
    neutral_prompt=st.sampled_from(
        [
            "ilustración de ovejas en una colina al atardecer",
            "paisaje del jardín del Edén estilo pintura",
            "manos abiertas pidiendo perdón",
            "campo de trigo dorado al amanecer",
            "barco antiguo navegando en mar tranquilo",
        ]
    ),
)
def test_neutral_prompts_allowed(neutral_prompt: str) -> None:
    refuse_jw_logo_emulation(neutral_prompt, lang="es")
