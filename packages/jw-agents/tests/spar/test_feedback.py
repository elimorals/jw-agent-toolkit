"""Feedback engine tests."""

from __future__ import annotations

from jw_agents.spar.feedback import score_session
from jw_agents.spar.models import Persona, SparSession, UserTurn


def _session(user_texts: list[str]) -> SparSession:
    p = Persona(
        key="catholic",
        display_name="María",
        language="es",
        tone="warm",
    )
    s = SparSession(
        session_id="s",
        persona=p,
        language="es",
        started_at="now",
        user_turns=[
            UserTurn(text=t, turn_index=i)
            for i, t in enumerate(user_texts)
        ],
    )
    return s


def test_citation_quality_strong_on_wol_url() -> None:
    s = _session(
        ["Como dice https://wol.jw.org/es/wol/d/r4/lp-s/1101989101"]
    )
    out = score_session(s)
    assert out.feedback[0].citation_quality == "strong"


def test_citation_quality_strong_on_pub_code() -> None:
    s = _session(["Según w23.04 p. 12, esto es claro porque..."])
    out = score_session(s)
    assert out.feedback[0].citation_quality == "strong"


def test_citation_quality_weak_on_bare_bible_ref() -> None:
    s = _session(["Como enseña Juan 3:16, Dios amó tanto al mundo."])
    out = score_session(s)
    assert out.feedback[0].citation_quality == "weak"


def test_citation_quality_missing_on_naked_claim() -> None:
    s = _session(["Esto es así porque sí, sin más."])
    out = score_session(s)
    assert out.feedback[0].citation_quality == "missing"
    assert out.feedback[0].suggested_phrasing is not None


def test_nli_skipped_by_default() -> None:
    s = _session(["Esto es así porque sí, sin más."])
    out = score_session(s)
    assert out.feedback[0].nli_verdict == "skipped"


def test_nli_entails_when_provider_returns_entails() -> None:
    class FakeVerdict:
        verdict = "entails"
        score = 0.92

    class FakeNLI:
        def evaluate_entailment(self, *, claim: str, premise: str):  # noqa: ARG002
            return FakeVerdict()

    s = _session(["Como dice Juan 3:16, Dios amó tanto al mundo entero."])
    out = score_session(s, nli=FakeNLI())
    assert out.feedback[0].nli_verdict == "entails"
    assert out.feedback[0].nli_score == 0.92


def test_score_summary_aggregates_ratios() -> None:
    s = _session(
        [
            "Según w23.04 p. 5, esto es así.",
            "Esto es así porque sí, sin más.",
        ]
    )
    out = score_session(s)
    assert out.score_summary is not None
    assert out.score_summary["turns"] == 2.0
    assert out.score_summary["citation_strong_ratio"] == 0.5
    assert out.score_summary["citation_missing_ratio"] == 0.5
