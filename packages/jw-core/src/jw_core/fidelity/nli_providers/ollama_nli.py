"""OllamaNLI — local LLM judge via Ollama HTTP API.

Default model ``llama3.1:8b-instruct`` (env ``JW_NLI_OLLAMA_MODEL``); endpoint
``http://localhost:11434`` (env ``OLLAMA_HOST``).

``is_available()`` is cached per process: it sends one GET to ``/api/tags``
and checks the configured model appears in the response. The cache is
invalidated when ``JW_NLI_OLLAMA_MODEL`` or ``OLLAMA_HOST`` change between
calls.

Inference: POST ``/api/chat`` with ``format=json``, parse the assistant
message content as JSON, fall back to neutral/0.5 on parse error.

The constructor accepts an optional ``http_client: httpx.Client`` injected
by tests (the test suite builds one on top of ``httpx.MockTransport``,
which is stdlib of httpx and needs no extra dev dep).
"""

from __future__ import annotations

import json
import logging
import os

import httpx

from jw_core.fidelity.nli import Target
from jw_core.fidelity.verdicts import NLIVerdict, ensure_verdict

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = "llama3.1:8b-instruct"
_DEFAULT_HOST = "http://localhost:11434"
_SYSTEM_PROMPT = (
    "You are an NLI judge. Decide if the CONCLUSION strictly entails from "
    "the PREMISE. Reply JSON only: {verdict, score, reason}. verdict is one "
    "of entails|neutral|contradicts; score is a float 0.0-1.0."
)


class OllamaNLI:
    name = "ollama-nli"
    target: Target = "cpu"

    def __init__(self, *, http_client: httpx.Client | None = None) -> None:
        self._cache: tuple[str, str, bool] | None = None
        self._http_client = http_client  # injectable for tests

    def _host(self) -> str:
        return os.getenv("OLLAMA_HOST", _DEFAULT_HOST).rstrip("/")

    def _model(self) -> str:
        return os.getenv("JW_NLI_OLLAMA_MODEL", _DEFAULT_MODEL)

    def _client(self) -> httpx.Client:
        if self._http_client is not None:
            return self._http_client
        # Lazily build a default client. The factory probes ``is_available()``
        # frequently, so we cache the instance on the provider.
        self._http_client = httpx.Client(timeout=60.0)
        return self._http_client

    def is_available(self) -> bool:
        host = self._host()
        model = self._model()
        if self._cache and self._cache[0] == host and self._cache[1] == model:
            return self._cache[2]
        try:
            r = self._client().get(f"{host}/api/tags", timeout=2.0)
            r.raise_for_status()
            tags = r.json().get("models", []) or []
            ok = any(t.get("name") == model for t in tags)
        except Exception as exc:  # noqa: BLE001
            logger.debug("OllamaNLI.is_available() probe failed: %r", exc)
            ok = False
        self._cache = (host, model, ok)
        return ok

    def evaluate(
        self, claim: str, premise: str, *, language: str = "en"
    ) -> NLIVerdict:
        host = self._host()
        model = self._model()
        user_body = (
            f"PREMISE:\n{premise}\n\n"
            f"CONCLUSION:\n{claim}\n\n"
            f"Language: {language}"
        )
        try:
            r = self._client().post(
                f"{host}/api/chat",
                json={
                    "model": model,
                    "stream": False,
                    "format": "json",
                    "messages": [
                        {"role": "system", "content": _SYSTEM_PROMPT},
                        {"role": "user", "content": user_body},
                    ],
                },
                timeout=60.0,
            )
            r.raise_for_status()
            text = str(r.json().get("message", {}).get("content", ""))
        except Exception as exc:  # noqa: BLE001
            logger.warning("OllamaNLI call failed: %r", exc)
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
            raw={"reason": reason, "model": model, "host": host, "lang": language},
        )


__all__ = ["OllamaNLI"]
