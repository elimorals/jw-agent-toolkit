from __future__ import annotations

from typer.testing import CliRunner

from jw_cli.main import app


runner = CliRunner()


def test_study_help_runs() -> None:
    result = runner.invoke(app, ["study", "--help"])
    assert result.exit_code == 0
    assert "study" in result.stdout.lower()


def test_study_goals_lists_taxonomy() -> None:
    result = runner.invoke(app, ["study", "goals"])
    assert result.exit_code == 0
    out = result.stdout
    assert "attend_meetings" in out
    assert "baptism" in out
    assert "drop_addiction_smoking" in out


def test_study_lesson_renders_prep(monkeypatch) -> None:
    from jw_agents.base import AgentResult, Citation, Finding
    from jw_agents.study_conductor import AnticipationQuestion, LessonPrep

    prep = LessonPrep(
        pub_code="lff", chapter=1, language="es",
        title="¿Existe alguien que se preocupe por usted?",
        summary="Jehová es un Padre amoroso.",
        questions=[
            AnticipationQuestion(1, "¿Qué punto principal enseña el párrafo 1?",
                                 "es.fact", []),
        ],
        key_verses=["1 Pedro 5:7"], supporting_topics=["Jehová"], source="jwpub_local",
    )
    fake_result = AgentResult(
        query="prepare_lesson",
        agent_name="study_conductor",
        findings=[Finding(
            summary="L1", excerpt="Jehová...",
            citation=Citation(url="https://wol.jw.org/x", title="L1", kind="chapter"),
            metadata={"source": "jwpub_chapter", "payload": prep},
        )],
    )
    monkeypatch.setattr(
        "jw_cli.commands.study.prepare_lesson",
        lambda *a, **k: fake_result,
    )
    result = runner.invoke(app, ["study", "lesson", "lff", "1", "--lang", "es"])
    assert result.exit_code == 0
    assert "1 Pedro 5:7" in result.stdout
    assert "párrafo 1" in result.stdout
