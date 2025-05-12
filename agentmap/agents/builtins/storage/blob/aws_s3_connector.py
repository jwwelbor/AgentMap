"""
AWS S3 connector for JSON storage.

This module provides an AWS-specific implementation of the BlobStorageConnector
interface for reading and writing JSON files in S3 buckets.
"""
from typing import Any, Dict, Optional

from agentmap.agents.builtins.storage.blob.base_connector import BlobStorageConnector
from agentmap.exceptions import StorageConnectionError, StorageOperationError
from agentmap.logging import get_logger

logger = get_logger(__name__)


class AWSS3Connector(BlobStorageConnector):
    """
    AWS S3 connector for cloud storage operations.

    This connector implements the BlobStorageConnector interface for
    AWS S3, supporting both standard credentials and assumed roles.
    """

    URI_SCHEME = "s3"

    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize the AWS S3 connector.

        Args:
            config: AWS S3 configuration with connection details
        """
        super().__init__(config)
        self.region = None
        self.access_key = None
        self.secret_key = None
        self.session_token = None
        self.default_bucket = None

    def _initialize_client(self) -> None:
        """
        Initialize the AWS S3 client.

        Raises:
            StorageConnectionError: If client initialization fails
        """
        try:
            # Import boto3
            try:
                import boto3
                from botocore.exceptions import ClientError
            except ImportError:
                raise StorageConnectionError(
                    "AWS boto3 SDK not installed. "
                    "Please install with: pip install boto3"
                )

            # Extract configuration
            self.region = self.resolve_env_value(
                self.config.get("region", "")
            )
            self.access_key = self.resolve_env_value(
                self.config.get("access_key", "")
            )
            self.secret_key = self.resolve_env_value(
                self.config.get("secret_key", "")
            )
            self.session_token = self.resolve_env_value(
                self.config.get("session_token", "")
            )
            self.default_bucket = self.config.get("default_bucket", "")

            # Create session
            session_kwargs = {}
            if self.region:
                session_kwargs["region_name"] = self.region
            if self.access_key and self.secret_key:
                session_kwargs["aws_access_key_id"] = self.access_key
                session_kwargs["aws_secret_access_key"] = self.secret_key
                if self.session_token:
                    session_kwargs["aws_session_token"] = self.session_token

            # Create client
            self._client = boto3.client("s3", **session_kwargs)
            logger.debug("AWS S3 client initialized")

        except Exception as e:
            logger.error(f"Failed to initialize AWS S3 client: {str(e)}")
            raise StorageConnectionError(f"Failed to initialize AWS S3 client: {str(e)}")

    def read_blob(self, uri: str) -> bytes:
        """
        Read object from S3 bucket.

        Args:
            uri: URI of the S3 object to read

        Returns:
            Object content as bytes

        Raises:
            FileNotFoundError: If the object doesn't exist
            StorageOperationError: For other storage-related errors
        """
        try:
            # Parse URI into bucket and object key
            bucket_name, object_key = self._parse_s3_uri(uri)

            # Get object
            try:
                response = self.client.get_object(Bucket=bucket_name, Key=object_key)
                return response["Body"].read()
            except self.client.exceptions.NoSuchKey:
                logger.error(f"Object not found: {uri}")
                raise FileNotFoundError(f"S3 object not found: {uri}")
            except self.client.exceptions.NoSuchBucket:
                logger.error(f"Bucket not found: {bucket_name}")
                raise FileNotFoundError(f"S3 bucket not found: {bucket_name}")

        except FileNotFoundError:
            raise
        except Exception as e:
            logger.error(f"Error reading S3 object {uri}: {str(e)}")
            raise StorageOperationError(f"Failed to read S3 object {uri}: {str(e)}")

    def write_blob(self, uri: str, data: bytes) -> None:
        """
        Write object to S3 bucket.

        Args:
            uri: URI where the object should be written
            data: Object content as bytes

        Raises:
            StorageOperationError: If the write operation fails
        """
        try:
            # Parse URI into bucket and object key
            bucket_name, object_key = self._parse_s3_uri(uri)

            # Check if bucket exists
            try:
                self.client.head_bucket(Bucket=bucket_name)
            except self.client.exceptions.NoSuchBucket:
                # Create bucket if it doesn't exist
                logger.info(f"Creating bucket: {bucket_name}")
                bucket_params = {"Bucket": bucket_name}
                if self.region:
                    bucket_params["CreateBucketConfiguration"] = {
                        "LocationConstraint": self.region
                    }
                self.client.create_bucket(**bucket_params)
            except Exception as e:
                logger.error(f"Error checking bucket {bucket_name}: {str(e)}")
                raise StorageOperationError(f"Failed to access bucket {bucket_name}: {str(e)}")

            # Put object
            self.client.put_object(
                Bucket=bucket_name,
                Key=object_key,
                Body=data
            )

        except Exception as e:
            logger.error(f"Error writing S3 object {uri}: {str(e)}")
            raise StorageOperationError(f"Failed to write S3 object {uri}: {str(e)}")

    def blob_exists(self, uri: str) -> bool:
        """
        Check if an object exists in S3.

        Args:
            uri: URI to check

        Returns:
            True if the object exists, False otherwise
        """
        try:
            # Parse URI into bucket and object key
            bucket_name, object_key = self._parse_s3_uri(uri)

            # Check if object exists
            try:
                self.client.head_object(Bucket=bucket_name, Key=object_key)
                return True
            except self.client.exceptions.ClientError as e:
                error_code = int(e.response.get("Error", {}).get("Code", 0))
                if error_code == 404:
                    return False
                # Other errors - propagate
                raise

        except Exception as e:
            logger.error(f"Error checking S3 object existence {uri}: {str(e)}")
            return False

    def _parse_s3_uri(self, uri: str) -> tuple[str, str]:
        """
        Parse S3 URI into bucket and object key.

        Args:
            uri: S3 URI

        Returns:
            Tuple of (bucket_name, object_key)

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

        # Get object key
        object_key = parts["path"]
        if not object_key:
            raise ValueError(f"No object key specified in URI: {uri}")

        return bucket_name, object_key