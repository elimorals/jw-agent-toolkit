#!/usr/bin/env python3
"""Omnilingual ASR worker — runs INSIDE the Python 3.12 dedicated venv.

Driven by `OmnilingualProvider.transcribe()` via subprocess. Reads CLI
args, runs the pipeline, prints a single JSON object to stdout. Errors
go to stderr (the parent surfaces them).

This file has NO imports of jw_core — it must be loadable from any
Python 3.12 venv that has omnilingual-asr installed, without the rest
of the monorepo on sys.path.
"""

from __future__ import annotations

import argparse
import json
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description="Omnilingual ASR worker")
    parser.add_argument("--audio", required=True, help="Path to audio file")
    parser.add_argument("--model-card", required=True, help="Omnilingual model card id")
    parser.add_argument("--lang", default=None, help="FLORES-200 language code, or omit for detect")
    args = parser.parse_args()

    try:
        from omnilingual_asr.models.inference.pipeline import ASRInferencePipeline
    except ImportError as exc:
        print(f"omnilingual_asr not importable: {exc!r}", file=sys.stderr)
        return 2

    try:
        pipeline = ASRInferencePipeline(model_card=args.model_card)
        kwargs = {"batch_size": 1}
        if args.lang:
            kwargs["lang"] = [args.lang]
        result = pipeline.transcribe([args.audio], **kwargs)
    except Exception as exc:  # noqa: BLE001
        print(f"pipeline failure: {exc!r}", file=sys.stderr)
        return 3

    text = _extract_text(result)
    print(json.dumps({"text": text, "language": args.lang or "und"}))
    return 0


def _extract_text(transcriptions: object) -> str:
    if not transcriptions:
        return ""
    if isinstance(transcriptions, list):
        first = transcriptions[0]
        if isinstance(first, str):
            return first
        if isinstance(first, dict):
            return str(first.get("text") or first.get("transcript") or first)
        return str(first)
    return str(transcriptions)


if __name__ == "__main__":
    sys.exit(main())
