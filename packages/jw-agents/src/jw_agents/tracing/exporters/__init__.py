"""Exporters that consume `TraceEvent`s.

The base path (JsonlTraceStore in store.py) is the default. Exporters here
are additional sinks: in-memory (tests) and OpenTelemetry (opt-in extra).
"""
