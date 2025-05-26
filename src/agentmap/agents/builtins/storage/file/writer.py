"""
File document writer agent implementation.

This module provides an agent for writing to various document types,
focusing on text documents, Markdown, and simple text-based formats.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from agentmap.agents.builtins.storage.base_storage_agent import (
    BaseStorageAgent, log_operation
)
from agentmap.services.storage import DocumentResult, WriteMode, FileStorageService
from agentmap.services.storage.protocols import FileServiceUser
from agentmap.agents.mixins import WriterOperationsMixin, StorageErrorHandlerMixin
from agentmap.logging import get_logger
from agentmap.state.adapter import StateAdapter

logger = get_logger(__name__)


class FileWriterAgent(BaseStorageAgent, WriterOperationsMixin, StorageErrorHandlerMixin, FileServiceUser):
    """
    Enhanced document writer agent for text-based file formats.
    
    Writes to text, Markdown, and other text-based formats,
    with support for different write modes including append and update.
    """
    
    def __init__(self, name: str, prompt: str, context: Optional[Dict[str, Any]] = None):
        """
        Initialize the file writer agent.
        
        Args:
            name: Name of the agent node
            prompt: File path or prompt with path
            context: Additional configuration including encoding and newline settings
        """
        super().__init__(name, prompt, context)
        
        # Extract file writing configuration from context
        context = context or {}
        self.encoding = context.get("encoding", "utf-8")
        self.newline = context.get("newline", None)  # System default
        self._current_state = None  # Store current state for state key lookups
        
        # FileServiceUser protocol requirement - will be set via dependency injection
        # or initialized in _initialize_client()
        self.file_service = None
    
    def run(self, state: Any) -> Any:
        """
        Override run method to store state for later use in _prepare_content.
        
        Args:
            state: Current state object
            
        Returns:
            Updated state
        """
        # Store the state for use in _prepare_content
        self._current_state = state
        try:
            # Call parent run method
            return super().run(state)
        finally:
            # Clear state reference to avoid memory leaks
            self._current_state = None
    
    def _initialize_client(self) -> None:
        """Initialize FileStorageService as the client for file operations."""
        self._client = FileStorageService(self.context)
        # Set file_service for FileServiceUser protocol compliance
        self.file_service = self._client
    
    def _log_operation_start(self, collection: str, inputs: Dict[str, Any]) -> None:
        """
        Log the start of a file write operation.
        
        Args:
            collection: File path
            inputs: Input dictionary
        """
        mode = inputs.get("mode", "write")
        self.log_debug(f"[{self.__class__.__name__}] Starting write operation (mode: {mode}) on file: {collection}")
    
    def _validate_inputs(self, inputs: Dict[str, Any]) -> None:
        """
        Validate inputs for file write operations.
        
        Args:
            inputs: Input dictionary
            
        Raises:
            ValueError: If inputs are invalid
        """
        super()._validate_inputs(inputs)
        self._validate_writer_inputs(inputs)
        
        # Add file-specific validation if needed
        file_path = self.get_collection(inputs)
        mode = inputs.get("mode", "write").lower()
        
        # Check if we have data for non-delete operations
        if mode != "delete" and "data" not in inputs:
            raise ValueError("Missing required 'data' parameter for non-delete operations")
    
    def _execute_operation(self, collection: str, inputs: Dict[str, Any]) -> DocumentResult:
        """
        Execute write operation for file using FileStorageService.
        """
        data = inputs.get("data")
        mode_str = inputs.get("mode", "write").lower()
        try:
            mode = WriteMode.from_string(mode_str)
        except ValueError as e:
            return DocumentResult(success=False, file_path=collection, error=str(e))
        document_id = inputs.get("document_id")
        path = inputs.get("path")
        # Call the FileStorageService write method
        result = self.file_service.write(
            collection=collection,
            data=data,
            document_id=document_id,
            mode=mode,
            path=path
        )
        return result
    
    def _handle_operation_error(self, error: Exception, collection: str, inputs: Dict[str, Any]) -> DocumentResult:
        """
        Handle file write operation errors.
        
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
        elif isinstance(error, PermissionError):
            return DocumentResult(
                success=False,
                file_path=collection,
                error=f"Permission denied for file: {collection}"
            )
        
        return self._handle_storage_error(
            error,
            "file write",
            collection,
            file_path=collection,
            mode=inputs.get("mode", "write")
        )
    
    def _write_document(self, *args, **kwargs):
        raise NotImplementedError("Direct document writing is now handled by FileStorageService.")
    
    def _prepare_content(self, *args, **kwargs):
        raise NotImplementedError("Content preparation is now handled by FileStorageService.")
    
    def _is_text_file(self, *args, **kwargs):
        raise NotImplementedError("File type checking is now handled by FileStorageService.")
    
    def _write_text_file(self, *args, **kwargs):
        raise NotImplementedError("Text file writing is now handled by FileStorageService.")