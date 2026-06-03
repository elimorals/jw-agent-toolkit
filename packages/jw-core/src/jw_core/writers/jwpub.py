"""JWPUB writer — inverse of `jw_core.parsers.jwpub` (Phase 5.5).

Build a `.jwpub` from a set of HTML documents and optional media files. The
output is a fully-formed JW Library publication: outer ZIP with `manifest.json`
+ `contents` (inner ZIP) containing `{symbol}.db` (encrypted SQLite) plus
media assets.

Algorithm ported from `darioragusa/html2jwpub` (Swift, MIT). The SQLite
schema in `data/jwpub_schema.sql` is the same `InitStructure` from that
project's `dbQuery.swift`.

Typical use:

    from jw_core.writers.jwpub import JwpubBuilder

    builder = JwpubBuilder(
        symbol="ex22",
        title="Example Publication",
        year=2022,
        meps_language_index=0,  # 0 = English
    )
    builder.add_document(title="Chapter 1", content="<html>...</html>")
    builder.add_document(title="Chapter 2", content="<html>...</html>")
    out_path = builder.build(Path("/tmp/ex22.jwpub"))

The resulting `.jwpub` can be opened with `parsers.jwpub.parse_jwpub()`
(round-trip) and is structurally consumable by JW Library nativo.
"""

from __future__ import annotations

import hashlib
import json
import mimetypes
import sqlite3
import zipfile
from dataclasses import dataclass, field
from datetime import UTC, datetime
from importlib import resources
from io import BytesIO
from pathlib import Path

from jw_core.jwpub_crypto import compute_key_iv, encrypt_blob


@dataclass
class _PendingDocument:
    title: str
    content: str  # full XHTML / HTML the user wants encrypted
    media_paths: list[Path] = field(default_factory=list)


@dataclass
class _PendingMedia:
    path: Path
    mime_type: str


