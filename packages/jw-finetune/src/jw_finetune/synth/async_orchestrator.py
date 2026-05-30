"""Async + cached + concurrent Q&A synthesis orchestrator.

Wraps the synchronous `synthesize_chunk` with:
  * `asyncio.Semaphore` for concurrency limiting (Anthropic ~10, Ollama ~4)
  * `SynthCache` for hot-cache reuse across `prepare` runs
  * Retry/backoff for transient provider failures
  * Optional progress callback for rich progress bars

The function is async but the underlying provider call is sync. We use
`asyncio.to_thread()` to keep the event loop free.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass, field

from jw_rag.chunker import Chunk

from jw_finetune.data.formats import QAPair
from jw_finetune.synth.cache import SynthCache, cache_key_for
from jw_finetune.synth.orchestrator import synthesize_chunk
from jw_finetune.synth.provider import LLMProvider
from jw_finetune.synth.retry import retry_with_backoff

logger = logging.getLogger(__name__)


@dataclass
class AsyncSynthResult:
    """Aggregate result over many chunks."""

    pairs: list[QAPair] = field(default_factory=list)
    total_chunks: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    parse_errors: int = 0
    total_rejected: int = 0


async def synthesize_chunks_async(
    chunks: Iterable[Chunk],
    *,
    provider: LLMProvider,
    qa_style: str,
    language: str,
    n_pairs: int = 3,
    temperature: float = 0.5,
    max_tokens: int = 1024,
    concurrency: int = 4,
    cache: SynthCache | None = None,
    use_cache: bool = True,
    max_retry_attempts: int = 4,
    progress: Callable[[int, int, int], Awaitable[None] | None] | None = None,
) -> AsyncSynthResult:
    """Synthesize Q&A for many chunks concurrently.

    `progress` (if provided) is called with (completed, total, pairs_so_far)
    after every chunk completes. Can be sync or async.
    """
    chunks_list = list(chunks)
    total = len(chunks_list)
    result = AsyncSynthResult(total_chunks=total)
    cache = cache if (use_cache and cache is not None) else (SynthCache() if use_cache else None)
    semaphore = asyncio.Semaphore(max(1, concurrency))

    async def _process_one(idx: int, chunk: Chunk) -> list[QAPair]:
        async with semaphore:
            # Check cache first.
            key = cache_key_for(
                chunk_id=chunk.id,
                chunk_text=chunk.text,
                qa_style=qa_style,
                language=language,
                n_pairs=n_pairs,
                provider_name=getattr(provider, "name", "unknown"),
                provider_model=getattr(provider, "model", "unknown"),
            )
            if cache is not None:
                cached = cache.get(key)
                if cached is not None:
                    result.cache_hits += 1
                    return cached
                result.cache_misses += 1

            # Synth (with retry).
            def _do_call() -> list[QAPair]:
                synth_res = synthesize_chunk(
                    chunk,
                    provider=provider,
                    qa_style=qa_style,
                    language=language,
                    n_pairs=n_pairs,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                if synth_res.parse_error:
                    result.parse_errors += 1
                result.total_rejected += synth_res.rejected
                return synth_res.pairs

            pairs = await asyncio.to_thread(
                retry_with_backoff,
                _do_call,
                max_attempts=max_retry_attempts,
                label=f"synth chunk={chunk.id}",
            )

            # Save to cache if any pairs survived.
            if cache is not None:
                cache.put(
                    key, pairs,
                    chunk_id=chunk.id,
                    qa_style=qa_style,
                    language=language,
                    provider=getattr(provider, "name", "unknown"),
                )
            return pairs

    pending = [
        asyncio.create_task(_process_one(i, c))
        for i, c in enumerate(chunks_list)
    ]
    completed = 0
    for coro in asyncio.as_completed(pending):
        try:
            pairs = await coro
            result.pairs.extend(pairs)
        except Exception as e:  # noqa: BLE001
            logger.error("chunk synthesis ultimately failed: %s", e)
            result.parse_errors += 1
        completed += 1
        if progress is not None:
            try:
                ret = progress(completed, total, len(result.pairs))
                if asyncio.iscoroutine(ret):
                    await ret
            except Exception as e:  # noqa: BLE001
                logger.debug("progress callback error: %s", e)

    return result
