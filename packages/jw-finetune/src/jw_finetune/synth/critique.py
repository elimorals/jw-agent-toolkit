"""SL-CAI: self-critique + revise loop for synth Q&A pairs.

This is the supervised half of Constitutional AI applied to dataset
generation (not to a generalist assistant). For each generated
`(question, answer)`, we ask the LLM to:

  1. Read the principles (`jw_eval.principles.Principle`) that apply
     to the synth context (e.g. "doctrinal" qa_style).
  2. Critique the answer against them.
  3. If any `hard` principle is violated OR the regex tier flags the
     answer, produce a revised answer that fixes it.

The revised pair replaces the original in the dataset. Originals can
optionally be kept under `metadata.original_answer` for audit. Cost:
~1 extra LLM call per pair, so ~+30% tokens; turn off with `enabled=False`
when generating the baseline (rejected) side for DPO pairs.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from jinja2 import Environment, StrictUndefined

from jw_finetune.data.formats import QAPair
from jw_finetune.synth.provider import LLMProvider, LLMRequest

if TYPE_CHECKING:
    from jw_eval.principles import Principle

logger = logging.getLogger(__name__)


_CRITIQUE_PROMPT_ES = """\
Eres un revisor de fidelidad doctrinal de los testigos de Jehová.
Revisa la siguiente respuesta contra los principios listados.

PRINCIPIOS APLICABLES:
{% for p in principles -%}
- [{{ p.id }} | {{ p.severity }}] {{ p.rationale }}
{% endfor %}

PREGUNTA: {{ question }}
RESPUESTA: {{ answer }}

Si la respuesta viola algún principio severidad `hard`, reescríbela
manteniendo la cita y la enseñanza original pero corrigiendo la violación.
Si no viola ninguno, devuelve la respuesta tal cual.

Devuelve SOLO la respuesta revisada (o la original si no hay cambios),
sin explicaciones, sin "Respuesta revisada:", sin comillas.
"""

_CRITIQUE_PROMPT_EN = """\
You review answers for doctrinal fidelity to Jehovah's Witnesses publications.
Review the following answer against the listed principles.

APPLICABLE PRINCIPLES:
{% for p in principles -%}
- [{{ p.id }} | {{ p.severity }}] {{ p.rationale }}
{% endfor %}

QUESTION: {{ question }}
ANSWER: {{ answer }}

If the answer violates any `hard` principle, rewrite it preserving the
citation and the original teaching but fixing the violation. If no
violation, return the answer as-is.

Return ONLY the revised answer (or the original if unchanged), with
no preface, no "Revised answer:", no quotes.
"""


def _env() -> Environment:
    return Environment(
        undefined=StrictUndefined,
        autoescape=False,
        trim_blocks=True,
        lstrip_blocks=True,
    )


@dataclass
class CritiqueResult:
    """Outcome of one critique pass."""

    revised: QAPair
    changed: bool
    violated_principle_ids: list[str] = field(default_factory=list)
    original_answer: str = ""


def self_critique(
    pair: QAPair,
    *,
    principles: list[Principle],
    llm_provider: LLMProvider,
    agent: str | None = None,
    preserve_original: bool = True,
) -> CritiqueResult:
    """Run one SL-CAI pass on `pair`. Returns the (possibly) revised pair.

    Behaviour:
      - Filters principles to those that `applies(agent)` is True.
      - Cheap regex tier first (`violations_for`) — if no hits AND no
        principles apply, skip the LLM call entirely.
      - Otherwise asks the LLM to revise. If the LLM returns empty/error,
        keeps the original.

    `preserve_original` stashes the original answer under
    `metadata["original_answer"]` for downstream audit.
    """

    from jw_eval.principles import violations_for

    applicable = [p for p in principles if p.applies(agent)]
    if not applicable:
        return CritiqueResult(revised=pair, changed=False)

    hit = violations_for(pair.answer, applicable)
    if not hit:
        return CritiqueResult(revised=pair, changed=False)

    hard_ids = [p.id for p in hit if p.severity == "hard"]
    template_src = _CRITIQUE_PROMPT_ES if pair.language.startswith("es") else _CRITIQUE_PROMPT_EN
    prompt = (
        _env()
        .from_string(template_src)
        .render(
            principles=applicable,
            question=pair.question,
            answer=pair.answer,
        )
    )

    try:
        resp = llm_provider.generate(
            LLMRequest(
                system=(
                    "Eres un revisor de fidelidad doctrinal."
                    if pair.language.startswith("es")
                    else "You review doctrinal fidelity."
                ),
                user=prompt,
                temperature=0.2,
                max_tokens=1024,
            )
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("self_critique LLM call failed: %s — keeping original", exc)
        return CritiqueResult(
            revised=pair,
            changed=False,
            violated_principle_ids=hard_ids,
            original_answer=pair.answer,
        )

    revised_text = (resp.text or "").strip()
    if not revised_text or revised_text == pair.answer.strip():
        return CritiqueResult(
            revised=pair,
            changed=False,
            violated_principle_ids=hard_ids,
            original_answer=pair.answer,
        )

    new_metadata: dict[str, str] = dict(pair.metadata)
    new_metadata["sl_cai_revised"] = "true"
    new_metadata["sl_cai_principles"] = ",".join(hard_ids)
    if preserve_original:
        new_metadata["original_answer"] = pair.answer

    revised_pair = QAPair(
        question=pair.question,
        answer=revised_text,
        source_chunk_id=pair.source_chunk_id,
        language=pair.language,
        metadata=new_metadata,
    )
    return CritiqueResult(
        revised=revised_pair,
        changed=True,
        violated_principle_ids=hard_ids,
        original_answer=pair.answer,
    )


def batch_critique(
    pairs: list[QAPair],
    *,
    principles: list[Principle],
    llm_provider: LLMProvider,
    agent: str | None = None,
) -> tuple[list[QAPair], int]:
    """Run self_critique over every pair. Returns (revised_pairs, num_changed)."""

    out: list[QAPair] = []
    changed = 0
    for p in pairs:
        result = self_critique(
            p,
            principles=principles,
            llm_provider=llm_provider,
            agent=agent,
        )
        out.append(result.revised)
        if result.changed:
            changed += 1
    return out, changed
