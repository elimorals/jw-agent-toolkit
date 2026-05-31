"""Tests for the studio extra routes."""

from __future__ import annotations

import json
from pathlib import Path

import pytest


def _has_fastapi() -> bool:
    try:
        import fastapi  # noqa: F401

        return True
    except ImportError:
        return False


pytestmark = pytest.mark.skipif(not _has_fastapi(), reason="fastapi not installed")


def _make_run(tmp_path: Path, run_name: str = "run-20260530-120000") -> Path:
    run = tmp_path / run_name
    run.mkdir(parents=True)
    (run / "events.jsonl").write_text(
        json.dumps({"kind": "step", "step": 1, "loss": 1.2}) + "\n",
        encoding="utf-8",
    )
    (run / "dataset_qa.jsonl").write_text(
        json.dumps(
            {
                "messages": [
                    {"role": "user", "content": "¿Qué es el Reino?"},
                    {"role": "assistant", "content": "El Reino es el gobierno celestial de Jehová."},
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )
    # Use a tiny recipe yaml
    import yaml  # type: ignore[import-untyped]

    yaml_content = yaml.safe_dump(
        {
            "name": "test",
            "task": "sft",
            "sources": [
                {
                    "kind": "jwpub",
                    "path": "x.jwpub",
                    "language": "es",
                    "pub_code_hint": "",
                    "publication_kind_hint": None,
                }
            ],
            "languages": ["es"],
            "publication_kinds": ["watchtower"],
            "qa_style": "doctrinal",
            "base_model": "unsloth/Qwen2.5-3B-bnb-4bit",
            "lora_rank": 16,
            "lora_alpha": 32,
            "lora_dropout": 0.0,
            "max_seq_len": 2048,
            "epochs": 1,
            "batch_size": 2,
            "gradient_accumulation": 4,
            "learning_rate": 2e-4,
            "warmup_ratio": 0.05,
            "weight_decay": 0.0,
            "min_chunk_chars": 80,
            "max_chunk_chars": 1500,
            "dedupe_threshold": 4,
            "synth_provider": "ollama",
            "synth_model": None,
            "qa_per_chunk": 3,
            "eval_split": 0.05,
            "output_dir": "./jw-finetune-workspace",
            "seed": 42,
            "extra": {},
        }
    )
    (run / "recipe.yaml").write_text(yaml_content, encoding="utf-8")
    (run / "checkpoints" / "final").mkdir(parents=True)
    return run


def test_studio_index_returns_html(tmp_path: Path) -> None:
    from fastapi.testclient import TestClient
    from jw_finetune.monitor.studio import create_studio_app

    events = tmp_path / "events.jsonl"
    events.write_text("", encoding="utf-8")
    app = create_studio_app(events, tmp_path)
    client = TestClient(app)
    r = client.get("/studio")
    assert r.status_code == 200
    assert "jw-finetune Studio" in r.text


def test_api_presets(tmp_path: Path) -> None:
    from fastapi.testclient import TestClient
    from jw_finetune.monitor.studio import create_studio_app

    events = tmp_path / "events.jsonl"
    events.write_text("", encoding="utf-8")
    app = create_studio_app(events, tmp_path)
    client = TestClient(app)
    r = client.get("/api/presets")
    assert r.status_code == 200
    body = r.json()
    names = [p["name"] for p in body["presets"]]
    assert "doctrinal-qa-es-sft" in names


def test_api_models(tmp_path: Path) -> None:
    from fastapi.testclient import TestClient
    from jw_finetune.monitor.studio import create_studio_app

    events = tmp_path / "events.jsonl"
    events.write_text("", encoding="utf-8")
    app = create_studio_app(events, tmp_path)
    client = TestClient(app)
    r = client.get("/api/models")
    assert r.status_code == 200
    body = r.json()
    assert len(body["models"]) > 0
    assert "id" in body["models"][0]


def test_api_runs(tmp_path: Path) -> None:
    from fastapi.testclient import TestClient
    from jw_finetune.monitor.studio import create_studio_app

    _make_run(tmp_path)
    events = tmp_path / "events.jsonl"
    events.write_text("", encoding="utf-8")
    app = create_studio_app(events, tmp_path)
    client = TestClient(app)
    r = client.get("/api/runs")
    assert r.status_code == 200
    body = r.json()
    assert len(body["runs"]) == 1
    assert body["runs"][0]["run_id"].startswith("run-")
    assert body["runs"][0]["task"] == "sft"


def test_api_run_detail(tmp_path: Path) -> None:
    from fastapi.testclient import TestClient
    from jw_finetune.monitor.studio import create_studio_app

    run = _make_run(tmp_path)
    events = tmp_path / "events.jsonl"
    events.write_text("", encoding="utf-8")
    app = create_studio_app(events, tmp_path)
    client = TestClient(app)
    r = client.get("/api/run/" + run.name)
    assert r.status_code == 200
    body = r.json()
    assert body["recipe"]["name"] == "test"
    assert body["dataset"]["count"] >= 1


def test_api_run_path_traversal_rejected(tmp_path: Path) -> None:
    from fastapi.testclient import TestClient
    from jw_finetune.monitor.studio import create_studio_app

    events = tmp_path / "events.jsonl"
    events.write_text("", encoding="utf-8")
    app = create_studio_app(events, tmp_path)
    client = TestClient(app)
    r = client.get("/api/run/" + "..%2F..%2Fetc")
    assert r.status_code == 404


def test_api_dataset_preview(tmp_path: Path) -> None:
    from fastapi.testclient import TestClient
    from jw_finetune.monitor.studio import create_studio_app

    run = _make_run(tmp_path)
    events = tmp_path / "events.jsonl"
    events.write_text("", encoding="utf-8")
    app = create_studio_app(events, tmp_path)
    client = TestClient(app)
    r = client.get(f"/api/dataset/{run.name}?limit=5")
    assert r.status_code == 200
    body = r.json()
    assert body["count"] >= 1
    assert body["rows"][0]["messages"][0]["role"] == "user"


def test_api_recipe_save_rejects_invalid(tmp_path: Path) -> None:
    from fastapi.testclient import TestClient
    from jw_finetune.monitor.studio import create_studio_app

    events = tmp_path / "events.jsonl"
    events.write_text("", encoding="utf-8")
    app = create_studio_app(events, tmp_path)
    client = TestClient(app)
    # Empty sources → validation should fail
    payload = {
        "name": "bad",
        "task": "sft",
        "sources": [],
        "languages": ["es"],
        "publication_kinds": ["watchtower"],
        "qa_style": "doctrinal",
        "base_model": "unsloth/Qwen2.5-3B-bnb-4bit",
    }
    r = client.post("/api/recipe/save", json=payload)
    assert r.status_code == 400
    body = r.json()
    assert any("sources" in e for e in body["errors"])


def test_api_chat_404_without_run(tmp_path: Path) -> None:
    from fastapi.testclient import TestClient
    from jw_finetune.monitor.studio import create_studio_app

    events = tmp_path / "events.jsonl"
    events.write_text("", encoding="utf-8")
    app = create_studio_app(events, tmp_path)
    client = TestClient(app)
    r = client.post("/api/chat", json={"run_id": "nonexistent", "prompt": "hola"})
    assert r.status_code == 404
