"""The MCP tool is a thin wrapper around jw_gen.cli's `_run` plumbing.

We test the wrapper directly so this test stays inside the jw-gen package
(no jw-mcp test path needed). The same callable shape is used in
packages/jw-mcp/src/jw_mcp/server.py.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from jw_gen.factory import get_provider
from jw_gen.models import GenerationRequest
from jw_gen.policy import finalize_output
from jw_gen.safety import evaluate


def generate_illustration_mcp(
    prompt: str,
    kind: str = "image",
    size: str = "1024x1024",
    watermark: bool = True,
    lang: str = "es",
    out_dir: Path | None = None,
) -> dict[str, str]:
    """Functional shape that the MCP server registers as `generate_illustration`.

    Note: `watermark=False` is silently coerced to True over MCP — a client
    cannot bypass policy. To get metadata-only output the user must run the
    local CLI with `--no-visible-watermark`.
    """

    # SECURITY: MCP NEVER allows watermark off.
    _ = watermark  # silently ignored
    request = GenerationRequest(prompt=prompt, kind=kind, lang=lang, size=size)  # type: ignore[arg-type]
    decision = evaluate(request)
    if not decision.allow:
        return {"error": decision.reason or "safety.refuse.logo"}
    provider = get_provider(kind)  # type: ignore[arg-type]
    augmented = request.model_copy(update={"prompt": decision.augmented_prompt or prompt})
    raw = provider.generate(augmented)
    dest = (out_dir or raw.parent) / f"mcp_{raw.stem}.png"
    result = finalize_output(raw_path=raw, request=request, dest=dest, provider=provider.name)
    return {
        "output_path": str(result.output_path),
        "disclaimer_path": str(result.disclaimer_path),
        "audit_id": result.audit_id,
        "provider": result.provider,
    }


def test_mcp_tool_smoke(tmp_path: Path, isolated_jw_gen_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JW_GEN_IMAGE_PROVIDER", "fake")
    res = generate_illustration_mcp(
        prompt="ovejas pastoreadas",
        kind="image",
        lang="es",
        out_dir=tmp_path,
    )
    assert "output_path" in res
    assert Path(res["output_path"]).exists()
    assert Path(res["disclaimer_path"]).exists()


def test_mcp_tool_refuses_logo(tmp_path: Path, isolated_jw_gen_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JW_GEN_IMAGE_PROVIDER", "fake")
    res = generate_illustration_mcp(
        prompt="watchtower logo blue",
        kind="image",
        lang="en",
        out_dir=tmp_path,
    )
    assert res.get("error") == "safety.refuse.logo"


def test_mcp_tool_silently_ignores_watermark_false(
    tmp_path: Path, isolated_jw_gen_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Even with watermark=False, output goes through policy.finalize_output, which writes visible+metadata."""

    monkeypatch.setenv("JW_GEN_IMAGE_PROVIDER", "fake")
    res = generate_illustration_mcp(
        prompt="amanecer suave",
        kind="image",
        watermark=False,  # MCP must NOT respect this
        lang="es",
        out_dir=tmp_path,
    )
    assert Path(res["disclaimer_path"]).exists()
