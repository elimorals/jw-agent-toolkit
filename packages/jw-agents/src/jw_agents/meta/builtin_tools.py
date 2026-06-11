"""Register the 12 procedural agents as meta tools.

Each builtin tool wraps an existing agent's callable. Adapters
normalize the diverse signatures (e.g. `verse_explainer(text=...)`
vs the meta-orchestrator's expected `reference`) and serialize
`AgentResult` instances to plain dicts compatible with `StepResult`.

Sync agents like `plan_next_visit` are wrapped in a thin async layer.
"""

from __future__ import annotations

from typing import Any

from jw_agents.meta.registry import register_tool

BUILTIN_TOOL_NAMES: tuple[str, ...] = (
    "verse.explain",
    "research.topic",
    "apologetics.research",
    "meeting.workbook",
    "meeting.public_talk_outline",
    "meeting.student_part",
    "ministry.conversation",
    "ministry.presentation",
    "ministry.revisit",
    "apologetics.fact_check",
    "apologetics.apocrypha",
    "study.life_topics",
    "spar.session",
    "reason.doctrinal",
    "broadcasting.visual_search",
    "verification.image_quote",
    "book_camera.analyze",
    "drift.analyze",
)


def _serialize(result: Any) -> dict[str, Any]:
    """Normalize an agent return to a dict StepResult can carry."""

    if isinstance(result, dict):
        return result
    # Pydantic v2 BaseModel-like
    dump = getattr(result, "model_dump", None)
    if callable(dump):
        return dump()
    # Pydantic v1 fallback
    dict_fn = getattr(result, "dict", None)
    if callable(dict_fn):
        return dict_fn()
    return {"value": result}


# --- Adapters: signature normalization ---


async def _verse_explain_adapter(
    *, reference: str, language: str = "es", **_: Any
) -> dict[str, Any]:
    """`verse.explain` -> `verse_explainer(text=..., language=...)`."""
    from jw_agents.verse_explainer import verse_explainer

    return _serialize(await verse_explainer(reference, language=language))


async def _research_topic_adapter(
    *, query: str, language: str = "E", **_: Any
) -> dict[str, Any]:
    """`research.topic` -> `research_topic(topic=..., language=...)`."""
    from jw_agents.research_topic import research_topic

    return _serialize(await research_topic(query, language=language))


async def _apologetics_research_adapter(
    *, question: str, language: str = "E", **_: Any
) -> dict[str, Any]:
    """`apologetics.research` -> `apologetics(question=..., language=...)`."""
    from jw_agents.apologetics import apologetics

    return _serialize(await apologetics(question, language=language))


async def _meeting_workbook_adapter(
    *,
    language: str = "es",
    target_date: str | None = None,
    **_: Any,
) -> dict[str, Any]:
    """`meeting.workbook` -> `workbook_helper(target_date=..., language=...)`.

    The original meta spec proposed `year` + `week`, but the real
    `workbook_helper` resolves the week from a target_date (or today)."""
    from jw_agents.workbook_helper import workbook_helper

    return _serialize(
        await workbook_helper(target_date=target_date, language=language)
    )


async def _meeting_public_talk_outline_adapter(
    *, topic: str, language: str = "E", **_: Any
) -> dict[str, Any]:
    """`meeting.public_talk_outline` -> `public_talk_outline(theme=..., language=...)`."""
    from jw_agents.public_talk_outline import public_talk_outline

    return _serialize(await public_talk_outline(topic, language=language))


async def _meeting_student_part_adapter(
    *,
    kind: str,
    topic_or_ref: str = "",
    language: str = "es",
    **_: Any,
) -> dict[str, Any]:
    """`meeting.student_part` -> `student_part_helper(kind, topic_or_ref, language=...)`."""
    from jw_agents.student_part_helper import student_part_helper

    return _serialize(
        await student_part_helper(kind, topic_or_ref, language=language)
    )


async def _ministry_conversation_adapter(
    *, objection: str, language: str = "E", **_: Any
) -> dict[str, Any]:
    """`ministry.conversation` -> `conversation_assistant(text=..., language=...)`."""
    from jw_agents.conversation_assistant import conversation_assistant

    return _serialize(
        await conversation_assistant(objection, language=language)
    )


