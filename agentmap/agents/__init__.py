"""
AgentMap agent registry.
Provides a central mapping of agent types to their implementation classes.
"""

# Import base agent class
from agentmap.agents.base_agent import BaseAgent
from agentmap.agents.builtins.branching_agent import BranchingAgent
# Import built-in agent types
from agentmap.agents.builtins.default_agent import DefaultAgent
from agentmap.agents.builtins.echo_agent import EchoAgent
from agentmap.agents.builtins.failure_agent import FailureAgent
from agentmap.agents.builtins.input_agent import InputAgent
from agentmap.agents.builtins.success_agent import SuccessAgent

# Import optional agents if available
try:
    from agentmap.agents.builtins.openai_agent import OpenAIAgent
except ImportError:
    OpenAIAgent = None

try:
    from agentmap.agents.builtins.anthropic_agent import AnthropicAgent
except ImportError:
    AnthropicAgent = None

try:
    from agentmap.agents.builtins.google_agent import GoogleAgent
except ImportError:
    GoogleAgent = None

# Import loader after individual agent imports to avoid circular dependencies
from agentmap.agents.loader import AgentLoader, create_agent

# Central registry of agent types
AGENT_MAP = {
    "echo": EchoAgent,
    "default": DefaultAgent,
    "input": InputAgent,
    "success": SuccessAgent,
    "failure": FailureAgent,
    "branching": BranchingAgent
}

# Import storage agents
try:
    from agentmap.agents.builtins.storage import CSVReaderAgent, CSVWriterAgent
    AGENT_MAP["csv_reader"] = CSVReaderAgent
    AGENT_MAP["csv_writer"] = CSVWriterAgent
except ImportError:
    pass

# Add optional agents if available
if OpenAIAgent:
    AGENT_MAP["openai"] = OpenAIAgent
    AGENT_MAP["gpt"] = OpenAIAgent  # Add alias for convenience
    AGENT_MAP["chatgpt"] = OpenAIAgent  # Add alias for convenience

if AnthropicAgent:
    AGENT_MAP["anthropic"] = AnthropicAgent
    AGENT_MAP["claude"] = AnthropicAgent  # Add alias for convenience

if GoogleAgent:
    AGENT_MAP["google"] = GoogleAgent
    AGENT_MAP["gemini"] = GoogleAgent  # Add alias for convenience

def get_agent_class(agent_type: str):
    """
    Get an agent class by its type string.
    
    Args:
        agent_type: The type identifier for the agent
        
    Returns:
        The agent class or None if not found
    """
    if not agent_type:
        return DefaultAgent
        
    agent_type = agent_type.lower()
    return AGENT_MAP.get(agent_type)

def register_agent(agent_type: str, agent_class):
    """
    Register a custom agent class with the agent registry.
    
    Args:
        agent_type: The type identifier for the agent
        agent_class: The agent class to register
    """
    AGENT_MAP[agent_type.lower()] = agent_class

# Export symbols
__all__ = [
    'BaseAgent',
    'DefaultAgent',
    'EchoAgent',
    'BranchingAgent',
    'FailureAgent',
    'InputAgent',
    'SuccessAgent',
    'OpenAIAgent',
    'AnthropicAgent',
    'GoogleAgent',
    'AgentLoader',
    'create_agent',
    'get_agent_class',
    'register_agent',
    'AGENT_MAP'
]