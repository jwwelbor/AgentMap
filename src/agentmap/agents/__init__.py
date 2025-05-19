# agentmap/agents/__init__.py
"""
Agent registration and discovery module for AgentMap.

This module registers all available agents with the central registry and provides
agent-related functionality to the rest of the application.
"""
from agentmap.agents.base_agent import BaseAgent
from agentmap.agents.registry import register_agent, get_agent_class, get_agent_map
from agentmap.agents.loader import AgentLoader, create_agent
from agentmap.logging import get_logger
from agentmap.agents.features import HAS_LLM_AGENTS, HAS_STORAGE_AGENTS, enable_llm_agents, enable_storage_agents

_logger = get_logger("agentmap.agents")

# ----- CORE AGENTS (always available) -----
from agentmap.agents.builtins.default_agent import DefaultAgent
from agentmap.agents.builtins.echo_agent import EchoAgent
from agentmap.agents.builtins.branching_agent import BranchingAgent
from agentmap.agents.builtins.failure_agent import FailureAgent
from agentmap.agents.builtins.success_agent import SuccessAgent
from agentmap.agents.builtins.input_agent import InputAgent
from agentmap.agents.builtins.graph_agent import GraphAgent

# Register core agents
register_agent("default", DefaultAgent)
register_agent("echo", EchoAgent)
register_agent("branching", BranchingAgent)
register_agent("failure", FailureAgent)
register_agent("success", SuccessAgent)
register_agent("input", InputAgent)
register_agent("graph", GraphAgent)

# agentmap/agents/__init__.py - Modified section for LLM agent imports

# ----- LLM AGENTS (requires 'llm' extras) -----
from agentmap.features_registry import features
from agentmap.agents.dependency_checker import check_llm_dependencies, get_llm_installation_guide

try:
    # Import all LLM agents at once
    from agentmap.agents.builtins.llm.llm_agent import LLMAgent
    
    # Check and register each provider
    # OpenAI
    try:
        from agentmap.agents.builtins.llm.openai_agent import OpenAIAgent
        register_agent("openai", OpenAIAgent)
        register_agent("gpt", OpenAIAgent)  # Add alias for convenience
        features.set_provider_available("llm", "openai", True)
        _logger.debug("OpenAI agent registered successfully")
    except ImportError as e:
        _logger.debug(f"OpenAI agent not available: {e}")
        _, missing = check_llm_dependencies("openai")
        features.record_missing_dependencies("openai", missing)
    
    # Anthropic
    try:
        from agentmap.agents.builtins.llm.anthropic_agent import AnthropicAgent
        register_agent("anthropic", AnthropicAgent)
        register_agent("claude", AnthropicAgent)  # Add alias for convenience
        features.set_provider_available("llm", "anthropic", True)
        _logger.debug("Anthropic agent registered successfully")
    except ImportError as e:
        _logger.debug(f"Anthropic agent not available: {e}")
        _, missing = check_llm_dependencies("anthropic")
        features.record_missing_dependencies("anthropic", missing)
    
    # Google
    try:
        from agentmap.agents.builtins.llm.google_agent import GoogleAgent
        register_agent("google", GoogleAgent)
        register_agent("gemini", GoogleAgent)  # Add alias for convenience
        features.set_provider_available("llm", "google", True)
        _logger.debug("Google agent registered successfully")
    except ImportError as e:
        _logger.debug(f"Google agent not available: {e}")
        _, missing = check_llm_dependencies("google")
        features.record_missing_dependencies("google", missing)
    
    # Register the base LLM agent
    register_agent("llm", LLMAgent)
    
    # Enable LLM agents if at least one provider is available
    if features.get_available_providers("llm"):
        enable_llm_agents()
        _logger.info("LLM agents registered successfully")
    else:
        _logger.warning("No LLM providers available.")
    
except ImportError as e:
    _logger.debug(f"LLM agents not available: {e}. Install with: pip install agentmap[llm]")
    _, missing = check_llm_dependencies()
    features.record_missing_dependencies("llm", missing)

# ----- STORAGE AGENTS (requires 'storage' extras) -----
try:
    # Import all storage agents at once
    from agentmap.agents.builtins.storage import (
        CSVReaderAgent, CSVWriterAgent,
        JSONDocumentReaderAgent, JSONDocumentWriterAgent,
        FileReaderAgent, FileWriterAgent,
        VectorReaderAgent, VectorWriterAgent,
        DocumentReaderAgent, DocumentWriterAgent
    )
    
    # Register all storage agents
    register_agent("csv_reader", CSVReaderAgent)
    register_agent("csv_writer", CSVWriterAgent)
    register_agent("json_reader", JSONDocumentReaderAgent)
    register_agent("json_writer", JSONDocumentWriterAgent)
    register_agent("file_reader", FileReaderAgent)
    register_agent("file_writer", FileWriterAgent)
    register_agent("vector_reader", VectorReaderAgent)
    register_agent("vector_writer", VectorWriterAgent)
    
    # Log successful loading
    _logger.info("Storage agents registered successfully")
    
    # Flag indicating storage agents are available
    enable_storage_agents()
    
except ImportError as e:
     _logger.debug(f"Storage agents not available: {e}. Install with: pip install agentmap[storage]")

# ----- SUMMARY AGENT (mixed dependency) -----
try:
    from agentmap.agents.builtins.summary_agent import SummaryAgent
    register_agent("summary", SummaryAgent)
    _logger.info("Summary agent registered successfully")
except ImportError as e:
    _logger.debug(f"Summary agent not available: {e}")

# ----- ORCHESTRATOR AGENT -----
try:
    from agentmap.agents.builtins.orchestrator_agent import OrchestratorAgent
    register_agent("orchestrator", OrchestratorAgent)
    _logger.info("Orchestrator agent registered successfully")
except ImportError as e:
    _logger.debug(f"Orchestrator agent not available: {e}")

# Dynamic registry access
REGISTERED_AGENTS = get_agent_map()

# Export public API
__all__ = [
    'BaseAgent',
    'AgentLoader',
    'create_agent',
    'get_agent_class',
    'register_agent',
    'get_agent_map',
    'REGISTERED_AGENTS',
    'HAS_LLM_AGENTS',
    'HAS_STORAGE_AGENTS',
]

# Add agent classes to __all__ for convenience
_agent_classes = set(cls.__name__ for cls in get_agent_map().values())
for class_name in _agent_classes:
    if class_name and class_name not in __all__:
        __all__.append(class_name)