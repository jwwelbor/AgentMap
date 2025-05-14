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

# Import storage agents
try:
    from agentmap.agents.builtins.storage import (
        CSVReaderAgent, CSVWriterAgent, 
        JSONDocumentReaderAgent, JSONDocumentWriterAgent,
        FileReaderAgent, FileWriterAgent
    )
except ImportError:
    pass

try:
    from agentmap.agents.builtins.summary_agent import SummaryAgent
except ImportError:
    pass

try:
    from agentmap.agents.builtins.storage.vector import (
        VectorAgent, VectorReaderAgent, VectorWriterAgent
    )
except ImportError:
    pass   

# Import Firebase agents if available
try:
    from agentmap.agents.builtins.storage import (
        FirebaseDocumentReaderAgent, FirebaseDocumentWriterAgent
    )
except (ImportError, AttributeError):
    pass

# Import loader after individual agent imports to avoid circular dependencies
from agentmap.agents.loader import AgentLoader, create_agent
from agentmap.agents.registry import get_agent_class, register_agent

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
    'register_agent'
]