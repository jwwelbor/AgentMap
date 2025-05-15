"""
Prompt manager for AgentMap.

This module provides functionality for loading and resolving prompt references
from various sources, including files, YAML configurations, and a registry.
"""
from pathlib import Path
import os
import yaml
from typing import Dict, Optional, Union, Any

from agentmap.logging import get_logger
from agentmap.config import (
    get_prompts_config,
    get_prompts_directory,
    get_prompt_registry_path
)

logger = get_logger(__name__)


class PromptManager:
    """
    Manager for loading and resolving prompt references.
    
    This class provides a centralized way to manage prompts from
    different sources, including a registry, files, and YAML configurations.
    """
    
    def __init__(self, config_path: Optional[Union[str, Path]] = None):
        """
        Initialize the prompt manager with configuration.
        
        Args:
            config_path: Optional path to a custom config file
        """
        self.config_path = config_path
        self.config = get_prompts_config(config_path)
        self.prompts_dir = get_prompts_directory(config_path)
        self.registry_path = get_prompt_registry_path(config_path)
        self.enable_cache = self.config.get("enable_cache", True)
        self._cache = {}
        self._registry = self._load_registry()
        
        # Ensure prompts directory exists
        self.prompts_dir.mkdir(parents=True, exist_ok=True)
        
        logger.debug(f"Initialized PromptManager with directory: {self.prompts_dir}")
        logger.debug(f"Registry path: {self.registry_path}")
        logger.debug(f"Cache enabled: {self.enable_cache}")
    
    def _load_registry(self) -> Dict[str, str]:
        """
        Load the prompt registry from the configured path.
        
        Returns:
            Dictionary of registered prompts
        """
        if not self.registry_path.exists():
            logger.warning(f"Prompt registry not found at {self.registry_path}")
            return {}
        
        try:
            with open(self.registry_path, 'r') as f:
                registry = yaml.safe_load(f) or {}
                logger.debug(f"Loaded {len(registry)} prompts from registry")
                return registry
        except Exception as e:
            logger.error(f"Error loading prompt registry: {e}")
            return {}
    
    def resolve_prompt(self, prompt_ref: str) -> str:
        """
        Resolve a prompt reference to its actual content.
        
        Args:
            prompt_ref: Prompt reference string (prompt:name, file:path, or yaml:path#key)
            
        Returns:
            Resolved prompt text
        """
        if not prompt_ref or not isinstance(prompt_ref, str):
            return prompt_ref
        
        # Check cache if enabled
        if self.enable_cache and prompt_ref in self._cache:
            logger.debug(f"Prompt cache hit: {prompt_ref}")
            return self._cache[prompt_ref]
        
        # Handle different reference types
        try:
            if prompt_ref.startswith("prompt:"):
                result = self._resolve_registry_prompt(prompt_ref[7:])
            elif prompt_ref.startswith("file:"):
                result = self._resolve_file_prompt(prompt_ref[5:])
            elif prompt_ref.startswith("yaml:"):
                result = self._resolve_yaml_prompt(prompt_ref[5:])
            else:
                # Not a reference, return as-is
                return prompt_ref
                
            # Cache the result if enabled
            if self.enable_cache:
                self._cache[prompt_ref] = result
                
            return result
        except Exception as e:
            logger.error(f"Error resolving prompt reference '{prompt_ref}': {e}")
            return f"[Error resolving prompt: {prompt_ref}]"
    
    def _resolve_registry_prompt(self, prompt_name: str) -> str:
        """
        Resolve a prompt from the registry by name.
        
        Args:
            prompt_name: Name of the prompt in the registry
            
        Returns:
            Prompt text or error message
        """
        if prompt_name in self._registry:
            logger.debug(f"Found prompt '{prompt_name}' in registry")
            return self._registry[prompt_name]
        
        logger.warning(f"Prompt '{prompt_name}' not found in registry")
        return f"[Prompt not found: {prompt_name}]"
    
    def _resolve_file_prompt(self, file_path: str) -> str:
        """
        Resolve a prompt from a file.
        
        Args:
            file_path: Path to the prompt file (relative to prompts_dir or absolute)
            
        Returns:
            File contents or error message
        """
        # Handle absolute vs relative paths
        path = Path(file_path)
        if not path.is_absolute():
            path = self.prompts_dir / path
        
        if not path.exists():
            logger.warning(f"Prompt file not found: {path}")
            return f"[Prompt file not found: {file_path}]"
        
        try:
            with open(path, 'r') as f:
                content = f.read().strip()
                logger.debug(f"Loaded prompt from file: {path} ({len(content)} chars)")
                return content
        except Exception as e:
            logger.error(f"Error reading prompt file '{path}': {e}")
            return f"[Error reading prompt file: {file_path}]"
    
    def _resolve_yaml_prompt(self, yaml_ref: str) -> str:
        """
        Resolve a prompt from a YAML file with key path.
        
        Args:
            yaml_ref: Reference in format "path/to/file.yaml#key.path"
            
        Returns:
            Prompt text or error message
        """
        # Parse the reference
        if "#" not in yaml_ref:
            logger.warning(f"Invalid YAML prompt reference (missing #key): {yaml_ref}")
            return f"[Invalid YAML reference (missing #key): {yaml_ref}]"
        
        file_path, key_path = yaml_ref.split("#", 1)
        
        # Handle absolute vs relative paths
        path = Path(file_path)
        if not path.is_absolute():
            path = self.prompts_dir / path
        
        if not path.exists():
            logger.warning(f"YAML prompt file not found: {path}")
            return f"[YAML prompt file not found: {file_path}]"
        
        try:
            with open(path, 'r') as f:
                data = yaml.safe_load(f)
                
            # Navigate through the nested keys
            keys = key_path.split(".")
            value = data
            
            for key in keys:
                if isinstance(value, dict) and key in value:
                    value = value[key]
                else:
                    logger.warning(f"Key '{key}' not found in YAML prompt path: {key_path}")
                    return f"[Key not found in YAML: {key_path}]"
            
            # Ensure the result is a string
            if not isinstance(value, (str, int, float, bool)):
                logger.warning(f"YAML prompt value is not a scalar type: {type(value)}")
                return f"[Invalid prompt type in YAML: {type(value)}]"
            
            result = str(value)
            logger.debug(f"Loaded prompt from YAML: {path}#{key_path} ({len(result)} chars)")
            return result
            
        except Exception as e:
            logger.error(f"Error reading YAML prompt file '{path}': {e}")
            return f"[Error reading YAML prompt file: {file_path}]"
    
    def register_prompt(self, name: str, content: str, save: bool = False) -> bool:
        """
        Register a prompt with the given name.
        
        Args:
            name: Prompt name for the registry
            content: Prompt content
            save: Whether to save the updated registry to disk
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Update in-memory registry
            self._registry[name] = content
            
            # Clear cache entry if it exists
            if self.enable_cache:
                cache_key = f"prompt:{name}"
                if cache_key in self._cache:
                    del self._cache[cache_key]
            
            # Save to disk if requested
            if save:
                self._save_registry()
                
            return True
        except Exception as e:
            logger.error(f"Error registering prompt '{name}': {e}")
            return False
    
    def _save_registry(self) -> bool:
        """
        Save the current registry to disk.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            # Ensure directory exists
            self.registry_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.registry_path, 'w') as f:
                yaml.dump(self._registry, f, default_flow_style=False)
                
            logger.debug(f"Saved {len(self._registry)} prompts to registry: {self.registry_path}")
            return True
        except Exception as e:
            logger.error(f"Error saving prompt registry: {e}")
            return False
    
    def get_registry(self) -> Dict[str, str]:
        """
        Get the current prompt registry.
        
        Returns:
            Dictionary of registered prompts
        """
        return self._registry.copy()
    
    def clear_cache(self) -> None:
        """Clear the prompt cache."""
        self._cache.clear()
        logger.debug("Cleared prompt cache")


