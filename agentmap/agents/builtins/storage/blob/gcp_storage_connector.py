"""
Google Cloud Storage connector for JSON storage.

This module provides a GCP-specific implementation of the BlobStorageConnector
interface for reading and writing JSON files in Google Cloud Storage buckets.
"""
import os
from typing import Any, Dict, Optional

from agentmap.agents.builtins.storage.blob.base_connector import BlobStorageConnector
from agentmap.exceptions import StorageConnectionError, StorageOperationError
from agentmap.logging import get_logger

logger = get_logger(__name__)


class GCPStorageConnector(BlobStorageConnector):
    """
    Google Cloud Storage connector for cloud storage operations.

    This connector implements the BlobStorageConnector interface for
    Google Cloud Storage, supporting authentication via service account
    or application default credentials.
    """

    URI_SCHEME = "gs"

    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize the Google Cloud Storage connector.

        Args:
            config: GCP configuration with connection details
        """
        super().__init__(config)
        self.project_id = None
        self.credentials_file = None
        self.default_bucket = None

    def _initialize_client(self) -> None:
        """
        Initialize the Google Cloud Storage client.

        Raises:
            StorageConnectionError: If client initialization fails
        """
        try:
            # Import Google Cloud Storage
            try:
                from google.cloud import storage
                from google.auth.exceptions import DefaultCredentialsError
            except ImportError:
                raise StorageConnectionError(
                    "Google Cloud Storage SDK not installed. "
                    "Please install with: pip install google-cloud-storage"
                )

            # Extract configuration
            self.project_id = self.resolve_env_value(
                self.config.get("project_id", "")
            )
            self.credentials_file = self.resolve_env_value(
                self.config.get("credentials_file", "")
            )
            self.default_bucket = self.config.get("default_bucket", "")

            # Set credentials environment variable if provided
            if self.credentials_file and os.path.exists(self.credentials_file):
                os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = self.credentials_file

            # Create client
            client_kwargs = {}
            if self.project_id:
                client_kwargs["project"] = self.project_id

            self._client = storage.Client(**client_kwargs)
            logger.debug("Google Cloud Storage client initialized")

        except Exception as e:
            logger.error(f"Failed to initialize Google Cloud Storage client: {str(e)}")
            raise StorageConnectionError(f"Failed to initialize Google Cloud Storage client: {str(e)}")

    def read_blob(self, uri: str) -> bytes:
        """
        Read blob from Google Cloud Storage.

        Args:
            uri: URI of the blob to read

        Returns:
            Blob content as bytes

        Raises:
            FileNotFoundError: If the blob doesn't exist
            StorageOperationError: For other storage-related errors
        """
        try:
            # Parse URI into bucket and blob path
            bucket_name, blob_path = self._parse_gs_uri(uri)

            # Get bucket
            bucket = self.client.bucket(bucket_name)

            # Get blob
            blob = bucket.blob(blob_path)

            # Check if blob exists
            if not blob.exists():
                logger.error(f"Blob not found: {uri}")
                raise FileNotFoundError(f"Blob not found: {uri}")

            # Download blob
            return blob.download_as_bytes()

        except FileNotFoundError:
            raise
        except Exception as e:
            logger.error(f"Error reading blob {uri}: {str(e)}")
            raise StorageOperationError(f"Failed to read blob {uri}: {str(e)}")

    def write_blob(self, uri: str, data: bytes) -> None:
        """
        Write blob to Google Cloud Storage.

        Args:
            uri: URI where the blob should be written
            data: Blob content as bytes

        Raises:
            StorageOperationError: If the write operation fails
        """
        try:
            # Parse URI into bucket and blob path
            bucket_name, blob_path = self._parse_gs_uri(uri)

            # Get bucket
            bucket = self.client.bucket(bucket_name)

            # Create bucket if it doesn't exist
            if not bucket.exists():
                logger.info(f"Creating bucket: {bucket_name}")
                bucket = self.client.create_bucket(bucket_name)

            # Get blob
            blob = bucket.blob(blob_path)

            # Upload blob
            blob.upload_from_string(data)

        except Exception as e:
            logger.error(f"Error writing blob {uri}: {str(e)}")
            raise StorageOperationError(f"Failed to write blob {uri}: {str(e)}")

    def blob_exists(self, uri: str) -> bool:
        """
        Check if a blob exists in Google Cloud Storage.

        Args:
            uri: URI to check

        Returns:
            True if the blob exists, False otherwise
        """
        try:
            # Parse URI into bucket and blob path
            bucket_name, blob_path = self._parse_gs_uri(uri)

            # Get bucket
            bucket = self.client.bucket(bucket_name)

            # Check if bucket exists
            if not bucket.exists():
                return False

            # Get blob
            blob = bucket.blob(blob_path)

            # Check if blob exists
            return blob.exists()

        except Exception as e:
            logger.error(f"Error checking blob existence {uri}: {str(e)}")
            return False

    def _parse_gs_uri(self, uri: str) -> tuple[str, str]:
        """
        Parse Google Cloud Storage URI into bucket and blob path.

        Args:
            uri: Google Cloud Storage URI

        Returns:
            Tuple of (bucket_name, blob_path)

        Raises:
            ValueError: If the URI is invalid
        """
        parts = self.parse_uri(uri)

        # Get bucket name (from URI netloc or default)
        bucket_name = parts["container"]
        if not bucket_name:
            # Use default bucket if not specified in URI
            bucket_name = self.default_bucket
            if not bucket_name:
                raise ValueError(f"No bucket specified in URI and no default bucket configured: {uri}")

        # Check if bucket name is mapped in configuration
        bucket_mapping = self.config.get("buckets", {})
        if bucket_name in bucket_mapping:
            bucket_name = bucket_mapping[bucket_name]

        # Get blob path
        blob_path = parts["path"]
        if not blob_path:
            raise ValueError(f"No blob path specified in URI: {uri}")

        return bucket_name, blob_path