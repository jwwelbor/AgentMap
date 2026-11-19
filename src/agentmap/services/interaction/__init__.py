"""
Interaction handling module for AgentMap.

This module provides infrastructure for managing human-in-the-loop interactions
by organizing interaction handling into focused, maintainable components.
"""

# Load the optional compatibility export dynamically because its implementation
# is supplied by the host package rather than this source tree.
from importlib import import_module

from agentmap.services.interaction.interaction_storage import InteractionStorage
from agentmap.services.interaction.storage_helpers import StorageHelpers

ThreadMetadataManager = getattr(
    import_module("agentmap.services.interaction.thread_metadata_manager"),
    "ThreadMetadataManager",
)

__all__ = [
    "InteractionStorage",
    "StorageHelpers",
    "ThreadMetadataManager",
]
