# agentmap/agents/__init__.py
"""
Agent registration and discovery module for AgentMap.

This module registers all available agents with the central registry and provides
agent-related functionality to the rest of the application.
"""
from agentmap.agents.base_agent import BaseAgent
from agentmap.agents.registry import register_agent, get_agent_class, get_agent_map
from agentmap.agents.loader import AgentLoader, create_agent
from agentmap.agents.features import enable_llm_agents, enable_storage_agents, is_llm_enabled, is_storage_enabled
from agentmap.services.logging_service import _get_bootstrap_logger

_logger = _get_bootstrap_logger(__name__)

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
from agentmap.agents.dependency_checker import check_llm_dependencies

# Global check for basic LLM capabilities
has_basic_llm, missing_basic = check_llm_dependencies()
if not has_basic_llm:
    _logger.debug(f"LLM dependencies not available: {missing_basic}")
    features.record_missing_dependencies("llm", missing_basic)
else:
    # Try to register LLM base classes
    try:
        # Import and register base LLM agent
        from agentmap.agents.builtins.llm.llm_agent import LLMAgent
        register_agent("llm", LLMAgent)
        
        # Register individual providers if their dependencies are available
        
        # OpenAI provider
        has_openai, missing_openai = check_llm_dependencies("openai")
        if has_openai:
            try:
                from agentmap.agents.builtins.llm.openai_agent import OpenAIAgent
                register_agent("openai", OpenAIAgent)
                register_agent("gpt", OpenAIAgent)  # Add alias for convenience
                register_agent("chatgpt", OpenAIAgent)  # Add additional alias for convenience
                features.set_provider_available("llm", "openai", True)
                features.set_provider_validated("llm", "openai", True)
                _logger.debug("OpenAI agent validated and registered")
            except ImportError as e:
                _logger.debug(f"OpenAI agent import failed: {e}")
                features.set_provider_validated("llm", "openai", False)
        else:
            _logger.debug(f"OpenAI dependencies not available: {missing_openai}")
            features.record_missing_dependencies("openai", missing_openai)
            features.set_provider_available("llm", "openai", False)
            features.set_provider_validated("llm", "openai", False)
        
        # Anthropic provider
        has_anthropic, missing_anthropic = check_llm_dependencies("anthropic")
        if has_anthropic:
            try:
                from agentmap.agents.builtins.llm.anthropic_agent import AnthropicAgent
                register_agent("anthropic", AnthropicAgent)
                register_agent("claude", AnthropicAgent)  # Add alias for convenience
                features.set_provider_available("llm", "anthropic", True)
                features.set_provider_validated("llm", "anthropic", True)
                _logger.debug("Anthropic agent validated and registered")
            except ImportError as e:
                _logger.debug(f"Anthropic agent import failed: {e}")
                features.set_provider_validated("llm", "anthropic", False)
        else:
            _logger.debug(f"Anthropic dependencies not available: {missing_anthropic}")
            features.record_missing_dependencies("anthropic", missing_anthropic)
            features.set_provider_available("llm", "anthropic", False)
            features.set_provider_validated("llm", "anthropic", False)
        
        # Google provider
        has_google, missing_google = check_llm_dependencies("google")
        if has_google:
            try:
                from agentmap.agents.builtins.llm.google_agent import GoogleAgent
                register_agent("google", GoogleAgent)
                register_agent("gemini", GoogleAgent)  # Add alias for convenience
                features.set_provider_available("llm", "google", True)
                features.set_provider_validated("llm", "google", True)
                _logger.debug("Google agent validated and registered")
            except ImportError as e:
                _logger.debug(f"Google agent import failed: {e}")
                features.set_provider_validated("llm", "google", False)
        else:
            _logger.debug(f"Google dependencies not available: {missing_google}")
            features.record_missing_dependencies("google", missing_google)
            features.set_provider_available("llm", "google", False)
            features.set_provider_validated("llm", "google", False)
        
        # Enable LLM feature if at least one provider is validated
        if (features.is_provider_validated("llm", "openai") or 
            features.is_provider_validated("llm", "anthropic") or 
            features.is_provider_validated("llm", "google")):
            features.enable_feature("llm")
            _logger.info("LLM agents registered successfully with validated providers")
        else:
            _logger.warning("No validated LLM providers available")
            
    except ImportError as e:
        _logger.debug(f"Base LLM agent import failed: {e}")

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
]

# Add agent classes to __all__ for convenience
_agent_classes = set(cls.__name__ for cls in get_agent_map().values())
for class_name in _agent_classes:
    if class_name and class_name not in __all__:
        __all__.append(class_name)