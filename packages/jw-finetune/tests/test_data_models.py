"""Tests for ParagraphRecord and SourceSpec data models."""

from __future__ import annotations

import dataclasses

import pytest
from jw_finetune.data.models import ParagraphRecord, SourceSpec


def test_paragraph_record_minimal() -> None:
    p = ParagraphRecord(
        text="In the beginning God created the heavens and the earth.",
        pub_code="nwt",
        language="en",
        kind="bible",
        source_path="wol:gen:1",
    )
    assert p.text.startswith("In the beginning")
    assert p.language == "en"
    assert p.doc_id == ""
    assert p.paragraph_pid is None
    assert p.extra == {}


def test_paragraph_record_immutable() -> None:
    p = ParagraphRecord(
        text="x",
        pub_code="w24",
        language="es",
        kind="watchtower",
        source_path="x",
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        p.text = "y"  # type: ignore[misc]


def test_paragraph_record_full_fields() -> None:
    p = ParagraphRecord(
        text="El Reino de Dios es un gobierno celestial.",
        pub_code="w24",
        language="es",
        kind="watchtower",
        source_path="/path/to/file.jwpub",
        doc_id="123",
        section_ref="w24 12 p.7",
        paragraph_pid=7,
        spine_index=2,
        extra={"creator": "WBTS"},
    )
    assert p.section_ref == "w24 12 p.7"
    assert p.paragraph_pid == 7
    assert p.extra["creator"] == "WBTS"


def test_source_spec_jwpub() -> None:
    s = SourceSpec(kind="jwpub", path="./pubs/w_S_202412.jwpub", language="es")
    assert s.kind == "jwpub"
    assert s.language == "es"
    assert s.pub_code_hint == ""
    assert s.publication_kind_hint is None


def test_source_spec_wol_article() -> None:
    s = SourceSpec(
        kind="wol-article",
        path="https://wol.jw.org/en/wol/d/r1/lp-e/2024XXX",
        language="en",
        pub_code_hint="w24",
        publication_kind_hint="watchtower",
    )
    assert s.kind == "wol-article"
    assert s.pub_code_hint == "w24"
    assert s.publication_kind_hint == "watchtower"