async def _ministry_presentation_adapter(
    *,
    profile: str = "default",
    language: str = "E",
    **_: Any,
) -> dict[str, Any]:
    """`ministry.presentation` -> `presentation_builder(audience=profile, language=...)`."""
    from jw_agents.presentation_builder import presentation_builder

    return _serialize(
        await presentation_builder(profile, language=language)
    )


async def _ministry_revisit_adapter(
    *, action: str = "list", **_: Any
) -> dict[str, Any]:
    """`ministry.revisit` -> exposes the local RevisitStore as a list.

    The full `plan_next_visit` requires a `Revisit` instance which is
    stateful and out of scope for this thin adapter. Action "list"
    returns the in-memory store; future actions can extend the wrapper.
    """
    from jw_agents.revisit_tracker import RevisitStore

    store = RevisitStore()
    return {
        "agent_name": "revisit_tracker",
        "findings": [],
        "action": action,
        "revisits": [
            r.model_dump() if hasattr(r, "model_dump") else r
            for r in store.list_all()
        ]
        if action == "list"
        else [],
    }


async def _apologetics_fact_check_adapter(
    *, claim: str, language: str = "E", **_: Any
) -> dict[str, Any]:
    """`apologetics.fact_check` -> `fact_checker(claim=..., language=...)`."""
    from jw_agents.fact_checker import fact_checker

    return _serialize(await fact_checker(claim, language=language))


async def _apologetics_apocrypha_adapter(
    *, quote: str, language: str = "E", **_: Any
) -> dict[str, Any]:
    """`apologetics.apocrypha` -> `apocrypha_detector(text=..., language=...)`."""
    from jw_agents.apocrypha_detector import apocrypha_detector

    return _serialize(
        await apocrypha_detector(quote, language=language)
    )


async def _study_life_topics_adapter(
    *, topic: str, language: str = "es", **_: Any
) -> dict[str, Any]:
    """`study.life_topics` -> `life_topics(query=..., language=...)`."""
    from jw_agents.life_topics import life_topics

    return _serialize(await life_topics(topic, language=language))


async def _drift_analyze_adapter(
    *,
    query: str,
    chunks_path: str,
    language: str = "es",
    min_chunks_per_era: int = 3,
    min_delta: float = 0.05,
    **_: Any,
) -> dict[str, Any]:
    """`drift.analyze` -> analyze_doctrinal_drift() over a local JSONL file."""
    import json as _json
    from pathlib import Path

    import numpy as np

    from jw_core.drift.cluster import Chunk
    from jw_core.drift.engine import analyze_doctrinal_drift

    chunks: list[Chunk] = []
    for line in Path(chunks_path).expanduser().read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        d = _json.loads(line)
        emb = np.asarray(d["embedding"], dtype=np.float32)
        norm = float(np.linalg.norm(emb))
        if norm > 0:
            emb = emb / norm
        chunks.append(
            Chunk(
                text=str(d.get("text", "")),
                year=int(d["year"]),
                embedding=emb.astype(np.float32),
            )
        )
    report = analyze_doctrinal_drift(
        query=query,
        chunks=chunks,
        language=language,
        min_chunks_per_era=min_chunks_per_era,
        min_delta=min_delta,
    )
    return {
        "agent_name": "drift_analyze",
        "findings": [
            {
                "summary": f"{ev.from_era}->{ev.to_era} {ev.significance}",
                "excerpt": ev.summary_change,
                "kind": "doctrinal_drift_event",
                "significance": ev.significance,
                "delta": ev.cosine_delta,
            }
            for ev in report.drift_events
        ],
        "report": report.model_dump(),
    }


async def _book_camera_analyze_adapter(
    *,
    image_path: str | None = None,
    ocr_text: str | None = None,
    language: str = "es",
    **_: Any,
) -> dict[str, Any]:
    """`book_camera.analyze` -> analyze_capture()."""
    from jw_core.book_camera.engine import analyze_capture

    result = analyze_capture(
        image_path=image_path,
        ocr_text=ocr_text,
        language=language,
    )
    return {
        "agent_name": "book_camera_analyze",
        "findings": [
            {
                "summary": f"{result.detected.kind} from book capture",
                "excerpt": result.ocr_text[:200],
                "kind": result.detected.kind,
                "ocr_confidence": result.ocr_confidence,
                "actions": [a.kind for a in result.suggested_actions],
            }
        ],
        "result": result.model_dump(),
    }


