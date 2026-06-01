"""Sanity tests for provenance exception classes."""

from __future__ import annotations

import pytest

from jw_core.provenance.errors import (
    MissingProvenanceError,
    ProvenanceError,
    ProvenanceFetchError,
)


def test_missing_provenance_is_provenance_error() -> None:
    err = MissingProvenanceError("no content_hash in citation")
    assert isinstance(err, ProvenanceError)
    assert "no content_hash" in str(err)


def test_fetch_error_carries_url_attribute() -> None:
    err = ProvenanceFetchError("timeout", url="https://wol.jw.org/x")
    assert isinstance(err, ProvenanceError)
    assert err.url == "https://wol.jw.org/x"
    assert "timeout" in str(err)


def test_provenance_error_is_distinct_from_value_error() -> None:
    with pytest.raises(ProvenanceError):
        raise ProvenanceError("boom")
    with pytest.raises(ProvenanceError):
        raise MissingProvenanceError("also boom")
