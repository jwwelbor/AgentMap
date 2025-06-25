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
        if not collection.lower().endswith(".csv"):
            self.log_warning(f"Collection path does not end with .csv: {collection}")

    def _handle_operation_error(
        self, error: Exception, collection: str, inputs: Dict[str, Any]
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
                error=f"CSV file not found: {collection}",
            )

        # For all other errors, delegate to base class
        return super()._handle_operation_error(error, collection, inputs)
