"""Standalone TracerProvider bootstrap for AgentMap.

Configures the global OTEL TracerProvider when AgentMap runs standalone
with telemetry enabled and no host TracerProvider exists.

All ``opentelemetry.sdk.*`` and ``opentelemetry.exporter.*`` imports are
inside the function body so that importing this module never fails when
the SDK is not installed.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

# Obtain AgentMap version at import time -- fallback to "unknown".
try:
    from importlib.metadata import version as _pkg_version

    _agentmap_version: str = _pkg_version("agentmap")
except Exception:
    _agentmap_version = "unknown"

# Module-level references populated by deferred imports inside the
# bootstrap function.  They exist as ``None`` so that tests can patch
# them at ``agentmap.services.telemetry.bootstrap.<Name>`` without
# needing the SDK installed.
trace: Any = None
Resource: Any = None
TracerProvider: Any = None
BatchSpanProcessor: Any = None
ConsoleSpanExporter: Any = None
GrpcOTLPSpanExporter: Any = None
HttpOTLPSpanExporter: Any = None


def _load_otel_imports() -> None:
    """Populate module-level references from OTEL SDK packages.

    Raises ``ImportError`` if the SDK is not installed.
    """
    global trace, Resource, TracerProvider, BatchSpanProcessor
    global ConsoleSpanExporter, GrpcOTLPSpanExporter, HttpOTLPSpanExporter

    from opentelemetry import trace as _trace

    trace = _trace

    from opentelemetry.sdk.resources import Resource as _Resource

    Resource = _Resource

    from opentelemetry.sdk.trace import TracerProvider as _TracerProvider

    TracerProvider = _TracerProvider

    from opentelemetry.sdk.trace.export import BatchSpanProcessor as _BatchSpanProcessor

    BatchSpanProcessor = _BatchSpanProcessor

    from opentelemetry.sdk.trace.export import (
        ConsoleSpanExporter as _ConsoleSpanExporter,
    )

    ConsoleSpanExporter = _ConsoleSpanExporter

    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
        OTLPSpanExporter as _GrpcOTLPSpanExporter,
    )

    GrpcOTLPSpanExporter = _GrpcOTLPSpanExporter

    from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
        OTLPSpanExporter as _HttpOTLPSpanExporter,
    )

    HttpOTLPSpanExporter = _HttpOTLPSpanExporter


def bootstrap_standalone_tracer_provider(
    exporter: str,
    endpoint: str,
    protocol: str,
    resource_attributes: Dict[str, str],
    logger: logging.Logger,
) -> bool:
    """Bootstrap a TracerProvider for standalone mode.

    Returns True if bootstrap succeeded or was skipped (host provider
    detected), False if degraded to no-op due to error.
    """
    try:
        # Deferred import of OTEL SDK classes
        _load_otel_imports()

        # Step 1: Check if a real TracerProvider already exists
        provider = trace.get_tracer_provider()
        if not isinstance(provider, trace.ProxyTracerProvider):
            logger.info("Host TracerProvider detected; skipping standalone bootstrap")
            return True

        # Step 2: Handle "none" exporter early
        if exporter == "none":
            return True

        # Step 3: Build Resource
        attrs: Dict[str, str] = {
            "service.name": resource_attributes.get("service.name", "agentmap"),
        }
        attrs["agentmap.version"] = _agentmap_version
        attrs.update(resource_attributes)
        resource = Resource.create(attrs)

        # Step 4: Create exporter
        if exporter == "otlp":
            if protocol == "grpc":
                span_exporter = GrpcOTLPSpanExporter(endpoint=endpoint)
            elif protocol == "http/protobuf":
                span_exporter = HttpOTLPSpanExporter(endpoint=endpoint)
            else:
                logger.warning(
                    "Unsupported OTLP protocol '%s', " "degrading to no-op",
                    protocol,
                )
                return False
        elif exporter == "console":
            span_exporter = ConsoleSpanExporter()
        else:
            logger.warning(
                "Unsupported exporter '%s', degrading to no-op",
                exporter,
            )
            return False

        # Step 5: Configure TracerProvider
        tp = TracerProvider(resource=resource)
        tp.add_span_processor(BatchSpanProcessor(span_exporter))
        trace.set_tracer_provider(tp)

        return True

    except Exception as exc:
        logger.warning("Telemetry bootstrap failed, degrading to no-op: %s", exc)
        return False
