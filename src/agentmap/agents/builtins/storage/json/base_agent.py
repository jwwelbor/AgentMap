"""
JSON document storage agent implementation.

This module provides a simple base class for JSON agents that delegate
operations to JSONStorageService, keeping agents basic and focused.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from agentmap.agents.builtins.storage.base_storage_agent import (
    BaseStorageAgent, log_operation)
from agentmap.logging.tracking.execution_tracker import ExecutionTracker
from agentmap.services.storage import DocumentResult, JSONStorageService
from agentmap.services.storage.protocols import JSONServiceUser
from agentmap.agents.mixins import StorageErrorHandlerMixin

class JSONDocumentAgent(BaseStorageAgent, StorageErrorHandlerMixin, JSONServiceUser):
    """
    Base class for JSON document storage operations.
    
    Delegates JSON operations to JSONStorageService while providing
    a simple interface for JSON reader and writer agents.
    """
    
    def __init__(self, name: str, prompt: str, logger: logging.Logger, execution_tracker: ExecutionTracker, context: Optional[Dict[str, Any]] = None):
        """
        Initialize the JSON document agent.
        
        Args:
            name: Name of the agent node
            prompt: Prompt or instruction
            logger: Logger instance for logging operations
            execution_tracker: ExecutionTracker instance for tracking
            context: Additional context including JSON configuration
        """
        super().__init__(name, prompt, logger, execution_tracker, context)
        
        # JSONServiceUser protocol requirement - will be set via dependency injection
        # or initialized in _initialize_client()
        self.json_service = None
    
    def _initialize_client(self) -> None:
        """Initialize JSONStorageService as the client for JSON operations."""
        self._client = JSONStorageService(self.context)
        # Set json_service for JSONServiceUser protocol compliance
        self.json_service = self._client
    
    def _validate_inputs(self, inputs: Dict[str, Any]) -> None:
        """
        Validate inputs for JSON operations.
        
        Args:
            inputs: Input dictionary
            
        Raises:
            ValueError: If inputs are invalid
        """
        super()._validate_inputs(inputs)
        
        collection = self.get_collection(inputs)
        if not collection:
            raise ValueError("Missing required 'collection' parameter")
        
        # Check if file path has JSON extension (warning only)
        if not collection.lower().endswith('.json'):
            self.log_warning(f"Collection path does not end with .json: {collection}")
    
    def _handle_operation_error(
        self, 
        error: Exception, 
        collection: str, 
        inputs: Dict[str, Any]
    ) -> DocumentResult:
        """
        Handle JSON operation errors.
        
        Args:
            error: The exception that occurred
            collection: Collection identifier
            inputs: Input dictionary
            
        Returns:
            DocumentResult with error information
        """
        if isinstance(error, FileNotFoundError):
            return DocumentResult(
                success=False,
                file_path=collection,
                error=f"JSON file not found: {collection}"
            )
        elif isinstance(error, ValueError) and "Invalid JSON" in str(error):
            return DocumentResult(
                success=False,
                file_path=collection,
                error=f"Invalid JSON in file: {collection}"
            )
        
        return self._handle_storage_error(
            error,
            "JSON operation",
            collection,
            file_path=collection
        )