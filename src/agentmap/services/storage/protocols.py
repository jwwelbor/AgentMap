"""
Storage service protocols for AgentMap.

This module defines the protocols (interfaces) that storage services must implement,
following the Interface Segregation Principle and existing service patterns.
"""

from typing import (
    Any,
    Dict,
    List,
    Optional,
    Protocol,
    runtime_checkable,
)

from agentmap.services.storage.types import StorageResult, WriteMode


@runtime_checkable
class StorageReader(Protocol):
    """
    Protocol for storage read operations.

    Defines the interface for reading data from storage systems.
    Follows the Interface Segregation Principle by focusing only on read operations.
    """

    def read(
        self,
        collection: str,
        document_id: Optional[str] = None,
        query: Optional[Dict[str, Any]] = None,
        path: Optional[str] = None,
        **kwargs,
    ) -> Any:
        """
        Read data from storage.

        Args:
            collection: Collection/table/file identifier
            document_id: Optional specific document/record ID
            query: Optional query parameters for filtering
            path: Optional path within document (for nested data)
            **kwargs: Provider-specific parameters

        Returns:
            Data from storage (format depends on provider and request)
        """
        ...

    def exists(self, collection: str, document_id: Optional[str] = None) -> bool:
        """
        Check if collection or document exists in storage.

        Args:
            collection: Collection/table/file identifier
            document_id: Optional specific document/record ID

        Returns:
            True if exists, False otherwise
        """
        ...

    def count(self, collection: str, query: Optional[Dict[str, Any]] = None) -> int:
        """
        Count documents/records in collection.

        Args:
            collection: Collection/table/file identifier
            query: Optional query parameters for filtering

        Returns:
            Number of matching documents/records
        """
        ...


@runtime_checkable
class StorageWriter(Protocol):
    """
    Protocol for storage write operations.

    Defines the interface for writing data to storage systems.
    Follows the Interface Segregation Principle by focusing only on write operations.
    """

    def write(
        self,
        collection: str,
        data: Any,
        document_id: Optional[str] = None,
        mode: WriteMode = WriteMode.WRITE,
        path: Optional[str] = None,
        **kwargs,
    ) -> StorageResult:
        """
        Write data to storage.

        Args:
            collection: Collection/table/file identifier
            data: Data to write
            document_id: Optional specific document/record ID
            mode: Write mode (write, append, update, etc.)
            path: Optional path within document (for nested updates)
            **kwargs: Provider-specific parameters

        Returns:
            StorageResult with operation details
        """
        ...

    def delete(
        self,
        collection: str,
        document_id: Optional[str] = None,
        path: Optional[str] = None,
        **kwargs,
    ) -> StorageResult:
        """
        Delete from storage.

        Args:
            collection: Collection/table/file identifier
            document_id: Optional specific document/record ID
            path: Optional path within document (for partial deletion)
            **kwargs: Provider-specific parameters

        Returns:
            StorageResult with operation details
        """
        ...

    def batch_write(
        self,
        collection: str,
        data: List[Dict[str, Any]],
        mode: WriteMode = WriteMode.WRITE,
        **kwargs,
    ) -> StorageResult:
        """
        Write multiple documents/records in a batch operation.

        Args:
            collection: Collection/table/file identifier
            data: List of data items to write
            mode: Write mode for all items
            **kwargs: Provider-specific parameters

        Returns:
            StorageResult with batch operation details
        """
        ...


@runtime_checkable
class StorageService(StorageReader, StorageWriter, Protocol):
    """
    Combined storage service protocol.

    Inherits from both StorageReader and StorageWriter protocols,
    providing a complete storage interface. Also includes service
    lifecycle and health management methods.
    """

    def get_provider_name(self) -> str:
        """
        Get the storage provider name.

        Returns:
            Provider name (e.g., "csv", "json", "firebase", "postgres")
        """
        ...

    def health_check(self) -> bool:
        """
        Check if storage service is healthy and accessible.

        Returns:
            True if service is healthy, False otherwise
        """
        ...

    def list_collections(self) -> List[str]:
        """
        List all available collections.

        Returns:
            List of collection names/identifiers
        """
        ...

    def create_collection(
        self, collection: str, schema: Optional[Dict[str, Any]] = None
    ) -> StorageResult:
        """
        Create a new collection (if supported by provider).

        Args:
            collection: Collection name/identifier
            schema: Optional schema definition for structured storage

        Returns:
            StorageResult with creation details
        """
        ...


@runtime_checkable
class StorageServiceFactory(Protocol):
    """
    Protocol for creating storage service instances.

    Defines the interface for factory classes that can create
    storage services for different providers.
    """

    def create_service(
        self, provider: str, configuration: Dict[str, Any]
    ) -> StorageService:
        """
        Create a storage service for the specified provider.

        Args:
            provider: Provider name
            configuration: Provider-specific configuration

        Returns:
            StorageService instance
        """
        ...

    def supports_provider(self, provider: str) -> bool:
        """
        Check if factory supports the specified provider.

        Args:
            provider: Provider name to check

        Returns:
            True if supported, False otherwise
        """
        ...
