"""Studio — extended Web UI building on the monitor app.

Adds routes for:
  - GET  /studio                — main studio dashboard (HTML)
  - GET  /api/presets           — list recipe presets with metadata
  - GET  /api/runs              — list run directories under workspace
  - GET  /api/run/{run_id}      — run summary (recipe + dataset + checkpoints)
  - GET  /api/dataset/{run_id}  — first N records of dataset (for preview)
  - GET  /api/models            — curated Unsloth model catalog
  - POST /api/recipe/save       — write a recipe YAML
  - POST /api/chat              — single-turn chat with a checkpoint (lazy Unsloth)

All write endpoints validate inputs strictly and reject paths outside the
configured workspace root. The chat endpoint is opt-in and is the only one
that loads the GPU stack.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict
from pathlib import Path
from typing import Any

from jw_finetune.recipes.base import (
    Recipe,
    recipe_from_yaml,
    recipe_to_yaml,
    validate_recipe,
)
from jw_finetune.recipes.presets import get_preset, list_presets

logger = logging.getLogger(__name__)


# Curated catalog. Curating > exposing all of Unsloth's registry: keeps the
# UI uncluttered and ensures every entry is one we've seen work on at least
# one hardware target.
# Module-level cache for loaded chat models in the playground.
# Keys are checkpoint paths; values are (model, tokenizer) tuples.
# Bounded LRU-like behavior: at most _MAX_CACHED_MODELS, evict oldest.
_LOADED_MODEL_CACHE: dict[str, Any] = {}
_MAX_CACHED_MODELS = 2


def _get_or_load_model(checkpoint_dir: Path) -> tuple[Any, Any]:
    """Cache the (model, tokenizer) per checkpoint to avoid re-loading.

    Loading a 7B model from disk takes 10-30s; this turns subsequent chat
    requests into ~1s. LRU-evict oldest entry when cache is full.
    """
    key = str(checkpoint_dir.resolve())
    if key in _LOADED_MODEL_CACHE:
        return _LOADED_MODEL_CACHE[key]
    if len(_LOADED_MODEL_CACHE) >= _MAX_CACHED_MODELS:
        # Evict oldest (first inserted; dict preserves insertion order in 3.7+)
        oldest = next(iter(_LOADED_MODEL_CACHE))
        _LOADED_MODEL_CACHE.pop(oldest, None)
    from unsloth import FastLanguageModel  # type: ignore[import-untyped]

    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=str(checkpoint_dir),
        max_seq_length=2048,
        load_in_4bit=True,
        dtype=None,
    )
    FastLanguageModel.for_inference(model)
    _LOADED_MODEL_CACHE[key] = (model, tokenizer)
    return model, tokenizer


def clear_model_cache() -> int:
    """Clear all cached models. Returns count of evicted entries."""
    n = len(_LOADED_MODEL_CACHE)
    _LOADED_MODEL_CACHE.clear()
    return n


MODEL_CATALOG: list[dict[str, Any]] = [
    {
        "id": "unsloth/Qwen2.5-3B-bnb-4bit",
        "size": "3B",
        "context": 32768,
        "min_vram_gb": 8,
        "kind": "general",
        "tags": ["multilingual", "fast"],
    },
    {
        "id": "unsloth/Qwen2.5-7B-bnb-4bit",
        "size": "7B",
        "context": 32768,
        "min_vram_gb": 12,
        "kind": "general",
        "tags": ["multilingual", "balanced"],
    },
    {
        "id": "unsloth/Llama-3.2-3B-Instruct-bnb-4bit",
        "size": "3B",
        "context": 8192,
        "min_vram_gb": 8,
        "kind": "instruct",
        "tags": ["english-focused", "fast"],
    },
    {
        "id": "unsloth/gemma-3-4b-it-bnb-4bit",
        "size": "4B",
        "context": 8192,
        "min_vram_gb": 8,
        "kind": "instruct",
        "tags": ["multimodal-capable"],
    },
    {
        "id": "unsloth/Mistral-7B-Instruct-v0.3-bnb-4bit",
        "size": "7B",
        "context": 32768,
        "min_vram_gb": 12,
        "kind": "instruct",
        "tags": ["solid-general"],
    },
    {
        "id": "unsloth/Qwen2.5-13B-bnb-4bit",
        "size": "13B",
        "context": 32768,
        "min_vram_gb": 20,
        "kind": "general",
        "tags": ["high-quality", "needs-big-gpu"],
    },
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _safe_run_dir(workspace_root: Path, run_id: str) -> Path:
    """Resolve run_id under workspace_root, rejecting traversal attempts.

    `Path.resolve()` follows symlinks. To prevent a symlink inside the
    workspace from pointing outside, we use `os.path.commonpath` on the
    resolved candidate vs. the resolved root — they must share the root.

    Also rejects empty/whitespace run_ids and any name containing path
    separators or `..` segments before resolution.
    """
    import os

    # Pre-filter obvious traversal attempts in the raw input.
    if not run_id or not run_id.strip():
        raise ValueError("empty run_id")
    if "/" in run_id or "\\" in run_id or ".." in run_id.split("/"):
        raise ValueError(f"invalid run_id: {run_id!r}")

    root_resolved = workspace_root.resolve(strict=False)
    candidate = (workspace_root / run_id).resolve(strict=False)

    # After resolve (which follows symlinks), require shared prefix.
    try:
        common = os.path.commonpath([str(candidate), str(root_resolved)])
    except ValueError:
        # Different drives on Windows, etc.
        raise ValueError(f"run_id outside workspace: {run_id!r}")
    if common != str(root_resolved):
        raise ValueError(f"run_id outside workspace: {run_id!r}")

    if not candidate.exists() or not candidate.is_dir():
        raise FileNotFoundError(candidate)
    return candidate


def _list_runs(workspace_root: Path) -> list[dict[str, Any]]:
    if not workspace_root.exists():
        return []
    out = []
    for d in sorted(workspace_root.iterdir()):
        if not d.is_dir() or not d.name.startswith("run-"):
            continue
        recipe_path = d / "recipe.yaml"
        sft = d / "dataset_qa.jsonl"
        cpt = d / "dataset_raw.jsonl"
        ckpt_root = d / "checkpoints"
        ckpts = []
        if ckpt_root.is_dir():
            ckpts = sorted(c.name for c in ckpt_root.iterdir() if c.is_dir())
        out.append(
            {
                "run_id": d.name,
                "has_recipe": recipe_path.exists(),
                "task": "sft" if sft.exists() else ("cpt" if cpt.exists() else "unknown"),
                "dataset_path": str((sft if sft.exists() else cpt).name) if (sft.exists() or cpt.exists()) else "",
                "checkpoints": ckpts,
                "events_size_bytes": (d / "events.jsonl").stat().st_size if (d / "events.jsonl").exists() else 0,
            }
        )
    return out


def _read_dataset_preview(run_dir: Path, limit: int = 10) -> dict[str, Any]:
    """Return first `limit` records of the dataset (CPT raw or SFT QA)."""
    for fname in ("dataset_qa.jsonl", "dataset_raw.jsonl"):
        p = run_dir / fname
        if not p.exists():
            continue
        rows = []
        with p.open("r", encoding="utf-8") as f:
            for i, line in enumerate(f):
                if i >= limit:
                    break
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    rows.append({"_raw": line[:200]})
        return {"file": fname, "rows": rows, "count": len(rows)}
    return {"file": "", "rows": [], "count": 0}


def _validated_recipe_from_payload(payload: dict[str, Any]) -> tuple[Recipe, list[str]]:
    """Coerce a JSON dict from the UI back into a Recipe + errors."""
    from jw_finetune.data.models import SourceSpec

    src_raw = payload.pop("sources", []) or []
    sources = []
    for s in src_raw:
        sources.append(
            SourceSpec(
                kind=s.get("kind", "jwpub"),
                path=s.get("path", ""),
                language=s.get("language", "es"),
            )
        )
    payload["sources"] = sources
    recipe = Recipe(**payload)
    return recipe, validate_recipe(recipe)


# ---------------------------------------------------------------------------
# Studio app — extends `create_app` with extra routes
# ---------------------------------------------------------------------------


def attach_studio_routes(app: Any, workspace_root: Path) -> None:
    """Mount studio routes on an existing FastAPI app."""
    from fastapi import HTTPException  # type: ignore[import-not-found]
    from fastapi.responses import HTMLResponse, JSONResponse  # type: ignore[import-not-found]

    @app.get("/studio", response_class=HTMLResponse)
    async def studio_index() -> str:
        return (_templates_dir() / "studio.html").read_text(encoding="utf-8")

    @app.get("/api/presets")
    async def api_presets() -> Any:
        items = []
        for name in list_presets():
            r = get_preset(name)
            items.append(
                {
                    "name": name,
                    "task": r.task,
                    "languages": r.languages,
                    "publication_kinds": r.publication_kinds,
                    "qa_style": r.qa_style,
                    "base_model": r.base_model,
                    "epochs": r.epochs,
                    "lora_rank": r.lora_rank,
                }
            )
        return JSONResponse({"presets": items})

    @app.get("/api/models")
    async def api_models() -> Any:
        return JSONResponse({"models": MODEL_CATALOG})

    @app.get("/api/runs")
    async def api_runs() -> Any:
        return JSONResponse({"runs": _list_runs(workspace_root)})

    @app.get("/api/run/{run_id}")
    async def api_run(run_id: str) -> Any:
        try:
            run_dir = _safe_run_dir(workspace_root, run_id)
        except (ValueError, FileNotFoundError) as e:
            raise HTTPException(status_code=404, detail=str(e))
        recipe_path = run_dir / "recipe.yaml"
        recipe_dict: dict[str, Any] = {}
        if recipe_path.exists():
            try:
                r = recipe_from_yaml(recipe_path)
                recipe_dict = asdict(r)
            except Exception as e:  # noqa: BLE001
                recipe_dict = {"_error": f"failed to read recipe: {e}"}
        return JSONResponse(
            {
                "run_id": run_id,
                "recipe": recipe_dict,
                "dataset": _read_dataset_preview(run_dir, limit=5),
            }
        )

    @app.get("/api/dataset/{run_id}")
    async def api_dataset(run_id: str, limit: int = 20) -> Any:
        try:
            run_dir = _safe_run_dir(workspace_root, run_id)
        except (ValueError, FileNotFoundError) as e:
            raise HTTPException(status_code=404, detail=str(e))
        limit = max(1, min(limit, 200))
        return JSONResponse(_read_dataset_preview(run_dir, limit=limit))

    @app.post("/api/recipe/save")
    async def api_recipe_save(payload: dict) -> Any:
        recipe, errors = _validated_recipe_from_payload(dict(payload))
        if errors:
            return JSONResponse({"ok": False, "errors": errors}, status_code=400)
        out = workspace_root / f"recipe-{recipe.name}.yaml"
        recipe_to_yaml(recipe, out)
        return JSONResponse({"ok": True, "path": str(out)})

    @app.post("/api/chat")
    async def api_chat(payload: dict) -> Any:
        """Single-turn chat with a trained checkpoint.

        Caches loaded models per checkpoint (see `_get_or_load_model`) so
        repeated requests reuse the same in-memory model. The first call
        for a fresh checkpoint takes 10-30s; subsequent calls ~1-3s.
        """
        run_id = payload.get("run_id")
        prompt = payload.get("prompt", "")
        if not run_id or not prompt:
            raise HTTPException(400, "run_id and prompt required")
        try:
            run_dir = _safe_run_dir(workspace_root, str(run_id))
        except (ValueError, FileNotFoundError) as e:
            raise HTTPException(404, str(e))
        ckpt = run_dir / "checkpoints" / "final"
        if not ckpt.exists():
            raise HTTPException(404, f"no final checkpoint at {ckpt}")
        max_new_tokens = int(payload.get("max_new_tokens", 256))
        try:
            model, tokenizer = _get_or_load_model(ckpt)
        except ImportError as e:
            raise HTTPException(503, f"Unsloth not available: {e}")
        try:
            inputs = tokenizer.apply_chat_template(
                [{"role": "user", "content": prompt}],
                return_tensors="pt",
                add_generation_prompt=True,
            ).to(model.device)
            out = model.generate(inputs, max_new_tokens=max_new_tokens, do_sample=False)
            answer = tokenizer.decode(out[0][inputs.shape[1] :], skip_special_tokens=True)
        except Exception as e:  # noqa: BLE001
            raise HTTPException(500, f"generation error: {e}")
        # Score using the JW-specific evals.
        from jw_finetune.eval.doctrinal import score_terminology
        from jw_finetune.eval.refs import score_citation_accuracy

        lang = payload.get("language", "es")
        return JSONResponse(
            {
                "ok": True,
                "answer": answer,
                "citation_accuracy": score_citation_accuracy([answer]),
                "terminology_score": score_terminology([answer], language=lang),
                "cached": True,
            }
        )


def _templates_dir() -> Path:
    return Path(__file__).parent / "templates"


def create_studio_app(events_path: Path, workspace_root: Path) -> Any:
    """Build the monitor app AND attach studio routes on top."""
    from jw_finetune.monitor.app import create_app

    app = create_app(events_path)
    attach_studio_routes(app, workspace_root)
    return app


def run_studio(
    events_path: Path,
    workspace_root: Path,
    *,
    host: str = "127.0.0.1",
    port: int = 7860,
) -> None:
    """Block-run the studio server."""
    try:
        import uvicorn  # type: ignore[import-not-found]
    except ImportError as e:
        raise ImportError("uvicorn required: install with `--extra monitor`") from e

    app = create_studio_app(events_path, workspace_root)
    uvicorn.run(app, host=host, port=port, log_level="info")
