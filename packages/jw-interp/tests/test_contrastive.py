"""Tests for jw_interp.contrastive."""

from __future__ import annotations

import pytest

from jw_interp.contrastive import (
    ContrastiveSpec,
    PrincipleContrastiveBuilder,
    build_default_contrastive_specs,
)


def test_builder_expands_spec_into_pairs() -> None:
    spec = ContrastiveSpec(
        principle_id="PF-test",
        positive_template="pregunta positiva {topic}",
        negative_template="pregunta neutral {topic}",
        slots=[{"topic": "A"}, {"topic": "B"}, {"topic": "C"}],
    )
    builder = PrincipleContrastiveBuilder([spec])
    ds = builder.build("PF-test")
    assert ds.n_pairs == 3
    assert ds.pairs[0].positive == "pregunta positiva A"
    assert ds.pairs[0].negative == "pregunta neutral A"
    assert ds.pairs[0].metadata == {"topic": "A"}


def test_builder_handles_multiple_specs_per_principle() -> None:
    spec_a = ContrastiveSpec(
        principle_id="PF-test",
        positive_template="pos1 {x}",
        negative_template="neg1 {x}",
        slots=[{"x": "1"}, {"x": "2"}],
    )
    spec_b = ContrastiveSpec(
        principle_id="PF-test",
        positive_template="pos2 {x}",
        negative_template="neg2 {x}",
        slots=[{"x": "3"}],
    )
    builder = PrincipleContrastiveBuilder([spec_a, spec_b])
    ds = builder.build("PF-test")
    assert ds.n_pairs == 3
    positives = [p.positive for p in ds.pairs]
    assert "pos1 1" in positives
    assert "pos2 3" in positives


def test_builder_raises_on_missing_principle() -> None:
    builder = PrincipleContrastiveBuilder([])
    with pytest.raises(KeyError, match="No spec registered"):
        builder.build("PF-nope")


def test_build_all_covers_every_principle() -> None:
    specs = build_default_contrastive_specs()
    builder = PrincipleContrastiveBuilder(specs)
    by_id = builder.build_all()
    assert set(by_id.keys()) == {
        "PF001-canon-only",
        "PF002-cite-before-paraphrase",
        "PF003-citation-required",
        "PF010-no-impersonation",
        "PF012-respect-conscience",
    }
    # Every default spec should produce at least 3 pairs (seed minimum).
    for pid, ds in by_id.items():
        assert ds.n_pairs >= 3, f"{pid} produced only {ds.n_pairs} pairs"


def test_default_specs_positive_and_negative_differ() -> None:
    builder = PrincipleContrastiveBuilder(build_default_contrastive_specs())
    for pid in builder.principle_ids:
        ds = builder.build(pid)
        for pair in ds.pairs:
            assert pair.positive != pair.negative, (
                f"{pid}: positive==negative for pair {pair.metadata}"
            )
