"""Exporter exceptions.

Every exporter that requires an optional extra raises `MissingDependencyError`
with a copy-pasteable install hint when its dependency is not importable.
"""

from __future__ import annotations


class ExportError(Exception):
    """Base class for everything raised by the exporters module."""


class MissingDependencyError(ExportError):
    """Raised when an optional dependency (weasyprint/python-docx/genanki) is missing."""
