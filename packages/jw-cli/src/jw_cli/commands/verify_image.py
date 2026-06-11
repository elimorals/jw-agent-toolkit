"""``jw verify-image`` - defensive visual quote verifier CLI (Fase 70)."""

from __future__ import annotations

import asyncio

import typer
from rich.console import Console

from jw_core.verification.image_quote.engine import verify_image_quote

verify_image_app = typer.Typer(
    help="Verificador de citas en imágenes (Fase 70).",
    no_args_is_help=True,
)
console = Console()


@verify_image_app.command("check")
def cmd_check(
    image: str = typer.Argument(..., help="Local image path (PNG/JPEG)."),
    language: str = typer.Option("es", "--language", "-l"),
    ocr_override: str | None = typer.Option(
        None,
        "--ocr-text",
        help=(
            "Bypass Tesseract: provide OCR text directly. Useful when "
            "Tesseract is not installed or the image text is already known."
        ),
    ),
    vlm_description: str = typer.Option(
        "",
        "--vlm-description",
        help="Visual description hint (e.g. from an external VLM).",
    ),
    brief: bool = typer.Option(
        False, "--brief", help="Print only verdict + confidence + action."
    ),
) -> None:
    """Verify an image quote and print the verdict JSON."""

    verdict = asyncio.run(
        verify_image_quote(
            image,
            language=language,
            retriever=None,  # CLI default: no RAG retrieval
            nli=None,  # CLI default: no NLI (will UNVERIFIABLE)
            ocr_text_override=ocr_override,
            vlm_description=vlm_description,
        )
    )
    if brief:
        console.print(
            {
                "verdict": verdict.verdict,
                "confidence": verdict.confidence,
                "suggested_action": verdict.suggested_action,
            }
        )
        return
    console.print_json(verdict.model_dump_json())


@verify_image_app.command("verdicts")
def cmd_verdicts() -> None:
    """List the 4 possible verdicts with their suggested actions."""

    console.print(
        {
            "SUPPORTED": "share_with_correct_link",
            "DISTORTED": "share_corrected_version",
            "FABRICATED": "do_not_share",
            "UNVERIFIABLE": "discuss_with_elders",
        }
    )
