"""Fernet opt-in encryption tests (Fase 76 post-MVP)."""

from __future__ import annotations

import pytest

from jw_core.audio.voice_clone.encryption import (
    ENV_KEY,
    EncryptionDisabledError,
    EncryptionKeyInvalidError,
    decrypt_to_tempfile,
    encrypt_weights,
    generate_key,
    is_enabled,
)


def test_is_enabled_reflects_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(ENV_KEY, raising=False)
    assert is_enabled() is False
    monkeypatch.setenv(ENV_KEY, generate_key())
    assert is_enabled() is True


def test_encrypt_raises_when_disabled(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    monkeypatch.delenv(ENV_KEY, raising=False)
    src = tmp_path / "weights.bin"
    src.write_bytes(b"\x00\x01\x02")
    with pytest.raises(EncryptionDisabledError):
        encrypt_weights(src)


def test_encrypt_roundtrip(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    monkeypatch.setenv(ENV_KEY, generate_key())
    src = tmp_path / "weights.bin"
    payload = b"FAKEWEIGHTS-" + b"X" * 1024
    src.write_bytes(payload)

    enc = encrypt_weights(src)
    assert enc.exists()
    assert enc.read_bytes() != payload  # ciphertext differs from plaintext

    dec = decrypt_to_tempfile(enc)
    try:
        assert dec.read_bytes() == payload
    finally:
        dec.unlink(missing_ok=True)


def test_encrypt_to_custom_dst(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    monkeypatch.setenv(ENV_KEY, generate_key())
    src = tmp_path / "in.bin"
    src.write_bytes(b"data")
    dst = tmp_path / "out.encrypted"

    out = encrypt_weights(src, dst)
    assert out == dst
    assert dst.exists()


def test_invalid_key_raises(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    monkeypatch.setenv(ENV_KEY, "not-a-valid-fernet-key")
    src = tmp_path / "x.bin"
    src.write_bytes(b"x")
    with pytest.raises(EncryptionKeyInvalidError):
        encrypt_weights(src)


def test_wrong_key_fails_to_decrypt(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    key_a = generate_key()
    key_b = generate_key()
    src = tmp_path / "x.bin"
    src.write_bytes(b"secret")

    monkeypatch.setenv(ENV_KEY, key_a)
    enc = encrypt_weights(src)

    monkeypatch.setenv(ENV_KEY, key_b)
    with pytest.raises(EncryptionKeyInvalidError):
        decrypt_to_tempfile(enc)


def test_encrypt_missing_file_raises(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    monkeypatch.setenv(ENV_KEY, generate_key())
    with pytest.raises(FileNotFoundError):
        encrypt_weights(tmp_path / "does-not-exist.bin")


def test_generate_key_is_valid_fernet() -> None:
    from cryptography.fernet import Fernet

    key = generate_key()
    # Will raise if invalid
    Fernet(key.encode("ascii"))
