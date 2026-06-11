"""Pydantic models for the visual broadcasting index (Fase 69)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class VisualFrame(BaseModel):
    video_id: str
    timestamp_s: float = Field(ge=0)
    caption: str
    ocr_text: str = ""
    embedding_id: int = Field(ge=0)
    thumb_path: str | None = None
    transcript_concurrent: str = ""


class VisualSearchHit(BaseModel):
    video_id: str
    timestamp_s: float = Field(ge=0)
    score: float = Field(ge=0)
    source: Literal["fts", "clip", "ocr", "hybrid"]
    caption: str
    transcript_concurrent: str = ""
    thumb_path: str | None = None
    deep_link: str


class IndexStats(BaseModel):
    videos_indexed: int = Field(ge=0)
    frames_total: int = Field(ge=0)
    embeddings_dim: int = Field(ge=0)
    storage_mb: float = Field(ge=0)
    avg_frame_per_video: float = Field(ge=0)
