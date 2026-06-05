"""F57.16 — Congregation registry."""
from __future__ import annotations

import pytest

from jw_meeting_media.congregation import (
    Congregation,
    load_registry,
    remove_congregation,
    resolve_congregation,
    save_congregation,
)


def test_load_registry_empty_when_missing(tmp_path):
    reg_path = tmp_path / "congregations.toml"
    assert load_registry(reg_path) == {}


def test_save_and_load_roundtrip(tmp_path):
    reg_path = tmp_path / "congregations.toml"
    cong = Congregation(
        name="kingdom-hall-norte",
        language="es",
        weekend_kind="weekend",
        midweek_kind="midweek",
        notes="Congregación principal",
    )
    save_congregation(cong, registry_path=reg_path)
    loaded = load_registry(reg_path)
    assert "kingdom-hall-norte" in loaded
    assert loaded["kingdom-hall-norte"].language == "es"
    assert loaded["kingdom-hall-norte"].notes == "Congregación principal"


def test_resolve_single_returns_only_one(tmp_path):
    reg_path = tmp_path / "congregations.toml"
    save_congregation(
        Congregation(name="only", language="es"),
        registry_path=reg_path,
    )
    result = resolve_congregation(name=None, registry_path=reg_path)
    assert result.name == "only"


def test_resolve_multiple_without_name_raises(tmp_path):
    reg_path = tmp_path / "congregations.toml"
    save_congregation(Congregation(name="a", language="es"), registry_path=reg_path)
    save_congregation(Congregation(name="b", language="en"), registry_path=reg_path)
    with pytest.raises(ValueError, match="multiple congregations"):
        resolve_congregation(name=None, registry_path=reg_path)


def test_resolve_no_registry_returns_default(tmp_path):
    """Backwards compat: sin registry, devuelve Congregation('default')."""
    result = resolve_congregation(name=None, registry_path=tmp_path / "missing.toml")
    assert result.name == "default"
    assert result.language == "en"


def test_resolve_by_name(tmp_path):
    reg_path = tmp_path / "congregations.toml"
    save_congregation(Congregation(name="norte", language="es"), registry_path=reg_path)
    save_congregation(Congregation(name="sur", language="en"), registry_path=reg_path)
    result = resolve_congregation(name="sur", registry_path=reg_path)
    assert result.language == "en"


def test_resolve_unknown_name_raises(tmp_path):
    reg_path = tmp_path / "congregations.toml"
    save_congregation(Congregation(name="exists", language="es"), registry_path=reg_path)
    with pytest.raises(KeyError):
        resolve_congregation(name="nope", registry_path=reg_path)


def test_remove(tmp_path):
    reg_path = tmp_path / "congregations.toml"
    save_congregation(Congregation(name="a", language="es"), registry_path=reg_path)
    save_congregation(Congregation(name="b", language="en"), registry_path=reg_path)
    n = remove_congregation("a", registry_path=reg_path)
    assert n == 1
    assert "a" not in load_registry(reg_path)
    assert "b" in load_registry(reg_path)


def test_remove_missing_returns_zero(tmp_path):
    reg_path = tmp_path / "congregations.toml"
    save_congregation(Congregation(name="a", language="es"), registry_path=reg_path)
    n = remove_congregation("nope", registry_path=reg_path)
    assert n == 0
    assert "a" in load_registry(reg_path)
