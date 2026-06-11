"""Default-RAG / default-NLI factory tests for F70 (Fase 70 post-MVP)."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from jw_core.verification.image_quote import factories


def test_default_rag_retriever_none_without_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(factories.ENV_STORE_PATH, raising=False)
    assert factories.default_rag_retriever() is None


def test_default_rag_retriever_returns_none_when_store_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    monkeypatch.setenv(
        factories.ENV_STORE_PATH, str(tmp_path / "nope.json")
    )

    class _BoomEmbedder:
        dim = 0

        def embed(self, texts):  # pragma: no cover - never reached
            raise RuntimeError("boom")

    monkeypatch.setattr(
        factories,
        "default_rag_retriever",
        factories.default_rag_retriever,
    )

    # Force VectorStore import to raise by injecting jw_rag stub
    import sys
    import types as _types

    fake_mod = _types.ModuleType("jw_rag")
    fake_mod.VectorStore = lambda *a, **kw: (_ for _ in ()).throw(  # type: ignore[attr-defined]
        RuntimeError("cannot open")
    )
    fake_mod.get_default_embedder = lambda: _BoomEmbedder()  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "jw_rag", fake_mod)

    assert factories.default_rag_retriever() is None


def test_default_rag_retriever_routes_hits(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    """Happy path: a mock store returns one chunk, we get one SimpleHit."""

    import sys
    import types as _types

    fake_chunk = SimpleNamespace(
        text="quoted text",
        metadata={
            "source_url": "https://jw.org/x",
            "source_pub_code": "w23",
        },
    )
    fake_hit = SimpleNamespace(chunk=fake_chunk, score=0.9, rank=0)

    class _Store:
        def __init__(self, *a, **kw):
            pass

        def hybrid_search(self, query, *, top_k):
            assert top_k == 5
            return [fake_hit]

    fake_mod = _types.ModuleType("jw_rag")
    fake_mod.VectorStore = _Store  # type: ignore[attr-defined]
    fake_mod.get_default_embedder = lambda: SimpleNamespace(dim=8)  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "jw_rag", fake_mod)
    monkeypatch.setenv(
        factories.ENV_STORE_PATH, str(tmp_path / "store.json")
    )

    retriever = factories.default_rag_retriever()
    assert retriever is not None

    hits = asyncio.run(retriever("test query"))
    assert len(hits) == 1
    assert hits[0].source_url == "https://jw.org/x"
    assert hits[0].source_pub_code == "w23"
    assert hits[0].source_text_original == "quoted text"


def test_default_nli_adapter_translates_evaluate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_verdict = SimpleNamespace(verdict="entails", score=0.91)

    class _Provider:
        def evaluate(self, claim, premise, *, language):
            assert claim == "claim"
            assert premise == "premise"
            assert language == "es"
            return fake_verdict

    import jw_core.fidelity as fid

    monkeypatch.setattr(
        fid, "get_default_nli_provider", lambda: _Provider()
    )
    nli = factories.default_nli(language="es")
    assert nli is not None
    out = nli.evaluate_entailment(claim="claim", premise="premise")
    assert out is fake_verdict


def test_default_nli_returns_none_on_factory_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import jw_core.fidelity as fid

    def boom():
        raise RuntimeError("no nli backend")

    monkeypatch.setattr(fid, "get_default_nli_provider", boom)
    assert factories.default_nli() is None


def test_engine_use_real_defaults_wires_factories(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    """`use_real_defaults=True` should call factory helpers when retriever/nli are None."""

    from jw_core.verification.image_quote import engine

    sentinel_retriever = lambda q: asyncio.sleep(0, result=[])  # noqa: E731
    sentinel_nli = SimpleNamespace(
        evaluate_entailment=lambda *, claim, premise: SimpleNamespace(
            verdict="neutral", score=0.0
        )
    )

    monkeypatch.setattr(
        factories, "default_rag_retriever", lambda: sentinel_retriever
    )
    monkeypatch.setattr(factories, "default_nli", lambda language="es": sentinel_nli)

    # Smallest possible image — engine uses load_image then ocr_text_override
    img = tmp_path / "x.png"
    img.write_bytes(b"")
    monkeypatch.setattr(
        engine,
        "load_image",
        lambda p: (None, {"phash": "", "format": "PNG", "size": (1, 1)}),
    )

    out = asyncio.run(
        engine.verify_image_quote(
            str(img),
            ocr_text_override="texto",
            use_real_defaults=True,
        )
    )
    assert out.verdict is not None
