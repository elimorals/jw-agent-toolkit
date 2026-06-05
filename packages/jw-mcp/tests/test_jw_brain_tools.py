"""F66 — E2E tests for the second_brain_* MCP tools.

These tests boot a fresh DuckDB-backed brain in ``tmp_path`` via the
``jw brain init`` Typer CLI, then invoke the async tools exposed by
``jw_mcp.server`` directly (they are plain async functions, not fastmcp
wrappers, so calling them as coroutines is the canonical way to drive
them in-process).

The plan F66 originally assumed a ``brain: str | None`` resolved through
a registry; the real wrappers take ``brain_path: str`` (absolute path),
so the tests target the actual signatures.
"""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture()
def temp_brain(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Initialize an empty TJ brain at ``tmp_path/brain``.

    Returns the absolute brain home path. The fixture relies on
    ``jw brain init`` to create the config.toml + raw/vault/graph
    skeleton; this is what the MCP wrappers expect.

    The registry side effects of ``jw brain init`` are redirected to a
    ``tmp_path`` file (precedent: ``test_multi_tenant.py``) so the test
    does not mutate the user's real ``~/.jw-brain/registry.toml``.
    """

    from jw_brain.cli import brain_app
    from jw_brain.multi_tenant import load_registry, save_registry
    from typer.testing import CliRunner

    reg = tmp_path / "registry.toml"
    monkeypatch.setattr(
        "jw_brain.cli.register_brain",
        lambda alias, path: save_registry(
            {**load_registry(reg), alias: path}, reg
        ),
    )
    monkeypatch.setattr("jw_brain.cli.load_registry", lambda: load_registry(reg))

    brain_home = tmp_path / "brain"
    brain_home.mkdir()
    runner = CliRunner()
    result = runner.invoke(
        brain_app,
        [
            "init",
            "--brain",
            str(brain_home),
            "--vault",
            str(tmp_path / "vault"),
        ],
    )
    assert result.exit_code == 0, result.stdout
    return brain_home


async def test_second_brain_status_responds(temp_brain: Path) -> None:
    from jw_mcp.server import second_brain_status

    result = await second_brain_status(brain_path=str(temp_brain))
    assert "error" not in result, result
    # Fresh brain: zero nodes/edges, zero pending raw files.
    assert result["graph"]["n_nodes"] == 0
    assert result["graph"]["n_edges"] == 0
    assert result["raw"]["pending"] == 0


async def test_second_brain_status_unknown_brain_returns_error_or_zero(
    tmp_path: Path,
) -> None:
    """A non-existent brain must not crash the server.

    The current implementation falls back to default config + an empty
    DuckDB file, so it returns zero counts rather than raising. Any
    reasonable exception type is also accepted.
    """

    from jw_mcp.server import second_brain_status

    fake_path = tmp_path / "does_not_exist"
    try:
        result = await second_brain_status(brain_path=str(fake_path))
        assert isinstance(result, dict)
        # Either an explicit error field, or zero-stat response.
        ok_shape = (
            "error" in result
            or result.get("graph", {}).get("n_nodes", 0) == 0
        )
        assert ok_shape, result
    except (FileNotFoundError, ValueError, RuntimeError):
        pass


async def test_second_brain_query_empty_brain_returns_no_error(
    temp_brain: Path,
) -> None:
    from jw_mcp.server import second_brain_query

    result = await second_brain_query(
        brain_path=str(temp_brain),
        question="¿quién es Abraham?",
        mode="auto",
    )
    # Empty brain → zero-confidence answer, no error field.
    assert "error" not in result, result
    assert result.get("confidence", 0.0) == 0.0
    assert result.get("citations") == []


async def test_second_brain_snapshot_creates_artifact(temp_brain: Path) -> None:
    from jw_mcp.server import second_brain_snapshot

    result = await second_brain_snapshot(
        brain_path=str(temp_brain), label="test_snapshot"
    )
    assert "error" not in result, result
    # The implementation returns {"snapshot": "<path>"}; allow any of the
    # commonly-used keys for forward compatibility.
    snap_key = next(
        (k for k in ("snapshot", "snapshot_path", "path") if k in result),
        None,
    )
    assert snap_key is not None, f"no snapshot path key in {result}"
    snap_path = Path(result[snap_key])
    assert snap_path.exists(), f"snapshot file missing: {snap_path}"
    assert "test_snapshot" in snap_path.name


async def test_second_brain_lint_smoke(temp_brain: Path) -> None:
    """Empty brain: lint must respond without error (no orphan pages yet)."""
    from jw_mcp.server import second_brain_lint

    result = await second_brain_lint(brain_path=str(temp_brain))
    assert "error" not in result, result
    assert isinstance(result, dict)
