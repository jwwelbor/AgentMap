"""
Blob storage service for AgentMap.

This module provides a unified service for cloud blob storage operations,
integrating with multiple cloud providers (Azure, AWS S3, Google Cloud Storage)
and local file storage. It follows AgentMap's service-based architecture patterns
and leverages existing blob connector infrastructure.
"""

import json
from typing import Any, Dict, List, Optional, Type

from agentmap.services.storage.base_connector import (
    BlobStorageConnector,
    get_connector_for_uri,
    normalize_json_uri,
)
from agentmap.exceptions import (
    StorageConnectionError,
    StorageOperationError,
    StorageServiceError,
)
from agentmap.services.config.app_config_service import AppConfigService
from agentmap.services.logging_service import LoggingService
from agentmap.services.protocols import BlobStorageServiceProtocol


class BlobStorageService(BlobStorageServiceProtocol):
    """
    Unified blob storage service for cloud and local storage operations.

    This service provides a consistent interface for working with blob storage
    across multiple cloud providers, handling:
    - Provider selection based on URI scheme
    - Connection management and caching
    - Graceful degradation for missing dependencies
    - Configuration resolution
    - Error handling and logging
    """

    def __init__(
        self,
        configuration: AppConfigService,
        logging_service: LoggingService,
    ):
        """
        Initialize the blob storage service.

        Args:
            configuration: Application configuration service
            logging_service: Logging service for creating loggers
        """
        self.configuration = configuration
        self.logging_service = logging_service
        self._logger = logging_service.get_class_logger(self)

        # Cache for connector instances
        self._connectors: Dict[str, BlobStorageConnector] = {}

        # Load blob storage configuration
        self._config = self._load_blob_config()

        # Available providers (will be populated during runtime)
        self._available_providers: Dict[str, bool] = {}

        # Provider factory mapping
        self._provider_factories: Dict[str, Type[BlobStorageConnector]] = {}

        # Initialize provider registry
        self._initialize_provider_registry()

        self._logger.info("BlobStorageService initialized")

    def _load_blob_config(self) -> Dict[str, Any]:
        """
        Load blob storage configuration from app config.

        Returns:
            Configuration dictionary for blob storage
        """
        try:
            # Try multiple configuration paths for flexibility
            config = self.configuration.get_value("storage.blob", {})
            if not config:
                config = self.configuration.get_value("blob_storage", {})
            if not config:
                config = self.configuration.get_value("cloud_storage", {})

            self._logger.debug(f"Loaded blob storage configuration: {config}")
            return config
        except Exception as e:
            self._logger.warning(f"Failed to load blob storage config: {e}")
            return {}

    def _initialize_provider_registry(self) -> None:
        """
        Initialize the provider registry with available connectors.

        This method attempts to import all blob storage connectors and
        registers them if their dependencies are available.
        """
        # Azure Blob Storage
        try:
            from agentmap.services.storage.azure_blob_connector import (
                AzureBlobConnector,
            )

            self._provider_factories["azure"] = AzureBlobConnector
            self._available_providers["azure"] = self._check_azure_availability()
            self._logger.debug(f"Azure provider available: {self._available_providers['azure']}")
        except ImportError as e:
            self._logger.debug(f"Azure provider not available: {e}")
            self._available_providers["azure"] = False

        # AWS S3
        try:
            from agentmap.services.storage.aws_s3_connector import (
                AWSS3Connector,
            )

            self._provider_factories["s3"] = AWSS3Connector
            self._available_providers["s3"] = self._check_s3_availability()
            self._logger.debug(f"S3 provider available: {self._available_providers['s3']}")
        except ImportError as e:
            self._logger.debug(f"S3 provider not available: {e}")
            self._available_providers["s3"] = False

        # Google Cloud Storage
        try:
            from agentmap.services.storage.gcp_storage_connector import (
                GCPStorageConnector,
            )

            self._provider_factories["gs"] = GCPStorageConnector
            self._available_providers["gs"] = self._check_gcs_availability()
            self._logger.debug(f"GCS provider available: {self._available_providers['gs']}")
        except ImportError as e:
            self._logger.debug(f"GCS provider not available: {e}")
            self._available_providers["gs"] = False

        # Local file storage (always available)
        try:
            from agentmap.services.storage.local_file_connector import (
                LocalFileConnector,
            )

            self._provider_factories["file"] = LocalFileConnector
            self._provider_factories["local"] = LocalFileConnector  # Alias
            self._available_providers["file"] = True
            self._available_providers["local"] = True
            self._logger.debug("Local file provider available")
        except ImportError as e:
            self._logger.error(f"Local file provider not available: {e}")
            self._available_providers["file"] = False
            self._available_providers["local"] = False

    @staticmethod
    def _check_azure_availability() -> bool:
        """Check if Azure Blob Storage SDK is available."""
        try:
            import azure.storage.blob  # noqa: F401
            return True
        except ImportError:
            return False

    @staticmethod
    def _check_s3_availability() -> bool:
        """Check if AWS S3 SDK is available."""
        try:
            import boto3  # noqa: F401
            return True
        except ImportError:
            return False

    @staticmethod
    def _check_gcs_availability() -> bool:
        """Check if Google Cloud Storage SDK is available."""
        try:
            import google.cloud.storage  # noqa: F401
            return True
        except ImportError:
            return False

    def _get_connector(self, uri: str) -> BlobStorageConnector:
        """
        Get or create a connector for the given URI.

        Args:
            uri: Blob storage URI

        Returns:
            BlobStorageConnector instance

        Raises:
            StorageConnectionError: If no suitable connector is available
        """
        # Determine provider from URI
        provider = self._get_provider_from_uri(uri)

        # Check if connector is cached
        if provider in self._connectors:
            return self._connectors[provider]

        # Check if provider is available
        if not self._available_providers.get(provider, False):
            raise StorageConnectionError(
                f"Storage provider '{provider}' is not available. "
                f"Please install required dependencies."
            )

        # Create new connector
        try:
            connector = get_connector_for_uri(uri, self._config)
            self._connectors[provider] = connector
            self._logger.info(f"Created connector for provider: {provider}")
            return connector
        except Exception as e:
            self._logger.error(f"Failed to create connector for {provider}: {e}")
            raise StorageConnectionError(
                f"Failed to create connector for {provider}: {str(e)}"
            ) from e

    def _get_provider_from_uri(self, uri: str) -> str:
        """
        Determine the provider from URI scheme.

        Args:
            uri: Blob storage URI

        Returns:
            Provider name
        """
        if uri.startswith("azure://"):
            return "azure"
        elif uri.startswith("s3://"):
            return "s3"
        elif uri.startswith("gs://"):
            return "gs"
        else:
            return "file"

    def read_blob(self, uri: str, **kwargs) -> bytes:
        """
        Read blob from storage.

        Args:
            uri: URI of the blob to read (azure://, s3://, gs://, or local path)
            **kwargs: Provider-specific parameters

        Returns:
            Blob content as bytes

        Raises:
            FileNotFoundError: If the blob doesn't exist
            StorageOperationError: For other storage-related errors
        """
        self._logger.debug(f"Reading blob: {uri}")

        try:
            connector = self._get_connector(uri)
            data = connector.read_blob(uri)
            self._logger.debug(f"Successfully read blob: {uri} ({len(data)} bytes)")
            return data
        except FileNotFoundError:
            # Re-raise file not found as-is
            raise
        except Exception as e:
            self._logger.error(f"Failed to read blob {uri}: {e}")
            raise StorageOperationError(f"Failed to read blob: {str(e)}") from e

    def write_blob(self, uri: str, data: bytes, **kwargs) -> Dict[str, Any]:
        """
        Write blob to storage.

        Args:
            uri: URI where the blob should be written
            data: Blob content as bytes
            **kwargs: Provider-specific parameters

        Returns:
            Write result with operation details
        """
        self._logger.debug(f"Writing blob: {uri} ({len(data)} bytes)")

        try:
            connector = self._get_connector(uri)
            connector.write_blob(uri, data)
            
            result = {
                "success": True,
                "uri": uri,
                "size": len(data),
                "provider": self._get_provider_from_uri(uri),
            }
            
            self._logger.debug(f"Successfully wrote blob: {uri}")
            return result
        except Exception as e:
            self._logger.error(f"Failed to write blob {uri}: {e}")
            raise StorageOperationError(f"Failed to write blob: {str(e)}") from e

    def blob_exists(self, uri: str) -> bool:
        """
        Check if a blob exists.

        Args:
            uri: URI to check

        Returns:
            True if the blob exists, False otherwise
        """
        self._logger.debug(f"Checking blob existence: {uri}")

        try:
            connector = self._get_connector(uri)
            exists = connector.blob_exists(uri)
            self._logger.debug(f"Blob exists check for {uri}: {exists}")
            return exists
        except Exception as e:
            self._logger.warning(f"Error checking blob existence {uri}: {e}")
            return False

    def list_blobs(self, prefix: str, **kwargs) -> List[str]:
        """
        List blobs with given prefix.

        Args:
            prefix: URI prefix to search (e.g., "azure://container/path/")
            **kwargs: Provider-specific parameters (max_results, recursive, etc.)

        Returns:
            List of blob URIs
        """
        self._logger.debug(f"Listing blobs with prefix: {prefix}")

        try:
            connector = self._get_connector(prefix)
            
            # Check if connector has list_blobs method
            if hasattr(connector, 'list_blobs'):
                blobs = connector.list_blobs(prefix, **kwargs)
            else:
                # Fallback for connectors without list support
                self._logger.warning(
                    f"Connector for {prefix} doesn't support listing"
                )
                blobs = []

            self._logger.debug(f"Found {len(blobs)} blobs with prefix: {prefix}")
            return blobs
        except Exception as e:
            self._logger.error(f"Failed to list blobs with prefix {prefix}: {e}")
            raise StorageOperationError(f"Failed to list blobs: {str(e)}") from e

    def delete_blob(self, uri: str, **kwargs) -> Dict[str, Any]:
        """
        Delete a blob.

        Args:
            uri: URI of the blob to delete
            **kwargs: Provider-specific parameters

        Returns:
            Delete result with operation details
        """
        self._logger.debug(f"Deleting blob: {uri}")

        try:
            connector = self._get_connector(uri)
            
            # Check if connector has delete_blob method
            if hasattr(connector, 'delete_blob'):
                connector.delete_blob(uri)
            else:
                # Fallback error for connectors without delete support
                raise StorageOperationError(
                    f"Delete operation not supported for {uri}"
                )

            result = {
                "success": True,
                "uri": uri,
                "provider": self._get_provider_from_uri(uri),
            }
            
            self._logger.debug(f"Successfully deleted blob: {uri}")
            return result
        except Exception as e:
            self._logger.error(f"Failed to delete blob {uri}: {e}")
            raise StorageOperationError(f"Failed to delete blob: {str(e)}") from e

    # Convenience methods for JSON operations
    def read_json(self, uri: str, **kwargs) -> Any:
        """
        Read JSON data from blob storage.

        Args:
            uri: URI of the JSON blob to read
            **kwargs: Provider-specific parameters

        Returns:
            Parsed JSON data
        """
        # Normalize URI to ensure .json extension
        uri = normalize_json_uri(uri)
        
        try:
            data = self.read_blob(uri, **kwargs)
            return json.loads(data.decode('utf-8'))
        except json.JSONDecodeError as e:
            self._logger.error(f"Failed to parse JSON from {uri}: {e}")
            raise StorageOperationError(f"Invalid JSON in blob: {str(e)}") from e

    def write_json(self, uri: str, data: Any, **kwargs) -> Dict[str, Any]:
        """
        Write JSON data to blob storage.

        Args:
            uri: URI where the JSON blob should be written
            data: Data to serialize as JSON
            **kwargs: Provider-specific parameters

        Returns:
            Write result with operation details
        """
        # Normalize URI to ensure .json extension
        uri = normalize_json_uri(uri)
        
        try:
            json_bytes = json.dumps(data, indent=2).encode('utf-8')
            return self.write_blob(uri, json_bytes, **kwargs)
        except (TypeError, ValueError) as e:
            self._logger.error(f"Failed to serialize JSON for {uri}: {e}")
            raise StorageOperationError(f"Failed to serialize JSON: {str(e)}") from e

    def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on blob storage service.

        Returns:
            Health check results for all providers
        """
        self._logger.debug("Performing blob storage health check")

        results = {
            "healthy": True,
            "providers": {},
        }

        for provider, available in self._available_providers.items():
            provider_health = {
                "available": available,
                "configured": False,
                "healthy": False,
            }

            if available:
                # Check if provider is configured
                provider_config = self._config.get("providers", {}).get(provider, {})
                if provider in ["file", "local"] or provider_config:
                    provider_health["configured"] = True

                # Try to initialize connector
                if provider_health["configured"]:
                    try:
                        # Use a test URI for the provider
                        test_uri = f"{provider}://test/health-check"
                        if provider in ["file", "local"]:
                            test_uri = "/tmp/health-check"
                        
                        connector = self._get_connector(test_uri)
                        provider_health["healthy"] = True
                    except Exception as e:
                        self._logger.debug(
                            f"Health check failed for {provider}: {e}"
                        )
                        provider_health["healthy"] = False
                        provider_health["error"] = str(e)

            results["providers"][provider] = provider_health
            
            # Overall health is false if any configured provider is unhealthy
            if provider_health["configured"] and not provider_health["healthy"]:
                results["healthy"] = False

        self._logger.debug(f"Health check results: {results}")
        return results

    def get_available_providers(self) -> List[str]:
        """
        Get list of available storage providers.

        Returns:
            List of provider names that are available
        """
        return [
            provider
            for provider, available in self._available_providers.items()
            if available
        ]

    def get_provider_info(self, provider: Optional[str] = None) -> Dict[str, Any]:
        """
        Get information about storage providers.

        Args:
            provider: Optional specific provider to get info for

        Returns:
            Provider information dictionary
        """
        if provider:
            if provider not in self._available_providers:
                raise ValueError(f"Unknown provider: {provider}")
            
            return {
                provider: {
                    "available": self._available_providers.get(provider, False),
                    "configured": bool(
                        self._config.get("providers", {}).get(provider, {})
                    ),
                    "cached": provider in self._connectors,
                }
            }
        else:
            # Return info for all providers
            info = {}
            for prov in self._available_providers:
                info[prov] = {
                    "available": self._available_providers.get(prov, False),
                    "configured": bool(
                        self._config.get("providers", {}).get(prov, {})
                    ),
                    "cached": prov in self._connectors,
                }
            return info

    def clear_cache(self, provider: Optional[str] = None) -> None:
        """
        Clear cached connectors.

        Args:
            provider: Optional specific provider to clear
        """
        if provider:
            if provider in self._connectors:
                del self._connectors[provider]
                self._logger.info(f"Cleared cache for provider: {provider}")
        else:
            self._connectors.clear()
            self._logger.info("Cleared all blob storage connector caches")
