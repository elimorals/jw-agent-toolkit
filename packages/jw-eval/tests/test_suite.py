from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from jw_eval.models import GoldenCase
from jw_eval.suite import Suite


class FakeFinding:
    def __init__(self, text: str, source: str = "rag") -> None:
        self.text = text
        self.metadata = {"source": source, "citation_url": "https://wol.jw.org/x"}


class FakeResult:
    def __init__(self) -> None:
        self.findings = [FakeFinding("Hello world doctrinal answer")]


def fake_agent(_: dict[str, Any]) -> FakeResult:
    return FakeResult()


def test_suite_runs_layer_1_only(tmp_path: Path) -> None:
    yaml = tmp_path / "case.yaml"
    yaml.write_text(
        """
id: t_l1
agent: apologetics
layer: l1
input: {}
expected:
  must_have_source: rag
""",
        encoding="utf-8",
    )

    suite = Suite(
        cases_root=tmp_path,
        snapshots_root=tmp_path,
        agent_registry={"apologetics": fake_agent},
    )
    report = suite.run(layers=["l1"])
    assert len(report.results) == 1
    assert report.results[0].verdict == "pass"
    assert report.summary["l1"]["pass"] == 1


def test_suite_unknown_agent_marks_error(tmp_path: Path) -> None:
    yaml = tmp_path / "case.yaml"
    yaml.write_text(
        "id: t\nagent: missing\nlayer: l1\ninput: {}\nexpected: {}\n", encoding="utf-8"
    )
    suite = Suite(cases_root=tmp_path, snapshots_root=tmp_path, agent_registry={})
    report = suite.run(layers=["l1"])
    assert report.results[0].verdict == "error"
