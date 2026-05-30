"""Tests for the privacy module (Module 11)."""

from __future__ import annotations

import os

import pytest

from jw_core.privacy import (
    EncryptionError,
    FieldEncryptor,
    audit_telemetry_outflow,
    derive_key_from_password,
    generate_key,
    is_offline_mode,
)


# ── Encryption ──────────────────────────────────────────────────────────


def test_no_key_means_noop_encryption(monkeypatch) -> None:
    monkeypatch.delenv("JW_PRIVACY_KEY", raising=False)
    enc = FieldEncryptor()
    assert not enc.enabled
    token = enc.encrypt("hello")
    assert token == "hello"
    assert enc.decrypt(token) == "hello"


def test_with_key_roundtrips() -> None:
    try:
        from cryptography.fernet import Fernet  # noqa: F401
    except ImportError:
        pytest.skip("cryptography not installed")
    key = generate_key()
    enc = FieldEncryptor(key=key)
    assert enc.enabled
    token = enc.encrypt("very secret content")
    assert token != "very secret content"
    assert enc.decrypt(token) == "very secret content"


def test_invalid_key_raises() -> None:
    try:
        from cryptography.fernet import Fernet  # noqa: F401
    except ImportError:
        pytest.skip("cryptography not installed")
    with pytest.raises(EncryptionError):
        FieldEncryptor(key=b"not a real key")


def test_derive_key_deterministic() -> None:
    try:
        from cryptography.fernet import Fernet  # noqa: F401
    except ImportError:
        pytest.skip("cryptography not installed")
    a = derive_key_from_password("hunter2")
    b = derive_key_from_password("hunter2")
    assert a == b
    c = derive_key_from_password("hunter3")
    assert c != a


# ── Telemetry audit ────────────────────────────────────────────────────


def test_is_offline_mode_default_true(monkeypatch) -> None:
    monkeypatch.delenv("JW_TELEMETRY_ENABLED", raising=False)
    assert is_offline_mode()


def test_is_offline_mode_false_when_enabled(monkeypatch) -> None:
    monkeypatch.setenv("JW_TELEMETRY_ENABLED", "1")
    assert not is_offline_mode()


def test_audit_telemetry_returns_findings(monkeypatch) -> None:
    monkeypatch.delenv("JW_TELEMETRY_ENABLED", raising=False)
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    monkeypatch.delenv("DATADOG_API_KEY", raising=False)
    monkeypatch.delenv("NEW_RELIC_LICENSE_KEY", raising=False)
    result = audit_telemetry_outflow()
    assert result.is_offline is True


def test_audit_detects_third_party_telemetry(monkeypatch) -> None:
    monkeypatch.setenv("DATADOG_API_KEY", "fake")
    try:
        result = audit_telemetry_outflow()
        keys = [f["key"] for f in result.findings]
        assert "DATADOG_API_KEY" in keys
        assert any("DATADOG_API_KEY" in r for r in result.recommendations)
    finally:
        os.environ.pop("DATADOG_API_KEY", None)
