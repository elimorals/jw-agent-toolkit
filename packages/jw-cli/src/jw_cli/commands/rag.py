"""`jw rag …` — RAG indexing and search commands (Fase 37: visual subcommands)."""

from __future__ import annotations

import os
from pathlib import Path

import typer

rag_app = typer.Typer(
    name="rag",
    help="RAG indexing and search over the local corpus.",
    no_args_is_help=True,
)


# --- Fase 37: Visual RAG commands ----------------------------------------


@rag_app.command("ingest-visual")
def ingest_visual(
    path: Path = typer.Argument(..., exists=True, dir_okay=False, readable=True),
    store_path: Path = typer.Option(Path("./jw-rag-store/visual"), "--store", help="Visual store directory."),
    force: bool = typer.Option(False, "--force", help="Re-ingest even if already indexed."),
    language: str = typer.Option("", "--language", "-l", help="Language tag in chunk metadata."),
) -> None:
    """Rasterize and index a JWPUB/EPUB/PDF into the visual store."""
    if os.environ.get("JW_VISUAL_ENABLED", "1") == "0":
        typer.echo("JW_VISUAL_ENABLED=0 — visual subsystem disabled.", err=True)
        raise typer.Exit(2)
    from jw_rag.visual import (
        ConfigError,
        VisualVectorStore,
        get_default_visual_embedder,
        ingest_path_visual,
    )

    try:
        embedder = get_default_visual_embedder()
    except ConfigError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(3) from exc

    store = VisualVectorStore(store_path, embedder)
    try:
        store.load()
    except Exception as exc:  # noqa: BLE001
        typer.echo(f"warn: load failed ({exc}); starting fresh", err=True)
    result = ingest_path_visual(path, store, language=language, force=force)
    typer.echo(f"added={result.pages_added} skipped={result.pages_skipped} duration_ms={result.duration_ms}")


@rag_app.command("search-visual")
def search_visual(
    query: str = typer.Argument(...),
    text_store: Path = typer.Option(Path("./jw-rag-store"), "--text-store"),
    visual_store: Path = typer.Option(Path("./jw-rag-store/visual"), "--visual-store"),
    top_k: int = typer.Option(10, "--top-k", "-k"),
) -> None:
    """Hybrid search across text store + visual store via RRF."""
    if os.environ.get("JW_VISUAL_ENABLED", "1") == "0":
        typer.echo("JW_VISUAL_ENABLED=0 — visual subsystem disabled.", err=True)
        raise typer.Exit(2)
    from jw_rag.embed import FakeEmbedder
    from jw_rag.store import VectorStore
    from jw_rag.visual import (
        ConfigError,
        VisualVectorStore,
        get_default_visual_embedder,
        hybrid_search_with_visual,
    )

    text = VectorStore(text_store, FakeEmbedder())
    text.load()

    visual: VisualVectorStore | None
    try:
        v_embedder = get_default_visual_embedder()
        visual = VisualVectorStore(visual_store, v_embedder)
        visual.load()
    except ConfigError as exc:
        typer.echo(f"info: visual disabled ({exc.__class__.__name__}); text-only", err=True)
        visual = None

    hits = hybrid_search_with_visual(text, visual, query, top_k=top_k)
    for h in hits:
        marker = "[VISUAL]" if h.source == "visual" else "[TEXT]"
        typer.echo(f"{marker} {h.rank}. score={h.score:.4f} id={h.chunk.id}")


# --- Fase 62: marker + markitdown ingest commands ------------------------


def _open_text_store(store_path: Path) -> "object":
    """Load (or create) the text VectorStore using a deterministic
    FakeEmbedder so the CLI never reaches for a heavyweight model
    just to write chunks. Tests + CI rely on this — production users
    that already loaded the store with a real embedder should reuse
    the same dim, which FakeEmbedder's default does not guarantee.
    For F62 the focus is ingestion smoke, not retrieval quality.
    """
    from jw_rag.embed import FakeEmbedder
    from jw_rag.store import VectorStore

    store = VectorStore(store_path, FakeEmbedder())
    try:
        store.load()
    except Exception as exc:  # noqa: BLE001
        typer.echo(f"warn: load failed ({exc}); starting fresh", err=True)
    return store


@rag_app.command("ingest-pdf")
def ingest_pdf_cmd(
    path: Path = typer.Argument(
        ..., exists=True, dir_okay=False, readable=True, help="PDF a ingerir"
    ),
    store_path: Path = typer.Option(
        Path("./jw-rag-store"), "--store", help="Directorio del text store."
    ),
    language: str = typer.Option(
        "en", "--language", "-l", help="Código de idioma (en/es/pt/...)."
    ),
    chunker: str | None = typer.Option(
        None, "--chunker", help="Nombre del chunker (None = default)."
    ),
) -> None:
    """Ingiere un PDF al text store usando marker (Fase 62).

    CPU-only por default. Para GPU/LLM:
        JW_MARKER_USE_GPU=1 JW_MARKER_USE_LLM=1 jw rag ingest-pdf <path>
    """
    from jw_rag.loaders.pdf_marker import ingest_pdf as _impl

    store = _open_text_store(store_path)
    try:
        n = _impl(store, path, language=language, chunker=chunker)
    except ModuleNotFoundError as exc:
        # marker-pdf is imported lazily inside the loader, so a missing
        # extra surfaces here, not at module-import time.
        typer.echo(f"{exc}", err=True)
        raise typer.Exit(3) from exc
    store.save()  # type: ignore[attr-defined]
    typer.echo(f"Ingested {n} chunks from {path}")


@rag_app.command("ingest-office")
def ingest_office_cmd(
    path: Path = typer.Argument(
        ...,
        exists=True,
        dir_okay=False,
        readable=True,
        help="Ruta a .docx/.pptx/.xlsx",
    ),
    store_path: Path = typer.Option(
        Path("./jw-rag-store"), "--store", help="Directorio del text store."
    ),
    language: str = typer.Option("en", "--language", "-l"),
    chunker: str | None = typer.Option(None, "--chunker"),
) -> None:
    """Ingiere un .docx/.pptx/.xlsx al text store via markitdown (Fase 62)."""
    from jw_rag.loaders.docs_markitdown import ingest_office_doc as _impl

    store = _open_text_store(store_path)
    try:
        n = _impl(store, path, language=language, chunker=chunker)
    except ModuleNotFoundError as exc:
        # markitdown is imported lazily inside the loader, so a missing
        # extra surfaces here, not at module-import time.
        typer.echo(f"{exc}", err=True)
        raise typer.Exit(3) from exc
    store.save()  # type: ignore[attr-defined]
    typer.echo(f"Ingested {n} chunks from {path}")
