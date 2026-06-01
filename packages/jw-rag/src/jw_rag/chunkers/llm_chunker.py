"""LLMChunker — opt-in deep mode.

Pipeline:
  1) Run SemanticChunker to get a heuristic chunking.
  2) Ask the provider for index-level split/merge actions
     (NEVER rewrites text — Policy #6).
  3) Apply actions deterministically. Persist a cache by content hash.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from jw_rag.chunkers.paragraph_chunker import Chunk
from jw_rag.chunkers.semantic_chunker import SemanticChunker

logger = logging.getLogger(__name__)

PROMPT_VERSION = "v1"


class ChunkerProvider(Protocol):
    @property
    def provider_id(self) -> str: ...

    def propose_actions(
        self,
        *,
        source_id: str,
        chunks: list[Chunk],
        language: str,
    ) -> list[dict[str, Any]]: ...


@dataclass
class _CacheEntry:
    actions: list[dict[str, Any]]
    provider_id: str
    prompt_version: str


class LLMChunker:
    name = "llm"

    def __init__(
        self,
        *,
        provider: ChunkerProvider | None = None,
        max_chars: int = 1500,
        min_chars: int = 80,
        cache_dir: Path | None = None,
        strict: bool = False,
    ) -> None:
        self.max_chars = max_chars
        self.min_chars = min_chars
        self._semantic = SemanticChunker(max_chars=max_chars, min_chars=min_chars)
        self._provider = provider or _default_provider()
        self.cache_dir = cache_dir or _default_cache_dir()
        self.strict = strict
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def chunk(
        self,
        paragraphs: list[str],
        source_id: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> list[Chunk]:
        base_meta = dict(metadata or {})
        semantic_chunks = self._semantic.chunk(paragraphs, source_id, metadata=base_meta)
        if not semantic_chunks:
            return []

        language = (
            base_meta.get("language")
            or semantic_chunks[0].metadata.get("language_detected")
            or "en"
        )

        cache_key = _cache_key(
            source_id=source_id,
            paragraphs=paragraphs,
            provider_id=self._provider.provider_id,
            prompt_version=PROMPT_VERSION,
        )
        cached = _load_cache(self.cache_dir, cache_key)
        if cached is not None:
            actions = cached.actions
        else:
            actions = list(
                self._provider.propose_actions(
                    source_id=source_id,
                    chunks=semantic_chunks,
                    language=language,
                )
            )
            _save_cache(
                self.cache_dir,
                cache_key,
                _CacheEntry(
                    actions=actions,
                    provider_id=self._provider.provider_id,
                    prompt_version=PROMPT_VERSION,
                ),
            )

        final = _apply_actions(semantic_chunks, actions, strict=self.strict)
        for c in final:
            c.metadata["chunker"] = "llm"
            c.metadata.setdefault("llm_actions_applied", list(actions))
        return final


def _default_cache_dir() -> Path:
    root = Path(
        os.environ.get("JW_CHUNK_CACHE_DIR")
        or (Path.home() / ".jw-agent-toolkit" / "chunk-cache")
    )
    return root


def _default_provider() -> ChunkerProvider:
    """Lazy: try jw_gen.providers.resolve(); fall back to no-op fake."""

    try:
        from jw_gen.providers import resolve  # type: ignore[import-not-found]

        provider = resolve()
        if provider is not None:
            return _AdaptedGenProvider(provider)
    except Exception:  # pragma: no cover
        pass
    from jw_rag.chunkers.fakes import FakeChunkerProvider

    return FakeChunkerProvider(actions=[])


class _AdaptedGenProvider:
    """Adapt a jw_gen GenerationProvider to the ChunkerProvider interface."""

    def __init__(self, gen: Any) -> None:
        self._gen = gen

    @property
    def provider_id(self) -> str:
        return getattr(self._gen, "id", self._gen.__class__.__name__)

    def propose_actions(
        self,
        *,
        source_id: str,
        chunks: list[Chunk],
        language: str,
    ) -> list[dict[str, Any]]:
        prompt = _build_prompt(chunks=chunks, language=language)
        try:
            raw = self._gen.complete(prompt, temperature=0.0)
        except Exception as exc:  # noqa: BLE001
            logger.warning("LLMChunker provider call failed: %s", exc)
            return []
        try:
            data = json.loads(raw)
        except Exception:
            logger.warning("LLMChunker got non-JSON output: %r", raw[:200])
            return []
        actions = data.get("actions") if isinstance(data, dict) else None
        return actions if isinstance(actions, list) else []


def _build_prompt(*, chunks: list[Chunk], language: str) -> str:
    rendered = "\n\n".join(
        f"[chunk {i}]\n{c.text}" for i, c in enumerate(chunks)
    )
    return (
        f"You are a chunk auditor for language '{language}'. Read the following "
        f"chunks (numbered) and propose ONLY index-level actions to improve "
        f"argumentative cohesion. NEVER rewrite text. Return strict JSON:\n"
        f'{{"actions": [{{"op": "split"|"merge", ...}}]}}\n\n'
        f"Chunks:\n{rendered}"
    )


def _cache_key(*, source_id: str, paragraphs: list[str], provider_id: str, prompt_version: str) -> str:
    h = hashlib.sha256()
    h.update(source_id.encode("utf-8"))
    h.update(b"\x00")
    h.update("\n".join(paragraphs).encode("utf-8"))
    h.update(b"\x00")
    h.update(provider_id.encode("utf-8"))
    h.update(b"\x00")
    h.update(prompt_version.encode("utf-8"))
    return h.hexdigest()


def _cache_path(cache_dir: Path, key: str) -> Path:
    return cache_dir / key[:2] / f"{key}.json"


def _load_cache(cache_dir: Path, key: str) -> _CacheEntry | None:
    p = _cache_path(cache_dir, key)
    if not p.exists():
        return None
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        return _CacheEntry(
            actions=list(raw.get("actions", [])),
            provider_id=str(raw.get("provider_id", "")),
            prompt_version=str(raw.get("prompt_version", "")),
        )
    except Exception:  # pragma: no cover
        return None


def _save_cache(cache_dir: Path, key: str, entry: _CacheEntry) -> None:
    p = _cache_path(cache_dir, key)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps(
            {
                "actions": entry.actions,
                "provider_id": entry.provider_id,
                "prompt_version": entry.prompt_version,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def _apply_actions(
    chunks: list[Chunk],
    actions: list[dict[str, Any]],
    *,
    strict: bool,
) -> list[Chunk]:
    out = list(chunks)
    for action in actions:
        op = action.get("op")
        if op == "split":
            idx = action.get("chunk_index")
            after_para = action.get("after_paragraph")
            if not isinstance(idx, int) or not (0 <= idx < len(out)):
                if strict:
                    raise ValueError(f"invalid chunk_index in action: {action}")
                continue
            if not isinstance(after_para, int):
                if strict:
                    raise ValueError(f"invalid after_paragraph in action: {action}")
                continue
            split_result = _split_chunk_after_paragraph(out[idx], after_para)
            if split_result is None:
                continue
            left, right = split_result
            out[idx:idx + 1] = [left, right]
        elif op == "merge":
            indices = action.get("chunk_indices")
            if not isinstance(indices, list) or not all(isinstance(i, int) for i in indices):
                if strict:
                    raise ValueError(f"invalid chunk_indices in action: {action}")
                continue
            if any(not (0 <= i < len(out)) for i in indices):
                if strict:
                    raise ValueError(f"out-of-range chunk_indices in action: {action}")
                continue
            indices_sorted = sorted(set(indices))
            if not _are_consecutive(indices_sorted):
                if strict:
                    raise ValueError(f"merge requires consecutive indices, got {indices_sorted}")
                continue
            merged = _merge_chunks([out[i] for i in indices_sorted])
            first = indices_sorted[0]
            last = indices_sorted[-1]
            out[first:last + 1] = [merged]
        else:
            if strict:
                raise ValueError(f"unknown op: {op!r}")
    return [
        Chunk(
            id=f"{c.source_id}#{i}",
            text=c.text,
            source_id=c.source_id,
            metadata=c.metadata,
        )
        for i, c in enumerate(out)
    ]


def _split_chunk_after_paragraph(c: Chunk, after_para: int) -> tuple[Chunk, Chunk] | None:
    para_ids = c.metadata.get("para_ids") or []
    if after_para < 0 or after_para >= len(para_ids) - 1:
        return None
    parts = c.text.split(" ")
    boundary = int(len(parts) * (after_para + 1) / len(para_ids))
    left_text = " ".join(parts[:boundary]).strip()
    right_text = " ".join(parts[boundary:]).strip()
    if not left_text or not right_text:
        return None
    left = Chunk(
        id=c.id,
        text=left_text,
        source_id=c.source_id,
        metadata={**c.metadata, "para_ids": para_ids[: after_para + 1], "llm_split": True},
    )
    right = Chunk(
        id=c.id + "_b",
        text=right_text,
        source_id=c.source_id,
        metadata={**c.metadata, "para_ids": para_ids[after_para + 1 :], "llm_split": True},
    )
    return left, right


def _merge_chunks(items: list[Chunk]) -> Chunk:
    para_ids: list[int] = []
    for c in items:
        para_ids.extend(c.metadata.get("para_ids") or [])
    return Chunk(
        id=items[0].id,
        text=" ".join(c.text for c in items).strip(),
        source_id=items[0].source_id,
        metadata={**items[0].metadata, "para_ids": para_ids, "llm_merged": True},
    )


def _are_consecutive(indices: list[int]) -> bool:
    return all(indices[i + 1] - indices[i] == 1 for i in range(len(indices) - 1))
