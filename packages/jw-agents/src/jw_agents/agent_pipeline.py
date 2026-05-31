"""Compose multiple agents into chained pipelines.

Pattern: an "enricher" agent runs first and produces structured findings;
then those findings are flattened into context that a "responder" agent
consumes. The responder may be procedural (returns AgentResult directly)
or LLM-driven (uses the context to generate prose).

Built-in pipelines:
  * `verse_explainer → finetuned_assistant`: when the user asks about a
    verse, we let `verse_explainer` (procedural) gather study notes and
    cross-references, then pass those as context to the fine-tuned model.
  * `conversation_assistant → finetuned_assistant`: same pattern for
    apologetics/objections.

These are convenience helpers — callers can roll their own pipelines
following the same shape.
"""

from __future__ import annotations

import logging
from typing import Any

from jw_agents.base import AgentResult

logger = logging.getLogger(__name__)


def _findings_to_context(result: AgentResult) -> list[str]:
    """Flatten an AgentResult's findings into context strings.

    Used as input chunks for the responder agent. Preserves ref + summary
    in a compact format.
    """
    out: list[str] = []
    for f in result.findings:
        excerpt = f.excerpt or f.summary
        ref = f.citation.title or f.citation.url
        if ref:
            out.append(f"[{ref}] {excerpt}")
        else:
            out.append(excerpt)
    return out


async def verse_explainer_with_finetuned(
    query: str,
    *,
    finetuned_client: Any,
    language: str = "es",
    wol: Any | None = None,
    max_paragraphs: int = 3,
    include_study_notes: bool = True,
    max_new_tokens: int = 512,
    temperature: float = 0.4,
) -> AgentResult:
    """Run `verse_explainer` first, then pass its findings to the fine-tuned model.

    Returns a merged AgentResult where:
      - `findings` come from `verse_explainer` (verifiable citations)
      - `metadata["generated_answer"]` contains the fine-tuned model's prose
    """
    from jw_agents.finetuned_model import GenerateRequest
    from jw_agents.verse_explainer import verse_explainer

    enrich_result = await verse_explainer(
        query,
        language=language[0].upper() if language else "E",
        wol=wol,
        max_paragraphs=max_paragraphs,
        include_study_notes=include_study_notes,
    )

    context_chunks = _findings_to_context(enrich_result)
    if context_chunks:
        prompt = (
            "Contexto bíblico recuperado:\n\n" + "\n\n---\n\n".join(context_chunks) + f"\n\nPregunta: {query}\n\n"
            "Responde basándote estrictamente en el contexto, citando "
            "el versículo donde corresponda."
        )
    else:
        prompt = query

    try:
        resp = finetuned_client.generate(
            GenerateRequest(
                prompt=prompt,
                system=(
                    "Eres un asistente que explica textos bíblicos según las "
                    "publicaciones de los Testigos de Jehová. Cita versículos "
                    "fielmente y mantén el tono respetuoso."
                )
                if language.startswith("es")
                else (
                    "You are an assistant explaining bible passages from Jehovah's "
                    "Witnesses' publications. Cite verses faithfully and stay respectful."
                ),
                max_new_tokens=max_new_tokens,
                temperature=temperature,
                language=language,
            )
        )
        enrich_result.metadata["generated_answer"] = resp.text
        enrich_result.metadata["generation_backend"] = getattr(resp, "backend", "unknown")
        enrich_result.metadata["generation_usage"] = dict(resp.usage)
    except Exception as e:  # noqa: BLE001
        enrich_result.warnings.append(f"finetuned generation failed: {e}")
        enrich_result.metadata["generated_answer"] = ""

    enrich_result.agent_name = "verse_explainer_with_finetuned"
    return enrich_result


async def conversation_assistant_with_finetuned(
    query: str,
    *,
    finetuned_client: Any,
    language: str = "es",
    max_new_tokens: int = 512,
    temperature: float = 0.4,
) -> AgentResult:
    """Combine `conversation_assistant` (objection matching) with the fine-tuned model."""
    from jw_agents.conversation_assistant import conversation_assistant
    from jw_agents.finetuned_model import GenerateRequest

    jw_code = language[0].upper() if language else "E"
    enrich_result = await conversation_assistant(query, language=jw_code)

    context_chunks = _findings_to_context(enrich_result)
    prompt = (
        f"Objeción / pregunta: {query}\n\n"
        + (
            "Material de referencia:\n\n" + "\n\n---\n\n".join(context_chunks)
            if context_chunks
            else "No se encontró material previo en el catálogo."
        )
        + "\n\nRedacta una respuesta calmada y respetuosa, citando los "
        "textos bíblicos disponibles."
    )

    try:
        resp = finetuned_client.generate(
            GenerateRequest(
                prompt=prompt,
                system="Eres un publicador que maneja objeciones con respeto y citas escriturales.",
                max_new_tokens=max_new_tokens,
                temperature=temperature,
                language=language,
            )
        )
        enrich_result.metadata["generated_answer"] = resp.text
        enrich_result.metadata["generation_backend"] = getattr(resp, "backend", "unknown")
    except Exception as e:  # noqa: BLE001
        enrich_result.warnings.append(f"finetuned generation failed: {e}")
        enrich_result.metadata["generated_answer"] = ""

    enrich_result.agent_name = "conversation_assistant_with_finetuned"
    return enrich_result
