"""
Built-in agents for AgentMap.

This module provides pre-configured agents for common tasks. All agent
registration happens in the main agents/__init__.py.
"""
# Import feature flags from main agents module
from agentmap.agents import HAS_LLM_AGENTS, HAS_STORAGE_AGENTS

# Core agents - always available
from agentmap.agents.base_agent import BaseAgent
from agentmap.agents.builtins.default_agent import DefaultAgent
from agentmap.agents.builtins.echo_agent import EchoAgent
from agentmap.agents.builtins.branching_agent import BranchingAgent
from agentmap.agents.builtins.failure_agent import FailureAgent
from agentmap.agents.builtins.success_agent import SuccessAgent
from agentmap.agents.builtins.input_agent import InputAgent
from agentmap.agents.builtins.graph_agent import GraphAgent

# Base exports - always available
__all__ = [
    'BaseAgent',
    'DefaultAgent',
    'EchoAgent',
    'BranchingAgent',
    'FailureAgent',
    'SuccessAgent',
    'InputAgent',
    'GraphAgent',
]

# Conditionally include orchestrator agent
try:
    from agentmap.agents.builtins.orchestrator_agent import OrchestratorAgent
    __all__.append('OrchestratorAgent')
except ImportError:
    pass

# Conditionally include summary agent
try:
    from agentmap.agents.builtins.summary_agent import SummaryAgent
    __all__.append('SummaryAgent')
except ImportError:
    pass

# Conditionally import LLM agents based on feature flag
if HAS_LLM_AGENTS:
    # These imports should never fail because the feature flag guarantees availability
    from agentmap.agents.builtins.llm.llm_agent import LLMAgent
    from agentmap.agents.builtins.llm.openai_agent import OpenAIAgent
    from agentmap.agents.builtins.llm.anthropic_agent import AnthropicAgent
    from agentmap.agents.builtins.llm.google_agent import GoogleAgent
    
    # Add LLM agents to exports
    __all__.extend([
        'LLMAgent',
        'OpenAIAgent',
        'AnthropicAgent', 
        'GoogleAgent',
    ])

# Conditionally import storage agents based on feature flag
if HAS_STORAGE_AGENTS:
    # These imports should never fail because the feature flag guarantees availability
    from agentmap.agents.builtins.storage import (
        CSVReaderAgent, CSVWriterAgent,
        JSONDocumentReaderAgent, JSONDocumentWriterAgent,
        FileReaderAgent, FileWriterAgent,
        VectorStoreReaderAgent, VectorStoreWriterAgent
    )
    
    # Add storage agents to exports
    __all__.extend([
        'CSVReaderAgent',
        'CSVWriterAgent',
        'JSONDocumentReaderAgent',
        'JSONDocumentWriterAgent',
        'FileReaderAgent',
        'FileWriterAgent',
        'VectorStoreReaderAgent',
        'VectorStoreWriterAgent',
    ])