from __future__ import annotations

from jw_cli.main import app
from typer.testing import CliRunner

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
        pub_code="lff",
        chapter=1,
        language="es",
        title="¿Existe alguien que se preocupe por usted?",
        summary="Jehová es un Padre amoroso.",
        questions=[
            AnticipationQuestion(1, "¿Qué punto principal enseña el párrafo 1?", "es.fact", []),
        ],
        key_verses=["1 Pedro 5:7"],
        supporting_topics=["Jehová"],
        source="jwpub_local",
    )
    fake_result = AgentResult(
        query="prepare_lesson",
        agent_name="study_conductor",
        findings=[
            Finding(
                summary="L1",
                excerpt="Jehová...",
                citation=Citation(url="https://wol.jw.org/x", title="L1", kind="chapter"),
                metadata={"source": "jwpub_chapter", "payload": prep},
            )
        ],
    )
    monkeypatch.setattr(
        "jw_cli.commands.study.prepare_lesson",
        lambda *a, **k: fake_result,
    )
    result = runner.invoke(app, ["study", "lesson", "lff", "1", "--lang", "es"])
    assert result.exit_code == 0
    assert "1 Pedro 5:7" in result.stdout
    assert "párrafo 1" in result.stdout


def test_study_log_writes_and_reads(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("JW_STUDY_DB", str(tmp_path / "p.db"))
    monkeypatch.setenv("JW_STUDY_SALT", str(tmp_path / "salt.bin"))
    monkeypatch.setenv("JW_STUDY_PASSPHRASE", "hunter2")
    # Pre-create salt so consent prompt is skipped.
    from jw_agents.study_progress import load_or_create_salt

    load_or_create_salt(tmp_path / "salt.bin")

    result = runner.invoke(
        app,
        [
            "study",
            "log",
            "demo_user",
            "lff",
            "1",
            "--status",
            "in_progress",
            "--note",
            "buena receptividad",
            "--goal",
            "attend_meetings",
        ],
    )
    assert result.exit_code == 0, result.stdout
    assert "demo_user" in result.stdout
    assert "in_progress" in result.stdout


def test_study_log_rejects_bad_student_id(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("JW_STUDY_DB", str(tmp_path / "p.db"))
    monkeypatch.setenv("JW_STUDY_SALT", str(tmp_path / "salt.bin"))
    monkeypatch.setenv("JW_STUDY_PASSPHRASE", "hunter2")
    from jw_agents.study_progress import load_or_create_salt

    load_or_create_salt(tmp_path / "salt.bin")
    result = runner.invoke(app, ["study", "log", "Amelia García", "lff", "1"])
    assert result.exit_code != 0


def test_study_log_warns_on_crisis_keyword(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("JW_STUDY_DB", str(tmp_path / "p.db"))
    monkeypatch.setenv("JW_STUDY_SALT", str(tmp_path / "salt.bin"))
    monkeypatch.setenv("JW_STUDY_PASSPHRASE", "hunter2")
    from jw_agents.study_progress import load_or_create_salt

    load_or_create_salt(tmp_path / "salt.bin")
    result = runner.invoke(
        app,
        [
            "study",
            "log",
            "demo_user",
            "lff",
            "1",
            "--note",
            "Mencionó suicidio en la visita",
        ],
    )
    assert result.exit_code == 0
    assert "crisis" in result.stdout.lower() or "anciano" in result.stdout.lower()


def test_study_progress_shows_lifecycle(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("JW_STUDY_DB", str(tmp_path / "p.db"))
    monkeypatch.setenv("JW_STUDY_SALT", str(tmp_path / "salt.bin"))
    monkeypatch.setenv("JW_STUDY_PASSPHRASE", "hunter2")
    from jw_agents.study_progress import load_or_create_salt

    load_or_create_salt(tmp_path / "salt.bin")

    # Seed two lessons
    runner.invoke(app, ["study", "log", "demo_user", "lff", "1", "--status", "completed"])
    runner.invoke(app, ["study", "log", "demo_user", "lff", "2", "--status", "in_progress"])

    result = runner.invoke(app, ["study", "progress", "demo_user"])
    assert result.exit_code == 0
    assert "1" in result.stdout and "2" in result.stdout
    assert "completed" in result.stdout
    assert "in_progress" in result.stdout


def test_study_lessons_lists_chapter_titles() -> None:
    result = runner.invoke(app, ["study", "lessons", "lff", "--lang", "es"])
    assert result.exit_code == 0
    assert "Disfruta" in result.stdout
    assert "60" in result.stdout  # total chapters


def test_study_directory_set_and_clear(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("JW_STUDY_DIRECTORY", str(tmp_path / "directory.json"))

    r1 = runner.invoke(app, ["study", "directory", "set", "demo_user", "Demo García"])
    assert r1.exit_code == 0

    r2 = runner.invoke(app, ["study", "directory", "show"])
    assert r2.exit_code == 0
    assert "Demo García" in r2.stdout

    r3 = runner.invoke(app, ["study", "directory", "clear", "--yes"])
    assert r3.exit_code == 0
