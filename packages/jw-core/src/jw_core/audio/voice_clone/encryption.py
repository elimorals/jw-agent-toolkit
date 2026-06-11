"""Opt-in Fernet encryption for voice-clone weights (Fase 76 post-MVP).

When `JW_VOICE_KEY` is set in the environment (Fernet-encoded), training
artifacts can be encrypted at rest and decrypted on demand:

- `encrypt_weights(src, dst)` reads the plaintext file at `src`, writes
  a Fernet-encrypted file at `dst`, and returns `dst`. A `.enc` suffix
  is conventional but not enforced.
- `decrypt_to_tempfile(path)` reads an encrypted file and writes the
  plaintext to a `NamedTemporaryFile`-style path that the caller must
  delete after use. The returned path is on the same filesystem so
  `os.replace` works.

`require_key()` raises `EncryptionDisabledError` when the user has not
opted in. This keeps the failure mode loud rather than silently
storing plaintext when the user expected encryption.

`cryptography` is an optional dependency; importing this module on a
minimal install raises a clear `MissingDependencyError`.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

try:
    from cryptography.fernet import Fernet, InvalidToken
except ImportError as exc:  # pragma: no cover - exercised via test guard
    raise ImportError(
        "voice_clone.encryption requires `cryptography` "
        "(pip install cryptography or `jw-agent-toolkit[voice]`)."
    ) from exc


ENV_KEY = "JW_VOICE_KEY"


class EncryptionDisabledError(RuntimeError):
    """Raised when encryption is requested but no key has been provided."""


class EncryptionKeyInvalidError(ValueError):
    """Raised when JW_VOICE_KEY is set but not a valid Fernet key."""


def is_enabled() -> bool:
    """Return True if `JW_VOICE_KEY` is set to a non-empty value."""

    return bool(os.environ.get(ENV_KEY, "").strip())


def generate_key() -> str:
    """Return a fresh Fernet key as a urlsafe-base64 string."""

    return Fernet.generate_key().decode("ascii")


def _load_fernet() -> Fernet:
    raw = os.environ.get(ENV_KEY, "").strip()
    if not raw:
        raise EncryptionDisabledError(
            f"{ENV_KEY} is not set; encryption is opt-in"
        )
    try:
        return Fernet(raw.encode("ascii"))
    except (ValueError, TypeError) as exc:
        raise EncryptionKeyInvalidError(
            f"{ENV_KEY} is not a valid Fernet key (urlsafe-base64, 32 bytes)"
        ) from exc


def require_key() -> Fernet:
    """Return the active Fernet instance or raise."""

    return _load_fernet()


def encrypt_weights(
    src: str | Path, dst: str | Path | None = None
) -> Path:
    """Encrypt `src` in place (default) or to `dst`. Returns the output path."""

    src_path = Path(src)
    if not src_path.exists():
        raise FileNotFoundError(src_path)
    fernet = _load_fernet()
    token = fernet.encrypt(src_path.read_bytes())
    out_path = Path(dst) if dst else src_path.with_suffix(
        src_path.suffix + ".enc"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(token)
    return out_path


def decrypt_to_tempfile(path: str | Path) -> Path:
    """Decrypt `path` to a fresh temp file and return its path.

    Caller is responsible for deleting the returned file. The path is
    suffixed with `.dec` and lives in the system temp dir.
    """

    src_path = Path(path)
    if not src_path.exists():
        raise FileNotFoundError(src_path)
    fernet = _load_fernet()
    try:
        plaintext = fernet.decrypt(src_path.read_bytes())
    except InvalidToken as exc:
        raise EncryptionKeyInvalidError(
            "Could not decrypt — token is invalid or key is wrong"
        ) from exc
    tmp = tempfile.NamedTemporaryFile(
        delete=False,
        prefix="jw_voice_",
        suffix=".dec",
    )
    try:
        tmp.write(plaintext)
    finally:
        tmp.close()
    return Path(tmp.name)


__all__ = [
    "ENV_KEY",
    "EncryptionDisabledError",
    "EncryptionKeyInvalidError",
    "decrypt_to_tempfile",
    "encrypt_weights",
    "generate_key",
    "is_enabled",
    "require_key",
]
