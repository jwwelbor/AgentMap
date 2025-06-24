"""
Vector reader agent implementation.

This module provides a simple agent for vector similarity search
that delegates to VectorStorageService for the actual implementation.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from agentmap.agents.builtins.storage.vector.base_agent import VectorAgent
from agentmap.services.execution_tracking_service import ExecutionTrackingService
from agentmap.services.state_adapter_service import StateAdapterService


class VectorReaderAgent(VectorAgent):
    """
    Simple agent for vector similarity search via VectorStorageService.

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
        Initialize the vector reader agent with new protocol-based pattern.

        Args:
            name: Name of the agent node
            prompt: Prompt or instruction
            context: Additional context including k, metadata_keys, etc.
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
        # Inherit k and metadata_keys from base class

    def _log_operation_start(self, collection: str, inputs: Dict[str, Any]) -> None:
        """Log the start of a vector search operation."""
        query = inputs.get(self.input_fields[0], "")
        query_preview = query[:30] + "..." if len(query) > 30 else query
        self.log_debug(
            f"[{self.__class__.__name__}] Starting vector search with query: {query_preview}"
        )

    def _execute_operation(self, collection: str, inputs: Dict[str, Any]) -> Any:
        """
        Execute vector search operation by delegating to VectorStorageService.

        Args:
            collection: Collection identifier
            inputs: Input dictionary

        Returns:
            Search operation result
        """
        self.log_info(f"Searching vector collection: {collection}")

        # Extract parameters for the service
        query_field = self.input_fields[0]
        query_text = inputs.get(query_field)

        if not query_text:
            return {"status": "error", "error": "No query provided for vector search"}

        # Call the vector storage service
        results = self.vector_service.read(
            collection=collection,
            query={"text": query_text},
            k=inputs.get("k", self.k),
            metadata_keys=inputs.get("metadata_keys", self.metadata_keys),
        )

        if results is None:
            return {"status": "error", "error": "Vector search failed"}

        # Return formatted results matching original agent output format
        return {
            "status": "success",
            "query": query_text,
            "results": results,
            "count": len(results) if results else 0,
        }
