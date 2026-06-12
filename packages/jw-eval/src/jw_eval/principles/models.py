"""Pydantic models for fidelity principles.

A principle has three jobs:
  1. Be inspectable (humans can read the YAML and audit).
  2. Drive judge/fidelity_wrap decisions (severity → action).
  3. Be machine-checkable for cheap, deterministic violations
     (`DetectionRules`: substring matches, regex). NLI/LLM checks live
     outside; this layer is the regex tier.

Severity:
  - hard  → block / reject. The judge and fidelity_wrap MUST refuse output.
  - soft  → warn / annotate. Surface to the user; don't reject.
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator

Severity = Literal["hard", "soft"]


class DetectionRules(BaseModel):
    """Cheap, deterministic checks. All matching is case-insensitive.

    `forbidden_phrases` and `forbidden_regex` are independent: hitting any
    of them counts as a violation. Empty lists = no regex tier (still useful
    as a documented principle consumed by NLI/LLM elsewhere).
    """

    forbidden_phrases: list[str] = Field(default_factory=list)
    forbidden_regex: list[str] = Field(default_factory=list)

    @field_validator("forbidden_regex")
    @classmethod
    def _compileable(cls, v: list[str]) -> list[str]:
        for pat in v:
            try:
                re.compile(pat, re.IGNORECASE)
            except re.error as exc:
                raise ValueError(f"invalid regex {pat!r}: {exc}") from exc
        return v


class Principle(BaseModel):
    """One fidelity principle loaded from YAML."""

    id: str = Field(min_length=3)
    version: int = Field(ge=1, default=1)
    severity: Severity
    applies_to: list[str] = Field(
        default_factory=list,
        description="Agent/surface names this principle applies to. Empty = global.",
    )
    source: str = Field(default="", description="Citation to published material.")
    rationale: str
    detect: DetectionRules = Field(default_factory=DetectionRules)

    @field_validator("id")
    @classmethod
    def _id_format(cls, v: str) -> str:
        # Convention: PF### or PF###-slug. Not enforced strictly to allow
        # plugin-supplied principles with custom prefixes.
        if not v.strip():
            raise ValueError("id must be non-empty")
        return v.strip()

    def applies(self, agent: str | None) -> bool:
        """True if this principle applies to `agent` (or is global)."""
        if not self.applies_to:
            return True
        return agent is None or agent in self.applies_to


def violations_for(text: str, principles: list[Principle]) -> list[Principle]:
    """Return the principles whose deterministic detect rules `text` violates.

    NLI/LLM-level checks are NOT performed here — that's the judge's job.
    This is the cheap regex tier, useful for fail-fast pre-checks.
    """

    if not text:
        return []
    haystack = text.lower()
    hit: list[Principle] = []
    for p in principles:
        rules = p.detect
        matched = False
        for phrase in rules.forbidden_phrases:
            if phrase and phrase.lower() in haystack:
                matched = True
                break
        if not matched:
            for pat in rules.forbidden_regex:
                if re.search(pat, text, re.IGNORECASE):
                    matched = True
                    break
        if matched:
            hit.append(p)
    return hit
