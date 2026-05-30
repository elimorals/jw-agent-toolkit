"""Shared Pydantic models."""

from __future__ import annotations

from pydantic import BaseModel, Field

from jw_core.languages import get_language


class Verse(BaseModel):
    """One Bible verse — clean text plus its position.

    `text` is stripped of pronunciation marks, inline cross-ref symbols (+),
    and footnote markers (*). The original leading verse number is removed.
    """

    book_num: int = Field(ge=1, le=66)
    chapter: int = Field(ge=1)
    verse: int = Field(ge=1)
    text: str
    language: str = "en"

    def wol_url(self, pub: str | None = None) -> str:
        """Build the wol.jw.org URL pointing at this exact verse anchor."""
        language = get_language(self.language)
        publication = pub or language.default_bible
        return (
            f"https://wol.jw.org/{language.iso}/wol/b/{language.wol_resource}/"
            f"{language.lp_tag}/{publication}/{self.book_num}/{self.chapter}"
            f"#study=discover&v={self.book_num}:{self.chapter}:{self.verse}"
        )


class StudyNote(BaseModel):
    """A study note from the NWT Study Edition (nwtsty).

    `verse` may be None when no matching strategy succeeds; in practice
    that's rare (<2% of notes) since the parser falls back to positional
    interpolation. Check `confidence` to know how the verse was assigned:

      - "headword": the headword tokens were found in the verse text
      - "positional": estimated from the note's DOM index (lower confidence)
      - "unmatched": no assignment possible (verse will be None)
    """

    book_num: int = Field(ge=1, le=66)
    chapter: int = Field(ge=1)
    verse: int | None = Field(default=None, ge=1)
    headword: str = Field(description="The phrase the note annotates, e.g. 'born again'")
    body: str = Field(description="Plain text of the commentary")
    inline_refs: list[str] = Field(
        default_factory=list,
        description="Cross-references mentioned inside the note text",
    )
    language: str = "en"
    confidence: str = Field(
        default="headword",
        description="How the verse was assigned: 'headword', 'positional', or 'unmatched'",
    )


class TopicCitation(BaseModel):
    """One citation under a topic index subheading.

    Two kinds:
      - 'bible': a Bible reference like "Genesis 1:1" or "1Ti 2:6" — these
        are rendered as `<a class="b">` in WOL, so we have a full URL.
      - 'publication': a JW publication abbreviation like "w88 6/1 18"
        (Watchtower June 1 1988 p18) or "ti 9" (Trinity brochure p9). These
        are plain text — turning them into URLs requires the publication
        catalog (Phase 5+).
    """

    text: str
    kind: str = Field(description="'bible' or 'publication'")
    url: str | None = Field(default=None, description="WOL URL when known")


class TopicSubheading(BaseModel):
    """A subheading inside a topic index page.

    The `is_top_level` flag distinguishes top-level subheadings
    (`<p class="su">`) from value entries (`<p class="sv">`) nested under
    them. Order is preserved across the list so the LLM can reconstruct
    the hierarchy if needed.
    """

    heading: str
    citations: list[TopicCitation] = Field(default_factory=list)
    is_top_level: bool = True


class TopicSubject(BaseModel):
    """A parsed topic / subject from the Watch Tower Publications Index."""

    docid: str = Field(description="WOL document id of the subject page")
    title: str
    see_also: list[str] = Field(default_factory=list)
    subheadings: list[TopicSubheading] = Field(default_factory=list)
    source_url: str = ""
    language: str = "en"
    style: str = Field(
        default="trinity",
        description=(
            "Layout style: 'trinity' (heading: cite; cite; ...) or "
            "'article_title' (one article-title anchor per paragraph)."
        ),
    )

    @property
    def total_citations(self) -> int:
        return sum(len(s.citations) for s in self.subheadings)


class EpubDocument(BaseModel):
    """One section/chapter of an EPUB publication."""

    id: str = Field(description="Spine item id (e.g. 'ch01').")
    title: str = Field(default="", description="Extracted from <title> or first heading.")
    href: str = Field(description="Internal path inside the EPUB (e.g. 'OEBPS/ch01.xhtml').")
    paragraphs: list[str] = Field(default_factory=list)
    spine_index: int = Field(default=0, description="0-based position in the spine.")


class Epub(BaseModel):
    """A parsed EPUB publication (the easy alternative to JWPUB)."""

    title: str = ""
    creator: str = ""
    language: str = ""
    publisher: str = ""
    identifier: str = ""
    documents: list[EpubDocument] = Field(default_factory=list)
    source_path: str = ""

    @property
    def document_count(self) -> int:
        return len(self.documents)

    @property
    def paragraph_count(self) -> int:
        return sum(len(d.paragraphs) for d in self.documents)


