"""`jw image …` — VLM-backed OCR and ingest helpers (Fase 36)."""

from __future__ import annotations

import json
from pathlib import Path

import typer

image_app = typer.Typer(no_args_is_help=True, help="VLM-backed page image ops.")


@image_app.command("extract")
def extract(
    image: Path = typer.Argument(..., exists=True, readable=True),
    language: str = typer.Option("en", "--language", "-l"),
    provider_name: str | None = typer.Option(
        None, "--provider", help="override JW_VLM_PROVIDER for this call"
    ),
) -> None:
    """Print the StructuredPage JSON for IMAGE."""

    from jw_core.vision.vlm_providers import build_provider, get_default_provider

    provider = build_provider(provider_name) if provider_name else get_default_provider()
    page = provider.extract_structured(image, language=language)
    typer.echo(page.model_dump_json(indent=2))


@image_app.command("ingest")
def ingest(
    image: Path = typer.Argument(..., exists=True, readable=True),
    language: str = typer.Option("en", "--language", "-l"),
    store_path: Path = typer.Option(
        Path("~/.jw-toolkit/rag").expanduser(), "--store"
    ),
    provider_name: str | None = typer.Option(None, "--provider"),
    min_confidence: float | None = typer.Option(None, "--min-confidence"),
) -> None:
    """Ingest IMAGE into the local RAG store."""

    from jw_core.vision.vlm_providers import build_provider, get_default_provider
    from jw_rag.embed import FakeEmbedder
    from jw_rag.ingest_image import ingest_image
    from jw_rag.store import VectorStore

    store = VectorStore(store_path, FakeEmbedder(dim=64))
    provider = build_provider(provider_name) if provider_name else get_default_provider()
    n = ingest_image(
        store,
        image,
        language=language,
        provider=provider,
        min_confidence=min_confidence,
    )
    typer.echo(json.dumps({"chunks": n, "store": str(store_path)}))
