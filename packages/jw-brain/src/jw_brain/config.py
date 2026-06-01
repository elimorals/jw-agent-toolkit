"""Per-brain config loaded from <brain>/config.toml."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path


@dataclass
class BrainConfig:
    name: str
    domain: str = "tj"
    vault: Path = Path()
    vault_namespace: str = "Second-Brain"
    graph_backend: str = "duckdb"
    graph_path: str = "graph/backend.duckdb"
    llm_provider: str = "ollama"
    llm_model: str = "llama3.1:8b"
    prompt_version: str = "v1"
    cache_dir: Path = Path()
    snapshot_on_compile: bool = True
    nli_provider: str = "deberta"
    nli_threshold: float = 0.7


def default_config(brain_path: Path, *, name: str = "jw-tj", domain: str = "tj") -> BrainConfig:
    return BrainConfig(
        name=name,
        domain=domain,
        vault=brain_path / "vault",
        graph_path=str(brain_path / "graph" / "backend.duckdb"),
        cache_dir=brain_path / "cache",
    )


def load_brain_config(brain_path: Path) -> BrainConfig:
    p = brain_path / "config.toml"
    if not p.exists():
        return default_config(brain_path)
    raw = tomllib.loads(p.read_text(encoding="utf-8"))
    flat: dict = {}
    for section in ("brain", "compiler", "lint"):
        flat.update(raw.get(section, {}) or {})
    cfg = default_config(brain_path, name=flat.get("name", "jw-tj"), domain=flat.get("domain", "tj"))
    if "vault" in flat:
        cfg.vault = Path(flat["vault"]).expanduser()
    if "vault_namespace" in flat:
        cfg.vault_namespace = flat["vault_namespace"]
    if "graph_backend" in flat:
        cfg.graph_backend = flat["graph_backend"]
    if "graph_path" in flat:
        cfg.graph_path = flat["graph_path"]
    if "llm_provider" in flat:
        cfg.llm_provider = flat["llm_provider"]
    if "llm_model" in flat:
        cfg.llm_model = flat["llm_model"]
    if "prompt_version" in flat:
        cfg.prompt_version = flat["prompt_version"]
    if "cache_dir" in flat:
        cfg.cache_dir = Path(flat["cache_dir"]).expanduser()
    if "snapshot_on_compile" in flat:
        cfg.snapshot_on_compile = bool(flat["snapshot_on_compile"])
    if "nli_provider" in flat:
        cfg.nli_provider = flat["nli_provider"]
    if "nli_threshold" in flat:
        cfg.nli_threshold = float(flat["nli_threshold"])
    return cfg


def write_default_config(brain_path: Path, *, domain: str = "tj") -> Path:
    brain_path.mkdir(parents=True, exist_ok=True)
    cfg_path = brain_path / "config.toml"
    body = f"""# Brain config — Fase 49
[brain]
name = "jw-{domain}"
domain = "{domain}"
vault = "{brain_path / 'vault'}"
vault_namespace = "Second-Brain"
graph_backend = "duckdb"
graph_path = "{brain_path / 'graph' / 'backend.duckdb'}"

[compiler]
llm_provider = "ollama"
llm_model = "llama3.1:8b"
prompt_version = "v1"
cache_dir = "{brain_path / 'cache'}"
snapshot_on_compile = true

[lint]
nli_provider = "deberta"
nli_threshold = 0.7
"""
    cfg_path.write_text(body, encoding="utf-8")
    return cfg_path
