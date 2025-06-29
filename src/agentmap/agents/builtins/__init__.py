"""
Built-in agents for AgentMap.

This module provides pre-configured agents for common tasks. All agent
registration is now handled by ApplicationBootstrapService during application
initialization, not at import time.

The agents themselves are still imported here for convenience and backward
compatibility of imports, but no side effects occur during import.
"""

# Core agents - always available
from agentmap.agents.base_agent import BaseAgent
from agentmap.agents.builtins.branching_agent import BranchingAgent
from agentmap.agents.builtins.default_agent import DefaultAgent
from agentmap.agents.builtins.echo_agent import EchoAgent
from agentmap.agents.builtins.failure_agent import FailureAgent
from agentmap.agents.builtins.human_agent import HumanAgent
from agentmap.agents.builtins.input_agent import InputAgent
from agentmap.agents.builtins.success_agent import SuccessAgent

# from agentmap.agents.builtins.graph_agent import GraphAgent

# Base exports - always available
__all__ = [
    "BaseAgent",
    "DefaultAgent",
    "EchoAgent",
    "BranchingAgent",
    "FailureAgent",
    "HumanAgent",
    "SuccessAgent",
    "InputAgent",
    "GraphAgent",
]

# Conditionally available agents - imported only if dependencies exist
# No registration happens here - that's handled by ApplicationBootstrapService

# Try to import orchestrator agent
try:
    pass

    __all__.append("OrchestratorAgent")
except ImportError:
    pass

# Try to import summary agent
try:
    pass

    __all__.append("SummaryAgent")
except ImportError:
    pass

# Try to import LLM agents
try:
    pass

    __all__.append("LLMAgent")
except ImportError:
    pass

try:
    pass

    __all__.append("OpenAIAgent")
except ImportError:
    pass

try:
    pass

    __all__.append("AnthropicAgent")
except ImportError:
    pass

try:
    pass

    __all__.append("GoogleAgent")
except ImportError:
    pass

# Try to import storage agents
try:
    pass

    __all__.append("BaseStorageAgent")
except ImportError:
    pass

try:
    pass

    __all__.extend(["CSVReaderAgent", "CSVWriterAgent"])
except ImportError:
    pass

try:
    pass

    __all__.extend(["JSONDocumentReaderAgent", "JSONDocumentWriterAgent"])
except ImportError:
    pass

try:
    pass

    __all__.extend(["FileReaderAgent", "FileWriterAgent"])
except ImportError:
    pass

try:
    pass

    __all__.extend(["VectorReaderAgent", "VectorWriterAgent"])
except ImportError:
    pass

# NOTE: All agent registration, feature enabling, and provider validation
# is now handled by ApplicationBootstrapService.bootstrap_application()
# during application initialization, not at import time.
#
# This provides clean separation of concerns:
# - Import time: Only make agents available for import
# - Bootstrap time: Register agents based on available dependencies
