"""
Modern blob storage writer agent implementation.

This module provides a simple agent for writing raw bytes to blob storage
that delegates to BlobStorageService for the actual implementation.
Follows the modernized BaseAgent contract with constructor injection.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

from agentmap.agents.base_agent import BaseAgent
from agentmap.services.execution_tracking_service import ExecutionTrackingService
from agentmap.services.protocols import (
    BlobStorageCapableAgent,
    BlobStorageServiceProtocol,
)
from agentmap.services.state_adapter_service import StateAdapterService


class BlobWriterAgent(BaseAgent, BlobStorageCapableAgent):
    """
    Modern agent for writing raw bytes to blob storage via BlobStorageService.

    Follows the modernized protocol-based pattern where:
    - Infrastructure services are injected via constructor
    - Business services (blob storage) are configured post-construction via protocols
    - Implements BlobStorageCapableAgent protocol for service configuration

    Delegates all blob operations to the service layer for clean separation of concerns.
    Focuses purely on blob operations while providing convenient data conversion.
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
        Initialize blob writer agent with modern protocol-based pattern.

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

        self.log_debug("BlobWriterAgent initialized with infrastructure services")

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

    def process(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process inputs to write data to blob storage.

        Handles data conversion for convenience while maintaining focus on blob operations.
        Converts string data to UTF-8 bytes and objects to JSON bytes automatically.

        Args:
            inputs: Dictionary of input values containing blob_uri and data

        Returns:
            Write result with operation details

        Raises:
            ValueError: If required inputs are missing
            StorageOperationError: For storage-related errors
        """
        self.log_debug(f"Processing blob write with inputs: {list(inputs.keys())}")

        # Extract blob URI from inputs
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

        # Extract data from inputs
        data = None
        for key in ["data", "content", "payload", "body"]:
            if key in inputs and inputs[key] is not None:
                data = inputs[key]
                break

        if data is None:
            raise ValueError(
                "Missing required data. Provide one of: data, content, payload, or body"
            )

        self.log_info(f"Writing blob to: {blob_uri}")

        try:
            # Convert data to bytes if needed (convenient data conversion)
            bytes_data = self._convert_to_bytes(data)

            # Use dependency-injected blob storage service
            result = self.blob_storage_service.write_blob(blob_uri, bytes_data)

            self.log_info(
                f"Successfully wrote blob: {blob_uri} ({len(bytes_data)} bytes)"
            )

            # Return write result with operation details
            return result

        except Exception as e:
            error_msg = f"Failed to write blob {blob_uri}: {str(e)}"
            self.log_error(error_msg)
            raise

    @staticmethod
    def _convert_to_bytes(data: Any) -> bytes:
        """
        Convert data to bytes for blob storage.

        Provides convenient data conversion while maintaining focus on blob operations.

        Args:
            data: Data to convert (bytes, str, dict, list, etc.)

        Returns:
            Data as bytes

        Raises:
            ValueError: If data cannot be converted to bytes
        """
        if isinstance(data, bytes):
            # Already bytes - return as-is
            return data
        elif isinstance(data, str):
            # String to UTF-8 bytes
            return data.encode("utf-8")
        elif isinstance(data, bool):
            # Boolean to Python string bytes
            return str(data).encode("utf-8")
        elif isinstance(data, (dict, list, int, float)) or data is None:
            # Object to JSON bytes
            try:
                json_str = json.dumps(data, ensure_ascii=False, indent=2)
                return json_str.encode("utf-8")
            except (TypeError, ValueError) as e:
                raise ValueError(f"Failed to serialize data to JSON: {str(e)}") from e
        else:
            # Try to convert to string first, then to bytes
            try:
                str_data = str(data)
                return str_data.encode("utf-8")
            except Exception as e:
                raise ValueError(
                    f"Cannot convert data of type {type(data)} to bytes: {str(e)}"
                ) from e

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
