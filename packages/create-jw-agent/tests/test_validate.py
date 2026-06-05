"""Tests for name validation."""

from __future__ import annotations

import pytest
from create_jw_agent.validate import (
    RESERVED_NAMES,
    python_module_name,
    validate_name,
)


@pytest.mark.parametrize("good", [
    "my-translator",
    "trinity-explainer",
    "salon-prep",
    "x",
    "a-b-c",
    "agent42",
    "v2-router",
])
def test_valid_names_accepted(good: str) -> None:
    assert validate_name(good) is None


@pytest.mark.parametrize("bad,expected_code", [
    ("", "empty"),
    ("MyProject", "case"),
    ("My-Project", "case"),
    ("jw-foo", "reserved-prefix"),
    ("jw-core", "reserved-prefix"),
    ("123start", "invalid-shape"),
    ("-leading", "invalid-shape"),
    ("trailing-", "invalid-shape"),
    ("double--hyphen", "invalid-shape"),
    ("with space", "invalid-shape"),
    ("with_underscore", "invalid-shape"),
    ("dotted.name", "invalid-shape"),
    ("UPPERCASE", "case"),
    ("test", "reserved-name"),
])
def test_invalid_names_rejected(bad: str, expected_code: str) -> None:
    err = validate_name(bad)
    assert err is not None
    assert err.code == expected_code


def test_python_module_name_converts_hyphens() -> None:
    assert python_module_name("my-translator") == "my_translator"
    assert python_module_name("x") == "x"
    assert python_module_name("a-b-c") == "a_b_c"


def test_reserved_names_include_core_packages() -> None:
    assert "jw-core" in RESERVED_NAMES
    assert "jw-brain" in RESERVED_NAMES
    assert "create-jw-agent" in RESERVED_NAMES
