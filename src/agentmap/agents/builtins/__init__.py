"""
Built-in agents for AgentMap.

This module provides pre-configured agents for common tasks. All agent
registration happens in the main agents/__init__.py.
"""
import importlib
import logging

from agentmap.features_registry import features
from agentmap.agents.features import (
    enable_llm_agents, enable_storage_agents,
    set_provider_available, is_provider_available
)

logger = logging.getLogger(__name__)

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

# Utility function to check and register agents
def try_import_and_register(module_path, class_name, register_names=None):
    """Try to import and register an agent class."""
    try:
        module = importlib.import_module(module_path)
        agent_class = getattr(module, class_name)
        
        # Add to exports
        __all__.append(class_name)
        
        # Return success and the class
        return True, agent_class
    except (ImportError, AttributeError) as e:
        logger.debug(f"Could not import {class_name} from {module_path}: {e}")
        return False, None

# Conditionally include orchestrator agent
success, OrchestratorAgent = try_import_and_register(
    "agentmap.agents.builtins.orchestrator_agent", 
    "OrchestratorAgent"
)

# Conditionally include summary agent
success, SummaryAgent = try_import_and_register(
    "agentmap.agents.builtins.summary_agent", 
    "SummaryAgent"
)

# Try to import base LLM agent
success, LLMAgent = try_import_and_register(
    "agentmap.agents.builtins.llm.llm_agent", 
    "LLMAgent"
)

if success:
    # Base LLM functionality available
    enable_llm_agents()
    
    # Try OpenAI agent
    try:
        from agentmap.agents.builtins.llm.openai_agent import OpenAIAgent
        __all__.append('OpenAIAgent')
        
        # Validate OpenAI dependencies
        try:
            import openai
            features.set_provider_available("llm", "openai", True)
            features.set_provider_validated("llm", "openai", True)
            logger.debug("OpenAI agent registered and validated")
        except Exception as e:
            features.set_provider_available("llm", "openai", True)
            features.set_provider_validated("llm", "openai", False)
            logger.debug(f"OpenAI agent registered but validation failed: {e}")
    except ImportError as e:
        logger.debug(f"OpenAI agent not available: {e}")
    
    # Try Anthropic agent
    try:
        from agentmap.agents.builtins.llm.anthropic_agent import AnthropicAgent
        __all__.append('AnthropicAgent')
        
        # Validate Anthropic dependencies
        try:
            import anthropic
            features.set_provider_available("llm", "anthropic", True)
            features.set_provider_validated("llm", "anthropic", True)
            logger.debug("Anthropic agent registered and validated")
        except Exception as e:
            features.set_provider_available("llm", "anthropic", True)
            features.set_provider_validated("llm", "anthropic", False)
            logger.debug(f"Anthropic agent registered but validation failed: {e}")
    except ImportError as e:
        logger.debug(f"Anthropic agent not available: {e}")
    
    # Try Google agent
    try:
        from agentmap.agents.builtins.llm.google_agent import GoogleAgent
        __all__.append('GoogleAgent')
        
        # Validate Google dependencies
        try:
            import google.generativeai
            features.set_provider_available("llm", "google", True)
            features.set_provider_validated("llm", "google", True)
            logger.debug("Google agent registered and validated")
        except Exception as e:
            features.set_provider_available("llm", "google", True)
            features.set_provider_validated("llm", "google", False)
            logger.debug(f"Google agent registered but validation failed: {e}")
    except ImportError as e:
        logger.debug(f"Google agent not available: {e}")

# Try to import storage base classes
try:
    from agentmap.agents.builtins.storage.base_storage_agent import BaseStorageAgent
    enable_storage_agents()
    __all__.append('BaseStorageAgent')
    
    # CSV agents
    try:
        from agentmap.agents.builtins.storage import CSVReaderAgent, CSVWriterAgent
        __all__.extend(['CSVReaderAgent', 'CSVWriterAgent'])
        features.set_provider_available("storage", "csv", True)
        features.set_provider_validated("storage", "csv", True)
    except ImportError as e:
        logger.debug(f"CSV agents not available: {e}")
    
    # JSON agents
    try:
        from agentmap.agents.builtins.storage import JSONDocumentReaderAgent, JSONDocumentWriterAgent
        __all__.extend(['JSONDocumentReaderAgent', 'JSONDocumentWriterAgent'])
        features.set_provider_available("storage", "json", True)
        features.set_provider_validated("storage", "json", True)
    except ImportError as e:
        logger.debug(f"JSON agents not available: {e}")
    
    # File agents
    try:
        from agentmap.agents.builtins.storage import FileReaderAgent, FileWriterAgent
        __all__.extend(['FileReaderAgent', 'FileWriterAgent'])
        features.set_provider_available("storage", "file", True)
        features.set_provider_validated("storage", "file", True)
    except ImportError as e:
        logger.debug(f"File agents not available: {e}")
    
    # Vector agents
    try:
        from agentmap.agents.builtins.storage import VectorReaderAgent, VectorWriterAgent
        __all__.extend(['VectorReaderAgent', 'VectorWriterAgent'])
        
        # Validate vector dependencies
        try:
            import chromadb
            features.set_provider_available("storage", "vector", True)
            features.set_provider_validated("storage", "vector", True)
        except Exception as e:
            features.set_provider_available("storage", "vector", True)
            features.set_provider_validated("storage", "vector", False)
            logger.debug(f"Vector agents registered but validation failed: {e}")
    except ImportError as e:
        logger.debug(f"Vector agents not available: {e}")
        
except ImportError as e:
    logger.debug(f"Storage agents not available: {e}")

# Log the status of enabled features
logger.debug(f"LLM agents enabled: {features.is_feature_enabled('llm')}")
logger.debug(f"Storage agents enabled: {features.is_feature_enabled('storage')}")

# Log available providers
if features.is_feature_enabled('llm'):
    providers = features.get_available_providers('llm')
    logger.debug(f"Available LLM providers: {', '.join(providers) if providers else 'None'}")

if features.is_feature_enabled('storage'):
    providers = features.get_available_providers('storage')
    logger.debug(f"Available storage providers: {', '.join(providers) if providers else 'None'}")