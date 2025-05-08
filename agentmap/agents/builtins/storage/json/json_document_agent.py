"""
JSON document storage agent implementation.

This module provides JSON-specific implementations of document storage operations,
supporting reading from and writing to JSON files with path-based access.
"""
from __future__ import annotations

import contextlib
import json
import os
from collections.abc import Generator
from pathlib import Path
from typing import Any, Dict, List, Optional, TextIO, Union

from agentmap.agents.builtins.storage.base_document_storage_agent import BaseDocumentStorageAgent
from agentmap.agents.builtins.storage.document_path_mixin import DocumentPathMixin
from agentmap.logging import get_logger

logger = get_logger(__name__)


class JSONDocumentAgent(BaseDocumentStorageAgent, DocumentPathMixin):
    """
    Base class for JSON document storage operations.
    
    Provides shared functionality for reading and writing JSON documents,
    with support for path-based access and document queries.
    """
    
    def _initialize_client(self) -> None:
        """No client initialization needed for JSON files."""
        pass
    
    @contextlib.contextmanager
    def _open_json_file(self, file_path: str, mode: str = 'r') -> Generator[TextIO, None, None]:
        """
        Context manager for safely opening JSON files.
        
        Args:
            file_path: Path to the JSON file
            mode: File open mode ('r' for reading, 'w' for writing)
            
        Yields:
            File object
                
        Raises:
            FileNotFoundError: If the file doesn't exist (in read mode)
            PermissionError: If the file can't be accessed
            IOError: For other file-related errors
        """
        try:
            # Ensure directory exists for write operations
            if 'w' in mode:
                directory = os.path.dirname(os.path.abspath(file_path))
                os.makedirs(directory, exist_ok=True)
                
            with open(file_path, mode, encoding='utf-8') as f:
                yield f
        except FileNotFoundError:
            if 'r' in mode:
                logger.debug(f"JSON file not found: {file_path}")
                raise
            else:
                # For write mode, create the file
                with open(file_path, 'w', encoding='utf-8') as f:
                    yield f
        except (PermissionError, IOError) as e:
            logger.error(f"File access error for {file_path}: {str(e)}")
            raise
    
    def _read_json_file(self, file_path: str) -> Any:
        """
        Read and parse a JSON file.
        
        Args:
            file_path: Path to the JSON file
            
        Returns:
            Parsed JSON data
            
        Raises:
            FileNotFoundError: If the file doesn't exist
            ValueError: If the file contains invalid JSON
        """
        try:
            with self._open_json_file(file_path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.debug(f"JSON file not found: {file_path}")
            raise FileNotFoundError(f"File not found: {file_path}")
        except json.JSONDecodeError as e:
            error_msg = f"Invalid JSON in {file_path}: {str(e)}"
            logger.error(error_msg)
            raise ValueError(error_msg)
    
    def _write_json_file(self, file_path: str, data: Any, indent: int = 2) -> None:
        """
        Write data to a JSON file.
        
        Args:
            file_path: Path to the JSON file
            data: Data to write
            indent: JSON indentation level
            
        Raises:
            PermissionError: If the file can't be written
            TypeError: If the data contains non-serializable objects
        """
        try:
            with self._open_json_file(file_path, 'w') as f:
                json.dump(data, f, indent=indent)
            logger.debug(f"Successfully wrote to {file_path}")
        except TypeError as e:
            error_msg = f"Cannot serialize to JSON: {str(e)}"
            logger.error(error_msg)
            raise ValueError(error_msg)
    
    def _ensure_document_exists(self, collection: str, document_id: str) -> bool:
        """
        Check if a document exists in the JSON file.
        
        Args:
            collection: Path to the JSON file
            document_id: Document ID to check
            
        Returns:
            True if the document exists, False otherwise
        """
        try:
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
        except (FileNotFoundError, ValueError):
            return False
    
    def _apply_document_query(self, data: Any, query: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply query filtering to document data.
        
        Args:
            data: Document data
            query: Query parameters
            
        Returns:
            Dict with filtered data and metadata
        """
        # Handle empty data or query
        if data is None or not query:
            return {"data": data, "count": 0, "is_collection": False}
            
        # Handle different data structures
        if isinstance(data, list):
            return self._filter_list(data, query)
        elif isinstance(data, dict):
            return self._filter_dict(data, query)
            
        # Other data types can't be filtered
        return {"data": data, "count": 0, "is_collection": False}
    
    def _filter_list(self, data: List, query: Dict[str, Any]) -> Dict[str, Any]:
        """
        Filter a list of items based on query parameters.
        
        Args:
            data: List of items
            query: Query parameters
            
        Returns:
            Dict with filtered data and metadata
        """
        # Extract special query parameters
        limit = query.pop("limit", None)
        offset = query.pop("offset", 0)
        sort_field = query.pop("sort", None)
        sort_order = query.pop("order", "asc").lower()
        
        # Apply field filtering
        result = data
        if query:  # Only filter if there are query parameters remaining
            result = [
                item for item in result 
                if isinstance(item, dict) and 
                all(
                    item.get(field) == value 
                    for field, value in query.items()
                )
            ]
        
        # Apply sorting
        if sort_field and result:
            reverse = (sort_order == "desc")
            result.sort(
                key=lambda x: x.get(sort_field) if isinstance(x, dict) else None,
                reverse=reverse
            )
        
        # Apply pagination
        if offset and isinstance(offset, int) and offset > 0:
            result = result[offset:]
            
        if limit and isinstance(limit, int) and limit > 0:
            result = result[:limit]
            
        return {
            "data": result,
            "count": len(result),
            "is_collection": True
        }
    
    def _filter_dict(self, data: Dict, query: Dict[str, Any]) -> Dict[str, Any]:
        """
        Filter a dictionary based on query parameters.
        
        Args:
            data: Dictionary
            query: Query parameters
            
        Returns:
            Dict with filtered data and metadata
        """
        # Extract special query parameters
        limit = query.pop("limit", None)
        offset = query.pop("offset", 0)
        
        # Filter based on field values
        result = {}
        for key, value in data.items():
            if isinstance(value, dict) and all(
                value.get(field) == query_value 
                for field, query_value in query.items()
            ):
                result[key] = value
        
        # Apply pagination to keys
        keys = list(result.keys())
        
        if offset and isinstance(offset, int) and offset > 0:
            keys = keys[offset:]
            
        if limit and isinstance(limit, int) and limit > 0:
            keys = keys[:limit]
            
        # Rebuild filtered dictionary
        if offset or limit:
            result = {k: result[k] for k in keys}
            
        return {
            "data": result,
            "count": len(result),
            "is_collection": True
        }
        
    def _apply_document_path(self, data: Any, path: str) -> Any:
        """
        Apply a path to extract data from a document.
        
        Args:
            data: Document data
            path: Path to extract
            
        Returns:
            Data at the specified path
        """
        # Use the DocumentPathMixin implementation
        return self._apply_path(data, path)
    
    def _update_document_path(self, data: Any, path: str, value: Any) -> Any:
        """
        Update data at a specific path.
        
        Args:
            data: Document data
            path: Path to update
            value: New value
            
        Returns:
            Updated document
        """
        # Use the DocumentPathMixin implementation
        return self._update_path(data, path, value)
 files."""
        pass
    
    @contextlib.contextmanager
    def _open_json_file(self, file_path: str, mode: str = 'r') -> Generator[TextIO, None, None]:
        """
        Context manager for safely opening JSON files.
        
        Args:
            file_path: Path to the JSON file
            mode: File open mode ('r' for reading, 'w' for writing)
            
        Yields:
            File object
                
        Raises:
            FileNotFoundError: If the file doesn't exist (in read mode)
            PermissionError: If the file can't be accessed
            IOError: For other file-related errors
        """
        try:
            # Ensure directory exists for write operations
            if 'w' in mode:
                directory = os.path.dirname(os.path.abspath(file_path))
                os.makedirs(directory, exist_ok=True)
                
            with open(file_path, mode, encoding='utf-8') as f:
                yield f
        except FileNotFoundError:
            if 'r' in mode:
                logger.debug(f"JSON file not found: {file_path}")
                raise
            else:
                # For write mode, create the file
                with open(file_path, 'w', encoding='utf-8') as f:
                    yield f
        except (PermissionError, IOError) as e:
            logger.error(f"File access error for {file_path}: {str(e)}")
            raise
    
    def _read_json_file(self, file_path: str) -> Any:
        """
        Read and parse a JSON file.
        
        Args:
            file_path: Path to the JSON file
            
        Returns:
            Parsed JSON data
            
        Raises:
            FileNotFoundError: If the file doesn't exist
            ValueError: If the file contains invalid JSON
        """
        try:
            with self._open_json_file(file_path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.debug(f"JSON file not found: {file_path}")
            raise FileNotFoundError(f"File not found: {file_path}")
        except json.JSONDecodeError as e:
            error_msg = f"Invalid JSON in {file_path}: {str(e)}"
            logger.error(error_msg)
            raise ValueError(error_msg)
    
    def _write_json_file(self, file_path: str, data: Any, indent: int = 2) -> None:
        """
        Write data to a JSON file.
        
        Args:
            file_path: Path to the JSON file
            data: Data to write
            indent: JSON indentation level
            
        Raises:
            PermissionError: If the file can't be written
            TypeError: If the data contains non-serializable objects
        """
        try:
            with self._open_json_file(file_path, 'w') as f:
                json.dump(data, f, indent=indent)
            logger.debug(f"Successfully wrote to {file_path}")
        except TypeError as e:
            error_msg = f"Cannot serialize to JSON: {str(e)}"
            logger.error(error_msg)
            raise ValueError(error_msg)
    
    def _ensure_document_exists(self, collection: str, document_id: str) -> bool:
        """
        Check if a document exists in the JSON file.
        
        Args:
            collection: Path to the JSON file
            document_id: Document ID to check
            
        Returns:
            True if the document exists, False otherwise
        """
        try:
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
        except (FileNotFoundError, ValueError):
            return False
    
    def _apply_document_query(self, data: Any, query: Dict[str, Any]) -> Any:
        """
        Apply query filtering to document data.
        
        Args:
            data: Document data
            query: Query parameters
            
        Returns:
            Filtered data
        """
        # Handle empty data or query
        if data is None or not query:
            return data
            
        # Handle different data structures
        if isinstance(data, list):
            return self._filter_list(data, query)
        elif isinstance(data, dict):
            return self._filter_dict(data, query)
            
        # Other data types can't be filtered
        return data
    
    def _filter_list(self, data: List, query: Dict[str, Any]) -> Dict[str, Any]:
        """
        Filter a list of items based on query parameters.
        
        Args:
            data: List of items
            query: Query parameters
            
        Returns:
            Dict with filtered data and metadata
        """
        # Extract special query parameters
        limit = query.pop("limit", None)
        offset = query.pop("offset", 0)
        sort_field = query.pop("sort", None)
        sort_order = query.pop("order", "asc").lower()
        
        # Apply field filtering
        result = data
        if query:  # Only filter if there are query parameters remaining
            result = [
                item for item in result 
                if isinstance(item, dict) and 
                all(
                    item.get(field) == value 
                    for field, value in query.items()
                )
            ]
        
        # Apply sorting
        if sort_field and result:
            reverse = (sort_order == "desc")
            result.sort(
                key=lambda x: x.get(sort_field) if isinstance(x, dict) else None,
                reverse=reverse
            )
        
        # Apply pagination
        if offset and isinstance(offset, int) and offset > 0:
            result = result[offset:]
            
        if limit and isinstance(limit, int) and limit > 0:
            result = result[:limit]
            
        return {
            "data": result,
            "count": len(result),
            "is_collection": True
        }
    
    def _filter_dict(self, data: Dict, query: Dict[str, Any]) -> Dict[str, Any]:
        """
        Filter a dictionary based on query parameters.
        
        Args:
            data: Dictionary
            query: Query parameters
            
        Returns:
            Dict with filtered data and metadata
        """
        # Extract special query parameters
        limit = query.pop("limit", None)
        offset = query.pop("offset", 0)
        
        # Filter based on field values
        result = {}
        for key, value in data.items():
            if isinstance(value, dict) and all(
                value.get(field) == query_value 
                for field, query_value in query.items()
            ):
                result[key] = value
        
        # Apply pagination to keys
        keys = list(result.keys())
        
        if offset and isinstance(offset, int) and offset > 0:
            keys = keys[offset:]
            
        if limit and isinstance(limit, int) and limit > 0:
            keys = keys[:limit]
            
        # Rebuild filtered dictionary
        if offset or limit:
            result = {k: result[k] for k in keys}
            
        return {
            "data": result,
            "count": len(result),
            "is_collection": True
        }