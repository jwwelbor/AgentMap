"""
File document reader agent implementation.

This module provides an agent for reading various document types using LangChain loaders,
focusing on text documents, PDFs, Markdown, HTML, and DOCX.
"""
from __future__ import annotations

import os
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from agentmap.agents.builtins.storage.base_storage_agent import (
    BaseStorageAgent, log_operation)
from agentmap.logging.tracking.execution_tracker import ExecutionTracker
from agentmap.services.storage import DocumentResult, FileStorageService
from agentmap.services.storage.protocols import FileServiceUser
from agentmap.agents.mixins import ReaderOperationsMixin, StorageErrorHandlerMixin


class FileReaderAgent(BaseStorageAgent, ReaderOperationsMixin, StorageErrorHandlerMixin, FileServiceUser):
    """
    Enhanced document reader agent using LangChain document loaders.
    
    Reads various document formats including text, PDF, Markdown, HTML, and DOCX,
    with options for chunking and filtering.
    """
    
    def __init__(self, name: str, prompt: str, logger: logging.Logger, execution_tracker: ExecutionTracker, context: Optional[Dict[str, Any]] = None):
        """
        Initialize the file reader agent.
        
        Args:
            name: Name of the agent node
            prompt: Prompt or instruction
            logger: Logger instance for logging operations
            execution_tracker: ExecutionTracker instance for tracking
            context: Additional context including chunking and format configuration
        """
        super().__init__(name, prompt, logger, execution_tracker, context)
        
        # Extract document processing configuration from context
        context = context or {}
        self.chunk_size = int(context.get("chunk_size", 1000))
        self.chunk_overlap = int(context.get("chunk_overlap", 200))
        self.should_split = context.get("should_split", False)
        self.include_metadata = context.get("include_metadata", True)
        
        # FileServiceUser protocol requirement - will be set via dependency injection
        # or initialized in _initialize_client()
        self.file_service = None
        
        # For testing - allows a test to inject a mock loader
        self._test_loader = None
    
    def _initialize_client(self) -> None:
        """Initialize FileStorageService as the client for file operations."""
        self._client = FileStorageService(self.context)
        # Set file_service for FileServiceUser protocol compliance
        self.file_service = self._client
    
    def _log_operation_start(self, collection: str, inputs: Dict[str, Any]) -> None:
        """
        Log the start of a file read operation.
        
        Args:
            collection: File path
            inputs: Input dictionary
        """
        self.log_debug(f"[{self.__class__.__name__}] Starting read operation on file: {collection}")
    
    def _validate_inputs(self, inputs: Dict[str, Any]) -> None:
        """
        Validate inputs for file read operations.
        
        Args:
            inputs: Input dictionary
            
        Raises:
            ValueError: If inputs are invalid
        """
        super()._validate_inputs(inputs)
        self._validate_reader_inputs(inputs)
        
        # Add file-specific validation
        file_path = self.get_collection(inputs)
        if not os.path.exists(file_path) and not self._test_loader:
            raise FileNotFoundError(f"File not found: {file_path}")
    
    def _execute_operation(self, collection: str, inputs: Dict[str, Any]) -> Any:
        """
        Execute read operation for file using FileStorageService.
        """
        document_id = inputs.get("document_id")
        query = inputs.get("query")
        path = inputs.get("path")
        output_format = inputs.get("format", "default")
        # Call the FileStorageService read method
        result = self.file_service.read(
            collection=collection,
            document_id=document_id,
            query=query,
            path=path,
            format=output_format
        )
        return result
    
    def _handle_operation_error(self, error: Exception, collection: str, inputs: Dict[str, Any]) -> DocumentResult:
        """
        Handle file read operation errors.
        
        Args:
            error: The exception that occurred
            collection: File path
            inputs: Input dictionary
            
        Returns:
            DocumentResult with error information
        """
        if isinstance(error, FileNotFoundError):
            return DocumentResult(
                success=False,
                file_path=collection,
                error=f"File not found: {collection}"
            )
        
        return self._handle_storage_error(
            error,
            "file read",
            collection,
            file_path=collection
        )