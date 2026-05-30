"""Bidirectional sync between an Obsidian vault and the toolkit (Phase 20).

Two directions:

  - **vault → toolkit**: walk a vault, parse every `.md` (with YAML
    frontmatter), produce one `Chunk` per note for the RAG store. Each
    chunk carries `path`, `title`, `tags`, `mtime`, `frontmatter` so the
    agent can later filter ("notes tagged #ministry", "notes about
    Romans"). Idempotent — re-running with no changes is a no-op via
    file mtime + content hash on a sidecar state file.
  - **toolkit → vault**: write a `.md` per `UserNote` from a
    `.jwlibrary` backup, with frontmatter (`book`, `chapter`, `tags`,
    `last_modified`) + body. Useful to fold your JW Library notes into
    your second-brain alongside your Obsidian writing.

Both directions are read-only on the *other* side: we never call the
JW Library cloud sync; we never modify the user's existing `.md` files
without explicit overwrite.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Iterator

from jw_core.integrations.markdown import (
    NameLength,
    QuoteTemplate,
    render_markdown_link,
    render_verse_block,
)
from jw_core.models import BibleRef
from jw_core.parsers.jw_library_backup import (
    BackupContents,
    UserNote,
    parse_jw_library_backup,
)

if TYPE_CHECKING:
    from jw_rag.store import VectorStore

logger = logging.getLogger(__name__)

__all__ = [
    "ExportReport",
    "IndexReport",
    "MarkdownNote",
    "VaultSyncState",
    "VaultSyncStateStore",
    "export_backup_to_vault",
    "index_vault_to_rag",
    "iter_vault_notes",
    "parse_markdown_note",
]


# ── Markdown note model ───────────────────────────────────────────────


_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", flags=re.DOTALL)


@dataclass
class MarkdownNote:
    """One `.md` file parsed into title + frontmatter + body."""

    path: str
    title: str
    frontmatter: dict
    body: str
    mtime: float
    content_hash: str

    @property
    def tags(self) -> list[str]:
        tags = self.frontmatter.get("tags")
        if isinstance(tags, list):
            return [str(t) for t in tags]
        if isinstance(tags, str):
            return [t.strip() for t in tags.split(",") if t.strip()]
        return []


def parse_markdown_note(path: Path | str) -> MarkdownNote:
    """Read a `.md` and split frontmatter / body."""
    p = Path(path).expanduser()
    text = p.read_text(encoding="utf-8")
    fm: dict = {}
    body = text
    m = _FRONTMATTER_RE.match(text)
    if m:
        fm_raw = m.group(1)
        body = text[m.end() :]
        fm = _parse_simple_yaml(fm_raw)
    title = _derive_title(body, p)
    return MarkdownNote(
        path=str(p),
        title=title,
        frontmatter=fm,
        body=body.strip(),
        mtime=p.stat().st_mtime,
        content_hash=_hash(text),
    )


def _derive_title(body: str, path: Path) -> str:
    for line in body.splitlines():
        line = line.strip()
        if line.startswith("# "):
            return line[2:].strip()
    return path.stem


_YAML_KV_RE = re.compile(r"^([A-Za-z0-9_\-\s]+):\s*(.*?)\s*$")


def _parse_simple_yaml(text: str) -> dict:
    """Tiny YAML parser tailored to frontmatter shapes Obsidian users write.

    Supports: scalars, quoted strings, simple lists (inline `[a, b]` or
    block `- item` indented two spaces). Anything trickier is left as
    string. Comments (`#`) ignored.
    """
    out: dict = {}
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        raw = lines[i]
        i += 1
        stripped = raw.split("#", 1)[0].rstrip()
        if not stripped.strip():
            continue
        if not raw.startswith(" "):
            m = _YAML_KV_RE.match(stripped)
            if not m:
                continue
            key, val = m.group(1).strip(), m.group(2).strip()
            if not val:
                # Block list follows.
                items: list[str] = []
                while i < len(lines) and lines[i].startswith("  "):
                    item = lines[i].strip()
                    if item.startswith("- "):
                        items.append(item[2:].strip().strip("\"'"))
                    i += 1
                out[key] = items
                continue
            out[key] = _coerce_yaml_scalar(val)
    return out


def _coerce_yaml_scalar(value: str) -> object:
    v = value.strip()
    if v.startswith("[") and v.endswith("]"):
        inner = v[1:-1].strip()
        if not inner:
            return []
        return [p.strip().strip("\"'") for p in _split_inline_list(inner)]
    if v.startswith('"') and v.endswith('"') and len(v) >= 2:
        return v[1:-1]
    if v.startswith("'") and v.endswith("'") and len(v) >= 2:
        return v[1:-1]
    low = v.lower()
    if low in ("true", "yes"):
        return True
    if low in ("false", "no"):
        return False
    if v.lstrip("-").isdigit():
        try:
            return int(v)
        except ValueError:
            pass
    return v


def _split_inline_list(inner: str) -> list[str]:
    parts: list[str] = []
    depth = 0
    cur: list[str] = []
    for ch in inner:
        if ch in "[(":
            depth += 1
        elif ch in "])":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
    if cur:
        parts.append("".join(cur))
    return parts


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:32]


# ── State sidecar ─────────────────────────────────────────────────────


@dataclass
class VaultSyncEntry:
    path: str
    mtime: float
    content_hash: str
    source_id: str


@dataclass
class VaultSyncState:
    vault_root: str
    last_synced_at: str = ""
    notes: dict[str, VaultSyncEntry] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "vault_root": self.vault_root,
            "last_synced_at": self.last_synced_at,
            "notes": {k: v.__dict__ for k, v in self.notes.items()},
        }

    @classmethod
    def from_dict(cls, data: dict) -> VaultSyncState:
        return cls(
            vault_root=str(data.get("vault_root", "")),
            last_synced_at=str(data.get("last_synced_at", "")),
            notes={
                k: VaultSyncEntry(**v)
                for k, v in (data.get("notes") or {}).items()
            },
        )


class VaultSyncStateStore:
    def __init__(self, path: Path | str) -> None:
        self.path = Path(path).expanduser()

    def load(self, vault_root: str) -> VaultSyncState:
        if not self.path.exists():
            return VaultSyncState(vault_root=vault_root)
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return VaultSyncState(vault_root=vault_root)
        entry = data.get(vault_root)
        if not isinstance(entry, dict):
            return VaultSyncState(vault_root=vault_root)
        return VaultSyncState.from_dict(entry)

    def save(self, state: VaultSyncState) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            data = (
                json.loads(self.path.read_text(encoding="utf-8"))
                if self.path.exists()
                else {}
            )
        except (json.JSONDecodeError, OSError):
            data = {}
        if not isinstance(data, dict):
            data = {}
        data[state.vault_root] = state.to_dict()
        self.path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )


# ── Vault → RAG ───────────────────────────────────────────────────────


@dataclass
class IndexReport:
    vault_root: str
    indexed: int = 0
    updated: int = 0
    deleted: int = 0
    unchanged: int = 0
    skipped: int = 0
    chunks_added: int = 0
    chunks_removed: int = 0
    state_path: str = ""

    def to_dict(self) -> dict:
        return self.__dict__.copy()


def iter_vault_notes(
    vault_root: Path | str,
    *,
    glob: str = "**/*.md",
    ignore_dirs: tuple[str, ...] = (".obsidian", ".trash", ".git", "node_modules"),
) -> Iterator[Path]:
    """Yield `.md` paths under `vault_root`, skipping Obsidian metadata."""
    root = Path(vault_root).expanduser()
    if not root.is_dir():
        raise FileNotFoundError(f"Vault not found: {root}")
    for path in root.glob(glob):
        if not path.is_file():
            continue
        rel_parts = path.relative_to(root).parts
        if any(part in ignore_dirs for part in rel_parts):
            continue
        yield path


def _vault_note_source_id(rel_path: str) -> str:
    return f"vault:{rel_path}"


def index_vault_to_rag(
    vault_root: Path | str,
    store: VectorStore,
    *,
    state_path: Path | str | None = None,
    glob: str = "**/*.md",
    require_tag: str | None = None,
    ignore_dirs: tuple[str, ...] = (".obsidian", ".trash", ".git", "node_modules"),
    min_chars: int = 16,
) -> IndexReport:
    """Walk a vault and incrementally sync `.md` notes into a `VectorStore`.

    Behavior:

      - First call: indexes every note matching `glob` (and `require_tag`).
      - Subsequent calls: re-uses the sidecar state to skip unchanged
        notes (mtime + content_hash). Modified notes get their old chunk
        evicted and re-indexed; deleted files are evicted entirely.
      - Notes shorter than `min_chars` (after frontmatter) are skipped
        but tracked in state so they don't re-trigger.

    Args:
        vault_root: Root of the Obsidian vault.
        store: Open `VectorStore`. Must support `delete_by_source_ids`.
        state_path: Sidecar path. Defaults to `<store.path>/vault_sync.json`.
        glob: File pattern. Default: `**/*.md`.
        require_tag: Only index notes whose frontmatter `tags` list
            contains this value.
        ignore_dirs: Directory names to skip recursively.
        min_chars: Drop notes with bodies shorter than this.
    """
    from jw_rag.chunker import chunk_paragraphs

    root = Path(vault_root).expanduser().resolve()
    vault_root_str = str(root)
    state_file = (
        Path(state_path)
        if state_path
        else Path(store.path) / "vault_sync.json"
    )
    state_store = VaultSyncStateStore(state_file)
    state = state_store.load(vault_root_str)

    report = IndexReport(
        vault_root=vault_root_str,
        state_path=str(state_file),
    )

    seen_paths: set[str] = set()
    for path in iter_vault_notes(root, glob=glob, ignore_dirs=ignore_dirs):
        try:
            note = parse_markdown_note(path)
        except (OSError, UnicodeDecodeError) as e:
            logger.warning("Skipping %s: %s", path, e)
            report.skipped += 1
            continue
        rel = str(path.relative_to(root))
        seen_paths.add(rel)
        if require_tag and require_tag not in note.tags:
            report.skipped += 1
            continue
        if len(note.body) < min_chars:
            state.notes[rel] = VaultSyncEntry(
                path=rel,
                mtime=note.mtime,
                content_hash=note.content_hash,
                source_id=_vault_note_source_id(rel),
            )
            report.skipped += 1
            continue

        prev = state.notes.get(rel)
        source_id = _vault_note_source_id(rel)
        if prev is not None and prev.content_hash == note.content_hash:
            report.unchanged += 1
            continue

        # New or modified.
        if prev is not None:
            removed = store.delete_by_source_ids([source_id])
            report.chunks_removed += removed
            report.updated += 1
        else:
            report.indexed += 1

        chunks = chunk_paragraphs(
            [note.body],
            source_id=source_id,
            metadata={
                "kind": "vault_note",
                "path": rel,
                "title": note.title,
                "tags": note.tags,
                "frontmatter": note.frontmatter,
                "vault_root": vault_root_str,
                "mtime": note.mtime,
            },
        )
        store.add(chunks)
        report.chunks_added += len(chunks)
        state.notes[rel] = VaultSyncEntry(
            path=rel,
            mtime=note.mtime,
            content_hash=note.content_hash,
            source_id=source_id,
        )

    # Evict notes deleted from disk.
    to_evict: list[str] = []
    for rel, entry in list(state.notes.items()):
        if rel not in seen_paths:
            to_evict.append(entry.source_id)
            del state.notes[rel]
            report.deleted += 1
    if to_evict:
        report.chunks_removed += store.delete_by_source_ids(to_evict)

    state.last_synced_at = datetime.now(timezone.utc).isoformat()
    state_store.save(state)
    return report


# ── Backup → Vault ────────────────────────────────────────────────────


@dataclass
class ExportReport:
    backup_path: str
    vault_dir: str
    files_written: int = 0
    files_skipped: int = 0

    def to_dict(self) -> dict:
        return self.__dict__.copy()


def export_backup_to_vault(
    backup_path: Path | str,
    vault_dir: Path | str,
    *,
    template: QuoteTemplate = "callout",
    length: NameLength = "medium",
    language: str = "en",
    subdir: str = "JW Library",
    overwrite: bool = False,
) -> ExportReport:
    """Write one `.md` per `UserNote` from a `.jwlibrary` backup.

    Files are placed under `<vault_dir>/<subdir>/<book>/<chapter>/<note>.md`
    when the note targets a Bible verse, or under
    `<vault_dir>/<subdir>/publications/<key_symbol>/<note>.md` for
    publication-anchored notes. Frontmatter records book, chapter,
    tags, created/last_modified so Obsidian dataview queries Just Work.

    Args:
        backup_path: Path to the `.jwlibrary` archive.
        vault_dir: Root of the target Obsidian vault.
        template: Quote template used when rendering the linked verse.
        length: Book-name length for the verse heading.
        language: Language to render labels in.
        subdir: Subdirectory under `vault_dir` to keep exported notes.
        overwrite: Replace existing files. Default False = skip them.
    """
    backup = parse_jw_library_backup(backup_path)
    root = Path(vault_dir).expanduser().resolve()
    target_root = root / subdir
    report = ExportReport(backup_path=str(backup_path), vault_dir=str(root))

    for note in backup.notes:
        rel_subdir, file_stem = _note_target_path(note)
        target_dir = target_root / rel_subdir
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / f"{file_stem}.md"
        if target.exists() and not overwrite:
            report.files_skipped += 1
            continue
        target.write_text(
            _render_note_md(backup, note, template=template, length=length, language=language),
            encoding="utf-8",
        )
        report.files_written += 1
    return report


def _note_target_path(note: UserNote) -> tuple[str, str]:
    safe_title = _slugify(note.title or note.guid or f"note-{note.note_id}")
    loc = note.location
    if loc is not None and loc.is_bible and loc.book_number is not None:
        return (
            str(Path("bible") / f"{loc.book_number:02d}" / f"chapter-{loc.chapter_number:03d}"),
            f"{loc.book_number:02d}{(loc.chapter_number or 0):03d}-{safe_title}",
        )
    if loc is not None and loc.key_symbol:
        return (
            str(Path("publications") / _slugify(loc.key_symbol)),
            f"{safe_title}",
        )
    return ("misc", safe_title)


_SLUG_RE = re.compile(r"[^A-Za-z0-9._-]+")


def _slugify(text: str) -> str:
    slug = _SLUG_RE.sub("-", text).strip("-")
    return (slug or "note")[:80]


def _render_note_md(
    backup: BackupContents,
    note: UserNote,
    *,
    template: QuoteTemplate,
    length: NameLength,
    language: str,
) -> str:
    loc = note.location
    frontmatter_lines = [
        "---",
        f'title: "{(note.title or "").replace(chr(34), chr(39))}"',
        f'note_id: {note.note_id}',
        f'guid: "{note.guid}"',
        f'source_backup: "{backup.manifest.name or backup.source_path}"',
    ]
    if loc is not None:
        if loc.book_number is not None:
            frontmatter_lines.append(f"book: {loc.book_number}")
        if loc.chapter_number is not None:
            frontmatter_lines.append(f"chapter: {loc.chapter_number}")
        if loc.key_symbol:
            frontmatter_lines.append(f'key_symbol: "{loc.key_symbol}"')
        if loc.document_id is not None:
            frontmatter_lines.append(f"document_id: {loc.document_id}")
    if note.created:
        frontmatter_lines.append(f'created: "{note.created}"')
    if note.last_modified:
        frontmatter_lines.append(f'last_modified: "{note.last_modified}"')
    if note.tags:
        frontmatter_lines.append("tags:")
        for t in note.tags:
            frontmatter_lines.append(f"  - {t}")
    frontmatter_lines.append("---")
    fm = "\n".join(frontmatter_lines)

    heading = f"# {note.title}" if note.title else f"# Note {note.note_id}"
    body_parts: list[str] = [fm, "", heading, ""]

    if loc is not None and loc.is_bible and loc.book_number and loc.chapter_number:
        # Anchor with a deep link callout so Obsidian users can click into JW Library.
        ref = BibleRef(
            book_num=loc.book_number,
            book_canonical="",
            chapter=loc.chapter_number,
            verse_start=None,
            verse_end=None,
            detected_language=language,
            raw_match="",
        )
        body_parts.append(render_verse_block(ref, "", template=template, length=length, language=language))
        body_parts.append("")
    elif loc is not None and loc.key_symbol and loc.document_id is not None:
        from jw_core.integrations.jw_library import build_publication_url

        url = build_publication_url(loc.document_id, wtlocale=language)
        body_parts.append(f"[{loc.key_symbol} #{loc.document_id}]({url})")
        body_parts.append("")

    if note.content:
        body_parts.append(note.content.strip())
    return "\n".join(body_parts) + "\n"
