"""Pydantic v2 mirror models for the procedural AgentResult dataclass.

These models exist only to drive constrained decoding. They are NOT the
canonical contract for jw-agents — that is still
`jw_agents.base.AgentResult`. Bidirectional conversion lives here so the
mirror remains opt-in.

Why a separate Pydantic mirror?

- Pydantic v2 has `model_json_schema()` which is what Anthropic / OpenAI
  structured outputs expect.
- The `StringConstraints` pattern on `CitationModel.url` doubles as the
  truth source for the GBNF citation URL rule (kept in sync via a single
  regex constant).
- The dataclass in `jw_agents.base` stays clean (no Pydantic dependency
  forced on every agent).
"""

from __future__ import annotations

from typing import Annotated, Any, Literal, get_args, get_origin

from pydantic import BaseModel, Field, StringConstraints

# Single source of truth for the citation URL anchor. The GBNF builder
# in citation_grammar.py uses the same regex shape; the Pydantic field
# enforces it at parse time.
CITATION_URL_REGEX = r"^https://wol\.jw\.org/[a-z]{2,3}/.+"

CitationKind = Literal["verse", "article", "daily_text", "chapter", "topic", "study_note"]


class CitationModel(BaseModel):
    """Mirror of jw_agents.base.Citation, with hard URL constraint."""

    url: Annotated[str, StringConstraints(pattern=CITATION_URL_REGEX, min_length=20, max_length=512)]
    title: str = ""
    kind: CitationKind = "article"


class FindingModel(BaseModel):
    """Mirror of jw_agents.base.Finding."""

    summary: Annotated[str, StringConstraints(min_length=1, max_length=2000)]
    citation: CitationModel
    excerpt: str = ""


class AgentResultModel(BaseModel):
    """Mirror of jw_agents.base.AgentResult."""

    query: str
    agent_name: str
    findings: Annotated[list[FindingModel], Field(min_length=1, max_length=32)]
    warnings: list[str] = Field(default_factory=list)

    # ---- Bidirectional conversion with the dataclass --------------------

    @classmethod
    def from_dataclass(cls, src: Any) -> AgentResultModel:
        """Convert a jw_agents.base.AgentResult into the Pydantic mirror.

        Findings whose citation URL does not match the WOL regex are
        DROPPED — the caller likely has a bug, but we don't want to
        explode at conversion time. If the resulting findings list is
        empty, we raise (Pydantic also enforces min_length=1).
        """

        from jw_agents.base import AgentResult

        if not isinstance(src, AgentResult):  # defensive
            raise TypeError(f"expected AgentResult, got {type(src).__name__}")

        findings_payload: list[dict[str, Any]] = []
        for f in src.findings:
            url = f.citation.url
            if not url.startswith("https://wol.jw.org/"):
                continue
            findings_payload.append(
                {
                    "summary": (f.summary or "")[:2000] or "(empty summary)",
                    "citation": {
                        "url": url,
                        "title": f.citation.title or "",
                        "kind": (f.citation.kind or "article"),
                    },
                    "excerpt": f.excerpt or "",
                }
            )

        return cls(
            query=src.query,
            agent_name=src.agent_name,
            findings=findings_payload,  # type: ignore[arg-type]
            warnings=list(src.warnings),
        )

    def to_dataclass(self) -> Any:
        """Convert back to the canonical dataclass."""

        from jw_agents.base import AgentResult, Citation, Finding

        return AgentResult(
            query=self.query,
            agent_name=self.agent_name,
            findings=[
                Finding(
                    summary=f.summary,
                    citation=Citation(url=f.citation.url, title=f.citation.title, kind=f.citation.kind),
                    excerpt=f.excerpt,
                )
                for f in self.findings
            ],
            warnings=list(self.warnings),
        )


# ---- Pydantic → GBNF compiler --------------------------------------------


