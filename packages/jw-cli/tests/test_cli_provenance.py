"""End-to-end tests for `jw provenance check`."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from jw_cli.main import app
from jw_core.provenance.hashing import content_sha256

runner = CliRunner()


def _write_agent_result(tmp_path: Path, *, body_text: str, accessed_at: str) -> Path:
    """Write a minimal AgentResult JSON with provenance fields filled in."""

    result = {
        "query": "Juan 3:16",
        "agent_name": "verse_explainer",
        "warnings": [],
        "metadata": {"language": "es"},
        "findings": [
            {
                "summary": "Juan 3:16 muestra el amor de Dios.",
                "excerpt": body_text,
                "metadata": {"source": "verse_text"},
                "citation": {
                    "url": "https://wol.jw.org/x",
                    "title": "Juan 3",
                    "kind": "verse",
                    "metadata": {
                        "accessed_at": accessed_at,
                        "content_hash": content_sha256(body_text),
                        "published_date": None,
                        "revision": "rev. 2023",
                    },
                },
            }
        ],
    }
    p = tmp_path / "result.json"
    p.write_text(json.dumps(result), encoding="utf-8")
    return p


def test_provenance_check_help() -> None:
    out = runner.invoke(app, ["provenance", "check", "--help"])
    assert out.exit_code == 0
    assert "agent-output" in out.stdout.lower() or "agent_output" in out.stdout.lower()


def test_provenance_check_reports_match_with_fake_fetcher(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    body = "Porque Dios amó tanto al mundo"
    result_path = _write_agent_result(tmp_path, body_text=body, accessed_at="2026-05-30T10:00:00Z")
    monkeypatch.setenv("JW_PROVENANCE_FETCHER", "fake")

    out = runner.invoke(
        app,
        ["provenance", "check", "--agent-output", str(result_path), "--report", "json"],
    )
    assert out.exit_code == 0, out.stdout
    data = json.loads(out.stdout.strip().splitlines()[-1])
    assert data["summary"]["match"] == 1


def test_provenance_check_exit_2_on_change(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    body = "original"
    result_path = _write_agent_result(tmp_path, body_text=body, accessed_at="2026-05-30T10:00:00Z")
    monkeypatch.setenv("JW_PROVENANCE_FETCHER", "fake-drift")

    out = runner.invoke(
        app,
        ["provenance", "check", "--agent-output", str(result_path), "--report", "json"],
    )
    assert out.exit_code == 2
    data = json.loads(out.stdout.strip().splitlines()[-1])
    assert data["summary"]["changed"] == 1


def test_provenance_check_since_filters_recent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """--since 2026-05-31 means the 2026-05-30 citation IS rechecked (it's older)."""

    body = "text"
    result_path = _write_agent_result(tmp_path, body_text=body, accessed_at="2026-05-30T10:00:00Z")
    monkeypatch.setenv("JW_PROVENANCE_FETCHER", "fake")

    out = runner.invoke(
        app,
        [
            "provenance",
            "check",
            "--agent-output",
            str(result_path),
            "--since",
            "2026-05-31",
            "--report",
            "json",
        ],
    )
    assert out.exit_code == 0
    data = json.loads(out.stdout.strip().splitlines()[-1])
    assert data["summary"].get("match") == 1
    assert data["summary"].get("skipped", 0) == 0


def test_provenance_check_markdown_report(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    body = "text"
    result_path = _write_agent_result(tmp_path, body_text=body, accessed_at="2026-05-30T10:00:00Z")
    monkeypatch.setenv("JW_PROVENANCE_FETCHER", "fake")
    out_path = tmp_path / "out.md"

    out = runner.invoke(
        app,
        [
            "provenance",
            "check",
            "--agent-output",
            str(result_path),
            "--report",
            "md",
            "--out",
            str(out_path),
        ],
    )
    assert out.exit_code == 0
    body_md = out_path.read_text(encoding="utf-8")
    assert "| URL |" in body_md or "URL" in body_md
    assert "match" in body_md
