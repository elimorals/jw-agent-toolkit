"""jw-core — Core library for jw-agent-toolkit."""

__version__ = "0.1.0"

from jw_core.models import BibleRef
from jw_core.parsers.reference import (
    parse_all_references,
    parse_reference,
)

__all__ = [
    "BibleRef",
    "parse_reference",
    "parse_all_references",
]
