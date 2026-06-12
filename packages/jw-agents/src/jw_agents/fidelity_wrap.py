"""@fidelity_wrap — wrap async agents to verify their findings.

Two orthogonal checks run per Finding:

  1. **NLI fidelity** (Phase 39): `excerpt` entails `summary` according
     to the configured NLI provider. A non-entails verdict or a low
     score is "failed".

  2. **Fidelity principles** (F77 — opt-in): the YAML principles loaded
     by `jw_eval.principles.load_principles` are matched (regex tier
     only — NLI/LLM checks live inside the synth judge). A `hard`
     match is always a failure; a `soft` match is annotated only.

Both checks are independent: a Finding can pass NLI and fail a
principle, or vice versa. The `on_fail` policy applies to either kind
of failure; `metadata` records which one fired so downstream tooling
can distinguish.

Why lazy-import `jw_eval.principles` instead of declaring it in
`pyproject.toml`: jw-eval already depends on jw-agents (for golden
cases that reference agents), so a direct dep here would be a cycle.
The lazy try/except matches the pattern in
`jw_finetune.synth.judge.judge`. If jw-eval isn't installed,
principle checks are silently skipped (callers get NLI only).

Default behavior is `on_fail="warn"`: findings are NEVER dropped
silently. Only `on_fail="reject"` filters the result list, and it
always logs a warning describing what was dropped.

Idempotence: we check `Finding.metadata` for an existing
`nli_verdict` (or `principle_violations`) and skip re-evaluation.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from functools import wraps
from typing import Any, Literal

from jw_core.fidelity import NLIProvider

from jw_agents.base import AgentResult, Finding

OnFail = Literal["warn", "reject", "annotate_only"]


def _principle_violations(text: str, principles: list[object] | None) -> list[object]:
    """Run the regex tier of `jw_eval.principles.violations_for`.

    Lazy import so jw-agents stays free of a jw-eval dep at install
    time. Returns an empty list when jw-eval is not installed OR no
    principles were passed.
    """
    if not principles:
        return []
    try:
        from jw_eval.principles import violations_for  # type: ignore[import-not-found]
    except ImportError:
        return []
    return list(violations_for(text, principles))  # type: ignore[arg-type]


def _filter_principles_for_agent(principles: list[object] | None, agent_name: str) -> list[object]:
    """Keep only principles whose `applies_to` includes the agent (or is global)."""
    if not principles:
        return []
    out: list[object] = []
    for p in principles:
        applies = getattr(p, "applies", None)
        if applies is None or applies(agent_name):
            out.append(p)
    return out


def _stamp_principle_metadata(finding: Finding, violations: list[object]) -> tuple[list[str], list[str]]:
    """Record violations on the finding's metadata. Returns (hard_ids, soft_ids)."""
    hard_ids: list[str] = []
    soft_ids: list[str] = []
    for p in violations:
        pid = getattr(p, "id", "?")
        sev = getattr(p, "severity", "soft")
        if sev == "hard":
            hard_ids.append(pid)
        else:
            soft_ids.append(pid)
    if violations:
        finding.metadata["principle_violations"] = ",".join(getattr(p, "id", "?") for p in violations)
        finding.metadata["principle_hard"] = ",".join(hard_ids)
        finding.metadata["principle_soft"] = ",".join(soft_ids)
    return hard_ids, soft_ids


