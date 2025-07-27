"""
Blob storage module for AgentMap.

This module provides integration with cloud blob storage services
for blob storage agents, including Azure Blob Storage, AWS S3, and Google Cloud Storage.
Provides modern agents following BaseAgent contract with dependency injection.
"""

from agentmap.agents.builtins.storage.blob.blob_reader_agent import BlobReaderAgent
from agentmap.agents.builtins.storage.blob.blob_writer_agent import BlobWriterAgent

# Define the list of exports - only agents now that connectors moved to services
__all__ = [
    "BlobReaderAgent",
    "BlobWriterAgent",
]
