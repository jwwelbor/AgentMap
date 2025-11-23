"""
Blob storage service for AgentMap.

This module provides a unified service for cloud blob storage operations,
integrating with multiple cloud providers (Azure, AWS S3, Google Cloud Storage)
and local file storage. It follows AgentMap's service-based architecture patterns
and leverages existing blob connector infrastructure.
"""

import json
from typing import Any, Callable, Dict, List, Optional, Type

from agentmap.exceptions import (
    StorageConnectionError,
    StorageOperationError,
    StorageServiceError,
)
from agentmap.services.config.availability_cache_service import (
    AvailabilityCacheService,
)
from agentmap.services.config.storage_config_service import StorageConfigService
from agentmap.services.logging_service import LoggingService
from agentmap.services.storage.base_connector import (
    BlobStorageConnector,
    get_connector_for_uri,
    normalize_json_uri,
)
from agentmap.services.storage.protocols import BlobStorageServiceProtocol


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
        configuration: StorageConfigService,
        logging_service: LoggingService,
        availability_cache: AvailabilityCacheService,
    ):
        """Initialize the blob storage service."""
        self.configuration = configuration
        self.logging_service = logging_service
        self.availability_cache = availability_cache
        self._logger = logging_service.get_class_logger(self)
        self._connectors: Dict[str, BlobStorageConnector] = {}
        self._config = self._load_blob_config()
        self._available_providers: Dict[str, bool] = {}
        self._provider_factories: Dict[str, Type[BlobStorageConnector]] = {}
        self._initialize_provider_registry()
        self._logger.info("BlobStorageService initialized")

    def _load_blob_config(self) -> Dict[str, Any]:
        """Load blob storage configuration from storage config service."""
        try:
            config = self.configuration.get_blob_config()
            self._logger.debug(f"Loaded blob storage configuration: {config}")
            return config
        except Exception as e:
            self._logger.warning(f"Failed to load blob storage config: {e}")
            return {}

    def _initialize_provider_registry(self) -> None:
        """Initialize the provider registry with available connectors."""
        self._register_cloud_provider(
            "azure",
            "azure_blob",
            "agentmap.services.storage.azure_blob_connector",
            "AzureBlobConnector",
            self._check_azure_availability,
        )
        self._register_cloud_provider(
            "s3",
            "aws_s3",
            "agentmap.services.storage.aws_s3_connector",
            "AWSS3Connector",
            self._check_s3_availability,
        )
        self._register_cloud_provider(
            "gs",
            "gcp_storage",
            "agentmap.services.storage.gcp_storage_connector",
            "GCPStorageConnector",
            self._check_gcs_availability,
        )
        self._register_local_provider()

    def _register_cloud_provider(
        self,
        provider_key: str,
        cache_key: str,
        module_path: str,
        class_name: str,
        check_func: Callable[[], bool],
    ) -> None:
        """Register a cloud storage provider if available."""
        available = self._check_and_cache_availability(cache_key, check_func)
        if available:
            try:
                module = __import__(module_path, fromlist=[class_name])
                connector_class = getattr(module, class_name)
                self._provider_factories[provider_key] = connector_class
                self._available_providers[provider_key] = True
                self._logger.debug(f"{provider_key.upper()} provider registered")
            except (ImportError, AttributeError) as e:
                self._logger.debug(f"{provider_key.upper()} import failed: {e}")
                self._available_providers[provider_key] = False
        else:
            self._available_providers[provider_key] = False
            self._logger.debug(f"{provider_key.upper()} not available")

    def _register_local_provider(self) -> None:
        """Register local file storage provider."""
        try:
            from agentmap.services.storage.local_file_connector import (
                LocalFileConnector,
            )

            self._provider_factories["file"] = LocalFileConnector
            self._provider_factories["local"] = LocalFileConnector
            self._available_providers["file"] = True
            self._available_providers["local"] = True
            self._logger.debug("Local file provider available")
        except ImportError as e:
            self._logger.error(f"Local file provider not available: {e}")
            self._available_providers["file"] = False
            self._available_providers["local"] = False

    def _check_and_cache_availability(
        self, provider: str, check_func: Callable[[], bool]
    ) -> bool:
        """Check and cache provider availability."""
        cached = self.availability_cache.get_availability(
            "dependency.storage", provider
        )
        if cached is not None:
            return cached.get("available", False)
        try:
            available = check_func()
            self.availability_cache.set_availability(
                "dependency.storage",
                provider,
                {"available": available, "provider": provider},
            )
            return available
        except Exception as e:
            self._logger.debug(f"Error checking {provider} availability: {e}")
            self.availability_cache.set_availability(
                "dependency.storage",
                provider,
                {"available": False, "provider": provider, "error": str(e)},
            )
            return False

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
        """Get or create a connector for the given URI."""
        provider = self._get_provider_from_uri(uri)
        if provider in self._connectors:
            return self._connectors[provider]
        if not self._available_providers.get(provider, False):
            raise StorageConnectionError(
                f"Storage provider '{provider}' is not available. "
                f"Please install required dependencies."
            )
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
        """Determine the provider from URI scheme."""
        if uri.startswith("azure://"):
            return "azure"
        elif uri.startswith("s3://"):
            return "s3"
        elif uri.startswith("gs://"):
            return "gs"
        return "file"

    def read_blob(self, uri: str, **kwargs) -> bytes:
        """Read blob from storage."""
        self._logger.debug(f"Reading blob: {uri}")
        try:
            connector = self._get_connector(uri)
            data = connector.read_blob(uri)
            self._logger.debug(f"Successfully read blob: {uri} ({len(data)} bytes)")
            return data
        except FileNotFoundError:
            raise
        except Exception as e:
            self._logger.error(f"Failed to read blob {uri}: {e}")
            raise StorageOperationError(f"Failed to read blob: {str(e)}") from e

    def write_blob(self, uri: str, data: bytes, **kwargs) -> Dict[str, Any]:
        """Write blob to storage."""
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
        """Check if a blob exists."""
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
        """List blobs with given prefix."""
        self._logger.debug(f"Listing blobs with prefix: {prefix}")
        try:
            connector = self._get_connector(prefix)
            if hasattr(connector, "list_blobs"):
                blobs = connector.list_blobs(prefix, **kwargs)
            else:
                self._logger.warning(f"Connector for {prefix} doesn't support listing")
                blobs = []
            self._logger.debug(f"Found {len(blobs)} blobs with prefix: {prefix}")
            return blobs
        except Exception as e:
            self._logger.error(f"Failed to list blobs with prefix {prefix}: {e}")
            raise StorageOperationError(f"Failed to list blobs: {str(e)}") from e

    def delete_blob(self, uri: str, **kwargs) -> Dict[str, Any]:
        """Delete a blob."""
        self._logger.debug(f"Deleting blob: {uri}")
        try:
            connector = self._get_connector(uri)
            if hasattr(connector, "delete_blob"):
                connector.delete_blob(uri)
            else:
                raise StorageOperationError(f"Delete operation not supported for {uri}")
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

    def read_json(self, uri: str, **kwargs) -> Any:
        """Read JSON data from blob storage."""
        uri = normalize_json_uri(uri)
        try:
            data = self.read_blob(uri, **kwargs)
            return json.loads(data.decode("utf-8"))
        except json.JSONDecodeError as e:
            self._logger.error(f"Failed to parse JSON from {uri}: {e}")
            raise StorageOperationError(f"Invalid JSON in blob: {str(e)}") from e

    def write_json(self, uri: str, data: Any, **kwargs) -> Dict[str, Any]:
        """Write JSON data to blob storage."""
        uri = normalize_json_uri(uri)
        try:
            json_bytes = json.dumps(data, indent=2).encode("utf-8")
            return self.write_blob(uri, json_bytes, **kwargs)
        except (TypeError, ValueError) as e:
            self._logger.error(f"Failed to serialize JSON for {uri}: {e}")
            raise StorageOperationError(f"Failed to serialize JSON: {str(e)}") from e

    def health_check(self) -> Dict[str, Any]:
        """Perform health check on blob storage service."""
        self._logger.debug("Performing blob storage health check")
        results = {"healthy": True, "providers": {}}
        for provider, available in self._available_providers.items():
            health = {"available": available, "configured": False, "healthy": False}
            if available:
                cfg = self.configuration.get_blob_provider_config(provider)
                if provider in ["file", "local"] or cfg:
                    health["configured"] = True
                if health["configured"]:
                    try:
                        uri = (
                            "/tmp/health"
                            if provider in ["file", "local"]
                            else f"{provider}://test/health"
                        )
                        self._get_connector(uri)
                        health["healthy"] = True
                    except Exception as e:
                        self._logger.debug(f"Health check failed for {provider}: {e}")
                        health["healthy"] = False
                        health["error"] = str(e)
            results["providers"][provider] = health
            if health["configured"] and not health["healthy"]:
                results["healthy"] = False
        self._logger.debug(f"Health check results: {results}")
        return results

    def get_available_providers(self) -> List[str]:
        """Get list of available storage providers."""
        return [p for p, avail in self._available_providers.items() if avail]

    def get_provider_info(self, provider: Optional[str] = None) -> Dict[str, Any]:
        """Get information about storage providers."""
        if provider:
            if provider not in self._available_providers:
                raise ValueError(f"Unknown provider: {provider}")
            return {
                provider: {
                    "available": self._available_providers.get(provider, False),
                    "configured": bool(
                        self.configuration.get_blob_provider_config(provider)
                    ),
                    "cached": provider in self._connectors,
                }
            }
        return {
            p: {
                "available": self._available_providers.get(p, False),
                "configured": bool(self.configuration.get_blob_provider_config(p)),
                "cached": p in self._connectors,
            }
            for p in self._available_providers
        }

    def clear_cache(self, provider: Optional[str] = None) -> None:
        """Clear cached connectors."""
        if provider:
            if provider in self._connectors:
                del self._connectors[provider]
                self._logger.info(f"Cleared cache for provider: {provider}")
        else:
            self._connectors.clear()
            self._logger.info("Cleared all blob storage connector caches")
