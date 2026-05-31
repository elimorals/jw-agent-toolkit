from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import pytest

from jw_eval.layers.citations import evaluate_citations_snapshot, snapshot_path
from jw_eval.models import GoldenCase


def _stub_agent(citations: list[str]):
    class _F:
        def __init__(self, url: str) -> None:
            self.metadata = {"citation_url": url}

    class _R:
        findings = [_F(u) for u in citations]

    def run(_: dict[str, Any]) -> _R:
        return _R()

    return run


def test_snapshot_path_is_sha256(tmp_path: Path) -> None:
    url = "https://wol.jw.org/example"
    p = snapshot_path(tmp_path, url)
    assert p.name == hashlib.sha256(url.encode()).hexdigest() + ".html"


def test_citations_pass_when_url_and_phrase_present(tmp_path: Path) -> None:
    url = "https://wol.jw.org/x"
    snap = snapshot_path(tmp_path, url)
    snap.write_text("<html>... amó tanto al mundo ...</html>", encoding="utf-8")

    case = GoldenCase(
        id="l2_demo",
        agent="verse_explainer",
        layer="l2",
        input={"reference": "Juan 3:16"},
        expected={
            "expected_citations": [url],
            "support_phrases": ["amó tanto al mundo"],
        },
    )
    r = evaluate_citations_snapshot(case, _stub_agent([url]), snapshots_root=tmp_path)
    assert r.verdict == "pass"


def test_citations_fail_when_url_missing(tmp_path: Path) -> None:
    url = "https://wol.jw.org/x"
    case = GoldenCase(
        id="l2_no_url",
        agent="verse_explainer",
        layer="l2",
        input={"reference": "Juan 3:16"},
        expected={"expected_citations": [url], "support_phrases": ["x"]},
    )
    r = evaluate_citations_snapshot(case, _stub_agent([]), snapshots_root=tmp_path)
    assert r.verdict == "fail"
    assert any("missing URL" in reason for reason in r.reasons)


def test_citations_fail_when_phrase_absent(tmp_path: Path) -> None:
    url = "https://wol.jw.org/x"
    snap = snapshot_path(tmp_path, url)
    snap.write_text("<html>completely different</html>", encoding="utf-8")
    case = GoldenCase(
        id="l2_no_phrase",
        agent="verse_explainer",
        layer="l2",
        input={"reference": "Juan 3:16"},
        expected={
            "expected_citations": [url],
            "support_phrases": ["amó tanto al mundo"],
        },
    )
    r = evaluate_citations_snapshot(case, _stub_agent([url]), snapshots_root=tmp_path)
    assert r.verdict == "fail"
    assert any("none of support_phrases" in reason for reason in r.reasons)


def test_citations_skip_when_snapshot_missing(tmp_path: Path) -> None:
    url = "https://wol.jw.org/x"  # no snapshot created
    case = GoldenCase(
        id="l2_no_snap",
        agent="verse_explainer",
        layer="l2",
        input={},
        expected={"expected_citations": [url], "support_phrases": ["x"]},
    )
    r = evaluate_citations_snapshot(case, _stub_agent([url]), snapshots_root=tmp_path)
    assert r.verdict == "skip"
