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
    BaseStorageAgent, DocumentResult, WriteMode, log_operation
)
from agentmap.logging import get_logger

logger = get_logger(__name__)


class FileWriterAgent(BaseStorageAgent):
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
            context: Additional configuration including:
                - encoding: File encoding (default: 'utf-8')
                - newline: Newline character (default: system default)
                - input_fields: Input fields to use
                - output_field: Output field to return results
        """
        super().__init__(name, prompt, context)
        
        # Extract file writing configuration from context
        context = context or {}
        self.encoding = context.get("encoding", "utf-8")
        self.newline = context.get("newline", None)  # System default
    
    def _initialize_client(self) -> None:
        """No client needed for filesystem operations."""
        pass
    
    @log_operation
    def process(self, inputs: Dict[str, Any]) -> DocumentResult:
        """
        Process inputs and write to document.
        
        Args:
            inputs: Dictionary with keys:
                - collection: File path or collection name
                - data: Content to write
                - mode: Write mode (default: 'write')
                - document_id: Optional document section (for some formats)
                - path: Optional path within document
                
        Returns:
            Result of the write operation
        """
        # Get required parameters
        file_path = self.get_collection(inputs)
        data = inputs.get("data")
        
        # Get optional parameters
        mode_str = inputs.get("mode", "write").lower()
        document_id = inputs.get("document_id")
        path = inputs.get("path")
        
        # Validate data
        if data is None and mode_str != "delete":
            return DocumentResult(
                success=False,
                file_path=file_path,
                error="No data provided to write"
            )
        
        try:
            # Convert string mode to enum
            try:
                mode = WriteMode.from_string(mode_str)
            except ValueError as e:
                return DocumentResult(
                    success=False,
                    file_path=file_path,
                    error=str(e)
                )
            
            # Write the document
            return self._write_document(file_path, data, document_id, mode, path)
            
        except Exception as e:
            # Handle and log the error
            logger.error(f"Error writing to file {file_path}: {str(e)}")
            
            # Map common exceptions to appropriate errors
            if isinstance(e, FileNotFoundError):
                error_msg = f"File not found: {file_path}"
            elif isinstance(e, PermissionError):
                error_msg = f"Permission denied for file: {file_path}"
            elif isinstance(e, ValueError) and "Unsupported file type" in str(e):
                error_msg = str(e)
            else:
                error_msg = f"Error writing to file: {str(e)}"
            
            # Return formatted error
            return DocumentResult(
                success=False,
                file_path=file_path,
                mode=mode_str,
                error=error_msg
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
            data: Input data in various formats
            
        Returns:
            String content for writing
        """
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