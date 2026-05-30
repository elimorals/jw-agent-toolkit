"""Base abstractions for jw-agents.

Design choice: agents are PROCEDURAL orchestrators (not LLM-driven).
They compose jw-core clients/parsers + jw-rag retrieval into multi-step
pipelines that produce STRUCTURED results. The synthesis-by-LLM step is
left to the calling client (Claude Desktop, etc.) which can read the
structured output and generate prose with citations.

This keeps the agents:
  - Testable (no LLM mocking required).
  - Deterministic.
  - Cheap (no API costs).
  - Composable (you can chain agents from your own LLM logic).

If you want a fully autonomous LLM agent that calls these tools in a loop,
build that on top — the structured outputs are designed for it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Citation:
    """A verifiable source pointer attached to every agent finding."""

    url: str
    title: str = ""
    kind: str = ""  # 'verse', 'article', 'daily_text', 'chapter'
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Finding:
    """One unit of information returned by an agent."""

    summary: str
    citation: Citation
    excerpt: str = ""  # The verbatim text the finding is based on
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentResult:
    """Standard envelope for every agent's output.

    The calling LLM (or downstream code) is expected to:
      1. Read `findings` and synthesize a response.
      2. Always include every `citation.url` in the final answer.
      3. Surface `warnings` to the user if non-empty.
    """

    query: str
    agent_name: str
    findings: list[Finding] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "agent_name": self.agent_name,
            "warnings": self.warnings,
            "metadata": self.metadata,
            "findings": [
                {
                    "summary": f.summary,
                    "excerpt": f.excerpt,
                    "metadata": f.metadata,
                    "citation": {
                        "url": f.citation.url,
                        "title": f.citation.title,
                        "kind": f.citation.kind,
                        "metadata": f.citation.metadata,
                    },
                }
                for f in self.findings
            ],
        }
