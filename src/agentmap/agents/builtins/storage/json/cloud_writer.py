"""
Cloud-specific JSON document reader and writer implementations.

This module provides JSON document agents that work with cloud storage providers
through the standardized connector interface.
"""
from typing import Any, Dict, Optional

from agentmap.agents.builtins.storage.document.writer import DocumentWriterAgent
from agentmap.agents.builtins.storage.document.reader import DocumentReaderAgent
from agentmap.agents.builtins.storage.json.cloud_agent import JSONCloudDocumentAgent
from agentmap.agents.registry import register_agent


class JSONCloudDocumentWriterAgent(JSONCloudDocumentAgent, DocumentWriterAgent):
    """
    JSON document writer agent with cloud storage support.
    
    Writes JSON documents to cloud storage providers including
    Azure Blob Storage, AWS S3, and Google Cloud Storage.
    """
    
    def __init__(self, name: str, prompt: str, context: Optional[Dict[str, Any]] = None):
        """
        Initialize the cloud-enabled JSON document writer agent.
        
        Args:
            name: Name of the agent node
            prompt: Document path or collection name
            context: Additional context including input/output field configuration
        """
        super().__init__(name, prompt, context)
        
    def _log_operation_start(self, collection: str, inputs: Dict[str, Any]) -> None:
        """
        Log the start of a cloud write operation.
        
        Args:
            collection: Collection identifier or URI
            inputs: Input dictionary
        """
        # Extract operation details for better logging
        mode = inputs.get("mode", "write")
        doc_id = inputs.get("document_id", "")
        path = inputs.get("path", "")
        
        # Normalize URI
        uri = self._resolve_collection_path(collection)
        scheme = uri.split("://")[0] if "://" in uri else "file"
        
        # Create informative log message
        operation = f"{mode} to {scheme}"
        if doc_id:
            operation += f", document: {doc_id}"
        if path:
            operation += f", path: {path}"
        
        self.log_debug(f"[{self.__class__.__name__}] Starting {operation}")


# Register agents

register_agent("cloud_json_writer", JSONCloudDocumentWriterAgent)