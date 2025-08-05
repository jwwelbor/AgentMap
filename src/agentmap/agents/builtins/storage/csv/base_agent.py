"""
Base CSV storage agent implementation using modernized protocol-based pattern.

This module provides common functionality for CSV agents that delegate
operations to CSVStorageService, keeping agents simple and focused.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from agentmap.agents.builtins.storage.base_storage_agent import (
    BaseStorageAgent,
)
from agentmap.models.storage import DocumentResult
from agentmap.services.execution_tracking_service import ExecutionTrackingService
from agentmap.services.state_adapter_service import StateAdapterService
from agentmap.services.storage.protocols import CSVCapableAgent


class CSVAgent(BaseStorageAgent, CSVCapableAgent):
    """
    Base class for CSV storage agents with shared functionality.

    Follows the modernized protocol-based pattern where:
    - Infrastructure services are injected via constructor
    - Business services (CSV storage) are configured post-construction via protocols
    - Implements CSVCapableAgent protocol for service configuration

    Delegates CSV operations to CSVStorageService while providing
    a simple interface for CSV reader and writer agents.
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
        Initialize CSV agent with new protocol-based pattern.

        Args:
            name: Name of the agent node
            prompt: Prompt or instruction
            context: Additional context including CSV configuration
            logger: Logger instance for logging operations
            execution_tracker: ExecutionTrackingService instance for tracking
            state_adapter: StateAdapterService instance for state operations
        """
        # Call new BaseStorageAgent constructor (infrastructure services only)
        super().__init__(
            name=name,
            prompt=prompt,
            context=context,
            logger=logger,
            execution_tracker_service=execution_tracker_service,
            state_adapter_service=state_adapter_service,
        )

        # CSV service will be configured via protocol
        self._csv_service = None

    # Protocol Implementation (Required by CSVCapableAgent)
    def configure_csv_service(self, csv_service) -> None:
        """
        Configure CSV storage service for this agent.

        This method is called by GraphRunnerService during agent setup.

        Args:
            csv_service: CSV storage service instance to configure
        """
        self._csv_service = csv_service
        # Also set as the main client for BaseStorageAgent
        self._client = csv_service
        self.log_debug("CSV service configured")

    @property
    def csv_service(self):
        """Get CSV service, raising clear error if not configured."""
        if self._csv_service is None:
            raise ValueError(f"CSV service not configured for agent '{self.name}'")
        return self._csv_service

    def _initialize_client(self) -> None:
        """
        Initialize client - in the new pattern, this should not be needed
        as services are injected via protocols.
        """
        # In the new pattern, services are injected via configure_* methods
        # This method is kept for compatibility but should not be used
        if self._csv_service is None:
            self.log_warning(
                "CSV service not configured - using fallback initialization"
            )
            # Fallback to create service directly (not recommended)
            from agentmap.services.storage.csv_service import CSVStorageService

            self._csv_service = CSVStorageService(self.context)
            self._client = self._csv_service

    def _is_auto_creation_enabled(self) -> bool:
        """
        Check if CSV auto-creation is enabled.
        
        Returns:
            True if auto-creation is enabled, False otherwise
        """
        try:
            if self._csv_service is not None:
                return self.csv_service.configuration.is_csv_auto_create_enabled()
            else:
                self.log_debug("CSV service not yet configured, assuming auto-creation disabled")
                return False
        except Exception as e:
            self.log_debug(f"Could not check auto-creation setting: {e}")
            return False
    
    def _is_write_operation(self, inputs: Dict[str, Any]) -> bool:
        """
        Determine if this is a write operation that could benefit from auto-creation.
        
        Args:
            inputs: Input dictionary
            
        Returns:
            True if this appears to be a write operation
        """
        # Write operations typically have data to write
        return "data" in inputs

    def _validate_inputs(self, inputs: Dict[str, Any]) -> None:
        """
        Validate inputs for CSV operations with auto-creation support.

        Args:
            inputs: Input dictionary

        Raises:
            ValueError: If inputs are invalid
            FileNotFoundError: If file doesn't exist and auto-creation won't help
        """
        collection = self.get_collection(inputs)
        if not collection:
            raise ValueError("Missing required 'collection' parameter")

        # Check if file path has CSV extension (warning only)
        if not collection.lower().endswith(".csv"):
            self.log_warning(f"Collection path does not end with .csv: {collection}")

        # Determine if we should skip file existence validation
        is_write_op = self._is_write_operation(inputs)
        auto_creation_enabled = self._is_auto_creation_enabled()
        
        if is_write_op and auto_creation_enabled:
            # For write operations with auto-creation enabled, skip parent file validation
            # The CSV service will handle creating the file if needed
            self.log_debug(f"Skipping file existence validation for write operation with auto-creation enabled: {collection}")
            
            # Still do basic input validation but skip the file existence check
            # We'll just validate the collection parameter which we already did above
            return
        else:
            # For read operations or when auto-creation is disabled, use strict validation
            if not is_write_op:
                self.log_debug(f"Using strict validation for read operation: {collection}")
            else:
                self.log_debug(f"Using strict validation (auto-creation disabled): {collection}")
            
            # Call parent validation which includes file existence check
            super()._validate_inputs(inputs)

    def _get_full_file_path(self, collection: str) -> str:
        """
        Get the full resolved file path for a collection.
        
        Args:
            collection: Collection identifier
            
        Returns:
            Full file path, or original collection if service unavailable
        """
        try:
            if self._csv_service is not None:
                return self.csv_service._get_file_path(collection)
            else:
                # Fallback if service not available
                return collection
        except Exception as e:
            self.log_debug(f"Could not resolve full file path for {collection}: {e}")
            return collection
    
    def _get_auto_creation_context(self) -> str:
        """
        Get context about auto-creation settings for error messages.
        
        Returns:
            Context string about auto-creation configuration
        """
        try:
            if self._is_auto_creation_enabled():
                return "Auto-creation is enabled but failed"
            else:
                return "Auto-creation is disabled. Enable with 'auto_create_files: true' in CSV config"
        except Exception:
            return "Could not determine auto-creation settings"

    def _handle_operation_error(
        self, error: Exception, collection: str, inputs: Dict[str, Any]
    ) -> DocumentResult:
        """
        Handle CSV operation errors with enhanced context and full paths.

        Args:
            error: The exception that occurred
            collection: Collection identifier
            inputs: Input dictionary

        Returns:
            DocumentResult with detailed error information
        """
        # Get full file path for better error reporting
        full_path = self._get_full_file_path(collection)
        
        if isinstance(error, FileNotFoundError):
            # Enhanced file not found error with full context
            auto_creation_context = self._get_auto_creation_context()
            is_write_op = self._is_write_operation(inputs)
            
            error_msg = f"CSV file not found: '{collection}'"
            if full_path != collection:
                error_msg += f" (resolved to: '{full_path}')"
            
            error_msg += f". {auto_creation_context}"
            
            if is_write_op and not self._is_auto_creation_enabled():
                error_msg += ". For write operations, consider enabling auto-creation in your storage configuration"
            elif not is_write_op:
                error_msg += ". File must exist for read operations"
            
            self.log_error(f"[{self.__class__.__name__}] {error_msg}")
            
            return DocumentResult(
                success=False,
                file_path=full_path,  # Use full path in result
                error=error_msg,
            )

        # For all other errors, enhance with full path info and delegate to base class
        if full_path != collection:
            self.log_debug(f"Error occurred with collection '{collection}' (resolved to: '{full_path}')")
        
        # Create enhanced error message for other error types
        original_result = super()._handle_operation_error(error, collection, inputs)
        
        # Enhance the error message with full path if different
        if full_path != collection and original_result.error:
            enhanced_error = original_result.error.replace(collection, f"{collection} (resolved to: {full_path})")
            return DocumentResult(
                success=False,
                file_path=full_path,
                error=enhanced_error,
            )
        
        return original_result
