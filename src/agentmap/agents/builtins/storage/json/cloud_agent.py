"""
Cloud-enabled JSON document agent implementation.

This module extends the standard JSON document agent to work with
cloud blob storage services like Azure Blob Storage, AWS S3, and Google Cloud Storage.
"""
from __future__ import annotations

import json
from typing import Any, Dict, Optional, Union

from agentmap.agents.builtins.storage.json.base_agent import JSONDocumentAgent
from agentmap.agents.builtins.storage.blob import (
    get_connector_for_uri,
    normalize_json_uri
)
from agentmap.config import load_storage_config
from agentmap.exceptions import StorageConnectionError, StorageOperationError


class JSONCloudDocumentAgent(JSONDocumentAgent):
    """
    JSON document agent with cloud storage support.

    This agent extends the standard JSON document agent with support for
    cloud blob storage services like Azure Blob Storage, AWS S3, and Google Cloud Storage.

    Cloud storage URIs are specified in the collection parameter:
    - Azure: azure://container/path/to/blob.json
    - AWS S3: s3://bucket/path/to/object.json
    - GCP: gs://bucket/path/to/blob.json
    """

    def __init__(self, name: str, prompt: str, context: Optional[Dict[str, Any]] = None):
        """
        Initialize the cloud-enabled JSON document agent.

        Args:
            name: Name of the agent node
            prompt: Document path or collection name
            context: Additional context including input/output field configuration
        """
        super().__init__(name, prompt, context)
        self._connectors = {}  # Cache for connectors
        self._storage_config = None

    @property
    def storage_config(self) -> Dict[str, Any]:
        """
        Get the JSON storage configuration.
        
        Returns:
            JSON storage configuration dictionary
        """
        if self._storage_config is None:
            self._storage_config = load_storage_config().get("json", {})
        return self._storage_config

    def _log_operation_start(self, collection: str, inputs: Dict[str, Any]) -> None:
        """
        Log the start of a cloud storage operation.
        
        Args:
            collection: Collection identifier or URI
            inputs: Input dictionary
        """
        # Normalize URI for better logging
        uri = self._resolve_collection_path(collection)
        scheme = uri.split("://")[0] if "://" in uri else "file"
        
        operation = "read" if hasattr(self, "_read_document") else "write"
        self.log_debug(f"[{self.__class__.__name__}] Starting cloud {operation} operation on {scheme}://{uri.split('://')[-1]}")

    def _resolve_collection_path(self, collection: str) -> str:
        """
        Resolve a collection name to an actual storage path using configuration.

        Args:
            collection: Collection name or path

        Returns:
            Resolved path (URI)
        """
        # Check if this is a named collection in the config
        collections = self.storage_config.get("collections", {})
        if collection in collections:
            return collections[collection]

        return collection

    def _get_connector_for_collection(self, collection: str) -> Any:
        """
        Get the appropriate storage connector for a collection.

        Args:
            collection: Collection name or URI

        Returns:
            Storage connector instance

        Raises:
            StorageConnectionError: If connector initialization fails
        """
        # Resolve collection to actual URI
        uri = self._resolve_collection_path(collection)

        # Ensure URI has proper extension
        uri = normalize_json_uri(uri)

        # Check if we already have a connector for this URI scheme
        scheme = uri.split("://")[0] if "://" in uri else "file"
        if scheme in self._connectors:
            return self._connectors[scheme]

        # Create a new connector
        try:
            connector = get_connector_for_uri(uri, self.storage_config)
            # Cache the connector
            self._connectors[scheme] = connector
            return connector
        except Exception as e:
            self.log_error(f"Failed to get connector for {uri}: {str(e)}")
            raise StorageConnectionError(f"Failed to initialize storage connector: {str(e)}")

    def _read_json_file(self, collection: str) -> Any:
        """
        Read JSON from cloud or local storage.

        Args:
            collection: Collection name or URI

        Returns:
            Parsed JSON data

        Raises:
            FileNotFoundError: If the file doesn't exist
            ValueError: If the file contains invalid JSON
        """
        try:
            # Get the appropriate connector
            connector = self._get_connector_for_collection(collection)

            # Resolve collection to actual URI
            uri = self._resolve_collection_path(collection)

            # Ensure URI has proper extension
            uri = normalize_json_uri(uri)

            # Read the blob
            json_bytes = connector.read_blob(uri)

            # Parse JSON
            try:
                return json.loads(json_bytes.decode('utf-8'))
            except json.JSONDecodeError as e:
                self.log_error(f"Invalid JSON in {uri}: {str(e)}")
                raise ValueError(f"Invalid JSON in {uri}: {str(e)}")

        except FileNotFoundError:
            self.log_error(f"File not found: {collection}")
            raise
        except Exception as e:
            if isinstance(e, (FileNotFoundError, ValueError)):
                raise
            self.log_error(f"Error reading JSON from {collection}: {str(e)}")
            raise StorageOperationError(f"Failed to read JSON from {collection}: {str(e)}")

    def _write_json_file(self, collection: str, data: Any, indent: int = 2) -> None:
        """
        Write JSON to cloud or local storage.

        Args:
            collection: Collection name or URI
            data: Data to write
            indent: JSON indentation level

        Raises:
            StorageOperationError: If the write operation fails
        """
        try:
            # Get the appropriate connector
            connector = self._get_connector_for_collection(collection)

            # Resolve collection to actual URI
            uri = self._resolve_collection_path(collection)

            # Ensure URI has proper extension
            uri = normalize_json_uri(uri)

            # Convert to JSON string
            try:
                json_str = json.dumps(data, indent=indent)
            except (TypeError, ValueError) as e:
                self.log_error(f"Cannot serialize to JSON: {str(e)}")
                raise ValueError(f"Cannot serialize to JSON: {str(e)}")

            # Write the blob
            connector.write_blob(uri, json_str.encode('utf-8'))

        except Exception as e:
            if isinstance(e, ValueError):
                raise
            self.log_error(f"Error writing JSON to {collection}: {str(e)}")
            raise StorageOperationError(f"Failed to write JSON to {collection}: {str(e)}")

    def _ensure_document_exists(self, collection: str, document_id: str) -> bool:
        """
        Check if a document exists.

        Args:
            collection: Collection name or URI
            document_id: Document ID

        Returns:
            True if the document exists, False otherwise
        """
        try:
            # First check if the collection exists
            connector = self._get_connector_for_collection(collection)
            uri = self._resolve_collection_path(collection)
            uri = normalize_json_uri(uri)

            if not connector.blob_exists(uri):
                return False

            # If collection exists, check if document exists within it
            data = self._read_json_file(collection)

            # Check different JSON structures
            if isinstance(data, dict):
                return document_id in data
            elif isinstance(data, list):
                return any(
                    isinstance(item, dict) and
                    item.get("id") == document_id
                    for item in data
                )
            return False
        except Exception:
            return False
    
    def _handle_operation_error(
        self, 
        error: Exception, 
        collection: str, 
        inputs: Dict[str, Any]
    ) -> Any:
        """
        Handle cloud storage operation errors.
        
        Args:
            error: The exception that occurred
            collection: Collection identifier or URI
            inputs: Input dictionary
            
        Returns:
            Error result
        """
        # Normalize URI for better error reporting
        try:
            uri = self._resolve_collection_path(collection)
            scheme = uri.split("://")[0] if "://" in uri else "file"
            resource = uri.split("://")[-1]
        except Exception:
            scheme = "unknown"
            resource = collection
            
        if isinstance(error, FileNotFoundError):
            error_msg = f"Resource not found: {resource}"
        elif isinstance(error, StorageConnectionError):
            error_msg = f"Connection error for {scheme} storage: {str(error)}"
        elif isinstance(error, StorageOperationError):
            error_msg = f"Operation failed on {scheme} storage: {str(error)}"
        else:
            error_msg = f"Error accessing {scheme} storage: {str(error)}"
            
        self.log_error(f"[{self.__class__.__name__}] {error_msg}")
        
        return {
            "success": False,
            "error": error_msg,
            "collection": collection
        }