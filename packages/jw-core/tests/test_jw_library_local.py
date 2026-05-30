"""Tests for jw_core.integrations.jw_library_local (Layer 3)."""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

from jw_core.integrations import jw_library_local as mod
from jw_core.integrations.jw_library_local import (
    ENV_OPT_IN,
    MacOSFullDiskAccessError,
    check_macos_full_disk_access,
    inspect_local_jw_library,
    read_macos_userdata,
)


def test_opt_in_required_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(ENV_OPT_IN, raising=False)
    result = inspect_local_jw_library()
    assert result.opt_in is False
    assert result.supported is False
    assert any("Opt-in required" in r for r in result.reasons)


def test_opt_in_via_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(ENV_OPT_IN, "1")
    result = inspect_local_jw_library()
    assert result.opt_in is True


def test_force_overrides_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(ENV_OPT_IN, raising=False)
    result = inspect_local_jw_library(force=True)
    assert result.opt_in is True


# ── macOS ────────────────────────────────────────────────────────────────


def _redirect_mac_paths(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    app_exists: bool,
    container_exists: bool,
) -> None:
    """Point the module's _MAC_* constants at tmp_path so we can control existence."""
    app = tmp_path / "JW Library.app"
    container = tmp_path / "Containers" / "org.jw.jwlibrary"
    if app_exists:
        app.mkdir(parents=True)
    if container_exists:
        container.mkdir(parents=True)
    monkeypatch.setattr(mod, "_MAC_APP_PATH", app)
    monkeypatch.setattr(mod, "_MAC_CONTAINER", container)


def test_macos_reports_app_when_installed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(mod, "_platform", lambda: "darwin")
    _redirect_mac_paths(monkeypatch, tmp_path, app_exists=True, container_exists=False)
    result = inspect_local_jw_library(force=True)
    assert result.platform == "darwin"
    assert result.supported is False  # macOS is never "supported" for DB reads
    assert result.app_detected is True
    assert any("backup" in s.lower() for s in result.suggestions)


def test_macos_reports_no_app_when_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(mod, "_platform", lambda: "darwin")
    _redirect_mac_paths(monkeypatch, tmp_path, app_exists=False, container_exists=False)
    result = inspect_local_jw_library(force=True)
    assert result.app_detected is False
    assert any("not found" in r.lower() for r in result.reasons)


def test_macos_container_detected_but_unreadable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(mod, "_platform", lambda: "darwin")
    _redirect_mac_paths(monkeypatch, tmp_path, app_exists=True, container_exists=True)
    result = inspect_local_jw_library(force=True)
    assert any("sandbox" in r.lower() for r in result.reasons)


# ── Windows ──────────────────────────────────────────────────────────────


def _seed_uwp_publications_db(local_appdata: Path) -> Path:
    pkg = (
        local_appdata
        / "Packages"
        / "WatchtowerBibleandTractSocietyofNewYorkInc.JWLibrary_8wekyb3d8bbwe"
        / "LocalState"
        / "Publications"
    )
    pkg.mkdir(parents=True)
    db_path = pkg / "publications.db"
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE Publication (
            PublicationId INTEGER PRIMARY KEY,
            KeySymbol TEXT,
            Title TEXT,
            ShortTitle TEXT,
            PublicationType TEXT,
            Year INTEGER,
            IssueTagNumber INTEGER,
            MepsLanguageIndex INTEGER,
            LastModified TEXT
        );
        INSERT INTO Publication VALUES
            (1, 'bh', 'Bible Teach', 'Bible Teach', 'Book', 2014, 0, 0, '2024-01-15'),
            (2, 'w24', 'The Watchtower (Study)', 'WT Study', 'Periodical', 2024, 20240401, 0, '2024-04-15'),
            (3, 'nwtsty', 'NWT Study Edition', 'NWT Study', 'Bible', 2018, 0, 0, '2024-09-01');
        """
    )
    conn.commit()
    conn.close()
    # Also drop a userData.db marker so the inspector reports it.
    (db_path.parent.parent / "userData.db").write_bytes(b"\x00")
    return db_path


def test_windows_publications_db_read(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(mod, "_platform", lambda: "win32")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    _seed_uwp_publications_db(tmp_path)
    result = inspect_local_jw_library(force=True)
    assert result.platform == "win32"
    assert result.supported is True
    assert result.app_detected is True
    assert len(result.publications) == 3
    titles = {p.title for p in result.publications}
    assert "Bible Teach" in titles
    assert "NWT Study Edition" in titles
    # userData.db marker present.
    assert result.user_data_path.endswith("userData.db")


def test_windows_no_package_found(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(mod, "_platform", lambda: "win32")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    # Empty LOCALAPPDATA.
    result = inspect_local_jw_library(force=True)
    assert result.app_detected is False
    assert any("not found" in r.lower() for r in result.reasons)


def test_windows_no_localappdata(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mod, "_platform", lambda: "win32")
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    result = inspect_local_jw_library(force=True)
    assert result.app_detected is False
    assert any("LOCALAPPDATA" in r for r in result.reasons)


def test_windows_publications_db_schema_partial(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # Only PublicationId + Title present; we must still return rows.
    monkeypatch.setattr(mod, "_platform", lambda: "win32")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    pkg = (
        tmp_path
        / "Packages"
        / "WatchtowerBibleandTractSocietyofNewYorkInc.JWLibrary_x"
        / "LocalState"
        / "Publications"
    )
    pkg.mkdir(parents=True)
    db_path = pkg / "publications.db"
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE Publication (PublicationId INTEGER PRIMARY KEY, Title TEXT);
        INSERT INTO Publication VALUES (42, 'A minimal pub');
        """
    )
    conn.commit()
    conn.close()
    result = inspect_local_jw_library(force=True)
    assert len(result.publications) == 1
    assert result.publications[0].title == "A minimal pub"
    assert result.publications[0].key_symbol == ""


