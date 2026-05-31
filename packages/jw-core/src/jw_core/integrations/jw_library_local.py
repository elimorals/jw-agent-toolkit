"""Read-only inspector for a locally installed JW Library library.

Goal: tell the user "what publications and what user data does the JW
Library app on this machine actually have?" without ever writing to its
files. This is opt-in (env `JW_LIBRARY_LOCAL_READ=1`) and platform-aware:

  - **Windows** (UWP package): we can read `publications.db` inside the
    app's `LocalState` folder while the app is closed. We surface the
    publication catalog and the `userData.db` if it exists in the same
    folder.
  - **macOS**: JW Library on Mac is the **iPad app** running under the
    Mac App Store sandbox. By default, third-party processes cannot read
    the sandbox container. However, **if the user grants Full Disk Access
    to the running terminal/MCP host** (System Settings → Privacy &
    Security → Full Disk Access), the container becomes readable. We
    detect that situation, look for `userData.db` (the same SQLite the
    backup ships), copy it to a tempfile, and parse it with the standard
    backup parser. When FDA is not granted, we report actionable
    instructions instead of silently failing.
  - **Linux**: no native build exists. We report 'unsupported'.

Mutating the live DB while the app is running corrupts the cloud sync —
this module never opens a writable connection.
"""

from __future__ import annotations

import glob
import logging
import os
import sqlite3
import sys
from contextlib import closing
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

__all__ = [
    "InstalledPublication",
    "LocalInspectionResult",
    "MacOSFullDiskAccessError",
    "ENV_OPT_IN",
    "check_macos_full_disk_access",
    "inspect_local_jw_library",
    "read_macos_userdata",
]


class MacOSFullDiskAccessError(RuntimeError):
    """Raised when reading the macOS sandbox container is blocked by TCC."""


ENV_OPT_IN = "JW_LIBRARY_LOCAL_READ"

# Used to locate UWP package folders on Windows. The suffix is the package
# family name; the wildcard absorbs the publisher hash that UWP appends.
_WINDOWS_UWP_GLOB = "Packages/WatchtowerBibleandTractSocietyofNewYorkInc.JWLibrary_*/"
# macOS install location (the WrappedBundle iPad app under /Applications).
_MAC_APP_PATH = Path("/Applications/JW Library.app")
# macOS sandbox container (unreachable without TCC + a private entitlement,
# checked anyway so we can give the user a precise answer).
_MAC_CONTAINER = Path.home() / "Library/Containers/org.jw.jwlibrary"


@dataclass
class InstalledPublication:
    """One entry from the app's publications.db (Windows)."""

    publication_id: int
    key_symbol: str = ""
    title: str = ""
    short_title: str = ""
    publication_type: str = ""
    year: int | None = None
    issue_tag_number: int | None = None
    meps_language: int | None = None
    last_modified: str = ""


@dataclass
class LocalInspectionResult:
    """What we found on this machine — for the MCP tool to return verbatim."""

    platform: str
    supported: bool
    opt_in: bool
    app_detected: bool
    library_path: str = ""
    user_data_path: str = ""
    publications: list[InstalledPublication] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "platform": self.platform,
            "supported": self.supported,
            "opt_in": self.opt_in,
            "app_detected": self.app_detected,
            "library_path": self.library_path,
            "user_data_path": self.user_data_path,
            "publications": [
                {
                    "publication_id": p.publication_id,
                    "key_symbol": p.key_symbol,
                    "title": p.title,
                    "short_title": p.short_title,
                    "publication_type": p.publication_type,
                    "year": p.year,
                    "issue_tag_number": p.issue_tag_number,
                    "meps_language": p.meps_language,
                    "last_modified": p.last_modified,
                }
                for p in self.publications
            ],
            "publication_count": len(self.publications),
            "reasons": self.reasons,
            "suggestions": self.suggestions,
        }


def inspect_local_jw_library(*, force: bool = False) -> LocalInspectionResult:
    """Scan this machine for an installed JW Library and report what we see.

    Args:
        force: Ignore the `JW_LIBRARY_LOCAL_READ=1` env-var requirement.
            Off-the-shelf MCP clients should not set this; it exists for
            tests and for power users who want to bypass the opt-in.

    Returns:
        `LocalInspectionResult`. Always non-None — fields convey whether
        anything was readable.
    """
    opt_in = force or os.environ.get(ENV_OPT_IN, "").strip() == "1"
    platform = _platform()

    if not opt_in:
        return LocalInspectionResult(
            platform=platform,
            supported=False,
            opt_in=False,
            app_detected=False,
            reasons=[
                f"Opt-in required: set {ENV_OPT_IN}=1 to allow local "
                "JW Library inspection. We never write to the app's data."
            ],
        )

    if platform == "win32":
        return _inspect_windows()
    if platform == "darwin":
        return _inspect_macos()
    if platform == "linux":
        return _inspect_linux()
    return LocalInspectionResult(
        platform=platform,
        supported=False,
        opt_in=True,
        app_detected=False,
        reasons=[f"Unknown platform: {sys.platform}"],
    )


