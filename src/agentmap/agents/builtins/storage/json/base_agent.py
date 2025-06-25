"""
Base JSON storage agent implementation using modernized protocol-based pattern.

This module provides common functionality for JSON agents that delegate
operations to JSONStorageService, keeping agents simple and focused.
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
from agentmap.services.storage.protocols import JSONCapableAgent


class JSONDocumentAgent(BaseStorageAgent, JSONCapableAgent):
    """
    Base class for JSON document storage operations.

    Follows the modernized protocol-based pattern where:
    - Infrastructure services are injected via constructor
    - Business services (JSON storage) are configured post-construction via protocols
    - Implements JSONCapableAgent protocol for service configuration

    Delegates JSON operations to JSONStorageService while providing
    a simple interface for JSON reader and writer agents.
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
        Initialize JSON agent with new protocol-based pattern.

        Args:
            name: Name of the agent node
            prompt: Prompt or instruction
            context: Additional context including JSON configuration
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

        # JSON service will be configured via protocol
        self._json_service = None

    # Protocol Implementation (Required by JSONCapableAgent)
    def configure_json_service(self, json_service) -> None:
        """
        Configure JSON storage service for this agent.

        This method is called by GraphRunnerService during agent setup.

        Args:
            json_service: JSON storage service instance to configure
        """
        self._json_service = json_service
        # Also set as the main client for BaseStorageAgent
        self._client = json_service
        self.log_debug("JSON service configured")

    @property
    def json_service(self):
        """Get JSON service, raising clear error if not configured."""
        if self._json_service is None:
            raise ValueError(f"JSON service not configured for agent '{self.name}'")
        return self._json_service

    def _initialize_client(self) -> None:
        """
        Initialize client - in the new pattern, this should not be needed
        as services are injected via protocols.
        """
        # In the new pattern, services are injected via configure_* methods
        # This method is kept for compatibility but should not be used
        if self._json_service is None:
            self.log_warning(
                "JSON service not configured - using fallback initialization"
            )
            # Fallback to create service directly (not recommended)
            from agentmap.services.storage.json_service import JSONStorageService

            self._json_service = JSONStorageService(self.context)
            self._client = self._json_service

    def _validate_inputs(self, inputs: Dict[str, Any]) -> None:
        """
        Validate inputs for JSON operations.

        Args:
            inputs: Input dictionary

        Raises:
            ValueError: If inputs are invalid
        """
        super()._validate_inputs(inputs)

        collection = self.get_collection(inputs)
        if not collection:
            raise ValueError("Missing required 'collection' parameter")

        # Check if file path has JSON extension (warning only)
        if not collection.lower().endswith(".json"):
            self.log_warning(f"Collection path does not end with .json: {collection}")

    def _handle_operation_error(
        self, error: Exception, collection: str, inputs: Dict[str, Any]
    ) -> DocumentResult:
        """
        Handle JSON operation errors.

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
                error=f"JSON file not found: {collection}",
            )
        elif isinstance(error, ValueError) and "Invalid JSON" in str(error):
            return DocumentResult(
                success=False,
                file_path=collection,
                error=f"Invalid JSON in file: {collection}",
            )

        # Delegate to base class for other errors
        return super()._handle_operation_error(error, collection, inputs)
