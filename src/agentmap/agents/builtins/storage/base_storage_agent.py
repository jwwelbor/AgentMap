"""
Base storage agent implementation using modernized protocol-based pattern.

This module provides the foundation for all storage agents in AgentMap,
with utilities for accessing data stores and handling operations.
"""

from __future__ import annotations

import functools
import logging
from typing import Any, Callable, Dict, Optional, Tuple, TypeVar, cast

from agentmap.agents.base_agent import BaseAgent
from agentmap.models.storage import DocumentResult
from agentmap.services.execution_tracking_service import ExecutionTrackingService
from agentmap.services.protocols import StorageCapableAgent, StorageServiceProtocol
from agentmap.services.state_adapter_service import StateAdapterService

F = TypeVar("F", bound=Callable[..., Any])  # Type for callable functions


def log_operation(func: F) -> F:
    """
    Decorator to log storage operations with consistent formatting.

    Args:
        func: The function to decorate

    Returns:
        Wrapped function with logging
    """

    @functools.wraps(func)
    def wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
        class_name = self.__class__.__name__
        self.log_debug(f"[{class_name}] Starting {func.__name__}")
        try:
            result = func(self, *args, **kwargs)
            self.log_debug(f"[{class_name}] Completed {func.__name__}")
            return result
        except Exception as e:
            self.log_error(f"[{class_name}] Error in {func.__name__}: {str(e)}")
            raise

    return cast(F, wrapper)


