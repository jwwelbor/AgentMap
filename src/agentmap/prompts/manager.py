"""
Prompt manager for AgentMap.

This module provides functionality for loading and resolving prompt references
from various sources, including files, YAML configurations, and a registry.
"""
import importlib.resources
import importlib.util
import sys
import os
import yaml
from pathlib import Path
from typing import Dict, Optional, Union, Any

from agentmap.logging import get_logger
from agentmap.config import (
    get_prompts_config,
    get_prompts_directory,
    get_prompt_registry_path
)

logger = get_logger(__name__)

from dependency_injector.wiring import inject, Provide
from agentmap.di.containers import ApplicationContainer
from agentmap.config.configuration import Configuration


class PromptManager:
    """
    Manager for loading and resolving prompt references.
    
    This class provides a centralized way to manage prompts from
    different sources, including a registry, files, and YAML configurations.
    """
    @inject
    def __init__(
            self,
            configuration: Configuration = Provide[ApplicationContainer.config.configuration]
    ):
        prompts_config = configuration.get_section("prompts")
        self.config = prompts_config
        self.prompts_dir = Path(prompts_config.get("directory", "prompts"))
        self.registry_path = Path(prompts_config.get("registry_file", "prompts/registry.yaml"))
        self.enable_cache = prompts_config.get("enable_cache", True)
        
        # Ensure prompts directory exists
        self.prompts_dir.mkdir(parents=True, exist_ok=True)
        
        logger.debug(f"Initialized PromptManager with directory: {self.prompts_dir}")
        logger.debug(f"Registry path: {self.registry_path}")
        logger.debug(f"Cache enabled: {self.enable_cache}")
    
    def _load_registry(self) -> Dict[str, str]:
        """
        Load the prompt registry with fallback to system package resource.
        
        Returns:
            Dictionary of registered prompts
        """
        registry = {}
        
        # Try configured registry path first
        if self.registry_path.exists():
            try:
                with open(self.registry_path, 'r') as f:
                    registry = yaml.safe_load(f) or {}
                    logger.debug(f"Loaded {len(registry)} prompts from registry at {self.registry_path}")
                    return registry
            except Exception as e:
                logger.error(f"Error loading prompt registry from {self.registry_path}: {e}")
        
        # Fall back to system registry
        try:
            system_registry = self._find_resource("registry.yaml")
            if system_registry:
                with open(system_registry, 'r') as f:
                    registry = yaml.safe_load(f) or {}
                    logger.debug(f"Loaded {len(registry)} prompts from system registry")
                    return registry
        except Exception as e:
            logger.error(f"Error loading system registry: {e}")
        
        return registry
    
    def _find_resource(self, resource_path: str) -> Optional[Path]:
        """
        Find a resource file using a unified resolution strategy.
        
        Args:
            resource_path: Path to the resource file
            
        Returns:
            Path object if found, None otherwise
        """
        # 1. If absolute path and exists, return it
        path = Path(resource_path)
        if path.is_absolute() and path.exists():
            return path
        
        # 2. Try relative to prompts directory
        if not path.is_absolute():
            local_path = self.prompts_dir / path
            if local_path.exists():
                return local_path
        
        # 3. Try as package resource in system directory
        package_path = self._get_package_resource(resource_path)
        if package_path:
            return package_path
            
        # Not found
        return None
    
    def _get_package_resource(self, resource_path: str) -> Optional[Path]:
        """
        Get a resource from the system package.
        
        Args:
            resource_path: Path relative to system package
        
        Returns:
            Path object to the resource or None if not found
        """
        return self._try_get_resource(resource_path)
    
    def _try_get_resource(self, resource_path: str) -> Optional[Path]:
        """
        Try to locate a specific resource path in the system package.
        
        Args:
            resource_path: Path relative to system package
            
        Returns:
            Path object if found, None otherwise
        """
        # Split path into parts
        parts = resource_path.split('/')
        
        # Base package is 'agentmap.prompts.system'
        package = 'agentmap.prompts.system'
        
        # If there are subdirectories, adjust package
        if len(parts) > 1:
            subdir = '.'.join(parts[:-1])
            package = f"{package}.{subdir}"
            
        resource_name = parts[-1]
        
        try:
            # Python 3.9+ API
            if sys.version_info >= (3, 9):
                try:
                    with importlib.resources.files(package).joinpath(resource_name) as f:
                        if f.exists():
                            return f
                except (ImportError, AttributeError, ValueError):
                    pass
            
            # Python 3.7+ API
            if sys.version_info >= (3, 7):
                try:
                    return importlib.resources.path(package, resource_name)
                except (ImportError, FileNotFoundError):
                    pass
            
            # Fallback to direct path construction
            package_spec = importlib.util.find_spec(package)
            if package_spec and package_spec.origin:
                package_dir = os.path.dirname(package_spec.origin)
                full_path = Path(package_dir) / resource_name
                if full_path.exists():
                    return full_path
        except Exception as e:
            logger.debug(f"Error locating package resource '{resource_path}': {e}")
        
        return None
    
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
        Resolve a prompt from a file with package resource fallback.
        
        Args:
            file_path: Path to the prompt file (relative or absolute)
            
        Returns:
            File contents or error message
        """
        path = self._find_resource(file_path)
        
        if not path:
            logger.warning(f"Prompt file not found: {file_path}")
            return f"[Prompt file not found: {file_path}]"
        
        # Read the file content
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
        path = self._find_resource(file_path)
        
        if not path:
            logger.warning(f"YAML prompt file not found: {yaml_ref}")
            return f"[YAML prompt file not found: {file_path}]"
        
        # Parse YAML and extract value
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

    def format_prompt(self, prompt_ref_or_text: str, values: Dict[str, Any]) -> str:
        """
        Resolve a prompt reference (if needed) and format it with values.
        
        Args:
            prompt_ref_or_text: Prompt reference string or direct prompt text
            values: Values to use in formatting the prompt
            
        Returns:
            Formatted prompt text
        """
        # Resolve the prompt if it's a reference
        known_prefixes = ["prompt:", "file:", "yaml:"]
        is_reference = any(prompt_ref_or_text.startswith(prefix) for prefix in known_prefixes)
        
        prompt_text = self.resolve_prompt(prompt_ref_or_text) if is_reference else prompt_ref_or_text
        
        # Try LangChain formatting first, then fallback to standard formatting
        try:
            from langchain.prompts import PromptTemplate
            prompt_template = PromptTemplate(
                template=prompt_text,
                input_variables=list(values.keys())
            )
            return prompt_template.format(**values)
        except Exception as e:
            logger.warning(f"Error using LangChain PromptTemplate: {e}, falling back to standard formatting")
            # Fall back to standard formatting
            try:
                return prompt_text.format(**values)
            except Exception as e2:
                logger.error(f"Error formatting prompt with standard formatting: {e2}")
                
                # Last resort: manual string replacement
                result = prompt_text
                for key, value in values.items():
                    placeholder = "{" + key + "}"
                    if placeholder in result:
                        result = result.replace(placeholder, str(value))
                
                return result


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

def format_prompt(prompt_ref_or_text: str, values: Dict[str, Any], 
                  config_path: Optional[Union[str, Path]] = None) -> str:
    """
    Resolve a prompt reference (if needed) and format it.
    
    Args:
        prompt_ref_or_text: Prompt reference string or direct prompt text
        values: Values to use in formatting the prompt
        config_path: Optional path to a custom config file
        
    Returns:
        Formatted prompt text
    """
    return get_prompt_manager(config_path).format_prompt(prompt_ref_or_text, values)

def get_formatted_prompt(primary_prompt: Optional[str], 
                         template_file: str, 
                         default_template: str,
                         values: Dict[str, Any],
                         context_name: str = "Agent") -> str:
    """
    Comprehensive prompt resolution with multi-level fallbacks.
    
    This function tries multiple approaches to get a formatted prompt:
    1. First tries the primary_prompt (if provided)
    2. Falls back to the template_file
    3. Falls back to the default_template
    
    Args:
        primary_prompt: First choice prompt (can be None)
        template_file: File reference to use as fallback (e.g., "file:path/to/template.txt")
        default_template: Hardcoded template to use as final fallback
        values: Dictionary of values to use in formatting
        context_name: Name to use in logging (e.g., agent type)
        
    Returns:
        Formatted prompt text
    """
    prompt_manager = get_prompt_manager()
    logger.debug(f"[{context_name}] Getting formatted prompt")
    
    # Try each option in order, moving to next on failure
    for prompt_option, desc in [
        (primary_prompt, "primary prompt"),
        (template_file, "file template"),
        (default_template, "default template")
    ]:
        if not prompt_option:
            continue
            
        try:
            resolved_text = resolve_prompt(prompt_option)
            logger.debug(f"[{context_name}] Using {desc}")
            return prompt_manager.format_prompt(resolved_text, values)
        except Exception as e:
            logger.warning(f"[{context_name}] Failed to use {desc}: {str(e)}")
    
    # If all else fails, return a basic concatenation of values
    logger.warning(f"[{context_name}] All prompt formatting methods failed")
    return f"Error: Unable to format prompt properly.\nValues: {values}"