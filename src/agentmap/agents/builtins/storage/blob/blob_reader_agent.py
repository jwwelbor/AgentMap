"""
Modern blob storage reader agent implementation.

This module provides a simple agent for reading raw bytes from blob storage
that delegates to BlobStorageService for the actual implementation.
Follows the modernized BaseAgent contract with constructor injection.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from agentmap.agents.base_agent import BaseAgent
from agentmap.services.execution_tracking_service import ExecutionTrackingService
from agentmap.services.protocols import (
    BlobStorageCapableAgent,
    BlobStorageServiceProtocol,
)
from agentmap.services.state_adapter_service import StateAdapterService


class BlobReaderAgent(BaseAgent, BlobStorageCapableAgent):
    """
    Modern agent for reading raw bytes from blob storage via BlobStorageService.

    Follows the modernized protocol-based pattern where:
    - Infrastructure services are injected via constructor
    - Business services (blob storage) are configured post-construction via protocols
    - Implements BlobStorageCapableAgent protocol for service configuration

    Delegates all blob operations to the service layer for clean separation of concerns.
    Focuses purely on blob operations without mixing JSON parsing concerns.
    """

    def __init__(
        self,
        name: str,
        prompt: str,
        context: Optional[Dict[str, Any]] = None,
        # Infrastructure services only - core services that ALL agents need
        logger: Optional[logging.Logger] = None,
        execution_tracking_service: Optional[ExecutionTrackingService] = None,
        state_adapter_service: Optional[StateAdapterService] = None,
    ):
        """
        Initialize blob reader agent with modern protocol-based pattern.

        Args:
            name: Name of the agent node
            prompt: Prompt or instruction
            context: Additional context including input/output configuration
            logger: Logger instance for logging operations
            execution_tracking_service: ExecutionTrackingService instance for tracking
            state_adapter_service: StateAdapterService instance for state operations
        """
        # Call modern BaseAgent constructor (infrastructure services only)
        super().__init__(
            name=name,
            prompt=prompt,
            context=context,
            logger=logger,
            execution_tracking_service=execution_tracking_service,
            state_adapter_service=state_adapter_service,
        )

        # Blob storage service will be configured via protocol
        self._blob_storage_service: Optional[BlobStorageServiceProtocol] = None

        self.log_debug("BlobReaderAgent initialized with infrastructure services")

    # Protocol Implementation (Required by BlobStorageCapableAgent)
    def configure_blob_storage_service(
        self, blob_service: BlobStorageServiceProtocol
    ) -> None:
        """
        Configure blob storage service for this agent.

        This method is called by GraphRunnerService during agent setup.

        Args:
            blob_service: Blob storage service instance to configure
        """
        self._blob_storage_service = blob_service
        self.log_debug("Blob storage service configured")

    @property
    def blob_storage_service(self) -> BlobStorageServiceProtocol:
        """Get blob storage service, raising clear error if not configured."""
        if self._blob_storage_service is None:
            raise ValueError(
                f"Blob storage service not configured for agent '{self.name}'"
            )
        return self._blob_storage_service

    def process(self, inputs: Dict[str, Any]) -> bytes:
        """
        Process inputs to read blob data as raw bytes.

        Focuses purely on blob read operations - no JSON parsing concerns.
        JSON processing should be handled by separate JSON-capable agents if needed.

        Args:
            inputs: Dictionary of input values containing blob_uri

        Returns:
            Raw blob data as bytes

        Raises:
            ValueError: If required inputs are missing
            FileNotFoundError: If the blob doesn't exist
            StorageOperationError: For other storage-related errors
        """
        self.log_debug(f"Processing blob read with inputs: {list(inputs.keys())}")

        # Extract blob URI from inputs using state adapter
        blob_uri = None
        for key in ["blob_uri", "uri", "path", "file_path", "blob_path"]:
            if key in inputs and inputs[key]:
                blob_uri = inputs[key]
                break

        if not blob_uri:
            raise ValueError(
                "Missing required blob URI. Provide one of: blob_uri, uri, path, "
                "file_path, or blob_path"
            )

        self.log_info(f"Reading blob from: {blob_uri}")

        try:
            # Use dependency-injected blob storage service
            blob_data = self.blob_storage_service.read_blob(blob_uri)

            self.log_info(
                f"Successfully read blob: {blob_uri} ({len(blob_data)} bytes)"
            )

            # Return raw bytes - let downstream agents handle JSON parsing if needed
            return blob_data

        except FileNotFoundError:
            error_msg = f"Blob not found: {blob_uri}"
            self.log_error(error_msg)
            raise
        except Exception as e:
            error_msg = f"Failed to read blob {blob_uri}: {str(e)}"
            self.log_error(error_msg)
            raise

    def _get_child_service_info(self) -> Optional[Dict[str, Any]]:
        """
        Provide blob storage-specific service information for debugging.

        Returns:
            Dictionary with blob storage service info
        """
        return {
            "services": {
                "blob_storage_service_configured": self._blob_storage_service
                is not None,
            },
            "protocols": {
                "implements_blob_storage_capable": True,
            },
            "blob_storage": {
                "service_type": (
                    type(self._blob_storage_service).__name__
                    if self._blob_storage_service
                    else None
                ),
                "available_providers": (
                    self._blob_storage_service.get_available_providers()
                    if self._blob_storage_service
                    else []
                ),
            },
        }
