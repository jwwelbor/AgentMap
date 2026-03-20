"""
Centralized span name and attribute key constants for AgentMap telemetry.

All instrumented code references these constants rather than hard-coding
string values.  This ensures consistency across the codebase and makes
renaming attributes a single-file change.

Convention:
- ``agentmap.*`` prefix for AgentMap-specific attributes.
- ``gen_ai.*`` prefix for OpenTelemetry GenAI semantic convention attributes.

This module has **no runtime dependencies** -- all values are plain string
literals.
"""

# ---------------------------------------------------------------------------
# Span names
# ---------------------------------------------------------------------------

WORKFLOW_RUN_SPAN: str = "agentmap.workflow.run"
"""Root span for a complete workflow execution."""

AGENT_RUN_SPAN: str = "agentmap.agent.run"
"""Span wrapping a single agent's ``run()`` invocation."""

LLM_CALL_SPAN: str = "gen_ai.chat"
"""Span wrapping an LLM chat completion call (GenAI semantic convention)."""

# ---------------------------------------------------------------------------
# Agent span attributes
# ---------------------------------------------------------------------------

AGENT_NAME: str = "agentmap.agent.name"
"""Agent instance name."""

AGENT_TYPE: str = "agentmap.agent.type"
"""Agent class name (e.g. ``'OpenAIAgent'``)."""

NODE_NAME: str = "agentmap.node.name"
"""Graph node name that this agent occupies."""

GRAPH_NAME: str = "agentmap.graph.name"
"""Parent graph name."""

AGENT_INPUTS: str = "agentmap.agent.inputs"
"""Captured agent input state (privacy-controlled)."""

AGENT_OUTPUTS: str = "agentmap.agent.outputs"
"""Captured agent output (privacy-controlled)."""

# ---------------------------------------------------------------------------
# Workflow span attributes
# ---------------------------------------------------------------------------

GRAPH_NODE_COUNT: str = "agentmap.graph.node_count"
"""Number of nodes in the compiled graph."""

GRAPH_AGENT_COUNT: str = "agentmap.graph.agent_count"
"""Number of agents in the compiled graph."""

GRAPH_PARENT_NAME: str = "agentmap.graph.parent_name"
"""Parent graph name for subgraph executions."""

# ---------------------------------------------------------------------------
# LLM span attributes (GenAI semantic conventions)
# ---------------------------------------------------------------------------

GEN_AI_SYSTEM: str = "gen_ai.system"
"""LLM provider identifier (e.g. ``'openai'``, ``'anthropic'``)."""

GEN_AI_REQUEST_MODEL: str = "gen_ai.request.model"
"""Model name requested by the caller."""

GEN_AI_RESPONSE_MODEL: str = "gen_ai.response.model"
"""Model name returned in the LLM response."""

GEN_AI_USAGE_INPUT_TOKENS: str = "gen_ai.usage.input_tokens"
"""Number of input (prompt) tokens consumed."""

GEN_AI_USAGE_OUTPUT_TOKENS: str = "gen_ai.usage.output_tokens"
"""Number of output (completion) tokens produced."""

GEN_AI_PROMPT_CONTENT: str = "gen_ai.prompt.content"
"""Captured LLM prompt content (privacy-controlled, opt-in)."""

GEN_AI_RESPONSE_CONTENT: str = "gen_ai.response.content"
"""Captured LLM response content (privacy-controlled, opt-in)."""

GEN_AI_PROVIDER_REQUEST_ID: str = "gen_ai.provider.request_id"
"""Request ID returned by the LLM provider (for support/debugging)."""

GEN_AI_SYSTEM_FINGERPRINT: str = "gen_ai.system.fingerprint"
"""System fingerprint returned by the LLM provider (OpenAI-specific)."""

# ---------------------------------------------------------------------------
# Routing span attributes
# ---------------------------------------------------------------------------

ROUTING_COMPLEXITY: str = "agentmap.routing.complexity"
"""Prompt complexity classification determined by the routing service."""

ROUTING_CONFIDENCE: str = "agentmap.routing.confidence"
"""Routing confidence score."""

ROUTING_PROVIDER: str = "agentmap.routing.provider"
"""LLM provider selected by the routing service."""

ROUTING_MODEL: str = "agentmap.routing.model"
"""Model selected by the routing service."""

ROUTING_CACHE_HIT: str = "agentmap.routing.cache_hit"
"""Whether the routing cache was hit."""

ROUTING_CIRCUIT_BREAKER_STATE: str = "agentmap.routing.circuit_breaker_state"
"""Current circuit breaker state for the selected provider."""

ROUTING_FALLBACK_TIER: str = "agentmap.routing.fallback_tier"
"""Fallback tier used when primary routing failed."""

# ---------------------------------------------------------------------------
# Storage span names and attributes
# ---------------------------------------------------------------------------

STORAGE_READ_SPAN: str = "agentmap.storage.read"
"""Span wrapping a storage read operation."""

STORAGE_WRITE_SPAN: str = "agentmap.storage.write"
"""Span wrapping a storage write operation."""

STORAGE_BACKEND: str = "agentmap.storage.backend"
"""Storage provider name (e.g. 'csv', 'json', 'firebase', 'chroma')."""

STORAGE_OPERATION: str = "agentmap.storage.operation"
"""Storage operation type ('read' or 'write')."""

STORAGE_RECORD_COUNT: str = "agentmap.storage.record_count"
"""Number of records involved in the storage operation."""

STORAGE_RESOURCE: str = "agentmap.storage.resource"
"""Opt-in resource identifier (file path or collection name). Controlled by config flag."""

# ---------------------------------------------------------------------------
# Metric name constants (LLM operations)
# ---------------------------------------------------------------------------

METRIC_LLM_DURATION: str = "agentmap.llm.duration"
"""Histogram recording LLM call duration in seconds."""

METRIC_LLM_TOKENS_INPUT: str = "agentmap.llm.tokens.input"
"""Counter for input (prompt) tokens consumed by LLM calls."""

METRIC_LLM_TOKENS_OUTPUT: str = "agentmap.llm.tokens.output"
"""Counter for output (completion) tokens produced by LLM calls."""

METRIC_LLM_ERRORS: str = "agentmap.llm.errors"
"""Counter for LLM call errors."""

METRIC_LLM_ROUTING_CACHE_HIT: str = "agentmap.llm.routing.cache_hit"
"""Counter for routing cache hits."""

METRIC_LLM_CIRCUIT_BREAKER: str = "agentmap.llm.circuit_breaker"
"""UpDownCounter (gauge) for circuit breaker state."""

METRIC_LLM_FALLBACK: str = "agentmap.llm.fallback"
"""Counter for LLM fallback events."""

# ---------------------------------------------------------------------------
# Metric dimension (attribute key) constants
# ---------------------------------------------------------------------------

METRIC_DIM_PROVIDER: str = "provider"
"""LLM provider dimension for metric attributes."""

METRIC_DIM_MODEL: str = "model"
"""LLM model dimension for metric attributes."""

METRIC_DIM_ERROR_TYPE: str = "error_type"
"""Error type dimension for metric attributes."""

METRIC_DIM_TIER: str = "tier"
"""Tier dimension for metric attributes."""
