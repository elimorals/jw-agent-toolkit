"""Post-session feedback engine (Fase 66).

For each user turn in a closed `SparSession`, runs heuristic
`citation_quality` detection and (optionally) NLI F39 validation
against a retrieval context to flag claims that don't entail.

The engine is intentionally formative — feedback flags weakness but
never grades the user comparatively. The output drives the
`session.score_summary` aggregate.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Protocol

from jw_agents.spar.models import SparSession, TurnFeedback, UserTurn

logger = logging.getLogger(__name__)

_WOL_URL = re.compile(r"https?://(?:www\.)?wol\.jw\.org/", re.IGNORECASE)
_JW_PUB_CODES = re.compile(
    r"\b("
    r"w\d{2,}|ws\d{2,}|wp\d{2,}|g\d{2,}|jt|bh|sjj|jy|rs|it|km\d{2,}|"
    r"yb\d{2,}|cl|lvs|lff|lr"
    r")\b",
    re.IGNORECASE,
)


def _bible_ref_in(text: str) -> bool:
    """True if `text` plausibly contains a Bible reference."""
    try:
        from jw_core.parsers.reference import parse_all_references

        return bool(parse_all_references(text))
    except Exception:
        return False


def _citation_quality(text: str) -> str:
    """Strong if wol/pub_code, weak if only Bible ref, missing otherwise."""
    if _WOL_URL.search(text) or _JW_PUB_CODES.search(text):
        return "strong"
    if _bible_ref_in(text):
        return "weak"
    return "missing"


class NLILike(Protocol):
    def evaluate_entailment(self, *, claim: str, premise: str) -> Any: ...


def _premise_for(turn: UserTurn) -> str | None:
    """Heuristic: use the user's own claim as both claim and premise to
    detect self-consistency. A real retrieval-backed premise can be
    plumbed via `nli_premise_fn` later.

    Returns None to skip NLI entirely on this turn (e.g., empty or trivial).
    """
    text = turn.text.strip()
    if len(text) < 20:
        return None
    return text


def _score_turn(
    user_turn: UserTurn,
    *,
    nli: NLILike | None,
) -> TurnFeedback:
    citation_quality = _citation_quality(user_turn.text)
    nli_verdict = "skipped"
    nli_score: float | None = None
    if nli is not None:
        premise = _premise_for(user_turn)
        if premise is not None:
            try:
                verdict = nli.evaluate_entailment(
                    claim=user_turn.text, premise=premise
                )
                nli_verdict = str(getattr(verdict, "verdict", "skipped"))
                raw_score = getattr(verdict, "score", None)
                if isinstance(raw_score, (int, float)):
                    nli_score = float(raw_score)
            except Exception as exc:  # noqa: BLE001
                logger.debug("spar feedback NLI raised: %s", exc)

    suggested_phrasing: str | None = None
    if citation_quality == "missing":
        suggested_phrasing = (
            "Considera respaldar tu afirmación con una cita Biblica "
            "concreta (libro capítulo:versículo)."
        )
    elif citation_quality == "weak" and nli_verdict == "contradicts":
        suggested_phrasing = (
            "El argumento parece chocar con la fuente esperada — revisa "
            "el contexto del versículo y considera citar una publicación."
        )

    return TurnFeedback(
        user_turn_index=user_turn.turn_index,
        nli_verdict=nli_verdict,  # type: ignore[arg-type]
        nli_score=nli_score,
        citation_quality=citation_quality,  # type: ignore[arg-type]
        suggested_phrasing=suggested_phrasing,
    )


def score_session(
    session: SparSession,
    *,
    nli: NLILike | None = None,
) -> SparSession:
    """Compute per-turn feedback + aggregate score summary. Mutates the
    passed session in place and returns it for chaining."""

    feedback: list[TurnFeedback] = [
        _score_turn(t, nli=nli) for t in session.user_turns
    ]
    session.feedback = feedback

    total = len(feedback) or 1
    strong = sum(1 for f in feedback if f.citation_quality == "strong")
    weak = sum(1 for f in feedback if f.citation_quality == "weak")
    missing = sum(1 for f in feedback if f.citation_quality == "missing")
    entails = sum(1 for f in feedback if f.nli_verdict == "entails")
    contradicts = sum(
        1 for f in feedback if f.nli_verdict == "contradicts"
    )
    session.score_summary = {
        "turns": float(total),
        "citation_strong_ratio": strong / total,
        "citation_weak_ratio": weak / total,
        "citation_missing_ratio": missing / total,
        "nli_entails_ratio": entails / total,
        "nli_contradicts_ratio": contradicts / total,
    }
    return session
