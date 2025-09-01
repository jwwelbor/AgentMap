"""
File document writer agent implementation.

This module provides an agent for writing to various document types,
focusing on text documents, Markdown, and simple text-based formats.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from agentmap.agents.builtins.storage.base_storage_agent import BaseStorageAgent
from agentmap.models.storage import DocumentResult, WriteMode
from agentmap.services.execution_tracking_service import ExecutionTrackingService
from agentmap.services.state_adapter_service import StateAdapterService
from agentmap.services.storage.protocols import FileCapableAgent


class FileWriterAgent(BaseStorageAgent, FileCapableAgent):
    """
    Enhanced document writer agent for text-based file formats.

    Writes to text, Markdown, and other text-based formats,
    with support for different write modes including append and update.
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
        Initialize the file writer agent with new protocol-based pattern.

        Args:
            name: Name of the agent node
            prompt: File path or prompt with path
            context: Additional configuration including encoding and newline settings
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

        # Extract file writing configuration from context
        context = context or {}
        self.encoding = context.get("encoding", "utf-8")
        self.newline = context.get("newline", None)  # System default
        self._current_state = None  # Store current state for state key lookups

        # FileCapableAgent protocol requirement - will be set via dependency injection
        # or initialized in _initialize_client()
        self.file_service = None

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
        Log the start of a file write operation.

        Args:
            collection: File path
            inputs: Input dictionary
        """
        mode = inputs.get("mode", "write")
        self.log_debug(
            f"[{self.__class__.__name__}] Starting write operation (mode: {mode}) on file: {collection}"
        )

    def _validate_inputs(self, inputs: Dict[str, Any]) -> None:
        """
        Validate inputs for file write operations.

        Args:
            inputs: Input dictionary

        Raises:
            ValueError: If inputs are invalid
        """
        # Don't call super()._validate_inputs() as it checks file existence
        # For write operations, files don't need to exist (can be created)

        # Validate collection parameter
        collection = self.get_collection(inputs)
        if not collection:
            raise ValueError("Missing required 'collection' parameter")

        # Validate mode and data requirements
        mode = inputs.get("mode", "append").lower()

        # Check if we have data for non-delete operations
        if mode != "delete" and "data" not in inputs:
            raise ValueError(
                "Missing required 'data' parameter for non-delete operations"
            )

    def _execute_operation(
        self, collection: str, inputs: Dict[str, Any]
    ) -> DocumentResult:
        """
        Execute write operation for file using FileStorageService.
        """
        data = inputs.get("data")
        mode_str = inputs.get("mode", "append").lower()
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
            path=path,
        )
        return result

    def _handle_operation_error(
        self, error: Exception, collection: str, inputs: Dict[str, Any]
    ) -> DocumentResult:
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
                error=f"File not found: {collection}",
            )
        elif isinstance(error, PermissionError):
            return DocumentResult(
                success=False,
                file_path=collection,
                error=f"Permission denied for file: {collection}",
            )

        return super()._handle_operation_error(error, collection, inputs)

    def _write_document(self, *args, **kwargs):
        raise NotImplementedError(
            "Direct document writing is now handled by FileStorageService."
        )

    def _prepare_content(self, *args, **kwargs):
        raise NotImplementedError(
            "Content preparation is now handled by FileStorageService."
        )

    def _is_text_file(self, *args, **kwargs):
        raise NotImplementedError(
            "File type checking is now handled by FileStorageService."
        )

    def _write_text_file(self, *args, **kwargs):
        raise NotImplementedError(
            "Text file writing is now handled by FileStorageService."
        )
