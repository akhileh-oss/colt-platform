"""Metrics (CLAUDE.md §35.2): counters and histograms exported via OTLP.

The minimum set §35.2 names (`http_request_count`, `workflow_started`, `llm_input_tokens`, ...)
is built up instrument-by-instrument as the milestone that produces each measurement lands —
Milestone 07 wires the pipeline and the first HTTP instruments; agent/LLM/message instruments
follow with the milestones that actually emit them (§0.1.9: no throwaway instruments ahead of
what emits to them).
"""

from __future__ import annotations

from opentelemetry import metrics
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.metrics import Meter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import MetricExporter, PeriodicExportingMetricReader
from opentelemetry.sdk.resources import SERVICE_NAME, Resource


def configure_metrics(
    *, service_name: str, otlp_endpoint: str, exporter: MetricExporter | None = None
) -> MeterProvider:
    """Install the process-wide `MeterProvider`. `exporter` is injectable for the same reason
    `configure_tracing`'s is — tests can substitute an in-memory reader."""
    provider = MeterProvider(
        resource=Resource.create({SERVICE_NAME: service_name}),
        metric_readers=[
            PeriodicExportingMetricReader(
                exporter or OTLPMetricExporter(endpoint=otlp_endpoint, insecure=True)
            )
        ],
    )
    metrics.set_meter_provider(provider)
    return provider


def get_meter(name: str) -> Meter:
    """Return a meter bound to the process-wide `MeterProvider`. Use `__name__` at the call
    site."""
    return metrics.get_meter(name)
