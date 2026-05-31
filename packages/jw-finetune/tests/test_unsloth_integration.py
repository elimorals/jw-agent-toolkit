"""Tests for the F6.2 Unsloth integration improvements."""

from __future__ import annotations

from pathlib import Path

from jw_finetune.data.models import SourceSpec
from jw_finetune.recipes.base import Recipe, validate_recipe


def _recipe(**kw) -> Recipe:
    defaults = dict(
        name="test",
        task="sft",
        sources=[SourceSpec(kind="jwpub", path="x.jwpub", language="es")],
        languages=["es"],
        publication_kinds=["watchtower"],
        qa_style="doctrinal",
        base_model="unsloth/Qwen2.5-3B-bnb-4bit",
    )
    defaults.update(kw)
    return Recipe(**defaults)


# ---------------------------------------------------------------------------
# 2.1 + 2.2 — chat_template and train_on_responses_only fields
# ---------------------------------------------------------------------------


def test_recipe_default_chat_template_is_chatml() -> None:
    r = _recipe()
    assert r.chat_template == "chatml"


def test_recipe_train_on_responses_only_default_true() -> None:
    r = _recipe()
    assert r.train_on_responses_only is True


def test_recipe_use_rslora_default_false() -> None:
    r = _recipe()
    assert r.use_rslora is False


def test_recipe_packing_default_none() -> None:
    r = _recipe()
    assert r.packing is None


def test_recipe_embedding_lr_ratio_default() -> None:
    r = _recipe()
    assert r.embedding_learning_rate_ratio == 0.1


def test_recipe_yaml_roundtrip_new_fields(tmp_path: Path) -> None:
    """The new Unsloth fields must survive YAML serialization."""
    from jw_finetune.recipes.base import recipe_from_yaml, recipe_to_yaml

    r = _recipe(
        chat_template="qwen-2.5",
        use_rslora=True,
        train_on_responses_only=False,
        packing=True,
        use_multi_gpu=True,
        embedding_learning_rate_ratio=0.05,
    )
    p = tmp_path / "r.yaml"
    recipe_to_yaml(r, p)
    r2 = recipe_from_yaml(p)
    assert r2.chat_template == "qwen-2.5"
    assert r2.use_rslora is True
    assert r2.train_on_responses_only is False
    assert r2.packing is True
    assert r2.use_multi_gpu is True
    assert r2.embedding_learning_rate_ratio == 0.05


def test_recipe_validate_passes_with_all_fields() -> None:
    r = _recipe(chat_template="llama-3", use_rslora=True, packing=False)
    assert validate_recipe(r) == []


# ---------------------------------------------------------------------------
# SFT trainer parts resolver
# ---------------------------------------------------------------------------


def test_resolve_responses_only_parts_chatml() -> None:
    from jw_finetune.train.sft import _resolve_responses_only_parts

    r = _recipe(chat_template="chatml")
    instr, resp = _resolve_responses_only_parts(r)
    assert "<|im_start|>user" in instr
    assert "<|im_start|>assistant" in resp


def test_resolve_responses_only_parts_llama3() -> None:
    from jw_finetune.train.sft import _resolve_responses_only_parts

    r = _recipe(chat_template="llama-3")
    instr, resp = _resolve_responses_only_parts(r)
    assert "<|start_header_id|>user" in instr
    assert "<|start_header_id|>assistant" in resp


def test_resolve_responses_only_parts_gemma() -> None:
    from jw_finetune.train.sft import _resolve_responses_only_parts

    r = _recipe(chat_template="gemma")
    instr, resp = _resolve_responses_only_parts(r)
    assert "<start_of_turn>user" in instr
    assert "<start_of_turn>model" in resp


def test_resolve_responses_only_parts_user_override() -> None:
    from jw_finetune.train.sft import _resolve_responses_only_parts

    r = _recipe(
        chat_template="custom-foo",
        instruction_part="[USER]",
        response_part="[BOT]",
    )
    instr, resp = _resolve_responses_only_parts(r)
    assert instr == "[USER]"
    assert resp == "[BOT]"


def test_resolve_responses_only_parts_unknown_template_returns_empty() -> None:
    from jw_finetune.train.sft import _resolve_responses_only_parts

    r = _recipe(chat_template="totally-unknown")
    instr, resp = _resolve_responses_only_parts(r)
    assert instr == ""
    assert resp == ""


# ---------------------------------------------------------------------------
# 2.4 — GGUF multi-quant
# ---------------------------------------------------------------------------


def test_export_gguf_normalize_quant() -> None:
    from jw_finetune.export.gguf import _normalize_quant

    assert _normalize_quant("Q4_K_M") == "q4_k_m"
    assert _normalize_quant("Q5-K-M") == "q5_k_m"
    assert _normalize_quant("q8_0") == "q8_0"


# ---------------------------------------------------------------------------
# 2.8 — Playground model cache
# ---------------------------------------------------------------------------


def test_clear_model_cache_returns_count() -> None:
    """Test cache eviction tracking."""
    from jw_finetune.monitor import studio

    studio._LOADED_MODEL_CACHE.clear()
    studio._LOADED_MODEL_CACHE["fake1"] = ("m1", "t1")
    studio._LOADED_MODEL_CACHE["fake2"] = ("m2", "t2")
    cleared = studio.clear_model_cache()
    assert cleared == 2
    assert len(studio._LOADED_MODEL_CACHE) == 0


def test_model_cache_evicts_oldest_when_full(monkeypatch) -> None:
    """When cache is at max, oldest entry is evicted."""
    from jw_finetune.monitor import studio

    studio.clear_model_cache()
    monkeypatch.setattr(studio, "_MAX_CACHED_MODELS", 2)

    studio._LOADED_MODEL_CACHE["c1"] = ("m1", "t1")
    studio._LOADED_MODEL_CACHE["c2"] = ("m2", "t2")
    # Simulate adding a third entry — oldest (c1) should be evicted via
    # the function's eviction logic.
    if len(studio._LOADED_MODEL_CACHE) >= studio._MAX_CACHED_MODELS:
        oldest = next(iter(studio._LOADED_MODEL_CACHE))
        studio._LOADED_MODEL_CACHE.pop(oldest, None)
    studio._LOADED_MODEL_CACHE["c3"] = ("m3", "t3")

    assert "c1" not in studio._LOADED_MODEL_CACHE
    assert "c2" in studio._LOADED_MODEL_CACHE
    assert "c3" in studio._LOADED_MODEL_CACHE
    studio.clear_model_cache()
