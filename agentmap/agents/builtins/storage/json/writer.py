"""
JSON document writer agent implementation.

This module provides an agent for writing data to JSON files,
with support for document creation, updates, merges, and deletions.
The implementation uses composition rather than deep inheritance.
"""
from __future__ import annotations

from typing import Any, Dict, Optional, Union

from agentmap.agents.builtins.storage.document.base_agent import (
    DocumentResult, DocumentWriterAgent, WriteMode, log_operation)
from agentmap.agents.builtins.storage.json.base_agent import JSONDocumentAgent
from agentmap.agents.builtins.storage.json.operations import JSONDocumentOperations
from agentmap.logging import get_logger

logger = get_logger(__name__)


class JSONDocumentWriterAgent(DocumentWriterAgent, JSONDocumentAgent):
    """
    Agent for writing data to JSON documents.
    
    Provides functionality for writing to JSON files, including
    document creation, updates, merges, and deletions.
    Uses composition with JSONDocumentOperations for the implementation.
    """
    
    def __init__(self, name: str, prompt: str, context: Optional[Dict[str, Any]] = None):
        """
        Initialize the JSON document writer agent.
        
        Args:
            name: Name of the agent node
            prompt: Prompt or instruction
            context: Additional context including input/output field configuration
        """
        super().__init__(name, prompt, context)
        # Create operations helper
        self.operations = JSONDocumentOperations()
    
    @log_operation
    def _write_document(
        self, 
        collection: str, 
        data: Any, 
        document_id: Optional[str] = None,
        mode: Union[WriteMode, str] = WriteMode.WRITE, 
        path: Optional[str] = None
    ) -> DocumentResult:
        """
        Write a document to a JSON file.
        
        Args:
            collection: Path to the JSON file
            data: Data to write
            document_id: Optional document ID
            mode: Write mode (write, update, merge, delete)
            path: Optional path within document
            
        Returns:
            Result of the write operation
        """
        # Convert string mode to enum if needed
        if isinstance(mode, str):
            try:
                mode = WriteMode.from_string(mode)
            except ValueError as e:
                return DocumentResult(
                    success=False,
                    error=str(e)
                )
        
        try:
            # Dispatch to the appropriate operation based on mode
            if mode == WriteMode.WRITE:
                return self.operations.create_document(collection, data, document_id)
            elif mode == WriteMode.UPDATE:
                return self.operations.update_document(collection, data, document_id, path)
            elif mode == WriteMode.MERGE:
                return self.operations.merge_document(collection, data, document_id, path)
            elif mode == WriteMode.DELETE:
                return self.operations.delete_document(collection, data, document_id, path)
            else:
                return DocumentResult(
                    success=False,
                    error=f"Unsupported write mode: {mode}"
                )
        except Exception as e:
            # Handle any unexpected errors
            logger.error(f"Error in {self.__class__.__name__}: {str(e)}")
            return DocumentResult(
                success=False,
                mode=str(mode),
                file_path=collection,
                document_id=document_id,
                path=path,
                error=str(e)
            )