# Global singleton instance
_prompt_manager = None

def get_prompt_manager(config_path: Optional[Union[str, Path]] = None) -> PromptManager:
    """
    Get the global PromptManager instance.
    
    Args:
        config_path: Optional path to a custom config file
        
    Returns:
        PromptManager instance
    """
    global _prompt_manager
    if _prompt_manager is None:
        _prompt_manager = PromptManager(config_path)
    return _prompt_manager

def resolve_prompt(prompt_ref: str, config_path: Optional[Union[str, Path]] = None) -> str:
    """
    Resolve a prompt reference to its actual content.
    
    Args:
        prompt_ref: Prompt reference string
        config_path: Optional path to a custom config file
        
    Returns:
        Resolved prompt text
    """
    if not prompt_ref or not isinstance(prompt_ref, str):
        return prompt_ref
        
    # Check if it's actually a reference
    if any(prompt_ref.startswith(prefix) for prefix in ["prompt:", "file:", "yaml:"]):
        return get_prompt_manager(config_path).resolve_prompt(prompt_ref)
    
    # Return as-is if not a reference
    return prompt_ref

def format_prompt(self, prompt_ref_or_text: str, values: Dict[str, Any]) -> str:
    """
    Resolve a prompt reference (if needed) and format it with LangChain.
    
    Args:
        prompt_ref_or_text: Prompt reference string or direct prompt text
        values: Values to use in formatting the prompt
        
    Returns:
        Formatted prompt text
    """
    from langchain.prompts import PromptTemplate
    
    # Resolve the prompt if it's a reference
    known_prefixes = ["prompt:", "file:", "yaml:"]
    is_reference = any(prompt_ref_or_text.startswith(prefix) for prefix in known_prefixes)
    
    prompt_text = self.resolve_prompt(prompt_ref_or_text) if is_reference else prompt_ref_or_text
    
    # Use LangChain's PromptTemplate
    try:
        prompt_template = PromptTemplate(
            template=prompt_text,
            input_variables=list(values.keys())
        )
        return prompt_template.format(**values)
    except Exception as e:
        logger.warning(f"Error using LangChain PromptTemplate: {e}, falling back to standard formatting")
        # Fall back to standard formatting
        return prompt_text.format(**values)