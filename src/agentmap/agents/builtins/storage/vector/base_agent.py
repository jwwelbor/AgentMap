"""
Base vector storage agent implementation using modernized protocol-based pattern.

This module provides common functionality for vector agents that delegate
operations to VectorStorageService, keeping agents simple and focused.
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
from agentmap.services.storage.protocols import VectorCapableAgent


class VectorAgent(BaseStorageAgent, VectorCapableAgent):
    """
    Base class for vector storage operations.

    Follows the modernized protocol-based pattern where:
    - Infrastructure services are injected via constructor
    - Business services (Vector storage) are configured post-construction via protocols
    - Implements VectorCapableAgent protocol for service configuration

    Delegates vector operations to VectorStorageService while providing
    a simple interface for vector reader and writer agents.
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
        Initialize vector agent with new protocol-based pattern.

        Args:
            name: Name of the agent node
            prompt: Prompt or instruction
            context: Additional context including vector configuration
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

        # Extract vector-specific configuration from context
        context = context or {}
        self.k = int(context.get("k", 4))
        self.metadata_keys = context.get("metadata_keys", None)
        self.input_fields = context.get("input_fields", ["query"])
        self.output_field = context.get("output_field", "result")

        # Vector service will be configured via protocol
        self._vector_service = None

    # Protocol Implementation (Required by VectorCapableAgent)
    def configure_vector_service(self, vector_service) -> None:
        """
        Configure vector storage service for this agent.

        This method is called by GraphRunnerService during agent setup.

        Args:
            vector_service: Vector storage service instance to configure
        """
        self._vector_service = vector_service
        # Also set as the main client for BaseStorageAgent
        self._client = vector_service
        self.log_debug("Vector service configured")

    @property
    def vector_service(self):
        """Get vector service, raising clear error if not configured."""
        if self._vector_service is None:
            raise ValueError(f"Vector service not configured for agent '{self.name}'")
        return self._vector_service

    def _initialize_client(self) -> None:
        """
        Initialize client - in the new pattern, this should not be needed
        as services are injected via protocols.
        """
        # In the new pattern, services are injected via configure_* methods
        # This method is kept for compatibility but should not be used
        if self._vector_service is None:
            self.log_warning(
                "Vector service not configured - using fallback initialization"
            )
            # Fallback to create service directly (not recommended)
            from agentmap.services.storage.vector_service import VectorStorageService

            self._vector_service = VectorStorageService(self.context)
            self._client = self._vector_service

    def _validate_inputs(self, inputs: Dict[str, Any]) -> None:
        """
        Validate inputs for vector operations.

        Args:
            inputs: Input dictionary

        Raises:
            ValueError: If inputs are invalid
        """
        # Don't call super()._validate_inputs() as it checks file existence
        # Vector storage uses collections/databases, not files

        # Validate collection parameter
        collection = self.get_collection(inputs)
        if not collection:
            raise ValueError("Missing required 'collection' parameter")

        # Check for required input field
        input_field = self.input_fields[0]
        if input_field not in inputs:
            raise ValueError(f"Missing required input field: {input_field}")

    def _handle_operation_error(
        self, error: Exception, collection: str, inputs: Dict[str, Any]
    ) -> DocumentResult:
        """
        Handle vector operation errors.

        Args:
            error: The exception that occurred
            collection: Collection identifier
            inputs: Input dictionary

        Returns:
            DocumentResult with error information
        """
        # For vector operations, we can handle specific vector-related errors here
        # For now, delegate all errors to base class for consistent handling
        return super()._handle_operation_error(error, collection, inputs)
