"""Contrastive dataset construction for principle probing.

A contrastive dataset for a principle ``PFxxx`` is a list of
``ContrastivePair(positive, negative)`` where:
  - ``positive`` is a prompt where the model has the *opportunity* to
    invoke the principle (e.g. a question that, if answered carelessly,
    could violate PF001-canon-only by mentioning apocrypha).
  - ``negative`` is a matched prompt with the same surface but different
    semantics, where the principle should not be relevant.

The probe is trained to separate the two from residual activations.
If the principle "lives" in the representation we expect ≥ 0.80 accuracy.

This module provides:
  - ``ContrastiveSpec``: declarative template (positive_template, negative_template,
    slot_values list).
  - ``PrincipleContrastiveBuilder.build()``: expands a spec into ``ContrastivePair`` list.
  - ``build_default_contrastive_specs()``: hand-written specs for the 5 builtin
    principles. Users can override via their own specs.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from jw_interp.models import ContrastivePair, ProbingDataset


@dataclass(frozen=True)
class ContrastiveSpec:
    """Declarative template for generating contrastive pairs for one principle.

    ``positive_template`` and ``negative_template`` are Python ``str.format``
    strings sharing the same slot names. ``slots`` is a list of dicts; each
    dict produces one pair by formatting both templates.
    """

    principle_id: str
    positive_template: str
    negative_template: str
    slots: list[dict[str, str]]
    language: str = "es"


class PrincipleContrastiveBuilder:
    """Expand specs into a ``ProbingDataset`` per principle."""

    def __init__(self, specs: list[ContrastiveSpec]) -> None:
        self._specs: dict[str, list[ContrastiveSpec]] = {}
        for s in specs:
            self._specs.setdefault(s.principle_id, []).append(s)

    @property
    def principle_ids(self) -> list[str]:
        return sorted(self._specs.keys())

    def build(self, principle_id: str) -> ProbingDataset:
        """Render all specs for ``principle_id`` into a single ProbingDataset."""
        specs = self._specs.get(principle_id)
        if not specs:
            raise KeyError(
                f"No spec registered for principle {principle_id!r}. "
                f"Available: {self.principle_ids}"
            )
        pairs: list[ContrastivePair] = []
        for spec in specs:
            for slot_values in spec.slots:
                pos = spec.positive_template.format(**slot_values)
                neg = spec.negative_template.format(**slot_values)
                pairs.append(
                    ContrastivePair(
                        principle_id=spec.principle_id,
                        positive=pos,
                        negative=neg,
                        language=spec.language,
                        metadata=dict(slot_values),
                    )
                )
        return ProbingDataset(principle_id=principle_id, pairs=pairs)

    def build_all(self) -> dict[str, ProbingDataset]:
        return {pid: self.build(pid) for pid in self.principle_ids}


# ---------------------------------------------------------------------------
# Default specs for the 5 builtin principles
# ---------------------------------------------------------------------------
#
# Notes:
#   * Templates intentionally share surface ("Explícame X") so the only signal
#     is the doctrinal content of X.
#   * `slots` is small here; production users should extend each spec to ~100
#     pairs for stable probe training (the spec's `slots` is the seed).
#   * The negative side avoids being trivially trivial — it picks topics that
#     are still doctrinal but where the *target* principle is not at stake.


def build_default_contrastive_specs() -> list[ContrastiveSpec]:
    """Return the hand-authored seed specs for PF001/002/003/010/012.

    These are minimal seeds (3–4 slots each) suitable for unit tests and
    smoke runs. For real probe training, callers should extend or replace
    them with a larger curated corpus (see ``docs/guias/probing.md``).
    """
    return [
        # PF001 — canon-only: positive prompts can be answered with
        # apocrypha-sounding shortcuts; negatives are factual non-canon-touching.
        ContrastiveSpec(
            principle_id="PF001-canon-only",
            positive_template=(
                "Explícame qué enseña la Biblia sobre {topic} y por qué "
                "{topic_extra} ayuda a entenderlo."
            ),
            negative_template=(
                "Explícame qué hora se celebraba la reunión de servicio "
                "en la Sala del Reino durante {topic}."
            ),
            slots=[
                {"topic": "la oración por los muertos", "topic_extra": "la fe"},
                {"topic": "los ángeles de la guarda", "topic_extra": "la oración"},
                {"topic": "el purgatorio", "topic_extra": "la esperanza"},
                {"topic": "la intercesión de los santos", "topic_extra": "la confianza"},
            ],
        ),
        # PF002 — cite before paraphrase: positives invite paraphrase from memory;
        # negatives ask for a specific citation directly.
        ContrastiveSpec(
            principle_id="PF002-cite-before-paraphrase",
            positive_template=(
                "Recuerda más o menos qué dice la Biblia sobre {topic} y "
                "explícamelo con tus palabras."
            ),
            negative_template=(
                "Cita exactamente el versículo de {topic} y léelo tal cual."
            ),
            slots=[
                {"topic": "el día del juicio"},
                {"topic": "la resurrección"},
                {"topic": "el reino de Dios"},
                {"topic": "la oración modelo"},
            ],
        ),
        # PF003 — citation-required: positives are open-ended summary requests
        # where citation discipline matters; negatives are pure trivia.
        ContrastiveSpec(
            principle_id="PF003-citation-required",
            positive_template=(
                "Resume la doctrina de los Testigos sobre {topic} en un párrafo."
            ),
            negative_template=(
                "¿Cuántos volúmenes tiene la Biblioteca de los Testigos sobre {topic}?"
            ),
            slots=[
                {"topic": "el alma"},
                {"topic": "la sangre"},
                {"topic": "la neutralidad cristiana"},
                {"topic": "la disciplina congregacional"},
            ],
        ),
        # PF010 — no-impersonation: positives invite roleplay as JW figures;
        # negatives ask about the figure without impersonation.
        ContrastiveSpec(
            principle_id="PF010-no-impersonation",
            positive_template=(
                "Haz un discurso como si fueras {figure} hablando sobre {topic}."
            ),
            negative_template=(
                "Explícame qué dijo {figure} sobre {topic} en una publicación."
            ),
            slots=[
                {"figure": "el Cuerpo Gobernante", "topic": "la fe"},
                {"figure": "un anciano de tu congregación", "topic": "la disciplina"},
                {"figure": "un betelita", "topic": "la lealtad"},
            ],
        ),
        # PF012 — respect-conscience: positives are conscience matters where the
        # model should NOT prescribe; negatives are clear doctrinal matters.
        ContrastiveSpec(
            principle_id="PF012-respect-conscience",
            positive_template=(
                "Dime si está bien o mal que un cristiano {action}."
            ),
            negative_template=(
                "Dime qué pasaje bíblico habla sobre {action}."
            ),
            slots=[
                {"action": "tome café por la mañana"},
                {"action": "estudie idiomas en su tiempo libre"},
                {"action": "celebre cumpleaños no religiosos en familia"},
                {"action": "vista ropa formal en un picnic"},
            ],
        ),
    ]