def fidelity_wrap(
    *,
    min_score: float = 0.7,
    on_fail: OnFail = "warn",
    provider: NLIProvider | None = None,
    min_excerpt_chars: int = 32,
    principles: list[object] | None = None,
) -> Callable[[Callable[..., Awaitable[AgentResult]]], Callable[..., Awaitable[AgentResult]]]:
    """Decorate an async agent to NLI-verify each Finding and check
    fidelity principles (F77).

    Args:
        min_score: NLI failure threshold. A verdict with
            ``score < min_score`` (or any non-"entails" verdict) is
            treated as failure.
        on_fail:
            "annotate_only" → write metadata, no warning, no drop.
            "warn"          → also append a warning to
                              ``AgentResult.warnings``.
            "reject"        → also drop the finding from the result.
            Policy applies to NLI failures AND to any `hard` principle
            violation. `soft` violations are always annotate-only,
            regardless of ``on_fail``.
        provider: explicit ``NLIProvider``. ``None`` → resolved lazily
            via ``get_default_nli_provider()``.
        min_excerpt_chars: excerpts shorter than this are not sent to
            the NLI provider; their ``nli_verdict`` is set to
            "skipped". Default 32 — this filters out citations whose
            excerpt is just a bible reference label
            (e.g. "John 3:16"). Principle checks always run regardless
            of excerpt length, since they're cheap regex.
        principles: optional list of ``jw_eval.principles.Principle``.
            ``None`` (default) skips the principle tier entirely.
            Filtered per Finding by the agent name in
            ``AgentResult.agent_name``.
    """

    def deco(
        fn: Callable[..., Awaitable[AgentResult]],
    ) -> Callable[..., Awaitable[AgentResult]]:
        @wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> AgentResult:
            result = await fn(*args, **kwargs)
            local_provider = provider
            if local_provider is None:
                from jw_core.fidelity import get_default_nli_provider

                local_provider = get_default_nli_provider()

            language = str(result.metadata.get("language", "en"))
            # Filter principles to the ones applicable to this agent.
            scoped_principles = _filter_principles_for_agent(principles, result.agent_name)

            kept: list[Finding] = []
            for f in result.findings:
                # Idempotence — if NLI already ran, skip NLI but still
                # consider principles (different layers may run them
                # independently).
                if "nli_verdict" in f.metadata:
                    # Run principles even on re-entry for safety.
                    if "principle_violations" not in f.metadata:
                        text = f.summary + " " + f.excerpt
                        viol = _principle_violations(text, scoped_principles)
                        hard, _ = _stamp_principle_metadata(f, viol)
                        if hard and on_fail == "reject":
                            result.warnings.append(f"Rejected finding (hard principle: {','.join(hard)})")
                            continue
                        if hard and on_fail == "warn":
                            result.warnings.append(f"Hard principle violation ({','.join(hard)}) on {f.citation.url}")
                    kept.append(f)
                    continue

                # -- NLI tier ------------------------------------------------
                if len(f.excerpt) < min_excerpt_chars:
                    f.metadata["nli_verdict"] = "skipped"
                    f.metadata["nli_score"] = None  # type: ignore[assignment]
                    f.metadata["nli_provider"] = local_provider.name
                    nli_failed = False
                    nli_summary = "skipped"
                else:
                    verdict = local_provider.evaluate(
                        claim=f.summary,
                        premise=f.excerpt,
                        language=language,
                    )
                    f.metadata["nli_verdict"] = verdict.verdict
                    f.metadata["nli_score"] = round(verdict.score, 4)  # type: ignore[assignment]
                    f.metadata["nli_provider"] = verdict.provider
                    nli_failed = verdict.verdict != "entails" or verdict.score < min_score
                    nli_summary = f"NLI={verdict.verdict}, score={verdict.score:.2f}"

                # -- Principle tier ------------------------------------------
                text_for_principles = f.summary + " " + f.excerpt
                violations = _principle_violations(text_for_principles, scoped_principles)
                hard_ids, _ = _stamp_principle_metadata(f, violations)

                failed = nli_failed or bool(hard_ids)
                if not failed:
                    kept.append(f)
                    continue

                # -- Apply on_fail policy ------------------------------------
                detail_parts: list[str] = []
                if nli_failed:
                    detail_parts.append(f"Low NLI fidelity ({nli_summary})")
                if hard_ids:
                    detail_parts.append(f"Hard principle: {','.join(hard_ids)}")
                detail = "; ".join(detail_parts)

                if on_fail == "annotate_only":
                    kept.append(f)
                elif on_fail == "warn":
                    result.warnings.append(f"{detail} for citation {f.citation.url}")
                    kept.append(f)
                elif on_fail == "reject":
                    result.warnings.append(f"Rejected finding ({detail}) for citation {f.citation.url}")
                    # do not append — finding dropped

            result.findings = kept
            result.metadata["nli_min_score"] = min_score  # type: ignore[assignment]
            result.metadata["nli_on_fail"] = on_fail
            if principles is not None:
                result.metadata["fidelity_principles_count"] = len(scoped_principles)  # type: ignore[assignment]
            return result

        return wrapper

    return deco


__all__ = ["fidelity_wrap", "OnFail"]