class BaseStorageAgent(BaseAgent, StorageCapableAgent):
    """
    Base class for all storage agents in AgentMap.

    Follows the modernized protocol-based pattern where:
    - Infrastructure services are injected via constructor
    - Business services (Storage) are configured post-construction via protocols
    - Implements StorageCapableAgent protocol for service configuration

    This abstract class defines the contract that all storage
    implementations must follow, with common utilities for
    error handling and connection management.
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
        Initialize storage agent with new protocol-based pattern.

        Args:
            name: Name of the agent node
            prompt: Prompt or instruction
            context: Additional context including input/output configuration
            logger: Logger instance for logging operations
            execution_tracker: ExecutionTrackingService instance for tracking
            state_adapter: StateAdapterService instance for state operations
        """
        # Call new BaseAgent constructor (infrastructure services only)
        super().__init__(
            name=name,
            prompt=prompt,
            context=context,
            logger=logger,
            execution_tracking_service=execution_tracker_service,
            state_adapter_service=state_adapter_service,
        )

        # Storage-specific initialization
        self._client: Any = None

    # Protocol Implementation (Required by StorageCapableAgent)
    def configure_storage_service(
        self, storage_service: StorageServiceProtocol
    ) -> None:
        """
        Configure storage service for this agent.

        This method is called by GraphRunnerService during agent setup.

        Args:
            storage_service: Storage service instance to configure
        """
        self._storage_service = storage_service
        self.log_debug("Storage service configured")

    @property
    def client(self) -> Any:
        """
        Access the storage client connection.

        Returns:
            Storage client instance

        Note:
            This property will initialize the client on first access
            if it doesn't already exist.
        """
        if self._client is None:
            self._initialize_client()
        return self._client

    def _initialize_client(self) -> None:
        """
        Initialize the storage client connection.

        Subclasses should implement this to set up their specific client connection.
        """
        raise NotImplementedError("Subclasses must implement _initialize_client")

    def get_collection(self, inputs: Dict[str, Any]) -> str:
        """
        Get the collection name/path from inputs or configuration.

        Args:
            inputs: Dictionary of input values

        Returns:
            Collection identifier (typically a file path for CSV)

        Raises:
            ValueError: If no collection is specified
        """
        # Try to get the collection from inputs
        collection = inputs.get("collection")

        # If not in inputs, try to get from prompt (for backward compatibility)
        if collection is None and self.prompt:
            collection = self.prompt

        if collection is None:
            raise ValueError("No collection specified in inputs or prompt")

        # Resolve collection path through configuration
        return self._resolve_collection_path(collection)

    def _resolve_collection_path(self, collection: str) -> str:
        """
        Resolve a collection name to an actual storage path using configuration.

        Args:
            collection: Collection name or path

        Returns:
            Resolved path
        """
        # This is a basic implementation, subclasses may override
        return collection

    def _handle_error(
        self,
        error_type: str,
        message: str,
        exception: Optional[Exception] = None,
        raise_error: bool = True,
    ) -> None:
        """
        Handle errors with consistent logging.

        Args:
            error_type: Type of error
            message: Error message
            exception: Optional exception object
            raise_error: Whether to raise the error or just log it

        Raises:
            ValueError: For input/validation errors
            RuntimeError: For other errors
        """
        # Build complete error message
        error_msg = f"{error_type}: {message}"
        if exception is not None:
            error_msg += f" - {str(exception)}"

        self.log_error(f"[{self.__class__.__name__}] {error_msg}")

        if not raise_error:
            return

        # Choose exception type based on the underlying error
        if isinstance(exception, (ValueError, TypeError)):
            raise ValueError(error_msg) from exception
        else:
            raise RuntimeError(error_msg) from exception

    def _normalize_document_id(self, document_id: Any) -> Optional[str]:
        """
        Normalize document ID to string format.

        Args:
            document_id: Document ID in any format

        Returns:
            String document ID or None
        """
        if document_id is None:
            return None
        return str(document_id)

    # Template method pattern implementation
    @log_operation
    def process(self, inputs: Dict[str, Any]) -> Any:
        """
        Process inputs using the template method pattern.

        Args:
            inputs: Dictionary of input values

        Returns:
            Operation result
        """
        # Extract common parameters
        collection = self.get_collection(inputs)

        # Pre-process operation
        self._log_operation_start(collection, inputs)

        try:
            # Validate inputs
            self._validate_inputs(inputs)

            # Execute storage operation
            result = self._execute_operation(collection, inputs)

            # Post-process result
            return self._process_result(result, inputs)

        except Exception as e:
            # Handle error
            return self._handle_operation_error(e, collection, inputs)

    def _log_operation_start(self, collection: str, inputs: Dict[str, Any]) -> None:
        """
        Log the start of a storage operation.

        Args:
            collection: Collection identifier
            inputs: Input dictionary
        """
        self.log_debug(
            f"[{self.__class__.__name__}] Starting operation on {collection}"
        )

    def _validate_inputs(self, inputs: Dict[str, Any]) -> None:
        """
        Validate operation inputs.

        Args:
            inputs: Input dictionary

        Raises:
            ValueError: If inputs are invalid
            FileNotFoundError: If the collection file does not exist
        """
        # Base implementation - subclasses should override
        collection = self.get_collection(inputs)
        if not collection:
            raise ValueError("Missing required 'collection' parameter")

        # Leave file existence validation to services

        # Check if the file exists (for file-based storage)
        # import os

        # if not os.path.exists(collection):
        #     raise FileNotFoundError(f"File not found: {collection}")

    def _execute_operation(self, collection: str, inputs: Dict[str, Any]) -> Any:
        """
        Execute the storage operation.

        Args:
            collection: Collection identifier
            inputs: Input dictionary

        Returns:
            Operation result

        Raises:
            NotImplementedError: When not implemented by subclass
        """
        raise NotImplementedError("Subclasses must implement _execute_operation")

    def _process_result(self, result: Any, inputs: Dict[str, Any]) -> Any:
        """
        Process the operation result.

        Args:
            result: Operation result
            inputs: Input dictionary

        Returns:
            Processed result
        """
        # Base implementation - return result as-is
        return result

    def _pre_process(
        self, state: Any, inputs: Dict[str, Any]
    ) -> Tuple[Any, Dict[str, Any]]:
        """
        Pre-processing hook that can be overridden by subclasses.

        Args:
            state: Current state
            inputs: Extracted input values

        Returns:
            Tuple of (state, processed_inputs)
        """

        return state, inputs

    def _handle_operation_error(
        self, error: Exception, collection: str, inputs: Dict[str, Any]
    ) -> DocumentResult:
        """
        Handle operation errors.

        Args:
            error: The exception that occurred
            collection: Collection identifier
            inputs: Input dictionary

        Returns:
            DocumentResult with error information
        """
        error_msg = f"Error processing {collection}: {str(error)}"
        self.log_error(f"[{self.__class__.__name__}] {error_msg}")

        # Create error result
        return DocumentResult(success=False, file_path=collection, error=error_msg)
