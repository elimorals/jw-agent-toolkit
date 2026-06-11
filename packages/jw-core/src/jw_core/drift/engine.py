"""End-to-end doctrinal drift analyzer (Fase 72).

Takes a list of `Chunk` objects (text + year + embedding) for a doctrinal
query, partitions by era, clusters each era, detects drift events
between consecutive populated eras, and emits a `DoctrinalDrift`
report with the mandatory explanatory note about "growing light".
"""

from __future__ import annotations

import logging

from jw_core.drift.cluster import Chunk, dbscan_cluster, partition_by_era
from jw_core.drift.drift_detect import (
    build_era_snapshot,
    detect_drift_events,
)
from jw_core.drift.explanatory_notes import get_explanatory_note
from jw_core.drift.models import ALL_ERAS, DoctrinalDrift, Era

logger = logging.getLogger(__name__)


def _summary_prose(report: DoctrinalDrift, *, language: str) -> str:
    if report.insufficient_data:
        intro = {
            "es": "Datos insuficientes para detectar drift confiable.",
            "en": "Insufficient data to detect a reliable drift.",
            "pt": "Dados insuficientes para detectar drift confiável.",
        }.get(language, "Insufficient data.")
        return intro
    if not report.drift_events:
        intro = {
            "es": "No se detectaron cambios significativos entre eras.",
            "en": "No significant changes detected across eras.",
            "pt": "Sem mudanças significativas entre eras.",
        }.get(language, "No significant changes detected.")
        return intro

    lead = {
        "es": "Resumen del refinamiento doctrinal observado:",
        "en": "Summary of observed doctrinal refinement:",
        "pt": "Resumo do refinamento doutrinal observado:",
    }.get(language, "Summary of observed doctrinal refinement:")
    parts: list[str] = [lead, ""]
    for ev in report.drift_events:
        parts.append(
            f"- {ev.from_era} -> {ev.to_era} "
            f"(delta={ev.cosine_delta:.3f}, {ev.significance})"
        )
    return "\n".join(parts)


def analyze_doctrinal_drift(
    *,
    query: str,
    chunks: list[Chunk],
    language: str = "es",
    min_chunks_per_era: int = 3,
    dbscan_epsilon: float = 0.30,
    dbscan_min_samples: int = 2,
    min_delta: float = 0.05,
) -> DoctrinalDrift:
    """Build a `DoctrinalDrift` report from chunks.

    `chunks` is what the caller (CLI / agent) gets from F49 Second Brain
    + F62 historical PDF ingest. We never go to the network here.
    """

    explanatory = get_explanatory_note(language)

    era_chunks_all = partition_by_era(chunks)
    eras_skipped: list[Era] = []
    era_chunks: dict[Era, list[Chunk]] = {}
    for era in ALL_ERAS:
        cs = era_chunks_all.get(era, [])
        if not cs:
            continue
        if len(cs) < min_chunks_per_era:
            eras_skipped.append(era)
            continue
        era_chunks[era] = cs

    if len(era_chunks) < 2:
        return DoctrinalDrift(
            query=query,
            language=language,  # type: ignore[arg-type]
            era_snapshots=[],
            drift_events=[],
            summary_prose=_summary_prose(
                DoctrinalDrift(
                    query=query,
                    language=language,  # type: ignore[arg-type]
                    insufficient_data=True,
                    explanatory_note=explanatory,
                ),
                language=language,
            ),
            explanatory_note=explanatory,
            insufficient_data=True,
            eras_skipped_low_data=eras_skipped,
        )

    era_clusters = {
        era: dbscan_cluster(
            cs, epsilon=dbscan_epsilon, min_samples=dbscan_min_samples
        )
        for era, cs in era_chunks.items()
    }
    snapshots = [
        build_era_snapshot(
            era=era, chunks=era_chunks[era], cluster=era_clusters[era]
        )
        for era in ALL_ERAS
        if era in era_chunks
    ]
    events = detect_drift_events(
        era_chunks=era_chunks,
        era_clusters=era_clusters,
        min_delta=min_delta,
    )

    report = DoctrinalDrift(
        query=query,
        language=language,  # type: ignore[arg-type]
        era_snapshots=snapshots,
        drift_events=events,
        summary_prose="",
        explanatory_note=explanatory,
        insufficient_data=False,
        eras_skipped_low_data=eras_skipped,
    )
    report.summary_prose = _summary_prose(report, language=language)
    return report