# ── Linux ────────────────────────────────────────────────────────────────


def test_linux_is_unsupported(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mod, "_platform", lambda: "linux")
    result = inspect_local_jw_library(force=True)
    assert result.supported is False
    assert any("no native Linux build" in r for r in result.reasons)


# ── Smoke ────────────────────────────────────────────────────────────────


def _seed_macos_container_with_userdata(tmp_path: Path) -> Path:
    """Build a minimal sandbox container with a populated userData.db."""
    import sqlite3

    container = tmp_path / "Containers" / "org.jw.jwlibrary"
    db_dir = container / "Data" / "Library" / "Application Support"
    db_dir.mkdir(parents=True)
    db_path = db_dir / "userData.db"
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE Location (LocationId INTEGER PRIMARY KEY, BookNumber INTEGER, ChapterNumber INTEGER, DocumentId INTEGER, Track INTEGER, IssueTagNumber INTEGER, KeySymbol TEXT, MepsLanguage INTEGER, Type INTEGER, Title TEXT);
        CREATE TABLE Note (NoteId INTEGER PRIMARY KEY, Guid TEXT, UserMarkId INTEGER, LocationId INTEGER, Title TEXT, Content TEXT, LastModified TEXT, Created TEXT, BlockType INTEGER, BlockIdentifier INTEGER);
        INSERT INTO Location VALUES (1, 43, 3, NULL, NULL, NULL, 'nwtsty', 0, 2, 'Juan 3');
        INSERT INTO Note VALUES (1, 'g1', NULL, 1, 'Live note', 'Loaded from FDA path', 'now', 'now', NULL, NULL);
        """
    )
    conn.commit()
    conn.close()
    return container


def test_check_fda_returns_unreadable_for_missing_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(mod, "_MAC_CONTAINER", tmp_path / "nope")
    out = check_macos_full_disk_access()
    assert out["readable"] is False
    assert "does not exist" in out["error"]


def test_check_fda_succeeds_when_path_readable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    target = tmp_path / "Containers" / "org.jw.jwlibrary"
    target.mkdir(parents=True)
    monkeypatch.setattr(mod, "_MAC_CONTAINER", target)
    out = check_macos_full_disk_access()
    assert out["readable"] is True


def test_check_fda_reports_permission_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    target = tmp_path / "blocked"
    target.mkdir()
    monkeypatch.setattr(mod, "_MAC_CONTAINER", target)

    def boom(_path):  # noqa: ANN001
        raise PermissionError("Operation not permitted")

    monkeypatch.setattr(mod.os, "scandir", boom)
    out = check_macos_full_disk_access()
    assert out["readable"] is False
    assert "PermissionError" in out["error"]


def test_read_macos_userdata_succeeds_when_fda_granted(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    container = _seed_macos_container_with_userdata(tmp_path)
    monkeypatch.setattr(mod, "_MAC_CONTAINER", container)
    backup = read_macos_userdata()
    assert backup.counts["notes"] == 1
    assert backup.notes[0].title == "Live note"
    assert backup.notes[0].location is not None
    assert backup.notes[0].location.book_number == 43


def test_read_macos_userdata_raises_when_blocked(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    target = tmp_path / "blocked"
    target.mkdir()
    monkeypatch.setattr(mod, "_MAC_CONTAINER", target)

    def boom(_path):  # noqa: ANN001
        raise PermissionError("Operation not permitted")

    monkeypatch.setattr(mod.os, "scandir", boom)
    with pytest.raises(MacOSFullDiskAccessError):
        read_macos_userdata()


def test_inspect_macos_reports_fda_granted_and_userdata_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(mod, "_platform", lambda: "darwin")
    monkeypatch.setattr(mod, "_MAC_APP_PATH", tmp_path / "JW Library.app")
    (tmp_path / "JW Library.app").mkdir()
    container = _seed_macos_container_with_userdata(tmp_path)
    monkeypatch.setattr(mod, "_MAC_CONTAINER", container)
    result = inspect_local_jw_library(force=True)
    assert result.supported is True
    assert result.user_data_path.endswith("userData.db")
    assert any("Full Disk Access" in r for r in result.reasons)


def test_inspect_macos_gives_fda_instructions_when_blocked(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(mod, "_platform", lambda: "darwin")
    monkeypatch.setattr(mod, "_MAC_APP_PATH", tmp_path / "JW Library.app")
    (tmp_path / "JW Library.app").mkdir()
    container = tmp_path / "Containers" / "org.jw.jwlibrary"
    container.mkdir(parents=True)
    monkeypatch.setattr(mod, "_MAC_CONTAINER", container)

    def boom(_path):  # noqa: ANN001
        raise PermissionError("Operation not permitted")

    monkeypatch.setattr(mod.os, "scandir", boom)
    result = inspect_local_jw_library(force=True)
    assert result.supported is False
    assert any("Privacy & Security" in s for s in result.suggestions)


def test_to_dict_shape_matches_expected_keys(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(mod, "_platform", lambda: "darwin")
    _redirect_mac_paths(monkeypatch, tmp_path, app_exists=False, container_exists=False)
    d = inspect_local_jw_library(force=True).to_dict()
    assert set(d.keys()) >= {
        "platform",
        "supported",
        "opt_in",
        "app_detected",
        "publications",
        "publication_count",
        "reasons",
        "suggestions",
    }
