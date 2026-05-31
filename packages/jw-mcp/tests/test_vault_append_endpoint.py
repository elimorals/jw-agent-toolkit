"""POST /api/v1/vault/append — append a verse markdown block to a vault file.

Critical security property: the path MUST be inside an Obsidian vault
(detected by ancestor directory containing a ``.obsidian/`` folder).
The endpoint MUST refuse writes to ~/.ssh, /etc, $HOME root, etc.
"""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from jw_mcp.rest_api import app


def _make_fake_vault(root: Path) -> Path:
    """Create a directory that looks like an Obsidian vault."""
    vault = root / "MyVault"
    vault.mkdir()
    (vault / ".obsidian").mkdir()
    (vault / ".obsidian" / "app.json").write_text("{}", encoding="utf-8")
    return vault


def test_vault_append_writes_inside_vault(tmp_path: Path) -> None:
    vault = _make_fake_vault(tmp_path)
    c = TestClient(app)
    r = c.post(
        "/api/v1/vault/append",
        json={
            "reference": "Juan 3:16",
            "vault_path": str(vault),
            "template": "callout",
            "language": "es",
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    written = Path(body["path"])
    assert written.exists()
    assert vault in written.parents
    assert "Juan" in written.read_text(encoding="utf-8")


def test_vault_append_refuses_non_vault_path(tmp_path: Path) -> None:
    not_a_vault = tmp_path / "random_dir"
    not_a_vault.mkdir()
    c = TestClient(app)
    r = c.post(
        "/api/v1/vault/append",
        json={
            "reference": "Juan 3:16",
            "vault_path": str(not_a_vault),
            "template": "callout",
            "language": "es",
        },
    )
    assert r.status_code == 400
    assert "obsidian" in r.json()["detail"].lower()


def test_vault_append_refuses_dotssh_lookalike(tmp_path: Path) -> None:
    """Defense against Spec Risk #7 — user points vault_path at ~/.ssh."""
    ssh = tmp_path / ".ssh"
    ssh.mkdir()
    (ssh / "id_rsa").write_text("private key", encoding="utf-8")
    c = TestClient(app)
    r = c.post(
        "/api/v1/vault/append",
        json={
            "reference": "Juan 3:16",
            "vault_path": str(ssh),
            "template": "callout",
            "language": "es",
        },
    )
    assert r.status_code == 400


def test_vault_append_refuses_path_traversal(tmp_path: Path) -> None:
    vault = _make_fake_vault(tmp_path)
    c = TestClient(app)
    r = c.post(
        "/api/v1/vault/append",
        json={
            "reference": "Juan 3:16",
            "vault_path": str(vault),
            "subdir": "../../../../etc",
            "template": "callout",
            "language": "es",
        },
    )
    assert r.status_code == 400
    detail = r.json()["detail"].lower()
    assert "outside" in detail or "traversal" in detail


def test_vault_append_refuses_root_path() -> None:
    c = TestClient(app)
    r = c.post(
        "/api/v1/vault/append",
        json={
            "reference": "Juan 3:16",
            "vault_path": "/",
            "template": "callout",
            "language": "es",
        },
    )
    assert r.status_code == 400


def test_vault_append_creates_subdir_when_missing(tmp_path: Path) -> None:
    vault = _make_fake_vault(tmp_path)
    c = TestClient(app)
    r = c.post(
        "/api/v1/vault/append",
        json={
            "reference": "John 3:16",
            "vault_path": str(vault),
            "subdir": "Verses",
            "template": "callout",
            "language": "en",
        },
    )
    assert r.status_code == 200
    body = r.json()
    written = Path(body["path"])
    assert "Verses" in written.parts