def pydantic_to_gbnf(model: type[BaseModel], *, root_name: str = "root") -> str:
    """Compile a Pydantic model into a GBNF grammar string.

    Supported types:
        str (with/without pattern), int, float, bool,
        Literal[str, ...], Optional[T], list[T], BaseModel (recursion).

    Unsupported types raise ValueError at *build* time, never at runtime.
    """

    rules: dict[str, str] = {}
    _compile_model(model, rules, top_name=root_name)
    # Always inline the shared helpers.
    rules["ws"] = r"[ \t\n]*"
    rules["string"] = (
        r"""'"' ( [^"\\] | "\\" ["\\bfnrt/] | "\\u" [0-9a-fA-F] [0-9a-fA-F] [0-9a-fA-F] [0-9a-fA-F] )* '"'"""
    )
    rules["integer"] = r"""("-")? [0-9]+"""
    rules["number"] = r"""("-")? [0-9]+ ("." [0-9]+)? ( [eE] ("+"|"-")? [0-9]+ )?"""
    rules["boolean"] = r""" "true" | "false" """
    return _serialize_rules(rules)


def _compile_model(model: type[BaseModel], rules: dict[str, str], *, top_name: str) -> str:
    rule_name = top_name if top_name != "" else _model_rule_name(model)
    if rule_name in rules:
        return rule_name

    parts: list[str] = []
    fields = list(model.model_fields.items())
    for i, (name, info) in enumerate(fields):
        is_last = i == len(fields) - 1
        sub = _compile_field(name, info.annotation, info, rules)
        sep = "" if is_last else ' "," ws'
        parts.append(f'ws "\\"{name}\\"" ws ":" ws {sub}{sep}')

    rules[rule_name] = '"{" ' + " ".join(parts) + ' ws "}"'
    return rule_name


def _model_rule_name(model: type[BaseModel]) -> str:
    return model.__name__.lower().replace("model", "")


def _compile_field(name: str, ann: Any, info: Any, rules: dict[str, str]) -> str:
    origin = get_origin(ann)
    args = get_args(ann)

    # Optional[T] / T | None
    if origin is None and ann is type(None):
        return '"null"'
    if origin is not None and type(None) in args:
        non_none = [a for a in args if a is not type(None)]
        if len(non_none) == 1:
            inner = _compile_field(name, non_none[0], info, rules)
            return f'({inner} | "null")'

    # Literal[...]
    if origin is Literal or str(origin) == "typing.Literal":
        choices = " | ".join(f'"\\"{a}\\""' for a in args)
        return f"({choices})"

    # list[T]
    if origin in (list, "list"):
        inner_type = args[0] if args else str
        inner_rule = _compile_field(name + "_item", inner_type, info, rules)
        return f'"[" ws ({inner_rule} (ws "," ws {inner_rule})*)? ws "]"'

    # Nested BaseModel
    if isinstance(ann, type) and issubclass(ann, BaseModel):
        sub_rule = _compile_model(ann, rules, top_name=_model_rule_name(ann))
        return sub_rule

    # Primitive str / int / float / bool
    if ann is str:
        # If the field has a pattern constraint, emit a regex-anchored rule.
        meta = getattr(info, "metadata", []) or []
        for m in meta:
            pattern = getattr(m, "pattern", None)
            if pattern == CITATION_URL_REGEX:
                # Reuse the citation-url rule.
                from jw_core.grammar.citation_grammar import (
                    inject_citation_url_rule,
                )

                inject_citation_url_rule(rules)
                return "citation-url"
        return "string"
    if ann is int:
        return "integer"
    if ann is float:
        return "number"
    if ann is bool:
        return "boolean"

    raise ValueError(f"pydantic_to_gbnf: unsupported annotation {ann!r} on field {name!r}")


def _serialize_rules(rules: dict[str, str]) -> str:
    # Guarantee `root` is first when present for readability.
    ordered = ["root"] + [k for k in rules if k != "root"]
    lines = [f"{name} ::= {rules[name]}" for name in ordered if name in rules]
    return "\n".join(lines) + "\n"
