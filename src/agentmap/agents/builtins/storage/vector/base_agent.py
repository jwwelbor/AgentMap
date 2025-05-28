"""
Base vector storage agent implementation.

This module provides a simple base class for vector agents that delegate
operations to VectorStorageService, keeping agents basic and focused.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from agentmap.agents.builtins.storage.base_storage_agent import (
    BaseStorageAgent, log_operation)
from agentmap.services.storage import VectorStorageService
from agentmap.services.storage.protocols import VectorServiceUser, StorageServiceUser
from agentmap.agents.mixins import StorageErrorHandlerMixin


class VectorAgent(BaseStorageAgent, StorageErrorHandlerMixin, VectorServiceUser, StorageServiceUser):
    """
    Base class for vector storage operations.
    
    Delegates vector operations to VectorStorageService while providing
    a simple interface for vector reader and writer agents.
    """
    
    def __init__(self, name: str, prompt: str, context: Optional[Dict[str, Any]] = None):
        """
        Initialize the vector agent.
        
        Args:
            name: Name of the agent node
            prompt: Prompt or instruction
            context: Additional context including vector configuration
        """
        super().__init__(name, prompt, context or {})
        
        # Extract vector-specific configuration
        context = context or {}
        self.k = int(context.get("k", 4))
        self.metadata_keys = context.get("metadata_keys", None)
        self.input_fields = context.get("input_fields", ["query"])
        self.output_field = context.get("output_field", "result")
        
        # Protocol requirements
        self.vector_service = None     # VectorServiceUser protocol
        self.storage_service = None    # StorageServiceUser protocol
    
    def _initialize_client(self) -> None:
        """Initialize VectorStorageService as the client for vector operations."""
        self._client = VectorStorageService(self.context)
        # Set both protocol attributes to the same service instance
        self.vector_service = self._client     # VectorServiceUser protocol
        self.storage_service = self._client    # StorageServiceUser protocol
    
    def _validate_inputs(self, inputs: Dict[str, Any]) -> None:
        """
        Validate inputs for vector operations.
        
        Args:
            inputs: Input dictionary
            
        Raises:
            ValueError: If inputs are invalid
        """
        super()._validate_inputs(inputs)
        
        # Check for required input field
        input_field = self.input_fields[0]
        if input_field not in inputs:
            raise ValueError(f"Missing required input field: {input_field}")
    
    def _handle_operation_error(
        self, 
        error: Exception, 
        collection: str, 
        inputs: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Handle vector operation errors.
        
        Args:
            error: The exception that occurred
            collection: Collection identifier
            inputs: Input dictionary
            
        Returns:
            Error result dictionary
        """
        return self._handle_storage_error(
            error,
            "vector operation",
            collection
        )
