# agentmap/features_registry.py
"""
Feature registry for AgentMap.

This module provides a centralized singleton registry for feature flags
to ensure consistent state across all imports.
"""
import logging
from typing import Dict, List, Set

logger = logging.getLogger(__name__)

class FeatureRegistry:
    """
    Singleton registry for feature flags and plugin availability.
    
    This class ensures consistent state across all imports by maintaining
    a single instance that tracks feature availability.
    """
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(FeatureRegistry, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance
    
    def _initialize(self):
        """Initialize registry state."""
        # Feature flags
        self._features_enabled = set()
        
        # Provider availability
        self._providers_available = {
            "llm": {
                "openai": False,
                "anthropic": False,
                "google": False,
            },
            "storage": {
                "csv": True,  # Always available as core
                "json": True,  # Always available as core
                "file": True,  # Always available as core
                "firebase": False,
                "vector": False,
                "blob": False
            }
        }
        
        # Missing dependencies tracking
        self._missing_dependencies = {}
        
        logger.debug("FeatureRegistry initialized")
    
    def enable_feature(self, feature_name: str):
        """
        Enable a specific feature.
        
        Args:
            feature_name: Name of the feature to enable
        """
        self._features_enabled.add(feature_name.lower())
        logger.debug(f"Feature enabled: {feature_name}")
    
    def disable_feature(self, feature_name: str):
        """
        Disable a specific feature.
        
        Args:
            feature_name: Name of the feature to disable
        """
        feature_name = feature_name.lower()
        if feature_name in self._features_enabled:
            self._features_enabled.remove(feature_name)
            logger.debug(f"Feature disabled: {feature_name}")
    
    def is_feature_enabled(self, feature_name: str) -> bool:
        """
        Check if a feature is enabled.
        
        Args:
            feature_name: Name of the feature to check
            
        Returns:
            True if feature is enabled, False otherwise
        """
        return feature_name.lower() in self._features_enabled
    
    def set_provider_available(self, category: str, provider: str, available: bool = True):
        """
        Set availability for a specific provider.
        
        Args:
            category: Provider category ('llm', 'storage')
            provider: Provider name
            available: Availability status
        """
        category = category.lower()
        provider = provider.lower()
        
        if category in self._providers_available:
            if provider in self._providers_available[category]:
                self._providers_available[category][provider] = available
                logger.debug(f"Provider '{provider}' in category '{category}' set to: {available}")
            else:
                logger.warning(f"Unknown provider '{provider}' in category '{category}'")
        else:
            logger.warning(f"Unknown category: {category}")
    
    def is_provider_available(self, category: str, provider: str) -> bool:
        """
        Check if a specific provider is available.
        
        Args:
            category: Provider category ('llm', 'storage')
            provider: Provider name
            
        Returns:
            True if provider is available, False otherwise
        """
        category = category.lower()
        provider = provider.lower()
        
        # Handle aliases for LLM providers
        if category == "llm":
            if provider == "gpt":
                provider = "openai"
            elif provider == "claude":
                provider = "anthropic"
            elif provider == "gemini":
                provider = "google"
        
        return self._providers_available.get(category, {}).get(provider, False)
    
    def get_available_providers(self, category: str) -> List[str]:
        """
        Get a list of available providers in a category.
        
        Args:
            category: Provider category ('llm', 'storage')
            
        Returns:
            List of available provider names
        """
        category = category.lower()
        if category not in self._providers_available:
            return []
            
        return [
            provider for provider, available 
            in self._providers_available[category].items() 
            if available
        ]
    
    def record_missing_dependencies(self, category: str, missing: List[str]):
        """
        Record missing dependencies for a category.
        
        Args:
            category: Category name
            missing: List of missing dependencies
        """
        self._missing_dependencies[category] = missing
        
    def get_missing_dependencies(self, category: str = None) -> Dict[str, List[str]]:
        """
        Get missing dependencies.
        
        Args:
            category: Optional category to filter
            
        Returns:
            Dictionary of missing dependencies by category
        """
        if category:
            return {category: self._missing_dependencies.get(category, [])}
        return self._missing_dependencies.copy()

# Create global instance
features = FeatureRegistry()