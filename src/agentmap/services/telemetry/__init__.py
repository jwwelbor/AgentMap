"""
AgentMap telemetry service package.

Re-exports the protocol, both implementations, and all span/attribute
constants for convenient single-location imports::

    from agentmap.services.telemetry import (
        TelemetryServiceProtocol,
        NoOpTelemetryService,
        OTELTelemetryService,   # lazy -- triggers opentelemetry load
        AGENT_RUN_SPAN,
    )

``OTELTelemetryService`` is loaded lazily via ``__getattr__`` so that
importing this package never forces an ``opentelemetry`` import.
"""

from .constants import (
    AGENT_NAME,
    AGENT_RUN_SPAN,
    AGENT_TYPE,
    GEN_AI_REQUEST_MODEL,
    GEN_AI_RESPONSE_MODEL,
    GEN_AI_SYSTEM,
    GEN_AI_USAGE_INPUT_TOKENS,
    GEN_AI_USAGE_OUTPUT_TOKENS,
    GRAPH_AGENT_COUNT,
    GRAPH_NAME,
    GRAPH_NODE_COUNT,
    LLM_CALL_SPAN,
    NODE_NAME,
    ROUTING_CACHE_HIT,
    ROUTING_CIRCUIT_BREAKER_STATE,
    ROUTING_COMPLEXITY,
    ROUTING_CONFIDENCE,
    ROUTING_FALLBACK_TIER,
    ROUTING_MODEL,
    ROUTING_PROVIDER,
    WORKFLOW_RUN_SPAN,
)
from .noop_telemetry_service import NoOpTelemetryService
from .protocol import TelemetryServiceProtocol


def __getattr__(name: str) -> object:
    if name == "OTELTelemetryService":
        from .otel_telemetry_service import OTELTelemetryService

        return OTELTelemetryService
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    # Protocol
    "TelemetryServiceProtocol",
    # Implementations
    "OTELTelemetryService",
    "NoOpTelemetryService",
    # Span name constants
    "WORKFLOW_RUN_SPAN",
    "AGENT_RUN_SPAN",
    "LLM_CALL_SPAN",
    # Agent attribute constants
    "AGENT_NAME",
    "AGENT_TYPE",
    "NODE_NAME",
    "GRAPH_NAME",
    # Workflow attribute constants
    "GRAPH_NODE_COUNT",
    "GRAPH_AGENT_COUNT",
    # GenAI attribute constants
    "GEN_AI_SYSTEM",
    "GEN_AI_REQUEST_MODEL",
    "GEN_AI_RESPONSE_MODEL",
    "GEN_AI_USAGE_INPUT_TOKENS",
    "GEN_AI_USAGE_OUTPUT_TOKENS",
    # Routing attribute constants
    "ROUTING_COMPLEXITY",
    "ROUTING_CONFIDENCE",
    "ROUTING_PROVIDER",
    "ROUTING_MODEL",
    "ROUTING_CACHE_HIT",
    "ROUTING_CIRCUIT_BREAKER_STATE",
    "ROUTING_FALLBACK_TIER",
]