class JwpubDocument(BaseModel):
    """One section of a JWPUB publication.

    `text` is populated when the publication's Content blobs were
    successfully decrypted (Phase 5.5 — algorithm from
    `gokusander/jwpub-toolkit`). When the file uses an unknown
    encryption variant, the field is empty and `JwpubMetadata.
    decrypted_text_available` will be False.
    """

    document_id: int
    meps_document_id: int
    title: str = ""
    toc_title: str = ""
    chapter_number: int | None = None
    section_number: int = 0
    paragraph_count: int = 0
    first_page_number: int | None = None
    last_page_number: int | None = None
    content_length: int = Field(default=0, description="Decrypted text length, in bytes.")
    text: str = Field(default="", description="Decrypted XHTML content; empty if blocked.")
    paragraphs: list[str] = Field(
        default_factory=list,
        description="Extracted plain-text paragraphs from `text`.",
    )


class JwpubMetadata(BaseModel):
    """Metadata-only view of a JWPUB file.

    Text content is encrypted; we surface every field that's readable
    without decryption so the LLM still has a useful TOC + structure.
    """

    title: str = ""
    short_title: str = ""
    symbol: str = ""
    language_index: int = 0
    publication_type: str = ""
    year: int | None = None
    manifest_hash: str = ""
    schema_version: int = 0
    document_count: int = 0
    documents: list[JwpubDocument] = Field(default_factory=list)
    source_path: str = ""
    decrypted_text_available: bool = Field(
        default=False,
        description="True only when text content was successfully decrypted.",
    )


class CrossReference(BaseModel):
    """An inline cross-reference marker found inside a verse.

    The `href` points at the WOL cross-references panel
    (`/en/wol/bc/{resource}/{lp_tag}/{doc_id}/{group}/{index}`). Resolving
    that to the actual list of parallel scriptures requires a follow-up
    network call — see `WOLClient.get_cross_reference_panel`.
    """

    book_num: int = Field(ge=1, le=66)
    chapter: int = Field(ge=1)
    verse: int = Field(ge=1)
    href: str = Field(description="WOL relative URL for the cross-ref panel")
    marker: str = Field(default="+", description="Symbol used inline (usually '+')")
    language: str = "en"

    def full_url(self) -> str:
        """Return the absolute URL to the cross-ref panel."""
        if self.href.startswith("http"):
            return self.href
        return f"https://wol.jw.org{self.href}"


class BibleRef(BaseModel):
    """A parsed Bible reference."""

    book_num: int = Field(ge=1, le=66, description="Canonical book number (Gen=1, Rev=66)")
    book_canonical: str = Field(description="Canonical English book name")
    chapter: int = Field(ge=1)
    verse_start: int | None = Field(default=None, ge=1)
    verse_end: int | None = Field(default=None, ge=1)
    detected_language: str = Field(description="ISO code of language the parser detected")
    raw_match: str = Field(description="The substring that matched in the original input")

    @property
    def has_verse(self) -> bool:
        return self.verse_start is not None

    @property
    def verse_range(self) -> str:
        if self.verse_start is None:
            return ""
        if self.verse_end and self.verse_end != self.verse_start:
            return f"{self.verse_start}-{self.verse_end}"
        return str(self.verse_start)

    def display(self, lang: str | None = None) -> str:
        """Render as 'Book Chapter:Verse' for display.

        Uses canonical English name unless a different language is requested.
        """
        # For language-specific display, callers can look up book_num in BOOKS;
        # this default keeps the model dependency-light.
        name = self.book_canonical
        out = f"{name} {self.chapter}"
        if self.verse_start:
            out += f":{self.verse_range}"
        return out

    def wol_url(self, lang: str = "en", pub: str | None = None) -> str:
        """Build the canonical wol.jw.org URL for this reference.

        Pattern: https://wol.jw.org/{iso}/wol/b/{wol_resource}/{lp_tag}/{pub}/{book}/{chapter}

        `pub` defaults to the language's preferred Bible (nwtsty for English,
        nwt for Spanish/Portuguese). Override to target a specific edition.

        Verse anchor appended when verse_start is set.
        """
        language = get_language(lang)
        publication = pub or language.default_bible
        base = (
            f"https://wol.jw.org/{language.iso}/wol/b/{language.wol_resource}/"
            f"{language.lp_tag}/{publication}/{self.book_num}/{self.chapter}"
        )
        if self.verse_start is not None:
            base += (
                f"#study=discover&v={self.book_num}:"
                f"{self.chapter}:{self.verse_start}"
            )
        return base
