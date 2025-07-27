"""
Google Cloud Storage connector for JSON storage.

This module provides a GCP-specific implementation of the BlobStorageConnector
interface for reading and writing JSON files in Google Cloud Storage buckets.
"""

import os
from typing import Any, Dict, Tuple

from agentmap.exceptions import StorageConnectionError, StorageOperationError
from agentmap.services.storage.base_connector import BlobStorageConnector


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
        self.gcp_exceptions = None

    def _initialize_client(self) -> None:
        """
        Initialize the Google Cloud Storage client.

        Raises:
            StorageConnectionError: If client initialization fails
        """
        try:
            # Import Google Cloud Storage
            try:
                from google.auth.exceptions import DefaultCredentialsError
                from google.cloud import storage
                from google.cloud.exceptions import Forbidden, NotFound

                # Store exception classes for future reference
                self.gcp_exceptions = {
                    "NotFound": NotFound,
                    "Forbidden": Forbidden,
                    "DefaultCredentialsError": DefaultCredentialsError,
                }
            except ImportError:
                raise StorageConnectionError(
                    "Google Cloud Storage SDK not installed. "
                    "Please install with: pip install google-cloud-storage"
                )

            # Extract configuration
            self.project_id = self.resolve_env_value(self.config.get("project_id", ""))
            self.credentials_file = self.resolve_env_value(
                self.config.get("credentials_file", "")
            )
            self.default_bucket = self.config.get("default_bucket", "")

            # Set credentials environment variable if provided
            original_credential_env = None
            if self.credentials_file and os.path.exists(self.credentials_file):
                original_credential_env = os.environ.get(
                    "GOOGLE_APPLICATION_CREDENTIALS"
                )
                os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = self.credentials_file

            # Create client
            try:
                client_kwargs = {}
                if self.project_id:
                    client_kwargs["project"] = self.project_id

                self._client = storage.Client(**client_kwargs)
                self.log_debug("Google Cloud Storage client initialized successfully")
            except DefaultCredentialsError:
                raise StorageConnectionError(
                    "GCP credentials not found. Please configure credentials via "
                    "environment variables, service account key file, or GCE metadata server."
                )
            finally:
                # Restore original environment variable if it was changed
                if original_credential_env is not None:
                    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = (
                        original_credential_env
                    )
                elif (
                    self.credentials_file
                    and "GOOGLE_APPLICATION_CREDENTIALS" in os.environ
                ):
                    # Remove the environment variable if it wasn't present before
                    del os.environ["GOOGLE_APPLICATION_CREDENTIALS"]

        except Exception as e:
            self.log_error(
                f"Failed to initialize Google Cloud Storage client: {str(e)}"
            )
            raise StorageConnectionError(
                f"Failed to initialize Google Cloud Storage client: {str(e)}"
            )

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
            try:
                bucket = self.client.bucket(bucket_name)
                if not bucket.exists():
                    return self._handle_provider_error(
                        "reading",
                        uri,
                        Exception(f"Bucket {bucket_name} not found"),
                        raise_error=True,
                        resource_type="bucket",
                    )
            except Exception as e:
                return self._handle_provider_error(
                    "accessing",
                    bucket_name,
                    e,
                    raise_error=True,
                    resource_type="bucket",
                )

            # Get blob
            blob = bucket.blob(blob_path)

            # Check if blob exists
            if not blob.exists():
                return self._handle_provider_error(
                    "reading",
                    uri,
                    Exception(f"Blob {blob_path} not found"),
                    raise_error=True,
                    resource_type="blob",
                )

            # Download blob
            try:
                return blob.download_as_bytes()
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
            try:
                bucket = self.client.bucket(bucket_name)

                # Create bucket if it doesn't exist
                if not bucket.exists():
                    self.log_info(f"Creating bucket: {bucket_name}")
                    try:
                        if self.project_id:
                            self.client.create_bucket(bucket, project=self.project_id)
                        else:
                            self.client.create_bucket(bucket)
                    except Exception as e:
                        return self._handle_provider_error(
                            "creating",
                            bucket_name,
                            e,
                            raise_error=True,
                            resource_type="bucket",
                        )
            except Exception as e:
                return self._handle_provider_error(
                    "accessing",
                    bucket_name,
                    e,
                    raise_error=True,
                    resource_type="bucket",
                )

            # Get blob
            blob = bucket.blob(blob_path)

            # Upload blob
            try:
                blob.upload_from_string(data)
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
                self.log_debug(f"Bucket not found: {bucket_name}")
                return False

            # Get blob
            blob = bucket.blob(blob_path)

            # Check if blob exists
            exists = blob.exists()
            if not exists:
                self.log_debug(f"Blob not found: {blob_path}")
            return exists

        except Exception as e:
            self.log_warning(f"Error checking blob existence {uri}: {str(e)}")
            return False

    def _parse_gs_uri(self, uri: str) -> Tuple[str, str]:
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
                raise ValueError(
                    f"No bucket specified in URI and no default bucket configured: {uri}"
                )

        # Check if bucket name is mapped in configuration
        bucket_mapping = self.config.get("buckets", {})
        if bucket_name in bucket_mapping:
            bucket_name = bucket_mapping[bucket_name]

        # Get blob path
        blob_path = parts["path"]
        if not blob_path:
            raise ValueError(f"No blob path specified in URI: {uri}")

        return bucket_name, blob_path
