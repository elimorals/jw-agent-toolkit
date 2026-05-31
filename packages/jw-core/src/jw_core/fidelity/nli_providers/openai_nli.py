"""OpenAINLI — entailment via OpenAI Chat Completions with structured output.

Uses ``response_format={"type": "json_schema", "json_schema": {...}}`` so the
SDK guarantees we receive a JSON-shaped string matching our schema. Default
model ``gpt-4o-mini``, overridable via ``JW_NLI_OPENAI_MODEL``.

Same defensive parsing as ClaudeNLI: bad JSON / bad verdict label → fallback
to verdict="neutral", score=0.5, raw["parse_error"].
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from jw_core.fidelity.nli import Target
from jw_core.fidelity.verdicts import NLIVerdict, ensure_verdict

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = "gpt-4o-mini"
_SYSTEM_PROMPT = (
    "You are an NLI judge. Decide if the CONCLUSION strictly entails from "
    "the PREMISE. Reply JSON-only with this exact shape: "
    '{"verdict": "entails"|"neutral"|"contradicts", '
    '"score": 0.0-1.0, "reason": "short explanation"}.'
)
_JSON_SCHEMA = {
    "name": "nli_verdict",
    "schema": {
        "type": "object",
        "properties": {
            "verdict": {
                "type": "string",
                "enum": ["entails", "neutral", "contradicts"],
            },
            "score": {"type": "number", "minimum": 0.0, "maximum": 1.0},
            "reason": {"type": "string"},
        },
        "required": ["verdict", "score"],
        "additionalProperties": False,
    },
}
_MAX_PREMISE_CHARS = 6000
_MAX_TOTAL_CHARS = 8000


class OpenAINLI:
    name = "openai-nli"
    target: Target = "api"

    def __init__(self, *, client: Any | None = None) -> None:
        self._client = client

    def is_available(self) -> bool:
        if not os.getenv("OPENAI_API_KEY"):
            return False
        try:
            import openai  # noqa: F401
        except ImportError:
            return False
        return True

    def _ensure_client(self) -> Any:
        if self._client is not None:
            return self._client
        from openai import OpenAI

        self._client = OpenAI()
        return self._client

    def _truncate(self, premise: str, claim: str) -> str:
        if len(premise) + len(claim) <= _MAX_TOTAL_CHARS:
            return premise
        return premise[:_MAX_PREMISE_CHARS]

    def evaluate(
        self, claim: str, premise: str, *, language: str = "en"
    ) -> NLIVerdict:
        client = self._ensure_client()
        model = os.getenv("JW_NLI_OPENAI_MODEL", _DEFAULT_MODEL)
        truncated = self._truncate(premise, claim)
        user_body = (
            f"PREMISE:\n{truncated}\n\n"
            f"CONCLUSION:\n{claim}\n\n"
            f"Language: {language}"
        )
        try:
            resp = client.chat.completions.create(
                model=model,
                response_format={"type": "json_schema", "json_schema": _JSON_SCHEMA},
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": user_body},
                ],
            )
            text = resp.choices[0].message.content or ""
        except Exception as exc:  # noqa: BLE001
            logger.warning("OpenAINLI call failed: %r", exc)
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
            return ensure_verdict(
                verdict="neutral",
                score=0.5,
                provider=self.name,
                raw={"parse_error": str(exc), "raw_text": text[:500]},
            )

        if verdict not in {"entails", "neutral", "contradicts"}:
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


__all__ = ["OpenAINLI"]
