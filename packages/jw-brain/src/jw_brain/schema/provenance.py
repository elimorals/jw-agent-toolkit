"""Edge provenance — typed view."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class EdgeProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    model_id: str
    prompt_version: str
    confidence: float
    source_chunk_id: str
    extracted_at: str  # ISO 8601 UTC