async def _verification_image_quote_adapter(
    *,
    image_path: str,
    language: str = "es",
    ocr_text_override: str | None = None,
    vlm_description: str = "",
    **_: Any,
) -> dict[str, Any]:
    """`verification.image_quote` -> verify_image_quote() on a local image."""
    from jw_core.verification.image_quote.engine import (
        verify_image_quote,
    )

    verdict = await verify_image_quote(
        image_path,
        language=language,
        retriever=None,
        nli=None,
        ocr_text_override=ocr_text_override,
        vlm_description=vlm_description,
    )
    return {
        "agent_name": "verify_image_quote",
        "findings": [
            {
                "summary": f"{verdict.verdict} (conf={verdict.confidence:.2f})",
                "excerpt": verdict.reasoning,
                "kind": "image_quote_verdict",
                "verdict": verdict.verdict,
                "confidence": verdict.confidence,
                "suggested_action": verdict.suggested_action,
                "extracted_quote": verdict.extracted_quote.cleaned_quote,
            }
        ],
        "verdict": verdict.model_dump(),
    }


async def _broadcasting_visual_search_adapter(
    *,
    query: str,
    top_k: int = 10,
    min_score: float = 0.0,
    **_: Any,
) -> dict[str, Any]:
    """`broadcasting.visual_search` -> visual_search() over the local index."""
    from jw_core.broadcasting.visual.engine import search_index

    hits = search_index(query, top_k=top_k, min_score=min_score)
    return {
        "agent_name": "broadcasting_visual_search",
        "findings": [
            {
                "summary": h.caption[:80],
                "excerpt": h.caption,
                "citation": {"url": h.deep_link},
                "kind": "broadcasting_frame",
                "score": h.score,
                "video_id": h.video_id,
                "timestamp_s": h.timestamp_s,
                "source": h.source,
            }
            for h in hits
        ],
    }


async def _reason_doctrinal_adapter(
    *,
    question: str,
    language: str = "es",
    max_steps: int = 12,
    nli_mode: str = "reject",
    **_: Any,
) -> dict[str, Any]:
    """`reason.doctrinal` -> `doctrinal_reasoner(...)` with F65 LLM/NLI factories."""
    from jw_agents.reasoner.engine import doctrinal_reasoner
    from jw_agents.reasoner.models import ReasonerConfig

    try:
        from jw_agents.meta.llm_factory import build_llm_from_env

        llm = build_llm_from_env()
    except Exception:
        import json as _json

        class _Fake:
            name = "fake"

            async def acomplete(self, prompt: str) -> str:  # noqa: ARG002
                return _json.dumps({"steps": []})

        llm = _Fake()

    try:
        from jw_agents.meta.nli_factory import build_nli_from_env

        nli = build_nli_from_env(language=language)
    except Exception:
        nli = None

    cfg = ReasonerConfig(
        language=language,  # type: ignore[arg-type]
        max_steps=max_steps,
        nli_mode=nli_mode,  # type: ignore[arg-type]
    )
    tree = await doctrinal_reasoner(
        question=question, llm=llm, config=cfg, nli=nli
    )
    return tree.model_dump()


async def _spar_session_adapter(
    *,
    persona: str = "catholic",
    language: str = "es",
    user_turns: list[str] | None = None,
    **_: Any,
) -> dict[str, Any]:
    """`spar.session` -> run a complete sparring session and return the closed SparSession.

    Wraps `start_session` + N `take_turn` + `close_session` + `score_session`
    into a single callable so the meta-orchestrator can request "ejecuta una
    sesión de sparring contra un católico con estos 3 turnos". The LLM
    backend is resolved via the F65 llm_factory (JW_META_LLM env), falling
    back to FakeSparLLM when unavailable.
    """
    from jw_agents.spar.feedback import score_session
    from jw_agents.spar.session import (
        close_session,
        start_session,
        take_turn,
    )
    from jw_agents.spar.simulator import FakeSparLLM

    turns = list(user_turns or [])
    try:
        from jw_agents.meta.llm_factory import build_llm_from_env

        llm = build_llm_from_env()
    except Exception:
        llm = FakeSparLLM()

    session = start_session(persona_key=persona, language=language)
    for text in turns:
        await take_turn(session_id=session.session_id, user_text=text, llm=llm)
    session = close_session(session_id=session.session_id)
    score_session(session)
    return session.model_dump()


