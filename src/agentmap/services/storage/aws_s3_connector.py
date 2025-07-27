"""
AWS S3 connector for JSON storage.

This module provides an AWS-specific implementation of the BlobStorageConnector
interface for reading and writing JSON files in S3 buckets.
"""

from typing import Any, Dict, Tuple

from agentmap.exceptions import StorageConnectionError, StorageOperationError
from agentmap.services.storage.base_connector import BlobStorageConnector


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
        self.boto_exceptions = None

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
                from botocore.exceptions import ClientError, NoCredentialsError

                # Store exception classes for future reference
                self.boto_exceptions = {
                    "ClientError": ClientError,
                    "NoCredentialsError": NoCredentialsError,
                }
            except ImportError:
                raise StorageConnectionError(
                    "AWS boto3 SDK not installed. "
                    "Please install with: pip install boto3"
                )

            # Extract configuration
            self.region = self.resolve_env_value(self.config.get("region", ""))
            self.access_key = self.resolve_env_value(self.config.get("access_key", ""))
            self.secret_key = self.resolve_env_value(self.config.get("secret_key", ""))
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
            try:
                self._client = boto3.client("s3", **session_kwargs)
                self.log_debug("AWS S3 client initialized successfully")
            except NoCredentialsError:
                raise StorageConnectionError(
                    "AWS credentials not found. Please configure credentials via "
                    "environment variables, config file, or IAM role."
                )

        except Exception as e:
            self.log_error(f"Failed to initialize AWS S3 client: {str(e)}")
            raise StorageConnectionError(
                f"Failed to initialize AWS S3 client: {str(e)}"
            )

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
                return self._handle_provider_error(
                    "reading",
                    uri,
                    Exception("Object not found"),
                    raise_error=True,
                    resource_type="object",
                )
            except self.client.exceptions.NoSuchBucket:
                return self._handle_provider_error(
                    "reading",
                    uri,
                    Exception("Bucket not found"),
                    raise_error=True,
                    resource_type="bucket",
                )
            except Exception as e:
                return self._handle_provider_error(
                    "reading", uri, e, raise_error=True, resource_type="object"
                )

        except (FileNotFoundError, StorageOperationError, StorageConnectionError):
            # Re-raise standard exceptions
            raise
        except Exception as e:
            return self._handle_provider_error(
                "reading", uri, e, raise_error=True, resource_type="object"
            )

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
            except Exception as e:
                # Check error type to determine if bucket doesn't exist
                if (
                    hasattr(e, "response")
                    and e.response.get("Error", {}).get("Code") == "404"
                ):
                    # Create bucket if it doesn't exist
                    self.log_info(f"Creating bucket: {bucket_name}")
                    bucket_params = {"Bucket": bucket_name}
                    if self.region and self.region != "us-east-1":
                        bucket_params["CreateBucketConfiguration"] = {
                            "LocationConstraint": self.region
                        }
                    try:
                        self.client.create_bucket(**bucket_params)
                    except Exception as bucket_error:
                        return self._handle_provider_error(
                            "creating",
                            bucket_name,
                            bucket_error,
                            raise_error=True,
                            resource_type="bucket",
                        )
                else:
                    # Some other error accessing the bucket
                    return self._handle_provider_error(
                        "accessing",
                        bucket_name,
                        e,
                        raise_error=True,
                        resource_type="bucket",
                    )

            # Put object
            try:
                self.client.put_object(Bucket=bucket_name, Key=object_key, Body=data)
            except Exception as e:
                return self._handle_provider_error(
                    "writing", uri, e, raise_error=True, resource_type="object"
                )

        except (StorageOperationError, StorageConnectionError):
            # Re-raise standard exceptions
            raise
        except Exception as e:
            return self._handle_provider_error(
                "writing", uri, e, raise_error=True, resource_type="object"
            )

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

            # Check if bucket exists
            try:
                self.client.head_bucket(Bucket=bucket_name)
            except Exception:
                self.log_debug(f"Bucket not found: {bucket_name}")
                return False

            # Check if object exists
            try:
                self.client.head_object(Bucket=bucket_name, Key=object_key)
                return True
            except Exception as e:
                # Check for 404 error code
                if (
                    hasattr(e, "response")
                    and e.response.get("Error", {}).get("Code") == "404"
                ):
                    self.log_debug(f"Object not found: {object_key}")
                    return False
                # For other errors, log warning and return False
                self.log_warning(f"Error checking if object exists at {uri}: {str(e)}")
                return False

        except Exception as e:
            self.log_warning(f"Error checking S3 object existence {uri}: {str(e)}")
            return False

    def _parse_s3_uri(self, uri: str) -> Tuple[str, str]:
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
                raise ValueError(
                    f"No bucket specified in URI and no default bucket configured: {uri}"
                )

        # Check if bucket name is mapped in configuration
        bucket_mapping = self.config.get("buckets", {})
        if bucket_name in bucket_mapping:
            bucket_name = bucket_mapping[bucket_name]

        # Get object key
        object_key = parts["path"]
        if not object_key:
            raise ValueError(f"No object key specified in URI: {uri}")

        return bucket_name, object_key
