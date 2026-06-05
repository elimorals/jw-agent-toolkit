"""Compile loop: discover → parse → extract → write graph + wiki."""

from __future__ import annotations

import logging
import shutil
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from jw_brain.backends.protocol import GraphBackend
from jw_brain.compiler.cache import ExtractionCache, cache_key_for
from jw_brain.compiler.llm_extractor import ExtractionRequest, LLMExtractor
from jw_brain.compiler.parser_router import ParserRouter
from jw_brain.schema import EdgeRegistry, NodeRegistry
from jw_brain.wiki.obsidian_writer import ObsidianWikiWriter

logger = logging.getLogger(__name__)


@dataclass
class CompileOptions:
    inbox: Path
    processed: Path
    language: str = "es"
    dry_run: bool = False
    snapshot_first: bool = True


@dataclass
class CompileReport:
    n_files_processed: int = 0
    n_nodes_new: int = 0
    n_edges_new: int = 0
    n_cache_hits: int = 0
    n_low_confidence: int = 0
    warnings: list[str] = field(default_factory=list)
    dry_run: bool = False


class Compiler:
    def __init__(
        self,
        *,
        backend: GraphBackend,
        extractor: LLMExtractor,
        wiki_writer: ObsidianWikiWriter,
        node_registry: NodeRegistry,
        edge_registry: EdgeRegistry,
        cache_dir: Path,
        router: ParserRouter | None = None,
    ) -> None:
        self.backend = backend
        self.extractor = extractor
        self.wiki = wiki_writer
        self.nodes = node_registry
        self.edges = edge_registry
        self.cache = ExtractionCache(cache_dir)
        self.router = router or ParserRouter()

    async def compile(self, opts: CompileOptions) -> CompileReport:
        run_id = str(uuid.uuid4())
        report = CompileReport(dry_run=opts.dry_run)
        opts.processed.mkdir(parents=True, exist_ok=True)
        if not opts.inbox.exists():
            return report

        for raw_file in sorted(opts.inbox.iterdir()):
            if raw_file.is_dir():
                continue
            parsed = self.router.parse(raw_file)
            if parsed is None:
                report.warnings.append(f"no parser for {raw_file.name}")
                continue

            content_hash = cache_key_for(
                content=parsed.text,
                prompt_version=self.extractor.prompt_version,
                provider_id=self.extractor.provider.id,
            )
            cached = self.cache.get(content_hash)
            if cached is not None:
                report.n_cache_hits += 1
                extraction_payload = cached
            else:
                req = ExtractionRequest(
                    chunks=parsed.chunks or [parsed.text],
                    source_chunk_id=str(raw_file),
                    language=opts.language,
                    run_id=run_id,
                )
                result = await self.extractor.extract(req)
                extraction_payload = {
                    "nodes": [
                        {"node_type": n.node_type, "canonical_id": n.canonical_id,
                         "properties": n.properties, "confidence": n.confidence,
                         "low_confidence": n.low_confidence}
                        for n in result.nodes
                    ],
                    "edges": [
                        {"edge_type": e.edge_type, "from_node": e.from_node,
                         "to_node": e.to_node, "properties": e.properties,
                         "confidence": e.confidence, "low_confidence": e.low_confidence}
                        for e in result.edges
                    ],
                    "warnings": result.warnings,
                }
                if not opts.dry_run:
                    self.cache.put(content_hash, extraction_payload)
                report.warnings.extend(result.warnings)

            if opts.dry_run:
                report.n_nodes_new += len(extraction_payload["nodes"])
                report.n_edges_new += len(extraction_payload["edges"])
                continue

            with self.backend.transaction():
                for nd in extraction_payload["nodes"]:
                    self.backend.upsert_node(
                        node_type=nd["node_type"],
                        canonical_id=nd["canonical_id"],
                        properties=nd["properties"],
                        provenance={
                            "run_id": run_id,
                            "source_chunk_id": str(raw_file),
                            "confidence": nd["confidence"],
                            "model_id": self.extractor.provider.id,
                        },
                    )
                    if nd.get("low_confidence"):
                        report.n_low_confidence += 1
                    report.n_nodes_new += 1

                    spec = self.nodes.get(nd["node_type"])
                    if spec and spec.obsidian_subdir:
                        slug = nd["canonical_id"].replace(":", "_").replace("/", "_")
                        body = str(
                            nd["properties"].get("text")
                            or nd["properties"].get("title")
                            or ""
                        )
                        try:
                            self.wiki.write_page(
                                f"{spec.obsidian_subdir}{slug}.md",
                                body=body,
                                frontmatter={
                                    "node_type": nd["node_type"],
                                    "canonical_id": nd["canonical_id"],
                                    "confidence": nd["confidence"],
                                    "run_id": run_id,
                                },
                            )
                        except Exception as exc:  # noqa: BLE001
                            report.warnings.append(f"wiki write failed for {slug}: {exc}")

                for ed in extraction_payload["edges"]:
                    self.backend.upsert_edge(
                        edge_type=ed["edge_type"],
                        from_node=ed["from_node"],
                        to_node=ed["to_node"],
                        properties=ed.get("properties", {}),
                        provenance={
                            "run_id": run_id,
                            "confidence": ed["confidence"],
                            "model_id": self.extractor.provider.id,
                        },
                    )
                    report.n_edges_new += 1

            shutil.move(str(raw_file), str(opts.processed / raw_file.name))
            report.n_files_processed += 1

        if not opts.dry_run:
            self.wiki.append_log("compile", {
                "run_id": run_id,
                "files": report.n_files_processed,
                "nodes_new": report.n_nodes_new,
                "edges_new": report.n_edges_new,
                "cache_hits": report.n_cache_hits,
            })

        return report
