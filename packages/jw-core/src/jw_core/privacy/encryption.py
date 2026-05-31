"""Symmetric field-level encryption with Fernet.

VISION.md: "Cifrado de notas personales y del RAG store por defecto".

Key sources (in order of preference):
  1. Explicit `key` passed to the constructor.
  2. Environment var `JW_PRIVACY_KEY` (urlsafe base64 32-byte key).
  3. None → encryption is a no-op (the field is stored cleartext). The
     constructor logs a warning so the user knows.

We always wrap calls in `enabled` so the surrounding store can stay
identical whether encryption is on or off — turning it on is just an
env var away.
"""

from __future__ import annotations

import base64
import hashlib
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


class EncryptionError(RuntimeError):
    pass


def generate_key() -> bytes:
    """Generate a fresh urlsafe base64 Fernet key (32 random bytes)."""
    try:
        from cryptography.fernet import Fernet
    except ImportError as e:
        raise EncryptionError("`cryptography` is required. `pip install cryptography`") from e
    return Fernet.generate_key()


def derive_key_from_password(password: str, *, salt: bytes | None = None) -> bytes:
    """Derive a Fernet key from a passphrase (PBKDF2-HMAC-SHA256, 200k iters).

    Stores a fixed salt by default so the derived key is deterministic for a
    given passphrase. Override `salt` for per-user salts (recommended for
    multi-user installs).
    """
    salt = salt or b"jw-agent-toolkit/v1"
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations=200_000)
    return base64.urlsafe_b64encode(dk)


class FieldEncryptor:
    """Wraps cryptography.Fernet with a no-op fallback when no key is set."""

    def __init__(self, key: bytes | None = None) -> None:
        key = key or os.getenv("JW_PRIVACY_KEY", "").encode("utf-8") or None
        if not key:
            logger.warning(
                "FieldEncryptor: no key provided (set JW_PRIVACY_KEY to enable). "
                "All encrypt/decrypt calls will be no-ops."
            )
            self._fernet = None
            self.enabled = False
            return
        try:
            from cryptography.fernet import Fernet
        except ImportError as e:
            raise EncryptionError("`cryptography` is required to use a key. `pip install cryptography`") from e
        try:
            self._fernet = Fernet(key)
            self.enabled = True
        except Exception as e:
            raise EncryptionError(f"Invalid key (must be urlsafe base64, 32-byte decoded): {e}") from e

    def encrypt(self, value: Any) -> str:
        if not self.enabled or self._fernet is None:
            return str(value)
        if isinstance(value, bytes):
            payload = value
        else:
            payload = str(value).encode("utf-8")
        return self._fernet.encrypt(payload).decode("ascii")

    def decrypt(self, token: str) -> str:
        if not self.enabled or self._fernet is None:
            return token
        try:
            return self._fernet.decrypt(token.encode("ascii")).decode("utf-8")
        except Exception as e:
            raise EncryptionError(f"Decryption failed: {e}") from e
