"""@fidelity_wrap — wrap async agents to NLI-verify their findings.

Spec: docs/superpowers/specs/2026-05-31-fase-39-nli-runtime-design.md
      §"Decorator".

Why async-aware: the toolkit's agents are all async (they fan-out HTTP
calls to wol.jw.org and chase finetune candidates). The decorator preserves
that interface — ``await wrapped(...)`` still returns an AgentResult.

Default behavior is ``on_fail="warn"``: findings are NEVER dropped silently.
The only mode that modifies findings is ``on_fail="reject"``, and it always
attaches a warning describing what was dropped.

Idempotence: we check ``Finding.metadata`` for an existing ``nli_verdict``
and skip re-evaluation. Cheap, observable.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from functools import wraps
from typing import Any, Literal

from jw_agents.base import AgentResult
from jw_core.fidelity import NLIProvider

OnFail = Literal["warn", "reject", "annotate_only"]


def fidelity_wrap(
    *,
    min_score: float = 0.7,
    on_fail: OnFail = "warn",
    provider: NLIProvider | None = None,
    min_excerpt_chars: int = 32,
) -> Callable[
    [Callable[..., Awaitable[AgentResult]]], Callable[..., Awaitable[AgentResult]]
]:
    """Decorate an async agent to NLI-verify each Finding.

    Args:
        min_score: failure threshold. A verdict with ``score < min_score``
            (or any non-"entails" verdict) is treated as failure.
        on_fail:
            "annotate_only" → write nli_* metadata, no warning, no drop.
            "warn"          → also append a warning to AgentResult.warnings.
            "reject"        → also drop the finding from the result.
        provider: explicit NLIProvider. None → resolved lazily via
            ``get_default_nli_provider()``.
        min_excerpt_chars: excerpts shorter than this are not sent to the
            provider; their ``nli_verdict`` is set to "skipped". Default 32 —
            this filters out citations whose excerpt is just a bible
            reference label (e.g. "John 3:16").
    """

    def deco(
        fn: Callable[..., Awaitable[AgentResult]],
    ) -> Callable[..., Awaitable[AgentResult]]:
        @wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> AgentResult:
            result = await fn(*args, **kwargs)
            # Resolve provider lazily so import jw_agents doesn't pull in
            # heavy providers at import time.
            local_provider = provider
            if local_provider is None:
                from jw_core.fidelity import get_default_nli_provider

                local_provider = get_default_nli_provider()

            language = str(result.metadata.get("language", "en"))
            kept = []
            for f in result.findings:
                # Idempotence — if some outer layer already evaluated, skip.
                if "nli_verdict" in f.metadata:
                    kept.append(f)
                    continue

                if len(f.excerpt) < min_excerpt_chars:
                    f.metadata["nli_verdict"] = "skipped"
                    f.metadata["nli_score"] = None
                    f.metadata["nli_provider"] = local_provider.name
                    kept.append(f)
                    continue

                verdict = local_provider.evaluate(
                    claim=f.summary,
                    premise=f.excerpt,
                    language=language,
                )
                f.metadata["nli_verdict"] = verdict.verdict
                f.metadata["nli_score"] = round(verdict.score, 4)
                f.metadata["nli_provider"] = verdict.provider

                failed = verdict.verdict != "entails" or verdict.score < min_score
                if not failed:
                    kept.append(f)
                    continue

                if on_fail == "annotate_only":
                    kept.append(f)
                elif on_fail == "warn":
                    result.warnings.append(
                        f"Low NLI fidelity ({verdict.verdict}, "
                        f"score={verdict.score:.2f}) for citation {f.citation.url}"
                    )
                    kept.append(f)
                elif on_fail == "reject":
                    result.warnings.append(
                        f"Rejected finding (NLI={verdict.verdict}, "
                        f"score={verdict.score:.2f}) for citation {f.citation.url}"
                    )
                    # do not append — finding dropped

            result.findings = kept
            result.metadata["nli_min_score"] = min_score
            result.metadata["nli_on_fail"] = on_fail
            return result

        return wrapper

    return deco


__all__ = ["fidelity_wrap", "OnFail"]