# ── Platform routines ───────────────────────────────────────────────────


def _platform() -> str:
    p = sys.platform
    if p == "darwin":
        return "darwin"
    if p == "win32":
        return "win32"
    if p.startswith("linux"):
        return "linux"
    return "unknown"


def _inspect_windows() -> LocalInspectionResult:
    local_appdata = os.environ.get("LOCALAPPDATA")
    if not local_appdata:
        return LocalInspectionResult(
            platform="win32",
            supported=True,
            opt_in=True,
            app_detected=False,
            reasons=["LOCALAPPDATA is not set"],
        )
    pattern = str(Path(local_appdata) / _WINDOWS_UWP_GLOB)
    matches = sorted(glob.glob(pattern))
    if not matches:
        return LocalInspectionResult(
            platform="win32",
            supported=True,
            opt_in=True,
            app_detected=False,
            reasons=["JW Library UWP package folder not found under LocalAppData."],
            suggestions=["Install JW Library from Microsoft Store, run it once, then re-run this tool."],
        )
    package_dir = Path(matches[0])
    local_state = package_dir / "LocalState"
    publications_db = local_state / "Publications" / "publications.db"
    if not publications_db.exists():
        # Older builds keep publications.db at LocalState root.
        publications_db = local_state / "publications.db"
    user_data_db = local_state / "userData.db"

    result = LocalInspectionResult(
        platform="win32",
        supported=True,
        opt_in=True,
        app_detected=True,
        library_path=str(publications_db.parent) if publications_db.exists() else str(local_state),
        user_data_path=str(user_data_db) if user_data_db.exists() else "",
    )

    if publications_db.exists():
        try:
            result.publications = _read_publications_db(publications_db)
        except sqlite3.DatabaseError as e:
            result.reasons.append(f"publications.db unreadable: {e}")
    else:
        result.reasons.append("publications.db not found under LocalState")

    if not result.user_data_path:
        result.suggestions.append(
            "No userData.db found locally; export a backup from the app "
            "(Settings → Backup) and pass it to `import_jw_library_backup`."
        )
    return result


def _inspect_macos() -> LocalInspectionResult:
    app_detected = _MAC_APP_PATH.exists()
    container_exists = _MAC_CONTAINER.exists()
    reasons: list[str] = []
    suggestions: list[str] = []
    if app_detected:
        reasons.append(f"JW Library app detected at {_MAC_APP_PATH}.")
    else:
        reasons.append("JW Library not found in /Applications. Install from Mac App Store.")

    user_data_path = ""
    fda_status = check_macos_full_disk_access()

    if container_exists:
        if fda_status["readable"]:
            reasons.append(f"Sandbox container at {_MAC_CONTAINER} is readable (Full Disk Access detected).")
            ud = _find_userdata_in_container(_MAC_CONTAINER)
            if ud is not None:
                user_data_path = str(ud)
                suggestions.append(
                    "Call `read_macos_userdata()` to load notes/highlights "
                    "directly from the live container without exporting a "
                    "backup."
                )
            else:
                reasons.append(
                    "Container is readable but userData.db was not found. "
                    "Run the app at least once and let it create user data."
                )
        else:
            reasons.append(
                f"Sandbox container exists at {_MAC_CONTAINER} but is "
                "blocked by macOS Transparency, Consent & Control (TCC). "
                "Grant Full Disk Access to enable live reads."
            )
            suggestions.extend(_fda_instructions())
    else:
        reasons.append(
            f"Sandbox container has not been created yet (expected at {_MAC_CONTAINER}). Run the app at least once."
        )

    suggestions.append(
        "Alternatively, export a User Data Backup from the app (Settings → "
        "Backup → Save) and pass the `.jwlibrary` file to "
        "`import_jw_library_backup`. Backups work without Full Disk Access."
    )
    return LocalInspectionResult(
        platform="darwin",
        supported=user_data_path != "",
        opt_in=True,
        app_detected=app_detected,
        library_path=str(_MAC_APP_PATH) if app_detected else "",
        user_data_path=user_data_path,
        reasons=reasons,
        suggestions=suggestions,
    )


def _fda_instructions() -> list[str]:
    return [
        "Open System Settings → Privacy & Security → Full Disk Access.",
        "Click the + button and add the host running this MCP server "
        "(typically the Terminal app, iTerm, Claude Desktop, or VS Code).",
        "Restart that host completely so the new permission takes effect.",
        "Re-run `inspect_local_jw_library_tool(force=True)`.",
    ]


def check_macos_full_disk_access() -> dict[str, object]:
    """Test whether this process can read the JW Library sandbox container.

    Returns a small dict:

      - `readable`: True if scanning the container succeeded.
      - `path`: container path tested.
      - `error`: error message when blocked (PermissionError vs missing).

    This probe is cheap (one `os.scandir`) and does not modify anything.
    """
    out: dict[str, object] = {
        "path": str(_MAC_CONTAINER),
        "readable": False,
        "error": "",
    }
    if not _MAC_CONTAINER.exists():
        out["error"] = "container path does not exist"
        return out
    try:
        with os.scandir(_MAC_CONTAINER) as it:
            for _ in it:
                break
        out["readable"] = True
    except PermissionError as e:
        out["error"] = f"PermissionError: {e}"
    except OSError as e:
        out["error"] = f"OSError: {e}"
    return out


