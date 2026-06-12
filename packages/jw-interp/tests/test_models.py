"""Tests for jw_interp.models."""

from __future__ import annotations

import numpy as np
import pytest

from jw_interp.models import ActivationBatch, ContrastivePair, ProbingDataset


def test_contrastive_pair_immutable() -> None:
    p = ContrastivePair(
        principle_id="PF001",
        positive="pos",
        negative="neg",
    )
    assert p.language == "es"
    with pytest.raises(Exception):
        p.positive = "other"  # type: ignore[misc]


def test_activation_batch_validates_shape() -> None:
    acts = np.zeros((4, 8), dtype=np.float32)
    labels = np.array([True, False, True, False])
    ids = ["a", "b", "c", "d"]
    batch = ActivationBatch(
        layer=0,
        hook_name="resid_post",
        activations=acts,
        labels=labels,
        prompt_ids=ids,
    )
    assert batch.activations.shape == (4, 8)


def test_activation_batch_rejects_mismatched_labels() -> None:
    acts = np.zeros((4, 8), dtype=np.float32)
    labels = np.array([True, False])  # wrong length
    with pytest.raises(ValueError, match="labels length"):
        ActivationBatch(
            layer=0,
            hook_name="resid_post",
            activations=acts,
            labels=labels,
            prompt_ids=["a", "b", "c", "d"],
        )


def test_activation_batch_rejects_3d_activations() -> None:
    acts = np.zeros((4, 8, 2), dtype=np.float32)
    labels = np.array([True, False, True, False])
    with pytest.raises(ValueError, match="must be 2D"):
        ActivationBatch(
            layer=0,
            hook_name="resid_post",
            activations=acts,
            labels=labels,
            prompt_ids=["a", "b", "c", "d"],
        )


def test_probing_dataset_flat_prompts_order_and_labels() -> None:
    ds = ProbingDataset(
        principle_id="PF001",
        pairs=[
            ContrastivePair(principle_id="PF001", positive="p1+", negative="p1-"),
            ContrastivePair(principle_id="PF001", positive="p2+", negative="p2-"),
        ],
    )
    flat = ds.flat_prompts()
    assert ds.n_pairs == 2
    assert ds.n_prompts == 4
    assert [text for text, _, _ in flat] == ["p1+", "p1-", "p2+", "p2-"]
    assert [is_pos for _, is_pos, _ in flat] == [True, False, True, False]
    # prompt_ids are unique and identifiable
    assert flat[0][2].endswith("::pos")
    assert flat[1][2].endswith("::neg")
