"""Opt-in OpenTelemetry bridge.

Wraps `AgentTracer` events as OTel spans so power users can ship traces to
Jaeger / Tempo / Honeycomb / Datadog. The bridge is OPT-IN: it requires the
`[otel]` extra to be installed.

API:
    from jw_agents.tracing.exporters.otel import OTelTraceStore
    store = OTelTraceStore(service_name="jw-agents")
    tracer = AgentTracer(agent="apologetics", store=store)

Internally each `tracer.run()` opens a root span named after the agent, each
`tracer.step()` opens a nested span, and `kept` / `dropped` / `warn` events
become span events.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

from jw_agents.tracing.schema import (
    FindingDroppedEvent,
    FindingKeptEvent,
    StepEndEvent,
    StepStartEvent,
    Trace,
    TraceEvent,
    WarningEvent,
)

if TYPE_CHECKING:
    from opentelemetry.sdk.trace import TracerProvider


class OTelTraceStore:
    """TraceStore that converts AgentTracer events into OTel spans."""

    def __init__(
        self,
        *,
        tracer_provider: "TracerProvider | None" = None,
        service_name: str | None = None,
    ) -> None:
        try:
            from opentelemetry import trace as _otel
            from opentelemetry.sdk.resources import Resource
            from opentelemetry.sdk.trace import TracerProvider as _TP
        except ImportError as exc:
            raise RuntimeError(
                "OTelTraceStore requires the [otel] extra. "
                "Install with `uv pip install 'jw-agents[otel]'`."
            ) from exc

        if tracer_provider is None:
            resource = Resource.create(
                {
                    "service.name": service_name
                    or os.environ.get("OTEL_SERVICE_NAME", "jw-agents")
                }
            )
            tracer_provider = _TP(resource=resource)
        self._tp = tracer_provider
        self._otel_tracer = _otel.get_tracer(
            "jw_agents.tracing", tracer_provider=tracer_provider
        )
        self._root_span: Any | None = None
        self._step_stack: list[Any] = []

    def _ensure_root(self) -> None:
        if self._root_span is None:
            self._root_span = self._otel_tracer.start_span("agent.run")

    def append(self, event: TraceEvent) -> None:
        self._ensure_root()
        if isinstance(event, StepStartEvent):
            span = self._otel_tracer.start_span(event.name, context=None)
            if event.input_digest is not None:
                for k, v in event.input_digest.items():
                    span.set_attribute(f"input_digest.{k}", v)
            self._step_stack.append(span)
        elif isinstance(event, StepEndEvent):
            if not self._step_stack:
                return
            span = self._step_stack.pop()
            if event.hits is not None:
                span.set_attribute("hits", event.hits)
            if event.kept is not None:
                span.set_attribute("kept", event.kept)
            if event.dropped is not None:
                span.set_attribute("dropped", event.dropped)
            if event.error:
                span.set_attribute("error", event.error)
            span.set_attribute("duration_ms", event.duration_ms)
            span.end()
        elif isinstance(event, FindingKeptEvent):
            target = (
                self._step_stack[-1] if self._step_stack else self._root_span
            )
            target.add_event(
                "finding_kept",
                attributes={
                    "source": event.source,
                    "citation_url": event.citation_url,
                    "score": event.score if event.score is not None else -1.0,
                    "reason": event.reason,
                },
            )
        elif isinstance(event, FindingDroppedEvent):
            target = (
                self._step_stack[-1] if self._step_stack else self._root_span
            )
            target.add_event(
                "finding_dropped",
                attributes={
                    "source": event.source,
                    "citation_url": event.citation_url or "",
                    "reason": event.reason,
                    "score": event.score if event.score is not None else -1.0,
                },
            )
        elif isinstance(event, WarningEvent):
            target = (
                self._step_stack[-1] if self._step_stack else self._root_span
            )
            target.add_event(
                "warning",
                attributes={
                    "message": event.message,
                    "step": event.step or "",
                },
            )

    def complete(self, trace: Trace) -> None:
        if self._root_span is None:
            return
        self._root_span.set_attribute("agent", trace.agent)
        self._root_span.set_attribute("trace_id", str(trace.trace_id))
        self._root_span.set_attribute("findings_in", trace.findings_in)
        self._root_span.set_attribute("findings_out", trace.findings_out)
        self._root_span.set_attribute("warnings_count", trace.warnings_count)
        self._root_span.set_attribute("duration_ms", trace.duration_ms)
        self._root_span.end()
        self._root_span = None

    def close(self) -> None:
        pass


def store_from_env() -> "OTelTraceStore | None":
    """Construct an OTel store from environment if configured, else None.

    Recognized:
      JW_TRACE_OTEL_EXPORTER=otlp://collector:4317  (enables OTLP gRPC)
      OTEL_SERVICE_NAME=jw-agents                   (passthrough)
    """

    endpoint = os.environ.get("JW_TRACE_OTEL_EXPORTER")
    if not endpoint:
        return None
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
        OTLPSpanExporter,
    )
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    resource = Resource.create(
        {"service.name": os.environ.get("OTEL_SERVICE_NAME", "jw-agents")}
    )
    tp = TracerProvider(resource=resource)
    parsed = endpoint.replace("otlp://", "")
    tp.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=parsed)))
    return OTelTraceStore(tracer_provider=tp)
