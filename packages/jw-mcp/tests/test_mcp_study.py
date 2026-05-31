from __future__ import annotations


def test_prepare_lesson_tool_returns_dict(monkeypatch) -> None:
    from jw_agents.base import AgentResult, Citation, Finding
    from jw_mcp import server as srv

    def fake_prepare(*a, **k):
        return AgentResult(
            query="x",
            agent_name="study_conductor",
            findings=[
                Finding(
                    summary="Lección 1",
                    excerpt="…",
                    citation=Citation(url="https://wol.jw.org/x", title="t", kind="chapter"),
                    metadata={"source": "wol_chapter"},
                )
            ],
        )

    monkeypatch.setattr(srv, "prepare_lesson_agent", fake_prepare)
    out = srv.prepare_lesson("lff", 1, "es")
    assert "findings" in out
    assert len(out["findings"]) == 1


def test_log_student_progress_requires_passphrase(monkeypatch) -> None:
    monkeypatch.delenv("JW_STUDY_PASSPHRASE", raising=False)
    from jw_mcp import server as srv

    out = srv.log_student_progress("demo_user", "lff", 1)
    assert "error" in out
    assert "passphrase" in out["error"].lower() or "JW_STUDY_PASSPHRASE" in out["error"]


def test_log_student_progress_round_trip(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("JW_STUDY_PASSPHRASE", "hunter2")
    monkeypatch.setenv("JW_STUDY_DB", str(tmp_path / "p.db"))
    monkeypatch.setenv("JW_STUDY_SALT", str(tmp_path / "salt.bin"))
    from jw_agents.study_progress import load_or_create_salt

    load_or_create_salt(tmp_path / "salt.bin")

    from jw_mcp import server as srv

    out = srv.log_student_progress(
        "demo_user",
        "lff",
        1,
        status="completed",
        note="ok",
        goals=["attend_meetings"],
    )
    assert "error" not in out, out
    listing = srv.list_student_lessons("demo_user", book_pub="lff")
    assert listing["count"] == 1
    set_out = srv.set_student_goal(
        "demo_user",
        kind="baptism",
        target_iso="2026-12-31T00:00:00",
    )
    assert "error" not in set_out, set_out
