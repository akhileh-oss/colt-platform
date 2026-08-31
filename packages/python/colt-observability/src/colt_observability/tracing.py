"""Distributed tracing (CLAUDE.md §3.6, §35): HTTP requests, Temporal workflows/activities,
and database operations share one trace.

`configure_tracing` accepts an injectable `exporter` specifically so tests can substitute an
in-memory exporter for the real OTLP one and assert on captured spans directly, rather than
scraping a collector's own logs or standing up a queryable trace backend just for a test.
"""

from __future__ import annotations

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SpanExporter
from opentelemetry.sdk.trace.sampling import ParentBased, TraceIdRatioBased
from opentelemetry.trace import Tracer


def configure_tracing(
    *,
    service_name: str,
    otlp_endpoint: str,
    sample_rate: float,
    exporter: SpanExporter | None = None,
) -> TracerProvider:
    """Install the process-wide `TracerProvider`.

    `exporter` defaults to a real `OTLPSpanExporter` shipping to the local collector
    (`otlp_endpoint`); pass an `InMemorySpanExporter` (or any other `SpanExporter`) to capture
    spans directly instead — this is how the durability/trace-propagation tests observe spans
    without a queryable trace backend in the local stack.
    """
    provider = TracerProvider(
        resource=Resource.create({SERVICE_NAME: service_name}),
        sampler=ParentBased(TraceIdRatioBased(sample_rate)),
    )
    provider.add_span_processor(
        BatchSpanProcessor(exporter or OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True))
    )
    trace.set_tracer_provider(provider)
    return provider


def instrument_sqlalchemy() -> None:
    """Instrument every SQLAlchemy engine in this process, present and future.

    Engine-agnostic (no `engine=` argument) so it works the same whether called from the API
    process (`colt_db.get_default_engine()`) or a Temporal activity that opens its own engine —
    both need a DB span to appear in the trace CLAUDE.md §68's Milestone 07 acceptance criterion
    requires (API → workflow → activity → DB).
    """
    SQLAlchemyInstrumentor().instrument()


def get_tracer(name: str) -> Tracer:
    """Return a tracer bound to the process-wide `TracerProvider`. Use `__name__` at the call
    site."""
    return trace.get_tracer(name)
