"""LLM-based judge for L3 borderline cases.

Caller is a string-in, string-out function — keeps the judge independent
from any specific provider SDK. Three built-in callers:
  - ollama_caller(): http://localhost:11434/api/generate
  - claude_caller(): anthropic SDK (lazy import)
  - openai_caller(): openai SDK (lazy import)

The choice is driven by env var JW_EVAL_LLM ∈ {ollama, claude, openai, none}.
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable

JUDGE_PROMPT = """Eres un juez doctrinal de fidelidad. Compara la respuesta candidata
con la respuesta dorada. Responde estrictamente como JSON:
{{"verdict": "pass" | "fail", "reason": "..."}}

Respuesta dorada:
{golden}

Respuesta candidata:
{candidate}

Keywords requeridas (al menos UNA debe aparecer en candidata): {keywords_any}
Keywords prohibidas (NINGUNA puede aparecer): {keywords_none}
"""


class LLMJudge:
    def __init__(self, caller: Callable[[str], str]) -> None:
        self.caller = caller

    def judge(
        self,
        golden: str,
        candidate: str,
        keywords_any: list[str],
        keywords_none: list[str],
    ) -> tuple[str, str]:
        prompt = JUDGE_PROMPT.format(
            golden=golden,
            candidate=candidate,
            keywords_any=keywords_any,
            keywords_none=keywords_none,
        )
        try:
            raw = self.caller(prompt)
        except Exception as exc:  # noqa: BLE001
            return "error", f"caller raised: {exc!r}"
        try:
            data = json.loads(raw)
        except Exception:  # noqa: BLE001
            return "error", f"could not parse JSON from response: {raw[:200]!r}"
        v = str(data.get("verdict", "")).lower()
        if v not in {"pass", "fail"}:
            return "error", f"unexpected verdict: {v!r}"
        return v, str(data.get("reason", ""))


def _ollama_caller(model: str = "llama3.1:8b", base: str = "http://localhost:11434") -> Callable[[str], str]:
    import httpx

    def call(prompt: str) -> str:
        r = httpx.post(
            f"{base}/api/generate",
            json={"model": model, "prompt": prompt, "stream": False, "format": "json"},
            timeout=60.0,
        )
        r.raise_for_status()
        return str(r.json().get("response", ""))

    return call


def _claude_caller(model: str = "claude-haiku-4-5-20251001") -> Callable[[str], str]:
    from anthropic import Anthropic  # type: ignore[import-not-found]

    client = Anthropic()

    def call(prompt: str) -> str:
        msg = client.messages.create(
            model=model,
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text  # type: ignore[union-attr,attr-defined]

    return call


def _openai_caller(model: str = "gpt-4o-mini") -> Callable[[str], str]:
    from openai import OpenAI  # type: ignore[import-not-found]

    client = OpenAI()

    def call(prompt: str) -> str:
        r = client.chat.completions.create(
            model=model,
            response_format={"type": "json_object"},
            messages=[{"role": "user", "content": prompt}],
        )
        return r.choices[0].message.content or ""

    return call


def get_default_caller() -> Callable[[str], str] | None:
    """Inspect JW_EVAL_LLM env and return the configured caller, or None."""

    backend = os.environ.get("JW_EVAL_LLM", "ollama").lower()
    if backend == "ollama":
        return _ollama_caller()
    if backend == "claude":
        return _claude_caller()
    if backend == "openai":
        return _openai_caller()
    if backend == "none":
        return None
    raise ValueError(f"unknown JW_EVAL_LLM={backend!r}")
