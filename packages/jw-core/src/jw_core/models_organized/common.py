"""CRDT envelope: every mutable field carries its own `updatedAt` for sync.

This shape (`{value: T, updatedAt: ISO-8601}`) is the conflict-resolution
primitive used across organized-app. Last-write-wins per field.
"""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class Timestamped(BaseModel, Generic[T]):
    """CRDT envelope: a value plus the ISO timestamp at which it was set."""

    model_config = ConfigDict(populate_by_name=True)

    value: T
    updatedAt: str
