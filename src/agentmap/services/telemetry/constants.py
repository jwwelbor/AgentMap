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
