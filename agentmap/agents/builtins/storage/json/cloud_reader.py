"""
Cloud-specific JSON document reader and writer implementations.

This module provides JSON document agents that work with cloud storage providers
through the standardized connector interface.
"""
from typing import Any, Dict, Optional

from agentmap.agents.builtins.storage.document.base_agent import (
    DocumentReaderAgent, DocumentWriterAgent)
from agentmap.agents.builtins.storage.json.cloud_agent import JSONCloudDocumentAgent
from agentmap.agents.registry import register_agent
from agentmap.logging import get_logger

logger = get_logger(__name__)


class JSONCloudDocumentReaderAgent(JSONCloudDocumentAgent, DocumentReaderAgent):
    """
    JSON document reader agent with cloud storage support.
    
    Reads JSON documents from cloud storage providers including
    Azure Blob Storage, AWS S3, and Google Cloud Storage.
    """
    
    def __init__(self, name: str, prompt: str, context: Optional[Dict[str, Any]] = None):
        """
        Initialize the cloud-enabled JSON document reader agent.
        
        Args:
            name: Name of the agent node
            prompt: Document path or collection name
            context: Additional context including input/output field configuration
        """
        super().__init__(name, prompt, context)
        
    def _log_operation_start(self, collection: str, inputs: Dict[str, Any]) -> None:
        """
        Log the start of a cloud read operation.
        
        Args:
            collection: Collection identifier or URI
            inputs: Input dictionary
        """
        # Extract operation details for better logging
        doc_id = inputs.get("document_id", "")
        path = inputs.get("path", "")
        
        # Normalize URI
        uri = self._resolve_collection_path(collection)
        scheme = uri.split("://")[0] if "://" in uri else "file"
        
        # Create informative log message
        operation = f"reading from {scheme}"
        if doc_id:
            operation += f", document: {doc_id}"
        if path:
            operation += f", path: {path}"
        
        logger.debug(f"[{self.__class__.__name__}] Starting {operation}")


# Register agents
register_agent("cloud_json_reader", JSONCloudDocumentReaderAgent)