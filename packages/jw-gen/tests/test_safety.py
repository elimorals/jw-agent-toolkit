from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from jw_gen.models import GenerationRequest
from jw_gen.safety import (
    SafetyRefused,
    evaluate,
    refuse_jw_logo_emulation,
    refuse_realistic_faces_without_optin,
    refuse_voice_cloning_without_double_optin,
)


@pytest.mark.parametrize(
    "lang,prompt",
    [
        ("en", "Generate an official watchtower logo"),
        ("en", "Awake magazine cover style emblem"),
        ("es", "Logo de la Atalaya con fondo azul"),
        ("es", "letrero oficial Salón del Reino"),
        ("pt", "capa de Despertai oficial JW"),
        ("pt", "logo da Sentinela"),
    ],
)
def test_refuse_jw_logo_emulation_blocks_keywords(lang: str, prompt: str) -> None:
    with pytest.raises(SafetyRefused) as excinfo:
        refuse_jw_logo_emulation(prompt, lang=lang)  # type: ignore[arg-type]
    assert "safety.refuse.logo" in str(excinfo.value.reason)


def test_refuse_jw_logo_emulation_allows_neutral_prompt() -> None:
    refuse_jw_logo_emulation("ilustración de ovejas en una montaña", lang="es")


def test_refuse_jw_logo_emulation_handles_accents_and_case() -> None:
    # Normalization must catch this even with mixed case + accents.
    with pytest.raises(SafetyRefused):
        refuse_jw_logo_emulation("LOGO DE LA ÁTALAYA", lang="es")


def test_refuse_voice_clone_blocks_without_flag(tmp_path: Path) -> None:
    audio = tmp_path / "voice.wav"
    audio.write_bytes(b"fake-wav")
    with pytest.raises(SafetyRefused):
        refuse_voice_cloning_without_double_optin(
            audio_src=audio,
            voice_clone_flag=False,
            interactive_confirm=lambda _q: True,
        )


def test_refuse_voice_clone_blocks_without_consent_file(tmp_path: Path) -> None:
    audio = tmp_path / "voice.wav"
    audio.write_bytes(b"fake-wav")
    with pytest.raises(SafetyRefused):
        refuse_voice_cloning_without_double_optin(
            audio_src=audio,
            voice_clone_flag=True,
            interactive_confirm=lambda _q: True,
        )


def test_refuse_voice_clone_blocks_on_invalid_signature(tmp_path: Path) -> None:
    audio = tmp_path / "voice.wav"
    audio.write_bytes(b"fake-wav")
    consent = audio.with_suffix(".wav.consent.txt")
    consent.write_text(
        "voice_owner: Hermano X\ndate: 2026-05-31\npurpose: test\nsignature_sha256: deadbeef-bad-sig\n",
        encoding="utf-8",
    )
    with pytest.raises(SafetyRefused):
        refuse_voice_cloning_without_double_optin(
            audio_src=audio,
            voice_clone_flag=True,
            interactive_confirm=lambda _q: True,
        )


def _well_signed_consent(audio: Path, owner: str = "Hermano X") -> Path:
    """Write a consent file with a sha256 of the first three lines."""

    header_lines = [
        f"voice_owner: {owner}",
        "date: 2026-05-31",
        "purpose: prueba pre-discurso",
    ]
    header = "\n".join(header_lines) + "\n"
    sig = hashlib.sha256(header.encode("utf-8")).hexdigest()
    consent = audio.with_suffix(audio.suffix + ".consent.txt")
    consent.write_text(header + f"signature_sha256: {sig}\n", encoding="utf-8")
    return consent


def test_refuse_voice_clone_passes_with_full_optin(tmp_path: Path) -> None:
    audio = tmp_path / "voice.wav"
    audio.write_bytes(b"fake-wav")
    _well_signed_consent(audio)
    owner = refuse_voice_cloning_without_double_optin(
        audio_src=audio,
        voice_clone_flag=True,
        interactive_confirm=lambda _q: True,
    )
    assert owner == "Hermano X"


def test_refuse_voice_clone_blocks_when_user_declines_confirm(tmp_path: Path) -> None:
    audio = tmp_path / "voice.wav"
    audio.write_bytes(b"fake-wav")
    _well_signed_consent(audio)
    with pytest.raises(SafetyRefused):
        refuse_voice_cloning_without_double_optin(
            audio_src=audio,
            voice_clone_flag=True,
            interactive_confirm=lambda _q: False,
        )


def test_realistic_faces_default_appends_suffix() -> None:
    augmented = refuse_realistic_faces_without_optin(
        prompt="retrato de un hermano dando un discurso",
        lang="es",
        realistic_optin=False,
    )
    assert augmented.endswith("no fotorrealista")


def test_realistic_faces_no_op_when_no_person_keyword() -> None:
    augmented = refuse_realistic_faces_without_optin(
        prompt="ovejas en una colina al atardecer",
        lang="es",
        realistic_optin=False,
    )
    assert augmented == "ovejas en una colina al atardecer"


def test_realistic_faces_optin_keeps_prompt_intact() -> None:
    augmented = refuse_realistic_faces_without_optin(
        prompt="retrato de un hermano dando un discurso",
        lang="es",
        realistic_optin=True,
    )
    assert augmented == "retrato de un hermano dando un discurso"


def test_evaluate_combines_filters_pass() -> None:
    req = GenerationRequest(
        prompt="ilustración de ovejas pastoreadas",
        kind="image",
        lang="es",
    )
    decision = evaluate(req)
    assert decision.allow is True
    assert decision.audit_flags["logo_check"] == "pass"


def test_evaluate_combines_filters_fail_on_logo() -> None:
    req = GenerationRequest(prompt="logo de la atalaya en azul", kind="image", lang="es")
    decision = evaluate(req)
    assert decision.allow is False
    assert decision.reason == "safety.refuse.logo"
