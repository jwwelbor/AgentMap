"""
Base CSV storage agent implementation.

This module provides common functionality for CSV agents that delegate
operations to CSVStorageService, keeping agents simple and focused.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from agentmap.agents.builtins.storage.base_storage_agent import (
    BaseStorageAgent, log_operation)
from agentmap.services.storage import DocumentResult, CSVStorageService
from agentmap.services.storage.protocols import CSVServiceUser
from agentmap.agents.mixins import StorageErrorHandlerMixin


class CSVAgent(BaseStorageAgent, StorageErrorHandlerMixin, CSVServiceUser):
    """
    Base class for CSV storage agents with shared functionality.
    
    Delegates CSV operations to CSVStorageService while providing
    a simple interface for CSV reader and writer agents.
    """
    
    def __init__(self, name: str, prompt: str, context: Optional[Dict[str, Any]] = None):
        """
        Initialize the CSV agent.
        
        Args:
            name: Name of the agent node
            prompt: Prompt or instruction
            context: Additional context including CSV configuration
        """
        super().__init__(name, prompt, context)
        
        # CSVServiceUser protocol requirement - will be set via dependency injection
        # or initialized in _initialize_client()
        self.csv_service = None
    
    def _initialize_client(self) -> None:
        """Initialize CSVStorageService as the client for CSV operations."""
        self._client = CSVStorageService(self.context)
        # Set csv_service for CSVServiceUser protocol compliance
        self.csv_service = self._client
    
    def _validate_inputs(self, inputs: Dict[str, Any]) -> None:
        """
        Validate inputs for CSV operations.
        
        Args:
            inputs: Input dictionary
            
        Raises:
            ValueError: If inputs are invalid
        """
        super()._validate_inputs(inputs)
        
        collection = self.get_collection(inputs)
        if not collection:
            raise ValueError("Missing required 'collection' parameter")
        
        # Check if file path has CSV extension (warning only)
        if not collection.lower().endswith('.csv'):
            self.log_warning(f"Collection path does not end with .csv: {collection}")
    
    def _handle_operation_error(
        self, 
        error: Exception, 
        collection: str, 
        inputs: Dict[str, Any]
    ) -> DocumentResult:
        """
        Handle CSV operation errors.
        
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
                error=f"CSV file not found: {collection}"
            )
        
        return self._handle_storage_error(
            error,
            "CSV operation",
            collection,
            file_path=collection
        )