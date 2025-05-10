"""
Agent registration and discovery module for AgentMap.

This module registers built-in agents with the central registry and provides
agent-related functionality to the rest of the application.
"""
# Import base agent class
from agentmap.agents.base_agent import BaseAgent

# Import registry functions
from agentmap.agents.registry import (
    register_agent, 
    get_agent_class,
    get_agent_map
)

# Import built-in agents
from agentmap.agents.builtins.default_agent import DefaultAgent
from agentmap.agents.builtins.echo_agent import EchoAgent
from agentmap.agents.builtins.branching_agent import BranchingAgent
from agentmap.agents.builtins.failure_agent import FailureAgent
from agentmap.agents.builtins.input_agent import InputAgent
from agentmap.agents.builtins.success_agent import SuccessAgent

# Register built-in agents
register_agent("default", DefaultAgent)
register_agent("echo", EchoAgent)
register_agent("branching", BranchingAgent)
register_agent("failure", FailureAgent)
register_agent("input", InputAgent)
register_agent("success", SuccessAgent)

# Import and register optional LLM agents
try:
    from agentmap.agents.builtins.llm.openai_agent import OpenAIAgent
    register_agent("openai", OpenAIAgent)
    register_agent("gpt", OpenAIAgent)  # Add alias for convenience
    register_agent("chatgpt", OpenAIAgent)  # Add alias for convenience
except ImportError:
    OpenAIAgent = None

try:
    from agentmap.agents.builtins.llm.anthropic_agent import AnthropicAgent
    register_agent("anthropic", AnthropicAgent)
    register_agent("claude", AnthropicAgent)  # Add alias for convenience
except ImportError:
    AnthropicAgent = None

try:
    from agentmap.agents.builtins.llm.google_agent import GoogleAgent
    register_agent("google", GoogleAgent)
    register_agent("gemini", GoogleAgent)  # Add alias for convenience
except ImportError:
    GoogleAgent = None

# Try to register LLM base class if available
try:
    from agentmap.agents.builtins.llm.llm_agent import LLMAgent
    register_agent("llm", LLMAgent)
except ImportError:
    LLMAgent = None

# Try to register storage agents if available
try:
    from agentmap.agents.builtins.storage import CSVReaderAgent, CSVWriterAgent
    register_agent("csv_reader", CSVReaderAgent)
    register_agent("csv_writer", CSVWriterAgent)
except ImportError:
    pass

try:
    from agentmap.agents.builtins.storage import JSONDocumentReaderAgent, JSONDocumentWriterAgent
    register_agent("json_reader", JSONDocumentReaderAgent)
    register_agent("json_writer", JSONDocumentWriterAgent)
except ImportError:
    pass    

try:
    from agentmap.agents.builtins.storage import FileReaderAgent, FileWriterAgent
    register_agent("file_reader", FileReaderAgent)
    register_agent("file_writer", FileWriterAgent)
except ImportError:
    pass

try:
    from agentmap.agents.builtins.storage import VectorStoreReaderAgent, VectorStoreWriterAgent
    register_agent("vector_reader", VectorStoreReaderAgent)
    register_agent("vector_writer", VectorStoreWriterAgent)
except ImportError:
    pass


# Import agent loader functions - no circular dependency anymore
from agentmap.agents.loader import AgentLoader, create_agent

# For backwards compatibility, create an AGENT_MAP variable
AGENT_MAP = get_agent_map()

# Export public API
__all__ = [
    'BaseAgent',
    'AgentLoader',
    'create_agent',
    'get_agent_class',
    'register_agent',
    'AGENT_MAP',  # For backwards compatibility
]

# Add agent classes to __all__ for convenience
_agent_classes = set(cls.__name__ for cls in AGENT_MAP.values())
for class_name in _agent_classes:
    if class_name and class_name not in __all__:
        __all__.append(class_name)