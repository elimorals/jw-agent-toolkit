"""Detects contradictions across the graph via F39 NLI."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


class NLIProvider(Protocol):
    async def evaluate_entailment(self, claim: str, premise: str) -> Any: ...


@dataclass
class Contradiction:
    claim_a: str
    claim_b: str
    source_a: str
    source_b: str
    nli_score: float


class ContradictionFinder:
    def __init__(self, *, nli_provider: NLIProvider, backend) -> None:
        self.nli = nli_provider
        self.backend = backend

    async def find(self, *, threshold: float = 0.7) -> list[Contradiction]:
        """For each Topic node, get connected Publications, NLI each pair."""

        topics = self.backend.query(
            "SELECT canonical_id FROM nodes WHERE node_type = 'Topic'"
        )
        contradictions: list[Contradiction] = []
        for t in topics:
            cid = t.get("canonical_id") if isinstance(t, dict) else t[0]
            if not cid:
                continue
            neighbors = self.backend.neighbors(cid, hops=1, direction="in")
            claims = [n for n in neighbors if n.get("node_type") == "Publication"]
            for i, a in enumerate(claims):
                for b in claims[i + 1:]:
                    text_a = str(a.get("text") or a.get("title") or "")
                    text_b = str(b.get("text") or b.get("title") or "")
                    if not text_a or not text_b:
                        continue
                    verdict = await self.nli.evaluate_entailment(text_a, text_b)
                    label = getattr(verdict, "label", None)
                    if label is None and isinstance(verdict, dict):
                        label = verdict.get("label")
                    if label != "contradicts":
                        continue
                    score = getattr(verdict, "score", None)
                    if score is None and isinstance(verdict, dict):
                        score = verdict.get("score", 0.0)
                    if score and score >= threshold:
                        contradictions.append(Contradiction(
                            claim_a=text_a, claim_b=text_b,
                            source_a=str(a["canonical_id"]),
                            source_b=str(b["canonical_id"]),
                            nli_score=float(score),
                        ))
        return contradictions
