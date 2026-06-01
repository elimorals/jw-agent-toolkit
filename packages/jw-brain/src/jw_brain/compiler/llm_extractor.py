"""LLM-driven entity/edge extractor for compiler."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Protocol

from jw_brain.schema import EdgeRegistry, NodeRegistry

logger = logging.getLogger(__name__)

PROMPT_VERSION = "v1"


class GenerationProvider(Protocol):
    @property
    def id(self) -> str: ...

    async def complete(self, prompt: str, *, temperature: float = 0.0) -> str: ...


@dataclass
class NodeUpsert:
    node_type: str
    canonical_id: str
    properties: dict[str, Any]
    confidence: float
    low_confidence: bool = False


@dataclass
class EdgeUpsert:
    edge_type: str
    from_node: str
    to_node: str
    properties: dict[str, Any]
    confidence: float
    low_confidence: bool = False


@dataclass
class ExtractionRequest:
    chunks: list[str]
    source_chunk_id: str
    language: str
    run_id: str
    extra_context: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExtractionResult:
    nodes: list[NodeUpsert] = field(default_factory=list)
    edges: list[EdgeUpsert] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    raw_output: str = ""


class LLMExtractor:
    def __init__(
        self,
        *,
        provider: GenerationProvider,
        node_registry: NodeRegistry,
        edge_registry: EdgeRegistry,
        prompt_version: str = PROMPT_VERSION,
    ) -> None:
        self.provider = provider
        self.nodes = node_registry
        self.edges = edge_registry
        self.prompt_version = prompt_version

    def build_prompt(self, req: ExtractionRequest) -> str:
        ntypes = "\n".join(
            f"- {s.name}: canonical_id = {s.canonical_id_pattern}, properties = {list(s.properties)}"
            for s in self.nodes.all()
        )
        etypes = "\n".join(
            f"- {s.name}: ({', '.join(s.sources)}) -> ({', '.join(s.targets)})"
            for s in self.edges.all()
        )
        joined = "\n\n".join(req.chunks)
        return (
            f"You are a knowledge-graph entity extractor.\n"
            f"Language: {req.language}\n\n"
            f"VALID NODE TYPES:\n{ntypes}\n\n"
            f"VALID EDGE TYPES:\n{etypes}\n\n"
            f"Read the following text and emit ONLY strict JSON with this shape:\n"
            f'{{"nodes": [{{"node_type": "...", "canonical_id": "...", "properties": {{...}}, "confidence": 0.x}}], '
            f'"edges": [{{"edge_type": "...", "from_node": "...", "to_node": "...", "confidence": 0.x}}]}}\n\n'
            f"NEVER invent a node_type or edge_type outside the lists above.\n\n"
            f"TEXT:\n{joined}"
        )

    async def extract(self, req: ExtractionRequest) -> ExtractionResult:
        prompt = self.build_prompt(req)
        raw = await self.provider.complete(prompt, temperature=0.0)
        out = ExtractionResult(raw_output=raw)
        try:
            data = json.loads(raw)
        except Exception:
            out.warnings.append(f"LLM returned non-JSON: {raw[:200]}")
            return out

        for nd in data.get("nodes") or []:
            ntype = nd.get("node_type")
            spec = self.nodes.get(ntype)
            if spec is None:
                out.warnings.append(f"unknown node_type: {ntype} (canonical_id={nd.get('canonical_id')!r})")
                continue
            conf = float(nd.get("confidence", 0.0))
            out.nodes.append(NodeUpsert(
                node_type=ntype,
                canonical_id=nd.get("canonical_id", ""),
                properties=nd.get("properties") or {},
                confidence=conf,
                low_confidence=(conf < spec.confidence_threshold),
            ))

        for ed in data.get("edges") or []:
            etype = ed.get("edge_type")
            espec = self.edges.get(etype)
            if espec is None:
                out.warnings.append(f"unknown edge_type: {etype}")
                continue
            conf = float(ed.get("confidence", 0.0))
            out.edges.append(EdgeUpsert(
                edge_type=etype,
                from_node=ed.get("from_node", ""),
                to_node=ed.get("to_node", ""),
                properties=ed.get("properties") or {},
                confidence=conf,
                low_confidence=(conf < espec.confidence_threshold),
            ))

        return out
