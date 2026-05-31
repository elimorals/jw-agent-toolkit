"""ClaudeNLI — entailment via Anthropic's Claude.

Design (per spec §"ClaudeNLI"):

  - System prompt (cached): "You are an NLI judge. Decide if the CONCLUSION
    strictly entails from the PREMISE. Reply JSON-only: {verdict, score, reason}."
  - User prompt: "PREMISE:\\n{premise}\\n\\nCONCLUSION:\\n{claim}\\n\\nLanguage: {language}"
  - Parse JSON; on failure → verdict="neutral", score=0.5, raw["parse_error"]=raw.
  - Cost guard: truncate premise to 6000 chars when (premise + claim) > 8000.
  - Prompt caching: ``cache_control: {type: "ephemeral"}`` on the system block.
  - Model default: ``claude-sonnet-4-5-20250929``, override via ``JW_NLI_CLAUDE_MODEL``.

The optional ``client=`` kwarg in the constructor exists for testing —
production code passes nothing and we lazily instantiate ``Anthropic()``.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from jw_core.fidelity.nli import Target
from jw_core.fidelity.verdicts import NLIVerdict, ensure_verdict

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = "claude-sonnet-4-5-20250929"
_SYSTEM_PROMPT = (
    "You are an NLI judge. Decide if the CONCLUSION strictly entails from "
    "the PREMISE. Reply JSON-only with this exact shape: "
    '{"verdict": "entails"|"neutral"|"contradicts", '
    '"score": 0.0-1.0, "reason": "short explanation"}. '
    "Output nothing else."
)
_MAX_PREMISE_CHARS = 6000
_MAX_TOTAL_CHARS = 8000


class ClaudeNLI:
    name = "claude-nli"
    target: Target = "api"

    def __init__(self, *, client: Any | None = None) -> None:
        self._client = client  # injectable for tests

    def is_available(self) -> bool:
        if not os.getenv("ANTHROPIC_API_KEY"):
            return False
        try:
            import anthropic  # noqa: F401
        except ImportError:
            return False
        return True

    def _ensure_client(self) -> Any:
        if self._client is not None:
            return self._client
        from anthropic import Anthropic

        self._client = Anthropic()
        return self._client

    def _truncate(self, premise: str, claim: str) -> str:
        if len(premise) + len(claim) <= _MAX_TOTAL_CHARS:
            return premise
        return premise[:_MAX_PREMISE_CHARS]

    def evaluate(
        self, claim: str, premise: str, *, language: str = "en"
    ) -> NLIVerdict:
        client = self._ensure_client()
        model = os.getenv("JW_NLI_CLAUDE_MODEL", _DEFAULT_MODEL)
        truncated_premise = self._truncate(premise, claim)
        user_body = (
            f"PREMISE:\n{truncated_premise}\n\n"
            f"CONCLUSION:\n{claim}\n\n"
            f"Language: {language}"
        )
        system_blocks = [
            {
                "type": "text",
                "text": _SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ]
        try:
            msg = client.messages.create(
                model=model,
                max_tokens=256,
                system=system_blocks,
                messages=[{"role": "user", "content": user_body}],
            )
            text = msg.content[0].text  # type: ignore[union-attr,attr-defined]
        except Exception as exc:  # noqa: BLE001
            logger.warning("ClaudeNLI call failed: %r", exc)
            return ensure_verdict(
                verdict="neutral",
                score=0.5,
                provider=self.name,
                raw={"api_error": repr(exc)},
            )

        try:
            data = json.loads(text)
            verdict = str(data.get("verdict", "")).lower()
            score = float(data.get("score", 0.5))
            reason = str(data.get("reason", ""))
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "ClaudeNLI JSON parse failed: %r (raw=%s)", exc, text[:200]
            )
            return ensure_verdict(
                verdict="neutral",
                score=0.5,
                provider=self.name,
                raw={"parse_error": str(exc), "raw_text": text[:500]},
            )

        if verdict not in {"entails", "neutral", "contradicts"}:
            logger.warning("ClaudeNLI unexpected verdict %r → neutral/0.5", verdict)
            return ensure_verdict(
                verdict="neutral",
                score=0.5,
                provider=self.name,
                raw={"unexpected_verdict": verdict, "reason": reason},
            )

        return ensure_verdict(
            verdict=verdict,
            score=score,
            provider=self.name,
            raw={"reason": reason, "model": model, "lang": language},
        )


__all__ = ["ClaudeNLI"]