def _find_userdata_in_container(container: Path) -> Path | None:
    """Locate `userData.db` somewhere under the sandbox container.

    Real-world locations seen so far:
        Data/Library/Application Support/userData.db
        Data/Documents/userData.db
    We probe the well-known ones first and fall back to a shallow glob.
    """
    candidates = [
        container / "Data" / "Library" / "Application Support" / "userData.db",
        container / "Data" / "Documents" / "userData.db",
    ]
    for c in candidates:
        if c.is_file():
            return c
    # Defensive shallow scan (max depth 4) — the container is not huge.
    root = container / "Data"
    if root.is_dir():
        try:
            for path in root.rglob("userData.db"):
                if path.is_file():
                    return path
        except (PermissionError, OSError):
            return None
    return None


def read_macos_userdata():
    """Read the live macOS sandbox `userData.db` (requires Full Disk Access).

    The DB is copied to a temp file first so the running app's WAL writes
    can't interfere; the copy is parsed read-only with the standard backup
    parser and the temp file is deleted afterwards.

    Returns:
        `BackupContents`. Raises `MacOSFullDiskAccessError` when the
        container is not readable.
    """
    # Imported here to avoid pulling parser at module-import time.
    import shutil
    import tempfile

    from jw_core.parsers.jw_library_backup import (
        BackupManifest,
        parse_user_data_db,
    )

    fda = check_macos_full_disk_access()
    if not fda["readable"]:
        raise MacOSFullDiskAccessError(
            "Cannot read JW Library container without Full Disk Access. " + str(fda.get("error", ""))
        )
    src = _find_userdata_in_container(_MAC_CONTAINER)
    if src is None:
        raise MacOSFullDiskAccessError(
            "Container is readable but userData.db is missing. Run JW Library at least once."
        )
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    try:
        shutil.copy(src, tmp_path)
        manifest = BackupManifest(
            name="live-macos-container",
            database_name="userData.db",
            device_name="this Mac (Full Disk Access)",
        )
        return parse_user_data_db(tmp_path, manifest=manifest, source=str(src))
    finally:
        try:
            tmp_path.unlink()
        except OSError:
            pass


def _inspect_linux() -> LocalInspectionResult:
    return LocalInspectionResult(
        platform="linux",
        supported=False,
        opt_in=True,
        app_detected=False,
        reasons=[
            "JW Library has no native Linux build. Use a `.jwlibrary` backup exported from a supported device instead."
        ],
        suggestions=[
            "Export a backup from JW Library on Android/iOS/Windows, "
            "transfer the .jwlibrary file, and call "
            "`import_jw_library_backup`."
        ],
    )


# ── publications.db reader (Windows) ────────────────────────────────────


_PUBLICATION_COLUMNS = (
    "PublicationId",
    "KeySymbol",
    "Title",
    "ShortTitle",
    "PublicationType",
    "Year",
    "IssueTagNumber",
    "MepsLanguageIndex",
    "LastModified",
)


def _read_publications_db(path: Path) -> list[InstalledPublication]:
    """Read the Publication table from publications.db (read-only).

    Different JW Library builds expose slightly different schemas, so we
    PRAGMA the table first and project only the columns that actually
    exist on this install.
    """
    uri = f"file:{path}?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as conn:
        conn.row_factory = sqlite3.Row
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(Publication)")}
        cols_to_select = [c for c in _PUBLICATION_COLUMNS if c in cols]
        if "PublicationId" not in cols_to_select:
            return []
        sql = f"SELECT {', '.join(cols_to_select)} FROM Publication"
        try:
            rows = conn.execute(sql).fetchall()
        except sqlite3.DatabaseError as e:
            logger.warning("Publication query failed: %s", e)
            return []

    out: list[InstalledPublication] = []
    for r in rows:
        try:
            out.append(
                InstalledPublication(
                    publication_id=int(r["PublicationId"]),
                    key_symbol=_row_str(r, "KeySymbol"),
                    title=_row_str(r, "Title"),
                    short_title=_row_str(r, "ShortTitle"),
                    publication_type=_row_str(r, "PublicationType"),
                    year=_row_int(r, "Year"),
                    issue_tag_number=_row_int(r, "IssueTagNumber"),
                    meps_language=_row_int(r, "MepsLanguageIndex"),
                    last_modified=_row_str(r, "LastModified"),
                )
            )
        except (KeyError, ValueError):
            continue
    return out


def _row_int(row: sqlite3.Row, key: str) -> int | None:
    try:
        v = row[key]
    except (KeyError, IndexError):
        return None
    if v is None:
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _row_str(row: sqlite3.Row, key: str) -> str:
    try:
        v = row[key]
    except (KeyError, IndexError):
        return ""
    return "" if v is None else str(v)
