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

# Conditional imports for all available connectors
try:
    from agentmap.agents.builtins.storage.blob.local_file_connector import LocalFileConnector
    _local_connector_available = True
except ImportError:
    _local_connector_available = False

try:
    from agentmap.agents.builtins.storage.blob.azure_blob_connector import AzureBlobConnector
    _azure_connector_available = True
except ImportError:
    _azure_connector_available = False

try:
    from agentmap.agents.builtins.storage.blob.aws_s3_connector import AWSS3Connector
    _aws_connector_available = True
except ImportError:
    _aws_connector_available = False

try:
    from agentmap.agents.builtins.storage.blob.gcp_storage_connector import GCPStorageConnector
    _gcp_connector_available = True
except ImportError:
    _gcp_connector_available = False

# Define the list of exports
__all__ = [
    'BlobStorageConnector',
    'get_connector_for_uri',
    'normalize_json_uri'
]

# Add available connectors to exports
if _local_connector_available:
    __all__.append('LocalFileConnector')
if _azure_connector_available:
    __all__.append('AzureBlobConnector')
if _aws_connector_available:
    __all__.append('AWSS3Connector')
if _gcp_connector_available:
    __all__.append('GCPStorageConnector')