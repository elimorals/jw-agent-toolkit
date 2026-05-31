"""Three non-negotiable safety filters that run BEFORE any provider call.

LOAD-BEARING: code review must reject any change that weakens these.

1. `refuse_jw_logo_emulation(prompt, lang)`           — hard refuse, no opt-in.
2. `refuse_voice_cloning_without_double_optin(...)`   — flag + signed file + interactive.
3. `refuse_realistic_faces_without_optin(prompt,...)` — default stylized, --realistic-people opts in.

All matching is done on Unicode-normalized + deaccented + lowercased text so
attempts to bypass via casing or diacritics are caught.

The matching strategy is intentionally *fail-closed*: when ambiguous, refuse.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from collections.abc import Callable
from pathlib import Path

from jw_gen.i18n import get_message, list_logo_keywords, realism_suffix
from jw_gen.models import GenerationRequest, Language, SafetyDecision

Lang = Language


class SafetyRefused(Exception):
    """Raised when a safety filter refuses to proceed."""

    def __init__(self, reason_key: str, *, audit_flag: tuple[str, str]) -> None:
        super().__init__(reason_key)
        self.reason = reason_key
        self.audit_flag = audit_flag


# ---------------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------------


def _normalize(s: str) -> str:
    """Lowercase + NFKD + strip diacritics + collapse whitespace."""

    s = s.lower()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"\s+", " ", s).strip()
    return s


# ---------------------------------------------------------------------------
# Filter 1 — JW logo emulation (hard refuse, no opt-in)
# ---------------------------------------------------------------------------


_LOGO_NEIGHBORS = (
    "logo",
    "logotipo",
    "emblem",
    "emblema",
    "brand",
    "marca",
    "official",
    "oficial",
)


def refuse_jw_logo_emulation(prompt: str, lang: Lang = "es") -> None:
    """Block prompts that emulate official JW graphic identity. Fail-closed.

    Strategy:
      1) Normalize prompt + each keyword.
      2) Direct substring match → refuse.
      3) Proximity heuristic: if prompt mentions {watchtower/atalaya/sentinela/jw.org}
         within a small window of one of _LOGO_NEIGHBORS → refuse.
    """

    norm = _normalize(prompt)

    # Direct substring match across all three language keyword lists for safety.
    for catalog_lang in ("en", "es", "pt"):
        for kw in list_logo_keywords(catalog_lang):  # type: ignore[arg-type]
            if _normalize(kw) in norm:
                raise SafetyRefused(
                    "safety.refuse.logo", audit_flag=("logo_check", "fail")
                )

    # Proximity heuristic (multilingual): brand name + neighbor noun within window.
    brand_words = {
        "watchtower",
        "atalaya",
        "sentinela",
        "jw.org",
        "jw",
        "kingdom hall",
        "salao do reino",
        "salon del reino",
        "bethel",
    }
    tokens = norm.split()
    for i, _tok in enumerate(tokens):
        window_str = " ".join(tokens[max(0, i - 3) : i + 4])
        if any(b in window_str for b in brand_words):
            if any(n in window_str for n in _LOGO_NEIGHBORS):
                # Brand word + logo-neighbor noun in same window → refuse.
                raise SafetyRefused(
                    "safety.refuse.logo", audit_flag=("logo_check", "fail")
                )


# ---------------------------------------------------------------------------
# Filter 2 — Voice cloning without double opt-in
# ---------------------------------------------------------------------------


def _parse_consent_file(path: Path) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            fields[k.strip()] = v.strip()
    return fields


def refuse_voice_cloning_without_double_optin(
    *,
    audio_src: Path,
    voice_clone_flag: bool,
    interactive_confirm: Callable[[str], bool],
    lang: Lang = "es",
    signed_consent_fake_ok: bool = False,
) -> str:
    """Return the owner name if all four gates pass; raise SafetyRefused otherwise.

    Gates:
        1. `voice_clone_flag` must be True (CLI --voice-clone).
        2. `<audio_src>.consent.txt` must exist.
        3. signature_sha256 must equal sha256 of the first three lines.
        4. `interactive_confirm("¿Confirmas...?")` must return True.

    `signed_consent_fake_ok` exists only for FakeAudioProvider tests; it is
    NEVER reachable from CLI or MCP.
    """

    flag_fail = ("voice_clone_optin", "fail")

    if signed_consent_fake_ok:
        return "fake-owner"

    if not voice_clone_flag:
        raise SafetyRefused(
            "safety.refuse.voice_clone_no_consent", audit_flag=flag_fail
        )

    consent_path = audio_src.with_suffix(audio_src.suffix + ".consent.txt")
    if not consent_path.exists():
        raise SafetyRefused(
            "safety.refuse.voice_clone_no_consent", audit_flag=flag_fail
        )

    fields = _parse_consent_file(consent_path)
    required = {"voice_owner", "date", "purpose", "signature_sha256"}
    if not required.issubset(fields):
        raise SafetyRefused(
            "safety.refuse.voice_clone_no_consent", audit_flag=flag_fail
        )

    header = (
        f"voice_owner: {fields['voice_owner']}\n"
        f"date: {fields['date']}\n"
        f"purpose: {fields['purpose']}\n"
    )
    expected_sig = hashlib.sha256(header.encode("utf-8")).hexdigest()
    if expected_sig != fields["signature_sha256"]:
        raise SafetyRefused(
            "safety.refuse.voice_clone_no_consent", audit_flag=flag_fail
        )

    question = get_message(
        "safety.confirm.voice_clone", lang=lang, owner=fields["voice_owner"]
    )
    if not interactive_confirm(question):
        raise SafetyRefused(
            "safety.refuse.voice_clone_no_consent", audit_flag=flag_fail
        )

    return fields["voice_owner"]


# ---------------------------------------------------------------------------
# Filter 3 — Realistic faces without opt-in (augmentation, not refusal)
# ---------------------------------------------------------------------------


_PERSON_TOKENS = {
    "es": (
        "persona",
        "personas",
        "hermano",
        "hermana",
        "irma",
        "irmao",
        "rostro",
        "rostros",
        "retrato",
        "cara",
        "anciano",
        "publicador",
    ),
    "en": (
        "person",
        "people",
        "brother",
        "sister",
        "portrait",
        "face",
        "elder",
        "publisher",
    ),
    "pt": (
        "pessoa",
        "pessoas",
        "irmao",
        "irma",
        "rosto",
        "rostos",
        "retrato",
        "anciao",
        "publicador",
    ),
}


def _mentions_person(prompt: str, lang: Lang) -> bool:
    norm = _normalize(prompt)
    candidates = _PERSON_TOKENS.get(lang, ()) + _PERSON_TOKENS["en"]
    return any(token in norm.split() or token in norm for token in candidates)


def refuse_realistic_faces_without_optin(
    *,
    prompt: str,
    lang: Lang = "es",
    realistic_optin: bool,
) -> str:
    """Return possibly-augmented prompt.

    When optin is False AND prompt mentions a person, append the localized
    'not photorealistic' suffix.
    """

    if realistic_optin:
        return prompt
    if not _mentions_person(prompt, lang):
        return prompt
    suffix = realism_suffix(lang)
    if prompt.rstrip().endswith(suffix.strip()):
        return prompt
    return prompt.rstrip(" .") + suffix


# ---------------------------------------------------------------------------
# Combined entry point
# ---------------------------------------------------------------------------


def evaluate(req: GenerationRequest) -> SafetyDecision:
    """Run all applicable filters. Returns a SafetyDecision."""

    flags: dict[str, str] = {
        "logo_check": "n/a",
        "voice_clone_optin": "n/a",
        "realistic_faces_optin": "n/a",
    }
    try:
        refuse_jw_logo_emulation(req.prompt, lang=req.lang)
        flags["logo_check"] = "pass"
    except SafetyRefused as exc:
        k, v = exc.audit_flag
        flags[k] = v
        return SafetyDecision(allow=False, reason=exc.reason, audit_flags=flags)

    # Voice clone is gated at CLI/MCP layer (needs interactive_confirm callable).
    if req.voice_clone_source is not None:
        flags["voice_clone_optin"] = "pending"

    augmented = refuse_realistic_faces_without_optin(
        prompt=req.prompt, lang=req.lang, realistic_optin=req.realistic_people_optin
    )
    flags["realistic_faces_optin"] = (
        "optin" if req.realistic_people_optin else "stylized"
    )

    return SafetyDecision(
        allow=True,
        augmented_prompt=augmented if augmented != req.prompt else None,
        audit_flags=flags,
    )
