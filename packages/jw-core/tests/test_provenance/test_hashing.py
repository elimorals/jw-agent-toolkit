"""Tests for canonicalize_text() and content_sha256().

Design pinned by the spec:
  - NFC unicode normalization
  - Collapse internal whitespace runs to a single space
  - Strip leading/trailing whitespace
  - PRESERVE capitalization (Jehová vs jehová is doctrinally meaningful)
  - Eliminate zero-width characters
"""

from __future__ import annotations

from jw_core.provenance.hashing import canonicalize_text, content_sha256


def test_canonicalize_strips_outer_whitespace() -> None:
    assert canonicalize_text("   hello   ") == "hello"


def test_canonicalize_collapses_internal_whitespace_runs() -> None:
    assert canonicalize_text("hello\t  world\n\nfriend") == "hello world friend"


def test_canonicalize_preserves_capitalization() -> None:
    """Spec decision: do NOT lowercase. `Jehová` and `jehová` hash differently."""

    a = canonicalize_text("Jehová es Dios")
    b = canonicalize_text("jehová es dios")
    assert a != b
    assert "Jehová" in a
    assert "jehová" in b


def test_canonicalize_nfc_normalizes_decomposed_form() -> None:
    """`é` composed (U+00E9) vs decomposed (e + U+0301) must canonicalize the same."""

    composed = "Jehová"        # á as a single codepoint
    decomposed = "Jehová"     # a + combining acute
    assert canonicalize_text(composed) == canonicalize_text(decomposed)


def test_canonicalize_removes_zero_width_chars() -> None:
    """ZWSP / ZWJ / ZWNJ / BOM are stripped."""

    text = "Je​ho‌v‍﻿á"
    assert canonicalize_text(text) == "Jehová"


def test_canonicalize_is_idempotent() -> None:
    """Running it twice yields the same string."""

    a = canonicalize_text("  hello   world  ")
    assert canonicalize_text(a) == a


def test_content_sha256_stable_across_cosmetic_edits() -> None:
    """Whitespace, NFC, ZWSP must not change the hash."""

    base = "Jehová amó tanto al mundo que dio a su Hijo"
    cosmetic = "  Jehová   amó tanto al mundo\nque dio a su Hijo  "
    assert content_sha256(base) == content_sha256(cosmetic)


def test_content_sha256_changes_when_real_word_differs() -> None:
    base = "Jehová amó tanto al mundo que dio a su Hijo"
    edited = "Jehová amó tanto al universo que dio a su Hijo"
    assert content_sha256(base) != content_sha256(edited)


def test_content_sha256_changes_when_capitalization_differs() -> None:
    """Spec decision propagated: capitalization is meaningful."""

    a = content_sha256("Jehová es Dios")
    b = content_sha256("jehová es Dios")
    assert a != b


def test_content_sha256_returns_hex_string() -> None:
    """Returns lowercase hex (sha256 → 64 chars)."""

    h = content_sha256("hello")
    assert len(h) == 64
    assert all(c in "0123456789abcdef" for c in h)


def test_canonicalize_empty_input() -> None:
    assert canonicalize_text("") == ""
    assert canonicalize_text("   \n   ") == ""


def test_content_sha256_empty_is_stable() -> None:
    """An empty canonicalized string still hashes deterministically."""

    a = content_sha256("")
    b = content_sha256("   ")
    assert a == b
