from __future__ import annotations


# We test the function the MCP tool wraps; a full FastMCP roundtrip is
# already covered elsewhere in test_protocol.py.

def test_run_eval_suite_returns_summary(tmp_path) -> None:
    from jw_mcp.server import run_eval_suite

    out = run_eval_suite(
        layers=[1],
        cases_root=str(tmp_path),
        snapshots_root=str(tmp_path),
    )
    assert "summary" in out
    assert "results" in out
