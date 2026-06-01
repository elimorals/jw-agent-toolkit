"""Exceptions emitted by the provenance subsystem."""

from __future__ import annotations


class ProvenanceError(Exception):
    """Base class for all provenance-related failures."""


class MissingProvenanceError(ProvenanceError):
    """A Citation lacks the four conventional provenance keys in metadata."""


class ProvenanceFetchError(ProvenanceError):
    """The fetcher could not retrieve the URL for a re-check."""

    def __init__(self, message: str, *, url: str) -> None:
        super().__init__(message)
        self.url = url
