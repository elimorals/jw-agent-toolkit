"""finetuned_assistant — agent that uses a fine-tuned model + RAG context.

Pipeline:
  1. (optional) Retrieve top-k chunks from a jw-rag VectorStore for citations.
  2. Build a prompt that includes the retrieved context.
  3. Call the fine-tuned model via `FinetunedModelClient`.
  4. Return AgentResult: each retrieved chunk becomes a Finding (with
     verifiable Citation); the generated answer is in `result.metadata`.

The agent is *procedural* by jw-agents convention: it doesn't loop or
self-reflect. The LLM caller can use `result.metadata["generated_answer"]`
plus the cited findings to construct the final response.
"""

from __future__ import annotations

import logging
from typing import Any

from jw_agents.base import AgentResult, Citation, Finding
from jw_agents.finetuned_model import (
    FinetunedModelClient,
    GenerateRequest,
)

logger = logging.getLogger(__name__)


def finetuned_assistant(
    query: str,
    *,
    client: FinetunedModelClient,
    rag_store: Any | None = None,
    top_k: int = 3,
    language: str = "es",
    system: str = "",
    max_new_tokens: int = 512,
    temperature: float = 0.4,
) -> AgentResult:
    """Run the fine-tuned-model-with-RAG-context pipeline.

    `rag_store` is optional. If provided, it must expose a `search(query, k)`
    method that returns objects with `.chunk.text`, `.chunk.metadata`, and
    `.score`. The toolkit's `jw_rag.store.VectorStore` matches this shape.
    """
    result = AgentResult(query=query, agent_name="finetuned_assistant")
    result.metadata["language"] = language
    result.metadata["backend"] = getattr(client, "backend", "unknown")
    result.metadata["model"] = getattr(client, "model", "unknown")

    context_chunks: list[Any] = []
    if rag_store is not None:
        try:
            hits = rag_store.search(query, top_k=top_k)
        except Exception as e:  # noqa: BLE001
            result.warnings.append(f"RAG search failed: {e}")
            hits = []
        for hit in hits:
            chunk = getattr(hit, "chunk", None) or hit
            text = getattr(chunk, "text", "") or ""
            md = getattr(chunk, "metadata", {}) or {}
            citation = Citation(
                url=str(md.get("source_url") or md.get("source_path") or ""),
                title=str(md.get("section_ref") or md.get("title") or ""),
                kind=str(md.get("kind") or "chunk"),
                metadata={k: str(v) for k, v in md.items() if k != "text"},
            )
            result.findings.append(Finding(
                summary=(text[:160] + "…") if len(text) > 160 else text,
                citation=citation,
                excerpt=text,
                metadata={"rag_score": float(getattr(hit, "score", 0.0))},
            ))
            context_chunks.append(text)

    prompt = _build_prompt(query, context_chunks)
    try:
        resp = client.generate(GenerateRequest(
            prompt=prompt,
            system=system or _default_system(language),
            max_new_tokens=max_new_tokens,
            temperature=temperature,
            language=language,
        ))
    except Exception as e:  # noqa: BLE001
        result.warnings.append(f"model generation failed: {e}")
        result.metadata["generated_answer"] = ""
        return result

    result.metadata["generated_answer"] = resp.text
    result.metadata["usage"] = resp.usage
    return result


def _default_system(language: str) -> str:
    if language.startswith("es"):
        return (
            "Eres un asistente que responde preguntas sobre publicaciones de "
            "los Testigos de Jehová. Responde en español, con respeto, citando "
            "versículos bíblicos cuando aparezcan en el contexto proporcionado."
        )
    return (
        "You are an assistant answering questions about Jehovah's Witnesses' "
        "publications. Respond respectfully, citing bible verses when present "
        "in the provided context."
    )


def _build_prompt(query: str, context_chunks: list[str]) -> str:
    if not context_chunks:
        return query
    ctx = "\n\n---\n\n".join(context_chunks)
    return (
        f"Contexto recuperado de tu biblioteca local:\n\n{ctx}\n\n"
        f"Pregunta: {query}\n\n"
        f"Responde basándote en el contexto. Si el contexto no es suficiente, "
        f"di que la información disponible es limitada."
    )
