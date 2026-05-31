"""Q&A synthesis orchestrator: chunk + provider → validated QAPair list.

The orchestrator owns the prompt-construction → call → parse → validate flow.
Providers (`anthropic_provider`, `ollama_provider`) are agnostic.

JSON parsing is forgiving: we strip Markdown fences, accept missing trailing
fences, and reject malformed responses gracefully (no crash).
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined
from jw_rag.chunker import Chunk

from jw_finetune.data.formats import QAPair
from jw_finetune.synth.provider import LLMProvider, LLMRequest
from jw_finetune.synth.validators import lang_matches, length_ok

logger = logging.getLogger(__name__)

_TEMPLATES_DIR = Path(__file__).parent.parent / "recipes" / "templates"

_TEMPLATE_FOR_STYLE: dict[str, str] = {
    "doctrinal": "doctrinal_qa.j2",
    "verse-explain": "verse_explainer.j2",
    "objection-handling": "apologetics.j2",
}


@dataclass
class SynthResult:
    """Outcome of synthesizing Q&A from a single chunk."""

    pairs: list[QAPair] = field(default_factory=list)
    rejected: int = 0
    parse_error: bool = False
    usage: dict[str, int] = field(default_factory=lambda: {"input_tokens": 0, "output_tokens": 0})


_env_singleton: Environment | None = None


def _env() -> Environment:
    global _env_singleton
    if _env_singleton is None:
        _env_singleton = Environment(
            loader=FileSystemLoader(str(_TEMPLATES_DIR)),
            undefined=StrictUndefined,
            autoescape=False,
            trim_blocks=True,
            lstrip_blocks=True,
        )
    return _env_singleton


def _strip_json_fences(raw: str) -> str:
    s = raw.strip()
    if s.startswith("```"):
        s = s.lstrip("`")
        if s.lower().startswith("json"):
            s = s[4:]
        s = s.strip()
        # Trim trailing fence if present
        if s.endswith("```"):
            s = s[:-3].strip()
    return s


def synthesize_chunk(
    chunk: Chunk,
    *,
    provider: LLMProvider,
    qa_style: str,
    language: str,
    n_pairs: int = 3,
    temperature: float = 0.5,
    max_tokens: int = 1024,
) -> SynthResult:
    """Generate validated Q&A pairs from a single chunk."""
    template_name = _TEMPLATE_FOR_STYLE.get(qa_style)
    if not template_name:
        raise ValueError(f"Unknown qa_style: {qa_style!r}")

    tmpl = _env().get_template(template_name)
    user_prompt = tmpl.render(
        language=language,
        n_pairs=n_pairs,
        chunk_text=chunk.text,
        pub_code=chunk.metadata.get("pub_code", "?"),
        section_ref=chunk.metadata.get("section_ref", ""),
    )
    system = (
        "Eres un asistente que genera datasets de fine-tuning de alta calidad "
        "siguiendo estrictamente el formato JSON solicitado."
    )
    resp = provider.generate(
        LLMRequest(
            system=system,
            user=user_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    )

    result = SynthResult(usage=dict(resp.usage))

    raw = _strip_json_fences(resp.text)
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as e:
        logger.warning("Synth parse error for chunk %s: %s", chunk.id, e)
        result.parse_error = True
        return result

    pairs = parsed.get("pairs", []) if isinstance(parsed, dict) else []
    for entry in pairs:
        if not isinstance(entry, dict):
            result.rejected += 1
            continue
        q = (entry.get("q") or "").strip()
        a = (entry.get("a") or "").strip()
        if not length_ok(q, a):
            result.rejected += 1
            continue
        if not lang_matches(a, language):
            result.rejected += 1
            continue
        result.pairs.append(
            QAPair(
                question=q,
                answer=a,
                source_chunk_id=chunk.id,
                language=language,
                metadata={
                    "pub_code": str(chunk.metadata.get("pub_code", "")),
                    "section_ref": str(chunk.metadata.get("section_ref", "")),
                    "qa_style": qa_style,
                },
            )
        )
    return result
