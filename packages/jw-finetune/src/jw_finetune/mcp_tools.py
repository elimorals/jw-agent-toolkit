"""MCP tools exposed by jw-finetune.

Register these on an existing `FastMCP` instance to let Claude Desktop and
other MCP clients introspect and operate on fine-tuning runs. The tools
are read-mostly: nothing actually starts training (which is expensive and
GPU-bound). Instead they help the LLM operator answer questions like
"what runs exist?", "what was the latest loss?", "show me dataset preview",
"compare two checkpoints", etc.

Wire-up pattern (in `jw_mcp/server.py` or similar):

    from jw_finetune.mcp_tools import register_jw_finetune_tools
    register_jw_finetune_tools(mcp, workspace_root=Path("./jw-finetune-workspace"))
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def register_jw_finetune_tools(
    mcp: Any,
    *,
    workspace_root: Path | str = "./jw-finetune-workspace",
) -> list[str]:
    """Register all jw-finetune MCP tools on the given FastMCP instance.

    Returns the list of tool names registered (useful for tests + the
    `test_mcp_lists_all_expected_tools` check in jw-mcp).
    """
    root = Path(workspace_root)
    registered: list[str] = []

    @mcp.tool
    def list_finetune_runs() -> dict[str, Any]:
        """List all training runs under the workspace root.

        Returns:
            { "runs": [{run_id, task, has_recipe, checkpoints, ...}] }
        """
        from jw_finetune.monitor.studio import _list_runs

        return {"runs": _list_runs(root)}

    registered.append("list_finetune_runs")

    @mcp.tool
    def get_finetune_run(run_id: str) -> dict[str, Any]:
        """Get details of a specific run: recipe + dataset preview + checkpoints.

        Args:
            run_id: directory name under workspace_root (e.g. "run-20260530-120000")
        """
        from jw_finetune.monitor.studio import _read_dataset_preview, _safe_run_dir
        from jw_finetune.recipes.base import recipe_from_yaml

        try:
            run_dir = _safe_run_dir(root, run_id)
        except (ValueError, FileNotFoundError) as e:
            return {"error": str(e)}
        out: dict[str, Any] = {"run_id": run_id, "recipe": {}, "dataset": {}}
        if (run_dir / "recipe.yaml").exists():
            try:
                out["recipe"] = asdict(recipe_from_yaml(run_dir / "recipe.yaml"))
            except Exception as e:  # noqa: BLE001
                out["recipe_error"] = str(e)
        out["dataset"] = _read_dataset_preview(run_dir, limit=5)
        ckpt_root = run_dir / "checkpoints"
        out["checkpoints"] = sorted(c.name for c in ckpt_root.iterdir() if c.is_dir()) if ckpt_root.is_dir() else []
        return out

    registered.append("get_finetune_run")

    @mcp.tool
    def get_finetune_events(run_id: str, limit: int = 100) -> dict[str, Any]:
        """Return the last N training events from a run's events.jsonl.

        Useful for: "what was the most recent loss?", "did training finish?",
        "show me eval scores during training".
        """
        from jw_finetune.monitor.studio import _safe_run_dir

        try:
            run_dir = _safe_run_dir(root, run_id)
        except (ValueError, FileNotFoundError) as e:
            return {"error": str(e)}
        evp = run_dir / "events.jsonl"
        if not evp.exists():
            return {"events": [], "count": 0}
        lines = evp.read_text(encoding="utf-8").splitlines()
        recent = lines[-limit:]
        events = []
        for ln in recent:
            ln = ln.strip()
            if not ln:
                continue
            try:
                events.append(json.loads(ln))
            except json.JSONDecodeError:
                continue
        return {"events": events, "count": len(events)}

    registered.append("get_finetune_events")

    @mcp.tool
    def list_finetune_presets() -> dict[str, Any]:
        """List the built-in recipe presets with their metadata."""
        from jw_finetune.recipes.presets import get_preset, list_presets

        out = []
        for name in list_presets():
            r = get_preset(name)
            out.append(
                {
                    "name": name,
                    "task": r.task,
                    "languages": r.languages,
                    "publication_kinds": r.publication_kinds,
                    "qa_style": r.qa_style,
                    "base_model": r.base_model,
                    "epochs": r.epochs,
                    "lora_rank": r.lora_rank,
                    "synth_provider": r.synth_provider,
                }
            )
        return {"presets": out}

    registered.append("list_finetune_presets")

    @mcp.tool
    def chat_with_finetune_checkpoint(
        run_id: str,
        prompt: str,
        language: str = "es",
        max_new_tokens: int = 256,
    ) -> dict[str, Any]:
        """Run a single-turn chat against a trained checkpoint.

        Returns the answer plus JW-specific eval scores (citation accuracy,
        terminology). Requires the GPU stack; returns an error otherwise.
        """
        from jw_finetune.monitor.studio import _get_or_load_model, _safe_run_dir

        try:
            run_dir = _safe_run_dir(root, run_id)
        except (ValueError, FileNotFoundError) as e:
            return {"error": str(e)}
        ckpt = run_dir / "checkpoints" / "final"
        if not ckpt.exists():
            return {"error": f"no final checkpoint at {ckpt}"}
        try:
            model, tokenizer = _get_or_load_model(ckpt)
        except ImportError as e:
            return {"error": f"GPU stack not installed: {e}"}
        try:
            inputs = tokenizer.apply_chat_template(
                [{"role": "user", "content": prompt}],
                return_tensors="pt",
                add_generation_prompt=True,
            ).to(model.device)
            out = model.generate(inputs, max_new_tokens=max_new_tokens, do_sample=False)
            answer = tokenizer.decode(out[0][inputs.shape[1] :], skip_special_tokens=True)
        except Exception as e:  # noqa: BLE001
            return {"error": f"generation failed: {e}"}

        from jw_finetune.eval.doctrinal import score_terminology
        from jw_finetune.eval.refs import score_citation_accuracy

        return {
            "answer": answer,
            "citation_accuracy": score_citation_accuracy([answer]),
            "terminology_score": score_terminology([answer], language=language),
        }

    registered.append("chat_with_finetune_checkpoint")

    @mcp.tool
    def doctor_finetune() -> dict[str, Any]:
        """Run the jw-finetune environment health check (doctor command)."""
        from jw_finetune.ux.doctor import run_doctor

        report = run_doctor()
        return {
            "ok": report.ok,
            "checks": [{"name": c.name, "status": c.status, "detail": c.detail} for c in report.checks],
        }

    registered.append("doctor_finetune")

    return registered
