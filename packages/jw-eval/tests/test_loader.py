from __future__ import annotations

from pathlib import Path

import pytest

from jw_eval.loader import load_case_file, load_cases

FIXTURES = Path(__file__).parent / "fixtures" / "mini"


def test_load_case_file_minimal() -> None:
    case = load_case_file(FIXTURES / "demo_l1.yaml")
    assert case.id == "mini_l1_demo"
    assert case.layer == "l1"
    assert case.input["question"] == "demo"


def test_load_cases_filters_by_layer() -> None:
    cases = load_cases(FIXTURES, layers=["l1"])
    assert len(cases) >= 1
    assert all(c.layer == "l1" for c in cases)


def test_load_cases_empty_dir(tmp_path: Path) -> None:
    assert load_cases(tmp_path, layers=["l1"]) == []


def test_load_case_file_missing_required_field(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text("id: x\n")  # missing agent, layer, input
    with pytest.raises(ValueError):
        load_case_file(bad)
