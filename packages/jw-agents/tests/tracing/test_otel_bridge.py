"""OTel bridge test — opt-in, skipped when the extra is not installed."""

from __future__ import annotations

import pytest

pytest.importorskip("opentelemetry")
pytest.importorskip("opentelemetry.sdk.trace.export.in_memory_span_exporter")

from jw_agents.tracing.exporters.otel import OTelTraceStore  # noqa: E402
from jw_agents.tracing.tracer import AgentTracer  # noqa: E402


def test_otel_store_emits_spans_for_steps() -> None:
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
        InMemorySpanExporter,
    )

    provider = TracerProvider()
    exporter = InMemorySpanExporter()
    provider.add_span_processor(SimpleSpanProcessor(exporter))

    store = OTelTraceStore(
        tracer_provider=provider, service_name="jw-agents-test"
    )
    tr = AgentTracer(agent="apologetics", store=store)
    with tr.run(input_kwargs={"question": "x"}), tr.step("topic_index_lookup"):
        tr.kept(
            source="topic_index", citation_url="https://x", reason="ok"
        )
        tr.dropped(source="rag", reason="dup")

    spans = exporter.get_finished_spans()
    names = [s.name for s in spans]
    assert "topic_index_lookup" in names
    assert any(s.name in {"apologetics", "agent.run"} for s in spans)
