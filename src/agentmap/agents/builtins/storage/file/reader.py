"""
File document reader agent implementation.

This module provides an agent for reading various document types using LangChain loaders,
focusing on text documents, PDFs, Markdown, HTML, and DOCX.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

from agentmap.agents.builtins.storage.base_storage_agent import (
    BaseStorageAgent,
)
from agentmap.models.storage import DocumentResult
from agentmap.services.execution_tracking_service import ExecutionTrackingService
from agentmap.services.state_adapter_service import StateAdapterService
from agentmap.services.storage.protocols import FileCapableAgent


class FileReaderAgent(BaseStorageAgent, FileCapableAgent):
    """
    Enhanced document reader agent using LangChain document loaders.

    Reads various document formats including text, PDF, Markdown, HTML, and DOCX,
    with options for chunking and filtering.
    """

    def __init__(
        self,
        name: str,
        prompt: str,
        context: Optional[Dict[str, Any]] = None,
        # Infrastructure services only
        logger: Optional[logging.Logger] = None,
        execution_tracker_service: Optional[ExecutionTrackingService] = None,
        state_adapter_service: Optional[StateAdapterService] = None,
    ):
        """
        Initialize the file reader agent with new protocol-based pattern.

        Args:
            name: Name of the agent node
            prompt: Prompt or instruction
            context: Additional context including chunking and format configuration
            logger: Logger instance for logging operations
            execution_tracker_service: ExecutionTrackingService instance for tracking
            state_adapter_service: StateAdapterService instance for state operations
        """
        # Call new BaseAgent constructor (infrastructure services only)
        super().__init__(
            name=name,
            prompt=prompt,
            context=context,
            logger=logger,
            execution_tracker_service=execution_tracker_service,
            state_adapter_service=state_adapter_service,
        )

        # Extract document processing configuration from context
        context = context or {}
        self.chunk_size = int(context.get("chunk_size", 1000))
        self.chunk_overlap = int(context.get("chunk_overlap", 200))
        self.should_split = context.get("should_split", False)
        self.include_metadata = context.get("include_metadata", True)

        # FileCapableAgent protocol requirement - will be set via dependency injection
        # or initialized in _initialize_client()
        self.file_service = None

        # For testing - allows a test to inject a mock loader
        self._test_loader = None

    # Protocol Implementation (Required by FileCapableAgent)
    def configure_file_service(self, file_service) -> None:
        """
        Configure file storage service for this agent.

        This method is called by GraphRunnerService during agent setup.

        Args:
            file_service: File storage service instance to configure
        """
        self.file_service = file_service
        # Also set as the main client for BaseStorageAgent
        self._client = file_service
        self.log_debug("File service configured")

    def _initialize_client(self) -> None:
        """
        Initialize client - in the new pattern, services are injected via protocols.

        This method is kept for compatibility but should not be needed
        as services are injected via configure_file_service() method.
        """
        # In the new pattern, services are injected via configure_* methods
        # This method is kept for compatibility but should not be used
        if self.file_service is None:
            self.log_warning(
                "File service not configured - agent needs file service injection"
            )
            # Don't create service directly as we don't have required dependencies
            # Services should be injected via dependency injection in production
            raise ValueError(
                f"File service not configured for agent '{self.name}'. "
                "Please inject file service via configure_file_service() method."
            )

    def _log_operation_start(self, collection: str, inputs: Dict[str, Any]) -> None:
        """
        Log the start of a file read operation.

        Args:
            collection: File path
            inputs: Input dictionary
        """
        self.log_debug(
            f"[{self.__class__.__name__}] Starting read operation on file: {collection}"
        )

    def _validate_inputs(self, inputs: Dict[str, Any]) -> None:
        """
        Validate inputs for file read operations.

        Args:
            inputs: Input dictionary

        Raises:
            ValueError: If inputs are invalid
        """
        super()._validate_inputs(inputs)

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
            format=output_format,
        )
        return result

    def _handle_operation_error(
        self, error: Exception, collection: str, inputs: Dict[str, Any]
    ) -> DocumentResult:
        """
        Handle file read operation errors.

        Args:
            error: The exception that occurred
            collection: File path
            inputs: Input dictionary

        Returns:
            DocumentResult with error information
        """
        if isinstance(error, (FileNotFoundError, PermissionError)):
            # Log the actual error for debugging purposes
            if isinstance(error, PermissionError):
                self.log_warning(
                    f"Permission denied accessing file: {collection} - {str(error)}"
                )

            # Return generic "file not found" message for both cases (security through obscurity)
            return DocumentResult(
                success=False,
                file_path=collection,
                error=f"File not found: {collection}",
            )

        # Let base agent handle other errors
        return super()._handle_operation_error(error, collection, inputs)
