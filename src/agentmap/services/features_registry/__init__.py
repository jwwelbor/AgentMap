"""
Features Registry package for AgentMap.

This package provides feature management, provider availability tracking,
and NLP capability checking functionality.

Components:
- FeaturesRegistryService: Main service facade
- ProviderManager: Provider availability and validation
- NLPCapabilityChecker: NLP library detection
"""

from .nlp_capability import NLPCapabilityChecker
from .provider_management import ProviderManager
from .service import FeaturesRegistryService

__all__ = [
    "FeaturesRegistryService",
    "ProviderManager",
    "NLPCapabilityChecker",
]
