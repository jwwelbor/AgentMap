"""
Vector writer agent implementation.

This module provides a simple agent for storing documents in vector databases
that delegates to VectorStorageService for the actual implementation.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from agentmap.agents.builtins.storage.vector.base_agent import VectorAgent
from agentmap.models.storage import WriteMode
from agentmap.services.execution_tracking_service import ExecutionTrackingService
from agentmap.services.state_adapter_service import StateAdapterService


class VectorWriterAgent(VectorAgent):
    """
    Simple agent for storing documents in vector databases via VectorStorageService.

    Delegates all vector operations to the service layer for clean separation of concerns.
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
        Initialize the vector writer agent with new protocol-based pattern.

        Args:
            name: Name of the agent node
            prompt: Prompt or instruction
            context: Additional context including should_persist, input_fields, etc.
            logger: Logger instance for logging operations
            execution_tracker: ExecutionTrackingService instance for tracking
            state_adapter: StateAdapterService instance for state operations
        """
        super().__init__(
            name=name,
            prompt=prompt,
            context=context,
            logger=logger,
            execution_tracker_service=execution_tracker_service,
            state_adapter_service=state_adapter_service,
        )

        # Extract vector writer-specific configuration
        context = context or {}
        self.should_persist = context.get("should_persist", True)
        # Override input_fields from base class if needed
        self.input_fields = context.get("input_fields", ["docs"])

    def _log_operation_start(self, collection: str, inputs: Dict[str, Any]) -> None:
        """Log the start of a vector storage operation."""
        docs = inputs.get(self.input_fields[0])
        doc_count = (
            len(docs) if isinstance(docs, list) else "1" if docs is not None else "0"
        )
        self.log_debug(
            f"[{self.__class__.__name__}] Starting vector storage with {doc_count} document(s)"
        )

    def _validate_inputs(self, inputs: Dict[str, Any]) -> None:
        """
        Validate inputs for vector writer operations.

        Args:
            inputs: Input dictionary

        Raises:
            ValueError: If inputs are invalid
        """
        # Don't call super()._validate_inputs() as it gives generic error messages
        # Vector writer needs specific validation for documents

        # Validate collection parameter (from base class logic)
        collection = self.get_collection(inputs)
        if not collection:
            raise ValueError("Missing required 'collection' parameter")

        # Check for required input field with specific error message
        input_field = self.input_fields[0]
        if input_field not in inputs or inputs.get(input_field) is None:
            raise ValueError(f"No documents provided in '{input_field}' field")

    def _execute_operation(self, collection: str, inputs: Dict[str, Any]) -> Any:
        """
        Execute vector storage operation by delegating to VectorStorageService.

        Args:
            collection: Collection identifier
            inputs: Input dictionary

        Returns:
            Storage operation result
        """
        self.log_info(f"Storing documents in vector collection: {collection}")

        # Get documents from inputs
        docs_field = self.input_fields[0]
        docs = inputs.get(docs_field)

        if not docs:
            return {"status": "error", "error": "No documents provided"}

        # Call the vector storage service
        result = self.vector_service.write(
            collection=collection,
            data=docs,
            mode=WriteMode.APPEND,  # Vector stores typically append
            should_persist=inputs.get("should_persist", self.should_persist),
        )

        if result and result.success:
            return {
                "status": "success",
                "stored_count": getattr(result, "total_affected", 0),
                "ids": getattr(result, "ids", []),
                "persist_directory": getattr(result, "persist_directory", None),
            }
        else:
            return {
                "status": "error",
                "error": getattr(result, "error", "Vector storage failed"),
            }