_CATALOG: dict[str, tuple[Any, str, dict[str, str]]] = {
    "verse.explain": (
        _verse_explain_adapter,
        "Explain a Bible verse with notes and cross-refs.",
        {"reference": "str", "language": "str"},
    ),
    "research.topic": (
        _research_topic_adapter,
        "Research a topic via the JW publication index.",
        {"query": "str", "language": "str"},
    ),
    "apologetics.research": (
        _apologetics_research_adapter,
        "Apologetics multi-source research.",
        {"question": "str", "language": "str"},
    ),
    "meeting.workbook": (
        _meeting_workbook_adapter,
        "Discover this week's Workbook program.",
        {"language": "str", "target_date": "str|None"},
    ),
    "meeting.public_talk_outline": (
        _meeting_public_talk_outline_adapter,
        "Outline for a public talk on a topic.",
        {"topic": "str", "language": "str"},
    ),
    "meeting.student_part": (
        _meeting_student_part_adapter,
        "Student part helper (50 counsel points).",
        {"kind": "str", "topic_or_ref": "str", "language": "str"},
    ),
    "ministry.conversation": (
        _ministry_conversation_adapter,
        "Conversation assistant with objection answers.",
        {"objection": "str", "language": "str"},
    ),
    "ministry.presentation": (
        _ministry_presentation_adapter,
        "Presentation builder by interlocutor profile.",
        {"profile": "str", "language": "str"},
    ),
    "ministry.revisit": (
        _ministry_revisit_adapter,
        "Local revisit tracker (action=list|...).",
        {"action": "str"},
    ),
    "apologetics.fact_check": (
        _apologetics_fact_check_adapter,
        "Fact-check a claim against JW sources.",
        {"claim": "str", "language": "str"},
    ),
    "apologetics.apocrypha": (
        _apologetics_apocrypha_adapter,
        "Detect apocryphal attributions to JW publications.",
        {"quote": "str", "language": "str"},
    ),
    "study.life_topics": (
        _study_life_topics_adapter,
        "Informational life topics with elder redirect for sensitive.",
        {"topic": "str", "language": "str"},
    ),
    "spar.session": (
        _spar_session_adapter,
        "Run a sparring session against a simulated interlocutor.",
        {
            "persona": "str",
            "language": "str",
            "user_turns": "list[str]",
        },
    ),
    "reason.doctrinal": (
        _reason_doctrinal_adapter,
        "Doctrinal chain-of-thought with verifiable steps (Fase 67).",
        {
            "question": "str",
            "language": "str",
            "max_steps": "int",
            "nli_mode": "str",
        },
    ),
    "broadcasting.visual_search": (
        _broadcasting_visual_search_adapter,
        "Hybrid visual search over the JW Broadcasting frame index (Fase 69).",
        {
            "query": "str",
            "top_k": "int",
            "min_score": "float",
        },
    ),
    "verification.image_quote": (
        _verification_image_quote_adapter,
        "Verify whether an image carries a real, distorted, or fabricated JW quote (Fase 70).",
        {
            "image_path": "str",
            "language": "str",
            "ocr_text_override": "str|None",
            "vlm_description": "str",
        },
    ),
    "book_camera.analyze": (
        _book_camera_analyze_adapter,
        "Analyze a physical-book capture and produce suggested actions (Fase 71).",
        {
            "image_path": "str|None",
            "ocr_text": "str|None",
            "language": "str",
        },
    ),
    "drift.analyze": (
        _drift_analyze_adapter,
        "Analyze diachronic doctrinal drift over a chunks JSONL file (Fase 72).",
        {
            "query": "str",
            "chunks_path": "str",
            "language": "str",
            "min_chunks_per_era": "int",
            "min_delta": "float",
        },
    ),
}


def register_builtin_tools() -> None:
    """Register all known builtin tools (idempotent — overrides ok)."""

    for name, (callable_, desc, schema) in _CATALOG.items():
        register_tool(
            name=name,
            callable_=callable_,
            description=desc,
            args_schema=schema,
        )
