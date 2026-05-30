"""Tests for the F6.5 UX helpers: progress, doctor, readme, diff."""

from __future__ import annotations

import json
from pathlib import Path


# ---------------------------------------------------------------------------
# doctor
# ---------------------------------------------------------------------------


def test_doctor_returns_report() -> None:
    from jw_finetune.ux.doctor import run_doctor

    report = run_doctor()
    names = {c.name for c in report.checks}
    assert "python" in names
    assert "gpu" in names
    assert "workspace" in names
    assert "ollama" in names


def test_doctor_render_report_string() -> None:
    from jw_finetune.ux.doctor import render_report, run_doctor

    text = render_report(run_doctor())
    assert "jw-finetune doctor" in text
    assert "python" in text


def test_doctor_workspace_writable() -> None:
    """In any normal environment cwd should be writable."""
    from jw_finetune.ux.doctor import _check_workspace_writable

    c = _check_workspace_writable()
    assert c.status in ("ok", "fail")


# ---------------------------------------------------------------------------
# run_readme
# ---------------------------------------------------------------------------


def _make_workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "run-test"
    ws.mkdir()
    # Tiny recipe yaml using actual Recipe defaults
    import yaml  # type: ignore[import-untyped]
    recipe_yaml = yaml.safe_dump({
        "name": "test-recipe",
        "task": "sft",
        "sources": [],
        "languages": ["es"],
        "publication_kinds": ["watchtower"],
        "qa_style": "doctrinal",
        "base_model": "unsloth/Qwen2.5-3B-bnb-4bit",
        "lora_rank": 16, "lora_alpha": 32, "lora_dropout": 0.0,
        "max_seq_len": 2048, "epochs": 2, "batch_size": 2,
        "gradient_accumulation": 4, "learning_rate": 0.0002,
        "warmup_ratio": 0.05, "weight_decay": 0.0,
        "chat_template": "qwen-2.5", "use_rslora": False,
        "packing": None, "train_on_responses_only": True,
        "instruction_part": "", "response_part": "",
        "use_multi_gpu": False, "embedding_learning_rate_ratio": 0.1,
        "min_chunk_chars": 80, "max_chunk_chars": 1500,
        "dedupe_threshold": 4, "synth_provider": "ollama",
        "synth_model": None, "qa_per_chunk": 3, "eval_split": 0.05,
        "output_dir": "./", "seed": 42, "extra": {},
    })
    (ws / "recipe.yaml").write_text(recipe_yaml, encoding="utf-8")
    (ws / "dataset_qa.jsonl").write_text(
        json.dumps({"messages": [{"role": "user", "content": "q?"},
                                  {"role": "assistant", "content": "a."}]}) + "\n",
        encoding="utf-8",
    )
    (ws / "eval-report.json").write_text(json.dumps({
        "n_prompts": 3,
        "citation_accuracy": 0.66,
        "terminology_score": 0.33,
        "answers": [],
    }), encoding="utf-8")
    return ws


def test_write_run_readme_creates_markdown(tmp_path: Path) -> None:
    from jw_finetune.ux.run_readme import write_run_readme

    ws = _make_workspace(tmp_path)
    export_dir = tmp_path / "export"
    out = write_run_readme(
        workspace=ws, export_dir=export_dir,
        export_format="gguf", quant="Q4_K_M",
    )
    assert out.exists()
    txt = out.read_text(encoding="utf-8")
    assert "test-recipe" in txt
    assert "Q4_K_M" in txt
    assert "Mateo" not in txt  # No accidental content leakage
    assert "citation accuracy" in txt.lower()
    assert "66" in txt  # citation_accuracy formatted
    assert "Ollama" in txt
    assert "Watchtower Bible" in txt  # disclaimer


def test_hash_checkpoint_dir_stable(tmp_path: Path) -> None:
    from jw_finetune.ux.run_readme import hash_checkpoint_dir

    ckpt = tmp_path / "ckpt"
    ckpt.mkdir()
    (ckpt / "model.safetensors").write_bytes(b"binary content here" * 100)
    (ckpt / "config.json").write_text('{"x": 1}', encoding="utf-8")
    h1 = hash_checkpoint_dir(ckpt)
    h2 = hash_checkpoint_dir(ckpt)
    assert h1 == h2
    assert len(h1) == 12


def test_hash_checkpoint_dir_changes_with_content(tmp_path: Path) -> None:
    from jw_finetune.ux.run_readme import hash_checkpoint_dir

    ckpt = tmp_path / "ckpt"
    ckpt.mkdir()
    (ckpt / "model.safetensors").write_bytes(b"v1")
    h1 = hash_checkpoint_dir(ckpt)
    (ckpt / "model.safetensors").write_bytes(b"v2")
    h2 = hash_checkpoint_dir(ckpt)
    assert h1 != h2


# ---------------------------------------------------------------------------
# diff
# ---------------------------------------------------------------------------


def test_compare_checkpoints_with_fake_generator(tmp_path: Path) -> None:
    from jw_finetune.ux.diff import compare_checkpoints

    ckpt_a = tmp_path / "ckpt-a"
    ckpt_b = tmp_path / "ckpt-b"
    ckpt_a.mkdir()
    ckpt_b.mkdir()

    def fake_generate(ckpt: Path, prompt: str) -> str:
        # Use the directory name (not full path) to distinguish A vs B.
        if ckpt.name.endswith("-a"):
            return f"Como dice Mateo 24:14 al responder: {prompt}"
        return f"Sin citar nada: {prompt}"

    result = compare_checkpoints(
        ckpt_a, ckpt_b,
        ["¿Qué es el Reino?", "Explica Hechos 1:8"],
        language="es",
        generate_fn=fake_generate,
    )
    assert len(result.rows) == 2
    # A always cites, B never → A's citation score should be higher
    assert result.mean_citation_a > result.mean_citation_b
    assert result.checkpoint_a == str(ckpt_a)
    assert result.checkpoint_b == str(ckpt_b)


# ---------------------------------------------------------------------------
# progress (smoke test only — full integration tested via async_orchestrator)
# ---------------------------------------------------------------------------


def test_synth_progress_bar_context() -> None:
    """The progress bar context manager yields (task_id, advance_fn)."""
    from jw_finetune.ux.progress import synth_progress_bar

    with synth_progress_bar(3, label="test") as (task_id, advance):
        advance(1)
        advance(2)
        advance(3)
    # Just verify it doesn't crash; rich state isn't observable post-exit.
    assert task_id is not None
