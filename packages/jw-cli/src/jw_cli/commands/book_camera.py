"""``jw book-camera`` - live camera for physical books (Fase 71)."""

from __future__ import annotations

import typer
from rich.console import Console

from jw_core.book_camera.engine import analyze_capture

book_camera_app = typer.Typer(
    help="Cámara en vivo para libros físicos (Fase 71).",
    no_args_is_help=True,
)
console = Console()


@book_camera_app.command("analyze")
def cmd_analyze(
    image: str | None = typer.Option(
        None, "--image", "-i", help="Path to captured image (will run OCR)."
    ),
    ocr_text: str | None = typer.Option(
        None,
        "--ocr-text",
        "-t",
        help="Bypass OCR: provide already-extracted text.",
    ),
    language: str = typer.Option("es", "--language", "-l"),
) -> None:
    """Analyze a capture and print a `CameraFrameResult`."""

    if image is None and ocr_text is None:
        console.print(
            "[red]error:[/] one of --image or --ocr-text is required."
        )
        raise typer.Exit(code=1)
    result = analyze_capture(
        image_path=image,
        ocr_text=ocr_text,
        language=language,
    )
    console.print_json(result.model_dump_json())


@book_camera_app.command("kinds")
def cmd_kinds() -> None:
    """List the content kinds the classifier produces."""

    console.print(
        [
            "bible_verse",
            "study_question",
            "watchtower_paragraph",
            "plain_text",
            "unknown",
        ]
    )
