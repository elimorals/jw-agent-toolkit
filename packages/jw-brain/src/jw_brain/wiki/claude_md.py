"""Autogenerate <vault>/<namespace>/CLAUDE.md per active domain.

Renders the operational schema that the LLM compiler must follow:
node types, edge types, conflict policy per edge, citation contract.
"""

from __future__ import annotations

from textwrap import dedent
from typing import Any


def render_claude_md(*, domain_name: str, nodes: list[Any], edges: list[Any]) -> str:
    """Render CLAUDE.md content from active NodeTypes + EdgeTypes.

    Accepts duck-typed specs: each Node/Edge spec must expose `.name`,
    plus optional `.canonical_id_pattern`, `.properties`, `.sources`,
    `.targets`, `.sensitive`. Plugin domains can ship their own spec
    classes (cf. tests/fixtures/financial_brain_plugin).
    """

    ntypes_block = "\n".join(_render_node(s) for s in nodes) or "  (none)"
    etypes_block = "\n".join(_render_edge(s) for s in edges) or "  (none)"
    return dedent(f"""\
        # Second Brain — operational schema (domain: {domain_name})

        ## Ownership

        - `raw/` is the user's. The agent reads, never writes.
        - `vault/Second-Brain/` is the agent's. User edits are honored when
          frontmatter contains `human_edited: true`.
        - `graph/` is the agent's. The user reads via queries, never edits the
          binary backend directly.

        ## NodeTypes

        {ntypes_block}

        ## EdgeTypes

        {etypes_block}

        ## Compile loop

        When the user runs `jw brain compile`:

        1. For each new file under `raw/inbox/`:
           - Detect mime; route to parser.
           - Extract entities + relations matching the NodeTypes/EdgeTypes above.
           - Emit JSON: `{{"nodes": [...], "edges": [...], "confidence": ...}}`.
           - NEVER invent a NodeType outside this list. Unknown types are flagged.
           - For each entity, ensure a wiki page exists; update synthesis section.
        2. Append to `log.md`.
        3. Move processed files to `raw/processed/`.

        ## Conflict policy

        Per-EdgeType. EdgeTypes flagged `sensitive` default to FLAG (do not
        overwrite — record both with `flag: contradicts_existing`).

        ## Human edits

        If a wiki page's YAML frontmatter contains `human_edited: true`:
        - DO NOT regenerate the page on the next compile.
        - DO continue updating the graph based on links found in the body.

        ## Citation contract

        EVERY claim in the wiki MUST point to a passage in the graph with a
        content_hash (Fase 40 invariant). No claim, no cite. The compiler
        propagates `provenance.run_id`, `model_id`, `confidence` per edge.
        """)


def _render_node(spec: Any) -> str:
    name = getattr(spec, "name", "?")
    pattern = getattr(spec, "canonical_id_pattern", "<no pattern>")
    properties = getattr(spec, "properties", {}) or {}
    return f"  - **{name}**: `{pattern}` properties={sorted(properties)}"


def _render_edge(spec: Any) -> str:
    name = getattr(spec, "name", "?")
    sources = tuple(getattr(spec, "sources", ()))
    targets = tuple(getattr(spec, "targets", ()))
    sensitive = getattr(spec, "sensitive", False)
    flag = "sensitive" if sensitive else "normal"
    return f"  - **{name}**: {sources} -> {targets} ({flag})"


def write_claude_md(
    *,
    target_path,
    domain_name: str,
    nodes: list[Any],
    edges: list[Any],
):
    """Write CLAUDE.md to <vault>/<namespace>/CLAUDE.md."""

    from pathlib import Path

    target = Path(target_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    body = render_claude_md(domain_name=domain_name, nodes=nodes, edges=edges)
    target.write_text(body, encoding="utf-8")
    return target
