"""
Built-in agent implementations for AgentMap.
"""

from agentmap.agents.builtins.branching_agent import BranchingAgent
from agentmap.agents.builtins.default_agent import DefaultAgent
from agentmap.agents.builtins.echo_agent import EchoAgent
from agentmap.agents.builtins.failure_agent import FailureAgent
from agentmap.agents.builtins.input_agent import InputAgent
from agentmap.agents.builtins.success_agent import SuccessAgent

# Optional imports based on availability
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



__all__ = [
    'DefaultAgent',
    'EchoAgent',
    'BranchingAgent',
    'FailureAgent',
    'InputAgent', 
    'SuccessAgent',
    'OpenAIAgent',
    'AnthropicAgent',
    'GoogleAgent',
]

