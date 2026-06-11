"""End-to-end engine tests (Fase 70).

We never invoke real OCR (Tesseract) here — we pass `ocr_text_override`
so the pipeline can be exercised without optional deps.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from jw_core.verification.image_quote.engine import verify_image_quote
from jw_core.verification.image_quote.models import ImageQuoteVerdict


def _write_jpeg(p: Path) -> None:
    Image.new("RGB", (32, 32), color=(120, 200, 80)).save(p, "JPEG")


class FakeHit:
    def __init__(
        self,
        *,
        url: str = "https://wol.jw.org/x",
        pub_code: str = "w23.04",
        text: str = "amó tanto al mundo",
    ) -> None:
        self.source_url = url
        self.source_pub_code = pub_code
        self.source_text_original = text


class FakeNLIVerdict:
    def __init__(self, verdict: str = "entails", score: float = 0.92) -> None:
        self.verdict = verdict
        self.score = score


class FakeNLI:
    def __init__(self, verdict: str = "entails", score: float = 0.92) -> None:
        self._v = verdict
        self._s = score

    def evaluate_entailment(self, *, claim: str, premise: str) -> FakeNLIVerdict:  # noqa: ARG002
        return FakeNLIVerdict(self._v, self._s)


@pytest.mark.asyncio
async def test_verify_supported_path(tmp_path: Path) -> None:
    img = tmp_path / "x.jpg"
    _write_jpeg(img)

    async def retriever(_q: str) -> list[FakeHit]:
        return [FakeHit()]

    out = await verify_image_quote(
        str(img),
        language="es",
        retriever=retriever,
        nli=FakeNLI("entails", 0.93),
        ocr_text_override=(
            "Que el amor de Jehová guíe nuestras decisiones, "
            "y el reino que mencionamos es el suyo, según se enseña."
        ),
    )
    assert isinstance(out, ImageQuoteVerdict)
    assert out.verdict == "SUPPORTED"
    assert out.confidence >= 0.85
    assert out.suggested_action == "share_with_correct_link"


@pytest.mark.asyncio
async def test_verify_fabricated_when_no_hits_and_anomalies(
    tmp_path: Path,
) -> None:
    img = tmp_path / "x.jpg"
    _write_jpeg(img)

    out = await verify_image_quote(
        str(img),
        retriever=None,
        nli=None,
        ocr_text_override=(
            "Que el amor de Jehová guíe a sus testigos según el reino prometido."
        ),
        vlm_description="font mismatch in headline and altered logo",
    )
    assert out.verdict == "FABRICATED"
    assert out.suggested_action == "do_not_share"
    assert "font_mismatch" in out.visual_fingerprint.visual_anomalies


@pytest.mark.asyncio
async def test_verify_unverifiable_when_short_quote(tmp_path: Path) -> None:
    img = tmp_path / "x.jpg"
    _write_jpeg(img)
    out = await verify_image_quote(
        str(img),
        retriever=None,
        nli=None,
        ocr_text_override="hi",
    )
    assert out.verdict == "UNVERIFIABLE"
    assert out.suggested_action == "discuss_with_elders"


@pytest.mark.asyncio
async def test_verify_distorted_when_contradicts(tmp_path: Path) -> None:
    img = tmp_path / "x.jpg"
    _write_jpeg(img)

    async def retriever(_q: str) -> list[FakeHit]:
        return [FakeHit()]

    out = await verify_image_quote(
        str(img),
        retriever=retriever,
        nli=FakeNLI("contradicts", 0.9),
        ocr_text_override=(
            "Que el amor de Jehová guíe nuestras decisiones desde el reino."
        ),
    )
    assert out.verdict == "DISTORTED"
    assert out.suggested_action == "share_corrected_version"


@pytest.mark.asyncio
async def test_verify_retriever_exception_degrades_gracefully(
    tmp_path: Path,
) -> None:
    img = tmp_path / "x.jpg"
    _write_jpeg(img)

    async def boom(_q: str):
        raise RuntimeError("rag down")

    out = await verify_image_quote(
        str(img),
        retriever=boom,
        nli=FakeNLI(),
        ocr_text_override=(
            "Que el amor de Jehová guíe nuestras decisiones según se enseña."
        ),
    )
    # No matches -> UNVERIFIABLE (no anomalies)
    assert out.verdict == "UNVERIFIABLE"


@pytest.mark.asyncio
async def test_verify_populates_visual_fingerprint(tmp_path: Path) -> None:
    img = tmp_path / "x.jpg"
    _write_jpeg(img)

    out = await verify_image_quote(
        str(img),
        retriever=None,
        nli=None,
        ocr_text_override=(
            "Atalaya. Que el amor de Jehová guíe nuestras decisiones, "
            "según el reino que viene."
        ),
        vlm_description="Cover of Atalaya magazine, primary colors bold style",
    )
    assert out.visual_fingerprint.image_format == "JPEG"
    assert out.visual_fingerprint.image_size == (32, 32)
    assert out.visual_fingerprint.apparent_publication == "Atalaya"
    assert out.visual_fingerprint.apparent_era == "1980s"
    assert out.visual_fingerprint.image_phash
