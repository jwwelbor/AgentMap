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
from agentmap.agents.builtins.graph_agent import GraphAgent

# Import optional agents if available
try:
    from agentmap.agents.builtins.llm.openai_agent import OpenAIAgent
except ImportError:
    OpenAIAgent = None

try:
    from agentmap.agents.builtins.llm.anthropic_agent import AnthropicAgent
except ImportError:
    AnthropicAgent = None

try:
    from agentmap.agents.builtins.llm.google_agent import GoogleAgent
except ImportError:
    GoogleAgent = None


# Central registry of agent types
AGENT_MAP = {
    "echo": EchoAgent,
    "default": DefaultAgent,
    "input": InputAgent,
    "success": SuccessAgent,
    "failure": FailureAgent,
    "branching": BranchingAgent,
    "graph": GraphAgent
}

# Import storage agents
try:
    from agentmap.agents.builtins.storage import (
        CSVReaderAgent, CSVWriterAgent, 
        JSONDocumentReaderAgent, JSONDocumentWriterAgent,
        FileReaderAgent, FileWriterAgent
    )
    AGENT_MAP["csv_reader"] = CSVReaderAgent
    AGENT_MAP["csv_writer"] = CSVWriterAgent
    AGENT_MAP["json_reader"] = JSONDocumentReaderAgent
    AGENT_MAP["json_writer"] = JSONDocumentWriterAgent
    AGENT_MAP["file_reader"] = FileReaderAgent
    AGENT_MAP["file_writer"] = FileWriterAgent    
except ImportError:
    pass

try:
    from agentmap.agents.builtins.summary_agent import SummaryAgent
    AGENT_MAP["summary"] = SummaryAgent
except ImportError:
    pass

try:
    from agentmap.agents.builtins.storage.vector import (
        VectorAgent, VectorReaderAgent, VectorWriterAgent
    )
    # In your agent registry
    AGENT_MAP["vector_agent"] = VectorAgent  # Base agent
    AGENT_MAP["vector_reader"] = VectorReaderAgent
    AGENT_MAP["vector_writer"] = VectorWriterAgent
except ImportError:
    pass   


# Import Firebase agents if available
try:
    from agentmap.agents.builtins.storage import (
        FirebaseDocumentReaderAgent, FirebaseDocumentWriterAgent
    )
    AGENT_MAP["firebase_reader"] = FirebaseDocumentReaderAgent
    AGENT_MAP["firebase_writer"] = FirebaseDocumentWriterAgent
    AGENT_MAP["firestore_reader"] = FirebaseDocumentReaderAgent  # Alias for convenience
    AGENT_MAP["firestore_writer"] = FirebaseDocumentWriterAgent  # Alias for convenience
except (ImportError, AttributeError):
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


# Import loader after individual agent imports to avoid circular dependencies
from agentmap.agents.loader import AgentLoader, create_agent

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