class JwpubBuilder:
    """Build a `.jwpub` from documents + media.

    Mirrors the Swift `JwpubCreator` API but with idiomatic Python: documents
    are buffered in memory until `build()` is called, which materializes the
    SQLite, the inner ZIP, the manifest, and the outer ZIP in one shot.
    """

    def __init__(
        self,
        *,
        symbol: str,
        title: str,
        year: int,
        meps_language_index: int,
        issue_tag_number: int = 0,
        publication_type: str = "Manual/Guidelines",
        category: str = "manual",
    ) -> None:
        self.symbol = symbol
        self.title = title
        self.year = year
        self.meps_language_index = meps_language_index
        self.issue_tag_number = issue_tag_number
        self.publication_type = publication_type
        self.category = category
        self._documents: list[_PendingDocument] = []
        self._media: dict[str, _PendingMedia] = {}  # keyed by filename

    # ── Public API ──────────────────────────────────────────────────

    def add_document(self, *, title: str, content: str, media: list[Path] | None = None) -> int:
        """Add a document. Returns its 0-based index."""
        doc = _PendingDocument(title=title, content=content, media_paths=list(media or []))
        self._documents.append(doc)
        # Register media so it gets bundled and the document↔media link is recorded.
        for path in doc.media_paths:
            self._register_media(path)
        return len(self._documents) - 1

    def add_media(self, path: Path, mime_type: str | None = None) -> None:
        """Pre-register a media asset (bundled but not linked to a specific document)."""
        self._register_media(path, mime_type)

    def build(self, out_path: Path) -> Path:
        """Materialize the `.jwpub` at `out_path`. Returns the path written."""
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        db_bytes = self._build_sqlite()
        inner_zip_bytes = self._build_inner_zip(db_bytes)
        manifest_bytes = self._build_manifest(db_bytes, inner_zip_bytes)

        with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as outer:
            outer.writestr("manifest.json", manifest_bytes)
            outer.writestr("contents", inner_zip_bytes)
        return out_path

    # ── Internals ───────────────────────────────────────────────────

    def _register_media(self, path: Path, mime_type: str | None = None) -> None:
        name = path.name
        if name in self._media:
            return
        if mime_type is None:
            mime_type, _ = mimetypes.guess_type(name)
            mime_type = mime_type or "application/octet-stream"
        self._media[name] = _PendingMedia(path=path, mime_type=mime_type)

    def _build_sqlite(self) -> bytes:
        """Build the SQLite database and return its binary bytes.

        We populate :memory: then `backup()` to a tmpfile so we can read the
        on-disk SQLite format JW Library expects (iterdump would give SQL text).
        """
        import tempfile

        schema_sql = resources.files("jw_core.data").joinpath("jwpub_schema.sql").read_text(encoding="utf-8")
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            tmp_path = Path(tmp.name)
        try:
            source = sqlite3.connect(":memory:")
            target = sqlite3.connect(tmp_path)
            try:
                source.executescript(schema_sql)
                self._populate_publication_tables(source)
                self._populate_documents(source)
                self._populate_media(source)
                source.commit()
                source.backup(target)
            finally:
                source.close()
                target.close()
            return tmp_path.read_bytes()
        finally:
            tmp_path.unlink(missing_ok=True)

    def _populate_publication_tables(self, conn: sqlite3.Connection) -> None:
        # android_metadata
        conn.execute("INSERT INTO android_metadata VALUES ('en_US');")

        # Publication + RefPublication — same shape, different PK column name.
        params = (
            self.title,
            self.symbol,
            self.year,
            self.title,
            self.title,
            self.title,
            self.title,
            self.symbol,
            self.symbol,
            self.symbol,
            self.symbol,
            self.symbol,
            str(self.issue_tag_number),
            self.year,
            self.meps_language_index,
            self.publication_type,
            self.category,
        )
        for table, pk_col in (("Publication", "PublicationId"), ("RefPublication", "RefPublicationId")):
            conn.execute(
                f"INSERT INTO {table} ({pk_col}, VersionNumber, Type, Title, RootSymbol, RootYear, "
                "RootMepsLanguageIndex, ShortTitle, DisplayTitle, ReferenceTitle, "
                "UndatedReferenceTitle, Symbol, UndatedSymbol, UniqueSymbol, EnglishSymbol, "
                "UniqueEnglishSymbol, IssueTagNumber, IssueNumber, Year, VolumeNumber, "
                "MepsLanguageIndex, PublicationType, PublicationCategorySymbol, "
                "BibleVersionForCitations, HasPublicationChapterNumbers, "
                "HasPublicationSectionNumbers, MepsBuildNumber) "
                "VALUES (1, 8, 1, ?, ?, ?, 0, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, 0, ?, ?, ?, "
                "'NWTR', 1, 1, 12345);",
                params,
            )

        # PublicationAttribute / Category / View / ViewSchema / Year
        conn.execute("INSERT INTO PublicationAttribute (PublicationAttributeId, PublicationId, Attribute) VALUES (1,1,'PERSONAL');")
        conn.execute(
            "INSERT INTO PublicationCategory (PublicationCategoryId, PublicationId, Category) VALUES (1, 1, ?);",
            (self.category,),
        )
        conn.execute("INSERT INTO PublicationView (PublicationViewId, Name, Symbol) VALUES (1,'JW App Publication','jwpub');")
        conn.execute("INSERT INTO PublicationViewSchema (PublicationViewSchemaId, SchemaType, DataType) VALUES (1,0,'name');")
        conn.execute(
            "INSERT INTO PublicationYear (PublicationYearId, PublicationId, Year) VALUES (1, 1, ?);",
            (self.year,),
        )

        # Root PublicationViewItem (id=1) + its name field
        conn.execute(
            "INSERT INTO PublicationViewItem (PublicationViewItemId, PublicationViewId, "
            "ParentPublicationViewItemId, Title, SchemaType, ChildTemplateSchemaType, "
            "DefaultDocumentId) VALUES (1, 1, NULL, ?, 0, 0, NULL);",
            (self.title,),
        )
        conn.execute(
            "INSERT INTO PublicationViewItemField (PublicationViewItemFieldId, "
            "PublicationViewItemId, Value, Type) VALUES (1, 1, ?, 'name');",
            (self.title,),
        )

    def _populate_documents(self, conn: sqlite3.Connection) -> None:
        key, iv = compute_key_iv(self.meps_language_index, self.symbol, self.year, self.issue_tag_number)
        for idx, doc in enumerate(self._documents):
            doc_id = idx
            meps_doc_id = 12000000 + idx + 1
            view_item_id = idx + 2  # root is 1
            content_blob = encrypt_blob(doc.content, key, iv)
            conn.execute(
                "INSERT INTO Document (DocumentId, PublicationId, MepsDocumentId, "
                "MepsLanguageIndex, Class, Type, SectionNumber, Title, TocTitle, Content, "
                "ParagraphCount, HasMediaLinks, HasLinks, FirstPageNumber, LastPageNumber, "
                "ContentLength) VALUES (?, 1, ?, ?, '13', 0, 1, ?, ?, ?, 254, 0, 0, 1, 1, ?);",
                (doc_id, meps_doc_id, self.meps_language_index, doc.title, doc.title, content_blob, len(doc.content)),
            )
            # TextUnit
            conn.execute(
                "INSERT INTO TextUnit (TextUnitId, Type, Id) VALUES (?, 'Document', ?);",
                (doc_id + 1, doc_id),
            )
            # PublicationViewItem (child of root)
            conn.execute(
                "INSERT INTO PublicationViewItem (PublicationViewItemId, PublicationViewId, "
                "ParentPublicationViewItemId, Title, SchemaType, ChildTemplateSchemaType, "
                "DefaultDocumentId) VALUES (?, 1, 1, ?, 0, 0, ?);",
                (view_item_id, doc.title, doc_id),
            )
            # PublicationViewItemDocument
            conn.execute(
                "INSERT INTO PublicationViewItemDocument (PublicationViewItemDocumentId, "
                "PublicationViewItemId, DocumentId) VALUES (?, ?, ?);",
                (doc_id + 1, view_item_id, doc_id),
            )
            # PublicationViewItemField (per-document name)
            conn.execute(
                "INSERT INTO PublicationViewItemField (PublicationViewItemFieldId, "
                "PublicationViewItemId, Value, Type) VALUES (?, ?, ?, 'name');",
                (view_item_id, view_item_id, doc.title),
            )

    def _populate_media(self, conn: sqlite3.Connection) -> None:
        media_id_by_name: dict[str, int] = {}
        for mm_id, (name, media) in enumerate(self._media.items()):
            conn.execute(
                "INSERT INTO Multimedia (MultimediaId, DataType, MajorType, MinorType, "
                "MimeType, Caption, FilePath, CategoryType) VALUES (?, 0, 1, 1, ?, ?, ?, -1);",
                (mm_id, media.mime_type, name, name),
            )
            media_id_by_name[name] = mm_id
        # Link media → documents
        for doc_id, doc in enumerate(self._documents):
            for path in doc.media_paths:
                mm_id = media_id_by_name.get(path.name)
                if mm_id is None:
                    continue
                conn.execute(
                    "INSERT INTO DocumentMultimedia (DocumentId, MultimediaId) VALUES (?, ?);",
                    (doc_id, mm_id),
                )

    def _build_inner_zip(self, db_bytes: bytes) -> bytes:
        """Inner ZIP: `{symbol}.db` + media assets."""
        buf = BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(f"{self.symbol}.db", db_bytes)
            for name, media in self._media.items():
                zf.writestr(name, media.path.read_bytes())
        return buf.getvalue()

    def _build_manifest(self, db_bytes: bytes, inner_zip_bytes: bytes) -> bytes:
        """JSON manifest with SHA-1 of the .db, SHA-256 of the contents ZIP, sizes, timestamps."""
        db_hash_sha1 = hashlib.sha1(db_bytes).hexdigest()  # noqa: S324 - format dictated by JW Library
        contents_hash_sha256 = hashlib.sha256(inner_zip_bytes).hexdigest()
        timestamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

        manifest = {
            "name": f"{self.symbol}.jwpub",
            "hash": contents_hash_sha256,
            "timestamp": timestamp,
            "version": 1,
            "expandedSize": len(inner_zip_bytes),
            "contentFormat": "z-a",
            "htmlValidated": False,
            "mepsPlatformVersion": 2.1,
            "mepsBuildNumber": 12345,
            "publication": {
                "fileName": f"{self.symbol}.db",
                "type": 1,
                "title": self.title,
                "shortTitle": self.title,
                "displayTitle": self.title,
                "referenceTitle": "",
                "undatedReferenceTitle": "",
                "titleRich": "",
                "displayTitleRich": "",
                "referenceTitleRich": "",
                "undatedReferenceTitleRich": "",
                "symbol": self.symbol,
                "uniqueEnglishSymbol": self.symbol,
                "uniqueSymbol": self.symbol,
                "englishSymbol": self.symbol,
                "language": self.meps_language_index,
                "hash": db_hash_sha1,
                "timestamp": timestamp,
                "minPlatformVersion": 1,
                "schemaVersion": 8,
                "year": self.year,
                "issueId": self.issue_tag_number,
                "issueNumber": 0,
                "issueTagNumber": self.issue_tag_number,
                "publicationType": self.publication_type,
                "rootSymbol": self.symbol,
                "rootYear": self.year,
                "rootLanguage": 0,
                "images": [],
                "categories": [self.category],
                "attributes": [],
            },
        }
        return json.dumps(manifest, indent=2).encode("utf-8")
