"""
AgentMap Agents Module

This module provides clean imports for AgentMap agent classes. Agent registration and
discovery is now handled by ApplicationBootstrapService through the dependency injection
container, eliminating the previous import-time side effects.

## New Architecture (Service-Based Approach)

Agent registration and feature discovery now happens through ApplicationBootstrapService:

```python
from agentmap.di import initialize_application

# Initialize DI container and bootstrap agents
container = initialize_application()

# Access agents through the container
agent_registry = container.agent_registry_service()
agent_factory = container.agent_factory_service()

# Create agents using the factory
agent = agent_factory.create_agent("openai", {"model": "gpt-4"})
```

## Legacy Compatibility

Agent classes remain importable for backward compatibility:

```python
from agentmap.agents import DefaultAgent, EchoAgent
# This still works, but registration is handled by ApplicationBootstrapService
```

## Migration Guide

If your code previously relied on import-time agent registration:

**Old approach (deprecated):**
```python
import agentmap.agents  # Side effect: registered all agents
from agentmap.agents import get_agent_class
agent_class = get_agent_class("openai")
```

**New approach (recommended):**
```python
from agentmap.di import initialize_application
container = initialize_application()
agent_factory = container.agent_factory_service()
agent = agent_factory.create_agent("openai", {"model": "gpt-4"})
```

## Available Agent Classes

Core agents (always available):
- DefaultAgent: Default processing agent
- EchoAgent: Simple echo/passthrough agent
- BranchingAgent: Conditional routing agent
- FailureAgent: Explicit failure handling
- SuccessAgent: Explicit success handling
- InputAgent: User input collection
- GraphAgent: Sub-graph execution

LLM agents (requires LLM dependencies):
- LLMAgent: Base LLM agent
- OpenAIAgent: OpenAI/GPT integration
- AnthropicAgent: Anthropic/Claude integration
- GoogleAgent: Google/Gemini integration

Storage agents (requires storage dependencies):
- CSVReaderAgent, CSVWriterAgent: CSV file operations
- JSONDocumentReaderAgent, JSONDocumentWriterAgent: JSON operations
- FileReaderAgent, FileWriterAgent: General file operations
- VectorReaderAgent, VectorWriterAgent: Vector storage operations

Mixed dependency agents:
- SummaryAgent: Content summarization
- OrchestratorAgent: Complex workflow orchestration

Note: Agent availability depends on installed dependencies. Use ApplicationBootstrapService
for runtime discovery of available agents.
"""

# Base agent classes (always available)
from agentmap.agents.base_agent import BaseAgent
from agentmap.agents.builtins.branching_agent import BranchingAgent

# Core agent classes (always available - no external dependencies)
from agentmap.agents.builtins.default_agent import DefaultAgent
from agentmap.agents.builtins.echo_agent import EchoAgent
from agentmap.agents.builtins.failure_agent import FailureAgent
from agentmap.agents.builtins.graph_agent import GraphAgent
from agentmap.agents.builtins.input_agent import InputAgent
from agentmap.agents.builtins.success_agent import SuccessAgent

# LLM agent classes (may not be available depending on dependencies)
try:
    pass

    _llm_base_available = True
except ImportError:
    _llm_base_available = False

try:
    pass

    _openai_available = True
except ImportError:
    _openai_available = False

try:
    pass

    _anthropic_available = True
except ImportError:
    _anthropic_available = False

try:
    pass

    _google_available = True
except ImportError:
    _google_available = False

# Storage agent classes (may not be available depending on dependencies)
try:
    pass

    _storage_available = True
except ImportError:
    _storage_available = False

# Mixed dependency agents
try:
    pass

    _summary_available = True
except ImportError:
    _summary_available = False

try:
    pass

    _orchestrator_available = True
except ImportError:
    _orchestrator_available = False

# Build __all__ exports for backward compatibility
__all__ = [
    # Base classes
    "BaseAgent",
    # Core agents (always available)
    "DefaultAgent",
    "EchoAgent",
    "BranchingAgent",
    "FailureAgent",
    "SuccessAgent",
    "InputAgent",
    "GraphAgent",
]

# Add LLM agents if available
if _llm_base_available:
    __all__.append("LLMAgent")
if _openai_available:
    __all__.append("OpenAIAgent")
if _anthropic_available:
    __all__.append("AnthropicAgent")
if _google_available:
    __all__.append("GoogleAgent")

# Add storage agents if available
if _storage_available:
    __all__.extend(
        [
            "CSVReaderAgent",
            "CSVWriterAgent",
            "JSONDocumentReaderAgent",
            "JSONDocumentWriterAgent",
            "FileReaderAgent",
            "FileWriterAgent",
            "VectorReaderAgent",
            "VectorWriterAgent",
        ]
    )

# Add mixed dependency agents if available
if _summary_available:
    __all__.append("SummaryAgent")
if _orchestrator_available:
    __all__.append("OrchestratorAgent")
