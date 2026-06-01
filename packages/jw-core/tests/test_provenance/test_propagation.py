"""Tests for stamp_citation / stamp_finding_text propagation helpers."""

from __future__ import annotations

from jw_agents.base import Citation, Finding
from jw_core.provenance.hashing import content_sha256
from jw_core.provenance.propagation import stamp_citation, stamp_finding_text


def test_stamp_citation_writes_four_keys() -> None:
    cit = Citation(url="https://wol.jw.org/x", title="t", kind="verse", metadata={})
    text = "Jehová amó tanto al mundo"

    stamped = stamp_citation(
        cit,
        text=text,
        published_date="2024-01-15",
        revision="rev. 2023",
    )

    assert stamped is cit
    assert cit.metadata["content_hash"] == content_sha256(text)
    assert cit.metadata["published_date"] == "2024-01-15"
    assert cit.metadata["revision"] == "rev. 2023"
    assert isinstance(cit.metadata["accessed_at"], str)
    assert cit.metadata["accessed_at"].endswith(("+00:00", "Z"))


def test_stamp_citation_is_idempotent_for_same_text() -> None:
    """Re-stamping with the same text → hash unchanged; accessed_at refreshes."""

    cit = Citation(url="https://wol.jw.org/x", metadata={})
    text = "same body"

    stamp_citation(cit, text=text)
    h1 = cit.metadata["content_hash"]
    a1 = cit.metadata["accessed_at"]

    import time

    time.sleep(0.001)
    stamp_citation(cit, text=text)
    h2 = cit.metadata["content_hash"]
    a2 = cit.metadata["accessed_at"]

    assert h1 == h2
    assert isinstance(a2, str)
    _ = a1


def test_stamp_citation_different_text_changes_hash() -> None:
    cit = Citation(url="https://wol.jw.org/x", metadata={})
    stamp_citation(cit, text="version 1")
    h1 = cit.metadata["content_hash"]
    stamp_citation(cit, text="version 2")
    h2 = cit.metadata["content_hash"]
    assert h1 != h2


def test_stamp_citation_preserves_unrelated_metadata() -> None:
    cit = Citation(url="https://wol.jw.org/x", metadata={"source": "wol", "lang": "es"})
    stamp_citation(cit, text="body")
    assert cit.metadata["source"] == "wol"
    assert cit.metadata["lang"] == "es"
    assert "content_hash" in cit.metadata


def test_stamp_citation_optional_fields_omitted_remain_absent() -> None:
    """Don't write keys for `published_date=None` / `revision=None`."""

    cit = Citation(url="https://wol.jw.org/x", metadata={})
    stamp_citation(cit, text="x")
    assert "published_date" not in cit.metadata
    assert "revision" not in cit.metadata


def test_stamp_finding_text_uses_excerpt_as_default_text() -> None:
    cit = Citation(url="https://wol.jw.org/x", metadata={})
    finding = Finding(summary="s", citation=cit, excerpt="the excerpt body")

    stamp_finding_text(finding)

    assert cit.metadata["content_hash"] == content_sha256("the excerpt body")


def test_stamp_finding_text_no_op_when_excerpt_empty() -> None:
    """Findings without text shouldn't lie about their provenance."""

    cit = Citation(url="https://wol.jw.org/x", metadata={})
    finding = Finding(summary="s", citation=cit, excerpt="")
    stamp_finding_text(finding)
    assert "content_hash" not in cit.metadata


def test_stamp_finding_text_passes_through_published_date_kwargs() -> None:
    """Caller can override the auto-detected fields when known."""

    cit = Citation(url="https://wol.jw.org/x", metadata={})
    finding = Finding(summary="s", citation=cit, excerpt="hello")

    stamp_finding_text(finding, published_date="2024-01-01", revision="rev. 2023")

    assert cit.metadata["published_date"] == "2024-01-01"
    assert cit.metadata["revision"] == "rev. 2023"


def test_verse_explainer_stamps_findings_through_excerpt() -> None:
    """End-to-end-ish: a finding emitted from an agent body has provenance."""

    cit = Citation(url="https://wol.jw.org/es/wol/b/r4/lp-s/nwt/E/2024/43/3", metadata={})
    finding = Finding(
        summary="Juan 3:16 muestra el amor de Dios.",
        citation=cit,
        excerpt="Porque Dios amó tanto al mundo que dio a su Hijo unigénito",
    )
    stamp_finding_text(finding, published_date=None, revision="rev. 2023")
    record = finding.citation.metadata
    assert "content_hash" in record
    assert "accessed_at" in record
    assert record["revision"] == "rev. 2023"
