"""
LLM-related configuration for AgentMap.
"""
from pathlib import Path
from typing import Any, Dict, Optional, Union

from agentmap.config.base import load_config

def get_llm_config(provider: str, config_path: Optional[Union[str, Path]] = None) -> Dict[str, Any]:
    """
    Get configuration for a specific LLM provider.
    
    Args:
        provider: The LLM provider (openai, anthropic, google)
        config_path: Optional path to a custom config file
        
    Returns:
        Dictionary containing LLM configuration
    """
    config = load_config(config_path)
    return config.get("llm", {}).get(provider, {})