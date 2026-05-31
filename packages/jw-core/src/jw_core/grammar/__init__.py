"""GBNF + Pydantic constrained-decoding kit.

Public API:
    from jw_core.grammar import (
        AgentResultModel,
        CitationModel,
        ConstrainedCaller,
        FindingModel,
        agent_result_grammar,
        citation_url_grammar,
        get_default_constrained_caller,
        pydantic_to_gbnf,
    )

Importing this module triggers *zero* network and *zero* optional deps.
"""

from jw_core.grammar.citation_grammar import citation_url_grammar
from jw_core.grammar.factory import ConstrainedCaller, get_default_constrained_caller
from jw_core.grammar.gbnf import agent_result_grammar, json_object_grammar
from jw_core.grammar.schemas import (
    AgentResultModel,
    CitationModel,
    FindingModel,
    pydantic_to_gbnf,
)

__all__ = [
    "AgentResultModel",
    "CitationModel",
    "ConstrainedCaller",
    "FindingModel",
    "agent_result_grammar",
    "citation_url_grammar",
    "get_default_constrained_caller",
    "json_object_grammar",
    "pydantic_to_gbnf",
]
