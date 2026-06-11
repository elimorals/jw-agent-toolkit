"""REST endpoints for book-camera (Fase 71 post-MVP).

Surfaces three POST endpoints under `/api/v1/book_camera`:

    POST /analyze     body: {"image_path"|"ocr_text", "language", "ocr_confidence"}
    POST /tts         body: {"text", "voice_name", "output_path", "language"}
    POST /rag_answer  body: {"question", "language", "topic"}

Mount with::

    from jw_mcp.rest.book_camera import router as book_camera_router
    app.include_router(book_camera_router)

`/tts` requires the voice-clone gate from F76 (consent, license,
non-commercial) and writes the synthesized WAV to `output_path` or a
temp file. `/rag_answer` delegates to `jw_agents.research_topic` when
available; otherwise it returns an empty-results payload.
"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import Any

try:
    from fastapi import APIRouter, HTTPException
    from pydantic import BaseModel, Field
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "FastAPI is required for the book-camera REST router. "
        "Install with `pip install fastapi`."
    ) from exc

logger = logging.getLogger(__name__)


router = APIRouter(prefix="/api/v1/book_camera", tags=["book_camera"])


# ── Schemas ─────────────────────────────────────────────────────────────


class AnalyzeRequest(BaseModel):
    image_path: str | None = None
    ocr_text: str | None = None
    language: str = "es"
    ocr_confidence: float | None = Field(default=None, ge=0.0, le=1.0)


class TTSRequest(BaseModel):
    text: str
    voice_name: str
    output_path: str | None = None
    language: str = "es"


class TTSResponse(BaseModel):
    output_path: str
    voice_name: str
    bytes_written: int


class RAGAnswerRequest(BaseModel):
    question: str
    language: str = "es"
    topic: str | None = None
    top_k: int = Field(default=5, ge=1, le=25)


class RAGAnswerResponse(BaseModel):
    question: str
    findings: list[dict[str, Any]] = Field(default_factory=list)
    note: str | None = None


# ── Endpoints ───────────────────────────────────────────────────────────


@router.post("/analyze")
def analyze(req: AnalyzeRequest) -> dict[str, Any]:
    """Run `analyze_capture` and return the `CameraFrameResult` as JSON."""

    if req.ocr_text is None and req.image_path is None:
        raise HTTPException(
            status_code=400,
            detail="Provide either `image_path` or `ocr_text`.",
        )
    from jw_core.book_camera.engine import analyze_capture

    try:
        result = analyze_capture(
            image_path=req.image_path,
            ocr_text=req.ocr_text,
            language=req.language,
            ocr_confidence=req.ocr_confidence,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=500, detail=f"analyze_capture failed: {exc}"
        ) from exc
    return result.model_dump(mode="json")


@router.post("/tts", response_model=TTSResponse)
def tts(req: TTSRequest) -> TTSResponse:
    """Synthesize `text` with a registered family voice (F76 gate)."""

    from jw_core.audio.voice_clone.license_gate import LicenseGateError
    from jw_core.audio.voice_clone.registry import VoiceNotFoundError
    from jw_core.audio.voice_clone.synthesizer import (
        synthesize_with_voice,
    )

    if req.output_path:
        out = Path(req.output_path).expanduser()
    else:
        fh = tempfile.NamedTemporaryFile(
            delete=False, suffix=".wav", prefix="jw_tts_"
        )
        fh.close()
        out = Path(fh.name)

    try:
        path = synthesize_with_voice(
            req.voice_name, req.text, output_path=out
        )
    except VoiceNotFoundError as exc:
        raise HTTPException(
            status_code=404, detail=f"voice not found: {req.voice_name}"
        ) from exc
    except LicenseGateError as exc:
        raise HTTPException(
            status_code=403, detail=f"license gate blocked: {exc}"
        ) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=500, detail=f"synthesis failed: {exc}"
        ) from exc

    return TTSResponse(
        output_path=str(path),
        voice_name=req.voice_name,
        bytes_written=path.stat().st_size if path.exists() else 0,
    )


@router.post("/rag_answer", response_model=RAGAnswerResponse)
def rag_answer(req: RAGAnswerRequest) -> RAGAnswerResponse:
    """Answer a study question via `jw_agents.research_topic` if available."""

    topic = req.topic or req.question
    try:
        from jw_agents import research_topic as _research
    except ImportError:
        return RAGAnswerResponse(
            question=req.question,
            note="research_topic agent unavailable",
        )
    try:
        result = _research(
            topic=topic, language=req.language, max_results=req.top_k
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=500, detail=f"research_topic failed: {exc}"
        ) from exc

    findings_raw = getattr(result, "findings", None) or []
    findings: list[dict[str, Any]] = []
    for f in findings_raw:
        if hasattr(f, "model_dump"):
            findings.append(f.model_dump(mode="json"))
        elif isinstance(f, dict):
            findings.append(f)
        else:
            findings.append({"value": str(f)})

    return RAGAnswerResponse(question=req.question, findings=findings)


__all__ = [
    "AnalyzeRequest",
    "RAGAnswerRequest",
    "RAGAnswerResponse",
    "TTSRequest",
    "TTSResponse",
    "router",
]
