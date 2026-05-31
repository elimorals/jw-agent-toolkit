"""Tests for jw_core.grammar.schemas — Pydantic mirror models."""

from __future__ import annotations

import pytest
from jw_agents.base import AgentResult, Citation, Finding
from jw_core.grammar.schemas import (
    AgentResultModel,
    CitationModel,
    FindingModel,
    pydantic_to_gbnf,
)
from pydantic import ValidationError


def test_citation_accepts_wol_url() -> None:
    c = CitationModel(url="https://wol.jw.org/es/wol/d/r4/lp-s/2025001", kind="article")
    assert c.url.startswith("https://wol.jw.org/")


def test_citation_rejects_non_wol_url() -> None:
    with pytest.raises(ValidationError):
        CitationModel(url="https://example.com/whatever", kind="article")


def test_citation_rejects_http() -> None:
    with pytest.raises(ValidationError):
        CitationModel(url="http://wol.jw.org/es/x", kind="article")


def test_finding_requires_non_empty_summary() -> None:
    with pytest.raises(ValidationError):
        FindingModel(summary="", citation=CitationModel(url="https://wol.jw.org/es/x", kind="article"))


def test_agent_result_requires_at_least_one_finding() -> None:
    with pytest.raises(ValidationError):
        AgentResultModel(query="q", agent_name="a", findings=[])


def test_from_dataclass_roundtrip() -> None:
    src = AgentResult(
        query="What is hope?",
        agent_name="apologetics",
        findings=[
            Finding(
                summary="Hope is grounded in resurrection.",
                citation=Citation(
                    url="https://wol.jw.org/en/wol/d/r1/lp-e/2024101",
                    title="Hope of the Resurrection",
                    kind="article",
                ),
                excerpt="...",
            )
        ],
        warnings=["draft"],
    )
    model = AgentResultModel.from_dataclass(src)
    assert model.findings[0].citation.url.startswith("https://wol.jw.org/en/")
    back = model.to_dataclass()
    assert isinstance(back, AgentResult)
    assert back.findings[0].citation.url == src.findings[0].citation.url
    assert back.warnings == ["draft"]


def test_pydantic_to_gbnf_emits_root_rule() -> None:
    grammar = pydantic_to_gbnf(AgentResultModel)
    assert "root" in grammar
    assert "citation-url" in grammar
