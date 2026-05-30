"""jw-agents — High-level multi-step agents on top of jw-core + jw-rag.

Public surface:
    from jw_agents import (
        AgentResult, Citation, Finding,
        verse_explainer, research_topic, meeting_helper, apologetics,
    )

Agents are procedural — they orchestrate jw-core clients/parsers and return
structured `AgentResult`s. The calling LLM (or downstream code) synthesizes
the final answer using the cited evidence.
"""

from jw_agents.apologetics import apologetics
from jw_agents.base import AgentResult, Citation, Finding
from jw_agents.meeting_helper import meeting_helper
from jw_agents.research_topic import research_topic
from jw_agents.verse_explainer import verse_explainer

__version__ = "0.1.0"

__all__ = [
    "AgentResult",
    "Citation",
    "Finding",
    "apologetics",
    "meeting_helper",
    "research_topic",
    "verse_explainer",
]
