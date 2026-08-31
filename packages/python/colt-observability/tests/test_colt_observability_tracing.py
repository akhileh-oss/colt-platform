"""`configure_tracing` and trace-correlated logging (CLAUDE.md §35).

One test function, not several: `opentelemetry.trace.set_tracer_provider` is set-once per
process — a second `configure_tracing()` call elsewhere in the suite would silently no-op rather
than install a fresh exporter, so every assertion here uses the `TracerProvider` `configure_tracing`
returns directly (`provider.get_tracer(...)`) rather than relying on global registration, and
they all share one `configure_tracing()` call to avoid the set-once trap entirely.
"""

from __future__ import annotations

from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from colt_observability import configure_tracing, get_log_context


def test_tracing_captures_spans_and_correlates_them_into_log_context() -> None:
    exporter = InMemorySpanExporter()
    provider = configure_tracing(
        service_name="test-service", otlp_endpoint="unused:4317", sample_rate=1.0, exporter=exporter
    )
    tracer = provider.get_tracer(__name__)

    assert "trace_id" not in get_log_context()

    with tracer.start_as_current_span("unit-test-span") as span:
        context = get_log_context()
        assert context["trace_id"] == format(span.get_span_context().trace_id, "032x")
        assert context["span_id"] == format(span.get_span_context().span_id, "016x")

    assert "trace_id" not in get_log_context()

    # BatchSpanProcessor exports asynchronously — real production behavior, and exactly why
    # this test must flush before asserting rather than assuming the span already shipped.
    provider.force_flush()
    spans = exporter.get_finished_spans()
    assert len(spans) == 1
    assert spans[0].name == "unit-test-span"
    assert spans[0].resource.attributes["service.name"] == "test-service"
