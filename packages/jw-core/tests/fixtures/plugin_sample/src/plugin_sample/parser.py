"""Parser stub."""

from __future__ import annotations


def sample_parser(raw: bytes | str, *, source_url: str | None = None) -> dict:
    text = raw.decode("utf-8") if isinstance(raw, bytes) else raw
    return {
        "text": text,
        "source_url": source_url,
        "parser": "plugin_sample_parser",
    }


sample_parser.extensions = [".sample"]  # type: ignore[attr-defined]
sample_parser.mime_types = ["application/x-plugin-sample"]  # type: ignore[attr-defined]
