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
from jw_agents.audio_helper import (
    read_article_aloud,
    read_verse_aloud,
    search_broadcasting,
)
from jw_agents.base import AgentResult, Citation, Finding
from jw_agents.conversation_assistant import conversation_assistant
from jw_agents.meeting_helper import meeting_helper
from jw_agents.presentation_builder import list_audiences, presentation_builder
from jw_agents.public_talk_outline import public_talk_outline
from jw_agents.research_topic import research_topic
from jw_agents.revisit_tracker import Revisit, RevisitStore, plan_next_visit
from jw_agents.reverse_citation_lookup import reverse_citation_lookup
from jw_agents.student_part_helper import student_part_helper
from jw_agents.verse_explainer import verse_explainer
from jw_agents.workbook_helper import synthesize_comments, workbook_helper

__version__ = "0.1.0"

__all__ = [
    "AgentResult",
    "Citation",
    "Finding",
    "Revisit",
    "RevisitStore",
    "apologetics",
    "conversation_assistant",
    "list_audiences",
    "meeting_helper",
    "plan_next_visit",
    "presentation_builder",
    "public_talk_outline",
    "read_article_aloud",
    "read_verse_aloud",
    "research_topic",
    "reverse_citation_lookup",
    "search_broadcasting",
    "student_part_helper",
    "synthesize_comments",
    "verse_explainer",
    "workbook_helper",
]
