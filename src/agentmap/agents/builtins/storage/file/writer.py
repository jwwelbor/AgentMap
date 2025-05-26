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
from agentmap.services.storage import DocumentResult, WriteMode
from agentmap.agents.mixins import WriterOperationsMixin, StorageErrorHandlerMixin
from agentmap.logging import get_logger
from agentmap.state.adapter import StateAdapter

logger = get_logger(__name__)


class FileWriterAgent(BaseStorageAgent, WriterOperationsMixin, StorageErrorHandlerMixin):
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
        """No client needed for filesystem operations."""
        pass
    
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
        Execute write operation for file.
        
        Args:
            collection: File path
            inputs: Input dictionary
            
        Returns:
            Write operation result
        """
        # Get required data
        data = inputs.get("data")
        mode_str = inputs.get("mode", "write").lower()
        
        # Convert string mode to enum
        try:
            mode = WriteMode.from_string(mode_str)
        except ValueError as e:
            return DocumentResult(
                success=False,
                file_path=collection,
                error=str(e)
            )
        
        # Extract optional parameters
        document_id = inputs.get("document_id")
        path = inputs.get("path")
        
        # Log the write operation
        self._log_write_operation(collection, mode, document_id, path)
        
        # Perform the write operation
        return self._write_document(collection, data, document_id, mode, path)
    
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
    
    def _write_document(
        self, 
        file_path: str, 
        data: Any, 
        document_id: Optional[str] = None,
        mode: WriteMode = WriteMode.WRITE, 
        path: Optional[str] = None
    ) -> DocumentResult:
        """
        Write a document or update an existing one.
        
        Args:
            file_path: Path to the file
            data: Content to write
            document_id: Optional document section ID
            mode: Write mode
            path: Optional path within document
            
        Returns:
            Operation result
        """
        # Validate and normalize file path
        file_path = os.path.expanduser(file_path)
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
        
        # Check if file exists (for later reporting if we created a new file)
        file_exists = os.path.exists(file_path)
        
        # Prepare content
        content = self._prepare_content(data)
        
        # Handle different file types
        if self._is_text_file(file_path):
            return self._write_text_file(file_path, content, mode, file_exists)
        else:
            return DocumentResult(
                success=False,
                file_path=file_path,
                mode=str(mode),
                error=f"Unsupported file type: {file_path}"
            )
    
    def _prepare_content(self, data: Any) -> str:
        """
        Convert data to writable text content.
        
        Args:
            data: Input data in various formats, or string key to look up in state
            
        Returns:
            String content for writing
        """
        # If data is a string and we have access to state, try to use it as a state key
        if isinstance(data, str) and self._current_state is not None:
            # Try to get the value from state using the string as a key
            state_value = StateAdapter.get_value(self._current_state, data, None)
            if state_value is not None:
                # Recursively process the state value
                return self._prepare_content(state_value)
            else:
                # If key not found in state, treat the string as literal content
                self.log_debug(f"Key '{data}' not found in state, treating as literal content")
                return str(data)
        
        if hasattr(data, 'page_content'):
            # Single LangChain document
            return data.page_content
        elif isinstance(data, list) and data and hasattr(data[0], 'page_content'):
            # List of LangChain documents
            return "\n\n".join(doc.page_content for doc in data)
        elif isinstance(data, dict):
            # Try to extract content from dictionary
            if "content" in data:
                return str(data["content"])
            else:
                # Convert whole dict to string
                return str(data)
        else:
            # Convert to string directly
            return str(data)
    
    def _is_text_file(self, file_path: str) -> bool:
        """
        Check if the file is a supported text file.
        
        Args:
            file_path: Path to file
            
        Returns:
            True if supported, False otherwise
        """
        ext = file_path.lower()
        text_extensions = ['.txt', '.md', '.html', '.htm', '.csv', '.log', '.py', '.js', '.json', '.yaml', '.yml']
        return any(ext.endswith(e) for e in text_extensions)
    
    def _write_text_file(
        self, 
        file_path: str, 
        content: str, 
        mode: WriteMode,
        file_exists: bool
    ) -> DocumentResult:
        """
        Write content to a text file.
        
        Args:
            file_path: Path to file
            content: Content to write
            mode: Write mode
            file_exists: Whether file existed before operation
            
        Returns:
            Operation result
        """
        # Handle different write modes
        if mode == WriteMode.WRITE:
            # Create or overwrite file
            with open(file_path, 'w', encoding=self.encoding, newline=self.newline) as f:
                f.write(content)
                
            return DocumentResult(
                success=True,
                mode=str(mode),
                file_path=file_path,
                created_new=not file_exists
            )
            
        elif mode == WriteMode.APPEND:
            # Append to existing file or create new
            with open(file_path, 'a', encoding=self.encoding, newline=self.newline) as f:
                if file_exists:
                    # Add a newline before appending if needed
                    f.write("\n\n")
                f.write(content)
                
            return DocumentResult(
                success=True,
                mode=str(mode),
                file_path=file_path,
                created_new=not file_exists
            )
            
        elif mode == WriteMode.UPDATE:
            # For text files, update is the same as write for simplicity
            with open(file_path, 'w', encoding=self.encoding, newline=self.newline) as f:
                f.write(content)
                
            return DocumentResult(
                success=True,
                mode=str(mode),
                file_path=file_path,
                created_new=not file_exists
            )
            
        elif mode == WriteMode.DELETE:
            # Delete the file if it exists
            if file_exists:
                os.remove(file_path)
                return DocumentResult(
                    success=True,
                    mode=str(mode),
                    file_path=file_path,
                    file_deleted=True
                )
            else:
                return DocumentResult(
                    success=False,
                    mode=str(mode),
                    file_path=file_path,
                    error="File not found for deletion"
                )
        
        # Merge mode not well-defined for simple text files
        return DocumentResult(
            success=False,
            mode=str(mode),
            file_path=file_path,
            error=f"Unsupported mode for text files: {mode}"
        )