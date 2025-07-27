"""
Azure Blob Storage connector for JSON storage.

This module provides an Azure-specific implementation of the BlobStorageConnector
interface for reading and writing JSON files in Azure Blob Storage.
"""

from typing import Any, Dict

from agentmap.exceptions import StorageConnectionError, StorageOperationError
from agentmap.services.storage.base_connector import BlobStorageConnector


class AzureBlobConnector(BlobStorageConnector):
    """
    Azure Blob Storage connector for cloud storage operations.

    This connector implements the BlobStorageConnector interface for
    Azure Blob Storage, supporting both connection string and account key
    authentication methods.
    """

    URI_SCHEME = "azure"

    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize the Azure Blob Storage connector.

        Args:
            config: Azure configuration with connection details
        """
        super().__init__(config)
        self.connection_string = None
        self.account_name = None
        self.account_key = None
        self.default_container = None

    def _initialize_client(self) -> None:
        """
        Initialize the Azure Blob Storage client.

        Raises:
            StorageConnectionError: If client initialization fails
        """
        try:
            # Import Azure SDK
            try:
                from azure.storage.blob import BlobServiceClient
            except ImportError:
                raise StorageConnectionError(
                    "Azure Blob Storage SDK not installed. "
                    "Please install with: pip install azure-storage-blob"
                )

            # Extract configuration
            self.connection_string = self.resolve_env_value(
                self.config.get("connection_string", "")
            )
            self.account_name = self.resolve_env_value(
                self.config.get("account_name", "")
            )
            self.account_key = self.resolve_env_value(
                self.config.get("account_key", "")
            )
            self.sas_token = self.resolve_env_value(self.config.get("sas_token", ""))
            self.default_container = self.config.get("default_container", "")

            # Create client
            if self.connection_string:
                self._client = BlobServiceClient.from_connection_string(
                    self.connection_string
                )
                self.log_debug(
                    "Azure Blob Storage client initialized using connection string"
                )
            elif self.account_name and self.account_key:
                # Connect using account key
                endpoint = f"https://{self.account_name}.blob.core.windows.net"
                self._client = BlobServiceClient(
                    account_url=endpoint, credential=self.account_key
                )
                self.log_debug(
                    "Azure Blob Storage client initialized using account key"
                )
            elif self.account_name and self.sas_token:
                # Connect using SAS token
                if not self.sas_token.startswith("?"):
                    self.sas_token = "?" + self.sas_token
                endpoint = (
                    f"https://{self.account_name}.blob.core.windows.net{self.sas_token}"
                )
                self._client = BlobServiceClient(account_url=endpoint)
                self.log_debug("Azure Blob Storage client initialized using SAS token")
            else:
                raise StorageConnectionError(
                    "Azure Blob Storage connection not configured. "
                    "Please provide either connection_string, account_name+account_key, "
                    "or account_name+sas_token"
                )

        except Exception as e:
            self.log_error(f"Failed to initialize Azure Blob Storage client: {str(e)}")
            raise StorageConnectionError(
                f"Failed to initialize Azure Blob Storage client: {str(e)}"
            )

    def read_blob(self, uri: str) -> bytes:
        """
        Read blob from Azure Blob Storage.

        Args:
            uri: URI of the blob to read

        Returns:
            Blob content as bytes

        Raises:
            FileNotFoundError: If the blob doesn't exist
            StorageOperationError: For other storage-related errors
        """
        try:
            # Parse URI into container and blob path
            container_name, blob_path = self._parse_azure_uri(uri)

            # Get container client
            container_client = self.client.get_container_client(container_name)

            # Check if container exists
            try:
                container_client.get_container_properties()
            except Exception as e:
                return self._handle_provider_error(
                    "accessing",
                    container_name,
                    e,
                    raise_error=True,
                    resource_type="container",
                )

            # Get blob client
            blob_client = container_client.get_blob_client(blob_path)

            # Check if blob exists
            try:
                blob_client.get_blob_properties()
            except Exception as e:
                return self._handle_provider_error(
                    "accessing", uri, e, raise_error=True, resource_type="blob"
                )

            # Download blob
            try:
                download = blob_client.download_blob()
                return download.readall()
            except Exception as e:
                return self._handle_provider_error(
                    "downloading", uri, e, raise_error=True, resource_type="blob"
                )

        except (FileNotFoundError, StorageOperationError, StorageConnectionError):
            # Re-raise standard exceptions
            raise
        except Exception as e:
            return self._handle_provider_error(
                "reading", uri, e, raise_error=True, resource_type="blob"
            )

    def write_blob(self, uri: str, data: bytes) -> None:
        """
        Write blob to Azure Blob Storage.

        Args:
            uri: URI where the blob should be written
            data: Blob content as bytes

        Raises:
            StorageOperationError: If the write operation fails
        """
        try:
            # Parse URI into container and blob path
            container_name, blob_path = self._parse_azure_uri(uri)

            # Get container client
            container_client = self.client.get_container_client(container_name)

            # Create container if it doesn't exist
            try:
                container_client.get_container_properties()
            except Exception:
                self.log_info(f"Creating container: {container_name}")
                try:
                    container_client.create_container()
                except Exception as e:
                    return self._handle_provider_error(
                        "creating",
                        container_name,
                        e,
                        raise_error=True,
                        resource_type="container",
                    )

            # Get blob client
            blob_client = container_client.get_blob_client(blob_path)

            # Upload blob
            try:
                blob_client.upload_blob(data, overwrite=True)
            except Exception as e:
                return self._handle_provider_error(
                    "writing", uri, e, raise_error=True, resource_type="blob"
                )

        except (StorageOperationError, StorageConnectionError):
            # Re-raise standard exceptions
            raise
        except Exception as e:
            return self._handle_provider_error(
                "writing", uri, e, raise_error=True, resource_type="blob"
            )

    def blob_exists(self, uri: str) -> bool:
        """
        Check if a blob exists in Azure Blob Storage.

        Args:
            uri: URI to check

        Returns:
            True if the blob exists, False otherwise
        """
        try:
            # Parse URI into container and blob path
            container_name, blob_path = self._parse_azure_uri(uri)

            # Get container client
            container_client = self.client.get_container_client(container_name)

            # Check if container exists
            try:
                container_client.get_container_properties()
            except Exception:
                self.log_debug(f"Container not found: {container_name}")
                return False

            # Get blob client
            blob_client = container_client.get_blob_client(blob_path)

            # Check if blob exists
            try:
                blob_client.get_blob_properties()
                return True
            except Exception:
                self.log_debug(f"Blob not found: {blob_path}")
                return False

        except Exception as e:
            self.log_warning(f"Error checking blob existence {uri}: {str(e)}")
            return False

    def _parse_azure_uri(self, uri: str) -> tuple[str, str]:
        """
        Parse Azure URI into container and blob path.

        Args:
            uri: Azure Blob Storage URI

        Returns:
            Tuple of (container_name, blob_path)

        Raises:
            ValueError: If the URI is invalid
        """
        parts = self.parse_uri(uri)

        # Get container name (from URI netloc or default)
        container_name = parts["container"]
        if not container_name:
            # Use default container if not specified in URI
            container_name = self.default_container
            if not container_name:
                raise ValueError(
                    f"No container specified in URI and no default container configured: {uri}"
                )

        # Check if container name is mapped in configuration
        container_mapping = self.config.get("containers", {})
        if container_name in container_mapping:
            container_name = container_mapping[container_name]

        # Get blob path
        blob_path = parts["path"]
        if not blob_path:
            raise ValueError(f"No blob path specified in URI: {uri}")

        return container_name, blob_path
