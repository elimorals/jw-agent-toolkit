"""Smoke tests for trainers — verify they raise ImportError without GPU stack.

The real training is GPU-bound; we skip it unless Unsloth is installed.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from jw_finetune.data.models import SourceSpec
from jw_finetune.recipes.base import Recipe


def _has_unsloth() -> bool:
    try:
        import unsloth  # noqa: F401  # type: ignore[import-untyped]
        return True
    except ImportError:
        return False


def _recipe() -> Recipe:
    return Recipe(
        name="smoke",
        task="sft",
        sources=[SourceSpec(kind="jwpub", path="x", language="es")],
        languages=["es"],
        publication_kinds=["watchtower"],
        qa_style="doctrinal",
        base_model="unsloth/Qwen2.5-3B-bnb-4bit",
    )


def test_train_sft_no_dataset_raises_filenotfound(tmp_path: Path) -> None:
    from jw_finetune.train.sft import train_sft

    with pytest.raises(FileNotFoundError):
        train_sft(_recipe(), tmp_path / "missing.jsonl", tmp_path / "ws")


def test_train_cpt_no_dataset_raises_filenotfound(tmp_path: Path) -> None:
    from jw_finetune.train.cpt import train_cpt

    with pytest.raises(FileNotFoundError):
        train_cpt(_recipe(), tmp_path / "missing.jsonl", tmp_path / "ws")


@pytest.mark.skipif(_has_unsloth(), reason="Unsloth installed — would actually try to train")
def test_train_sft_without_unsloth_raises_import(tmp_path: Path) -> None:
    """When Unsloth isn't installed and dataset exists, function imports fail."""
    from jw_finetune.train.sft import train_sft

    dataset = tmp_path / "ds.jsonl"
    dataset.write_text("{}\n", encoding="utf-8")
    with pytest.raises((ImportError, ModuleNotFoundError)):
        train_sft(_recipe(), dataset, tmp_path / "ws")
