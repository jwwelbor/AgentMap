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

logger = get_logger(__name__)

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

# ----- LLM AGENTS (requires 'llm' extras) -----
try:
    # Import all LLM agents at once
    from agentmap.agents.builtins.llm.llm_agent import LLMAgent
    from agentmap.agents.builtins.llm.openai_agent import OpenAIAgent
    from agentmap.agents.builtins.llm.anthropic_agent import AnthropicAgent
    from agentmap.agents.builtins.llm.google_agent import GoogleAgent
    
    # Register all LLM agents
    register_agent("llm", LLMAgent)
    register_agent("openai", OpenAIAgent)
    register_agent("gpt", OpenAIAgent)  # Add alias for convenience
    register_agent("anthropic", AnthropicAgent)
    register_agent("claude", AnthropicAgent)  # Add alias for convenience
    register_agent("google", GoogleAgent)
    register_agent("gemini", GoogleAgent)  # Add alias for convenience
    
    # Log successful loading
    logger.info("LLM agents registered successfully")
    
    # Flag indicating LLM agents are available
    enable_llm_agents()
    
except ImportError as e:
    logger.debug(f"LLM agents not available: {e}. Install with: pip install agentmap[llm]")

# ----- STORAGE AGENTS (requires 'storage' extras) -----
try:
    # Import all storage agents at once
    from agentmap.agents.builtins.storage import (
        CSVReaderAgent, CSVWriterAgent,
        JSONDocumentReaderAgent, JSONDocumentWriterAgent,
        FileReaderAgent, FileWriterAgent,
        VectorStoreReaderAgent, VectorStoreWriterAgent,
        DocumentReaderAgent, DocumentWriterAgent
    )
    
    # Register all storage agents
    register_agent("csv_reader", CSVReaderAgent)
    register_agent("csv_writer", CSVWriterAgent)
    register_agent("json_reader", JSONDocumentReaderAgent)
    register_agent("json_writer", JSONDocumentWriterAgent)
    register_agent("file_reader", FileReaderAgent)
    register_agent("file_writer", FileWriterAgent)
    register_agent("vector_reader", VectorStoreReaderAgent)
    register_agent("vector_writer", VectorStoreWriterAgent)
    
    # Log successful loading
    logger.info("Storage agents registered successfully")
    
    # Flag indicating storage agents are available
    enable_storage_agents()
    
except ImportError as e:
    logger.debug(f"Storage agents not available: {e}. Install with: pip install agentmap[storage]")

# ----- SUMMARY AGENT (mixed dependency) -----
try:
    from agentmap.agents.builtins.summary_agent import SummaryAgent
    register_agent("summary", SummaryAgent)
    logger.info("Summary agent registered successfully")
except ImportError as e:
    logger.debug(f"Summary agent not available: {e}")

# ----- ORCHESTRATOR AGENT -----
try:
    from agentmap.agents.builtins.orchestrator_agent import OrchestratorAgent
    register_agent("orchestrator", OrchestratorAgent)
    logger.info("Orchestrator agent registered successfully")
except ImportError as e:
    logger.debug(f"Orchestrator agent not available: {e}")

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