"""Judge orchestrator — composes heuristics + LLM + NLI stages into a QAScore.

Public surface:
    Judge(mode, overrides, llm_provider, nli_provider).score(question, answer, language)
    score_qa_pair(question, answer, language, mode, ...) — functional shortcut

The judge is intentionally stateless beyond construction: each `.score()` call
is independent. This makes it trivial to compose with the async orchestrator
later (each chunk's pairs can be scored in parallel via threadpool).
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Protocol

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from jw_finetune.synth.judge.heuristics import (
    cites_jw_publication,
    has_minimum_substance,
)
from jw_finetune.synth.judge.models import QAScore, RejectionReason
from jw_finetune.synth.judge.nli_bridge import NLIProviderLike, run_nli_check
from jw_finetune.synth.judge.preference import PreferenceVerdict, compare_scores
from jw_finetune.synth.judge.scoring import compute_overall
from jw_finetune.synth.judge.thresholds import (
    JudgeMode,
    JudgeOverrides,
    resolve_cutoff,
    resolve_require_nli_entails,
)
from jw_finetune.synth.provider import LLMProvider, LLMRequest

logger = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).parent / "prompts"
_DIGIT_RE = re.compile(r"\b([0-3])\b")

_env_singleton: Environment | None = None


def _env() -> Environment:
    global _env_singleton
    if _env_singleton is None:
        _env_singleton = Environment(
            loader=FileSystemLoader(str(_PROMPTS_DIR)),
            undefined=StrictUndefined,
            autoescape=False,
            trim_blocks=True,
            lstrip_blocks=True,
        )
    return _env_singleton


def _template_for_language(language: str) -> str:
    code = (language or "en")[:2].lower()
    if code == "es":
        return "pedagogical_es.j2"
    if code == "pt":
        return "pedagogical_pt.j2"
    return "pedagogical_en.j2"


def _parse_pedagogical_response(text: str) -> int | None:
    """Tolerant parse of the LLM judge response: first 0..3 digit wins."""

    if not text:
        return None
    m = _DIGIT_RE.search(text.strip())
    if not m:
        return None
    n = int(m.group(1))
    if 0 <= n <= 3:
        return n
    return None


def _run_llm_pedagogical(
    *,
    question: str,
    answer: str,
    language: str,
    llm_provider: LLMProvider,
) -> int | None:
    """Render prompt → call LLM → parse digit. Returns None on any failure."""

    template_name = _template_for_language(language)
    try:
        prompt = (
            _env()
            .get_template(template_name)
            .render(question=question, answer=answer)
        )
    except Exception as exc:
        logger.debug("LLM judge prompt render failed: %s", exc)
        return None
    try:
        resp = llm_provider.generate(
            LLMRequest(
                system=(
                    "Eres un juez de calidad de datos. "
                    "Responde un solo dígito 0-3."
                ),
                user=prompt,
                temperature=0.0,
                max_tokens=8,
            )
        )
    except Exception as exc:
        logger.debug("LLM judge call failed: %s", exc)
        return None
    return _parse_pedagogical_response(resp.text)


class _MaybeNLIProvider(Protocol):
    def evaluate_entailment(self, *, claim: str, premise: str) -> object: ...


def score_qa_pair(
    *,
    question: str,
    answer: str,
    language: str,
    mode: JudgeMode,
    overrides: JudgeOverrides | None = None,
    llm_provider: LLMProvider | None = None,
    nli_provider: NLIProviderLike | _MaybeNLIProvider | None = None,
    principles: list[object] | None = None,
) -> QAScore:
    """Score a single Q&A pair. Returns a QAScore including the kept verdict.

    When ``principles`` is supplied (a list of `jw_eval.principles.Principle`),
    deterministic regex/phrase checks run first. A `hard` violation forces
    ``kept=False`` and adds a ``principle_hard_violation`` rejection reason.
    Soft violations are recorded but do not block.
    """

    if mode == JudgeMode.OFF:
        cites = cites_jw_publication(answer)
        substance = has_minimum_substance(question, answer)
        overall = compute_overall(
            cites=cites,
            substance=substance,
            nli_verdict=None,
            nli_score=None,
            pedagogical=None,
        )
        return QAScore(
            cites_jw_publication=cites,
            has_minimum_substance=substance,
            overall=overall,
            kept=True,
        )

    ov = overrides or JudgeOverrides()
    cutoff = resolve_cutoff(mode, ov)
    require_entails = resolve_require_nli_entails(mode, ov)

    reasons: list[RejectionReason] = []

    # Principle tier — deterministic regex checks first. Imported lazily
    # to avoid a hard dep on jw-eval at module-import time.
    principle_hard_hit = False
    if principles:
        try:
            from jw_eval.principles import violations_for  # type: ignore[import-not-found]
        except ImportError:
            violations_for = None  # type: ignore[assignment]
        if violations_for is not None:
            hit = violations_for(answer, principles)  # type: ignore[arg-type]
            for principle in hit:
                detail = f"{getattr(principle, 'id', '?')}"
                sev = getattr(principle, "severity", "soft")
                if sev == "hard":
                    principle_hard_hit = True
                    reasons.append(
                        RejectionReason(
                            code="principle_hard_violation",
                            detail=detail,
                        )
                    )

    cites = cites_jw_publication(answer)
    substance = has_minimum_substance(question, answer)
    if not cites:
        reasons.append(RejectionReason(code="no_jw_citation"))
    if not substance:
        reasons.append(RejectionReason(code="insufficient_substance"))

    pedagogical: int | None = None
    if llm_provider is not None:
        pedagogical = _run_llm_pedagogical(
            question=question,
            answer=answer,
            language=language,
            llm_provider=llm_provider,
        )
        if pedagogical is not None and pedagogical == 0:
            reasons.append(
                RejectionReason(code="pedagogical_low", detail="LLM scored 0/3")
            )

    nli_verdict: str | None = None
    nli_score: float | None = None
    nli_result = run_nli_check(answer=answer, nli_provider=nli_provider)  # type: ignore[arg-type]
    if nli_result is not None:
        nli_verdict, nli_score = nli_result
        if nli_verdict == "contradicts":
            reasons.append(
                RejectionReason(
                    code="nli_contradicts",
                    detail=f"score={nli_score:.2f}" if nli_score else "",
                )
            )
        elif nli_verdict == "neutral" and require_entails:
            reasons.append(
                RejectionReason(
                    code="nli_neutral_low",
                    detail="strict mode requires entails",
                )
            )

    overall = compute_overall(
        cites=cites,
        substance=substance,
        nli_verdict=nli_verdict,  # type: ignore[arg-type]
        nli_score=nli_score,
        pedagogical=pedagogical,
    )

    kept = True
    if cutoff is not None and overall < cutoff:
        kept = False
        reasons.append(
            RejectionReason(
                code="overall_below_threshold",
                detail=f"{overall:.2f} < {cutoff:.2f}",
            )
        )

    if not substance:
        kept = False
    if nli_verdict == "contradicts":
        kept = False
    if require_entails and nli_verdict == "neutral":
        kept = False
    if pedagogical == 0:
        kept = False
    if principle_hard_hit:
        kept = False

    return QAScore(
        cites_jw_publication=cites,
        has_minimum_substance=substance,
        nli_score=nli_score,
        nli_verdict=nli_verdict,  # type: ignore[arg-type]
        pedagogical_quality=pedagogical,
        overall=overall,
        kept=kept,
        reasons=reasons if not kept else [],
    )


class Judge:
    """Stateful wrapper that holds the configured providers + mode.

    F78 update: also holds an optional `principles` list (loaded from
    `jw_eval.principles`) and exposes `score_pair()` for pairwise
    comparisons used by the RLAIF preference-dataset generator.
    """

    def __init__(
        self,
        *,
        mode: JudgeMode,
        overrides: JudgeOverrides | None = None,
        llm_provider: LLMProvider | None = None,
        nli_provider: NLIProviderLike | None = None,
        principles: list[object] | None = None,
    ) -> None:
        self.mode = mode
        self.overrides = overrides or JudgeOverrides()
        self.llm_provider = llm_provider
        self.nli_provider = nli_provider
        self.principles = principles or []

    def score(self, *, question: str, answer: str, language: str) -> QAScore:
        return score_qa_pair(
            question=question,
            answer=answer,
            language=language,
            mode=self.mode,
            overrides=self.overrides,
            llm_provider=self.llm_provider,
            nli_provider=self.nli_provider,
            principles=self.principles or None,
        )

    def score_pair(
        self,
        *,
        question: str,
        answer_a: str,
        answer_b: str,
        language: str,
        tie_epsilon: float = 0.05,
    ) -> PreferenceVerdict:
        """Compare two candidate answers; return a `PreferenceVerdict`.

        Implementation: score each side with the configured providers,
        then delegate the comparison to `compare_scores`. This keeps the
        per-sample logic single-sourced and makes pairwise judging
        deterministic given identical providers + mode.
        """

        score_a = self.score(question=question, answer=answer_a, language=language)
        score_b = self.score(question=question, answer=answer_b, language=language)
        return compare_scores(score_a, score_b, tie_epsilon=tie_epsilon)
