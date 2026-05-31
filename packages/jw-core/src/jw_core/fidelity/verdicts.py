"""NLIVerdict (stub) — replaced in Task 2 with the full implementation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Verdict = Literal["entails", "neutral", "contradicts"]


@dataclass(frozen=True)
class NLIVerdict:
    verdict: Verdict
    score: float
    provider: str
    raw: dict
