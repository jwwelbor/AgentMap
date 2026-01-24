"""
FeaturesRegistryService for AgentMap.

This module re-exports FeaturesRegistryService from the refactored package
for backwards compatibility. All imports from this module will continue to work.

The actual implementation has been refactored into:
- agentmap.services.features_registry.service: Main service class
- agentmap.services.features_registry.provider_management: Provider operations
- agentmap.services.features_registry.nlp_capability: NLP library detection
"""

# Re-export for backwards compatibility
from agentmap.services.features_registry import (
    FeaturesRegistryService,
    NLPCapabilityChecker,
    ProviderManager,
)

__all__ = [
    "FeaturesRegistryService",
    "ProviderManager",
    "NLPCapabilityChecker",
]
