"""
Blob storage module for AgentMap.

This module provides integration with cloud blob storage services
for JSON agents, including Azure Blob Storage, AWS S3, and Google Cloud Storage.
"""

from agentmap.agents.builtins.storage.blob.base_connector import (
    BlobStorageConnector,
    get_connector_for_uri,
    normalize_json_uri
)

# We use lazy imports for provider-specific connectors to avoid
# requiring all cloud SDKs as dependencies.
__all__ = [
    'BlobStorageConnector',
    'get_connector_for_uri',
    'normalize_json_uri'
]