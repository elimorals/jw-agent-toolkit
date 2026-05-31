"""Shared fixtures for jw-gen tests.

The eval suite never hits a real provider or the network. The `fake_audit_log`
fixture redirects `~/.jw-gen/audit.log` into a per-test temp directory so
parallel tests don't collide.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest


@pytest.fixture
def isolated_jw_gen_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point JW_GEN_HOME at an isolated tmp dir so audit.log + private/ don't leak."""

    home = tmp_path / ".jw-gen"
    home.mkdir()
    monkeypatch.setenv("JW_GEN_HOME", str(home))
    return home


@pytest.fixture
def sample_png_bytes() -> bytes:
    """Smallest possible valid PNG (1x1 transparent)."""

    return bytes.fromhex(
        "89504E470D0A1A0A0000000D49484452000000010000000108060000001F15C489"
        "0000000D49444154789C636060000000040001274BE8410000000049454E44AE426082"
    )


@pytest.fixture
def fixtures_dir() -> Path:
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def no_network(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Hard-fail any attempt at HTTP egress during a test."""

    def _refuse(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("network access blocked in tests")

    # Block both httpx and requests at the socket level.
    import socket

    real_connect = socket.socket.connect

    def fake_connect(self: socket.socket, addr: object) -> None:  # noqa: ANN401
        if isinstance(addr, tuple) and addr[0] in {"127.0.0.1", "localhost"}:
            return real_connect(self, addr)
        _refuse()

    monkeypatch.setattr(socket.socket, "connect", fake_connect)
    yield
