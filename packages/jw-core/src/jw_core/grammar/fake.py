"""Deterministic GBNF-respecting fake sampler.

Used as the default in tests and as the safety-net fallback in
get_default_constrained_caller(). It is NOT a fake LLM — it samples
tokens that satisfy `AgentResultModel` directly. By construction it
cannot emit a string that fails Pydantic validation. That is exactly
the property the Hypothesis property test asserts.

Seeded by an int; identical seed + prompt + schema -> identical output.
"""

from __future__ import annotations

import json
import random
import re
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel

from jw_core.grammar.schemas import AgentResultModel

_URL_IN_PROMPT_REGEX = re.compile(r"https://wol\.jw\.org/[a-z]{2,3}/[-A-Za-z0-9_/.%]+")

_DEFAULT_URLS: tuple[str, ...] = (
    "https://wol.jw.org/es/wol/d/r4/lp-s/2024001",
    "https://wol.jw.org/en/wol/d/r1/lp-e/2024001",
    "https://wol.jw.org/pt/wol/d/r5/lp-t/2024001",
    "https://wol.jw.org/en/wol/b/r1/lp-e/nwt/E/2024/43/3",
    "https://wol.jw.org/es/wol/b/r4/lp-s/nwt/E/2024/45/6",
)

_KINDS: tuple[str, ...] = (
    "verse",
    "article",
    "daily_text",
    "chapter",
    "topic",
    "study_note",
)


@dataclass
class FakeConstrainedCaller:
    """A deterministic generator that always produces grammar-valid JSON."""

    seed: int = 0
    allowed_urls: list[str] = field(default_factory=lambda: list(_DEFAULT_URLS))
    min_findings: int = 1
    max_findings: int = 3

    async def is_available(self) -> bool:
        return True

    async def generate(
        self,
        prompt: str,
        *,
        grammar: str | None = None,
        json_schema: type[BaseModel] | None = None,
        temperature: float = 0.3,  # ignored
    ) -> str:
        if json_schema is None and grammar is None:
            raise ValueError("FakeConstrainedCaller requires json_schema or grammar")
        if json_schema is None:
            # We only know how to fake the canonical model.
            json_schema = AgentResultModel

        rng = random.Random((self.seed * 1_000_003) ^ hash(prompt))

        # If the prompt mentions allowed URLs (e.g. via run_with_citations),
        # restrict picks to that subset so reconciliation passes downstream.
        prompt_urls = list(dict.fromkeys(_URL_IN_PROMPT_REGEX.findall(prompt)))
        pick_pool = prompt_urls or self.allowed_urls

        n = rng.randint(self.min_findings, min(self.max_findings, max(len(pick_pool), 1)))

        findings: list[dict[str, Any]] = []
        for i in range(n):
            url = rng.choice(pick_pool)
            findings.append(
                {
                    "summary": f"finding {i} for prompt prefix {prompt[:40]!r}",
                    "citation": {
                        "url": url,
                        "title": f"Source {i}",
                        "kind": rng.choice(_KINDS),
                    },
                    "excerpt": "",
                }
            )

        payload = {
            "query": prompt,
            "agent_name": "fake",
            "findings": findings,
            "warnings": [],
        }

        # Validate before returning — guarantees the test invariant.
        if json_schema is not AgentResultModel:
            # Allow callers that pass a subclass-compatible model.
            json_schema.model_validate(payload)
        else:
            AgentResultModel.model_validate(payload)
        return json.dumps(payload, ensure_ascii=False)
