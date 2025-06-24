"""
Blob storage module for AgentMap.

This module provides integration with cloud blob storage services
for JSON agents, including Azure Blob Storage, AWS S3, and Google Cloud Storage.
"""

from agentmap.agents.builtins.storage.blob.base_connector import (
    BlobStorageConnector,
    get_connector_for_uri,
    normalize_json_uri,
)

# Conditional imports for all available connectors
try:
    pass

    _local_connector_available = True
except ImportError:
    _local_connector_available = False

try:
    pass

    _azure_connector_available = True
except ImportError:
    _azure_connector_available = False

try:
    pass

    _aws_connector_available = True
except ImportError:
    _aws_connector_available = False

try:
    pass

    _gcp_connector_available = True
except ImportError:
    _gcp_connector_available = False

# Define the list of exports
__all__ = ["BlobStorageConnector", "get_connector_for_uri", "normalize_json_uri"]

# Add available connectors to exports
if _local_connector_available:
    __all__.append("LocalFileConnector")
if _azure_connector_available:
    __all__.append("AzureBlobConnector")
if _aws_connector_available:
    __all__.append("AWSS3Connector")
if _gcp_connector_available:
    __all__.append("GCPStorageConnector")
