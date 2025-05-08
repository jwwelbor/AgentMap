"""
JSON document reader agent implementation.

This module provides an agent for reading data from JSON files,
with support for document lookups, query filtering, and path extraction.
"""
from __future__ import annotations

import os
import functools
from dataclasses import asdict
from typing import Any, Dict, Optional, Union

from agentmap.agents.builtins.storage.base_document_storage_agent import (
    DocumentReaderAgent, DocumentResult, log_operation)
from agentmap.agents.builtins.storage.json_document_agent import JSONDocumentAgent
from agentmap.logging import get_logger

logger = get_logger(__name__)


class JSONDocumentReaderAgent(DocumentReaderAgent, JSONDocumentAgent):
    """
    Agent for reading data from JSON documents.
    
    Provides functionality for reading from JSON files, including
    document lookups, query filtering, and path extraction.
    """
    
    @log_operation
    def _read_document(
        self, 
        collection: str, 
        document_id: Optional[str] = None, 
        query: Optional[Dict[str, Any]] = None, 
        path: Optional[str] = None,
        use_envelope: bool = True
    ) -> Any:
        """
        Read document(s) from a JSON file.
        
        Args:
            collection: Path to the JSON file
            document_id: Optional document ID
            query: Optional query parameters
            path: Optional path within document
            use_envelope: Whether to wrap results in a consistent envelope structure
            
        Returns:
            Document data, optionally wrapped in an envelope
        """
        # Read the JSON file
        try:
            data = self._read_json_file(collection)
        except FileNotFoundError:
            self._handle_error("File Not Found", f"JSON file not found: {collection}")
        except ValueError as e:
            self._handle_error("Invalid JSON", str(e))
        
        # Process the data based on parameters
        if document_id:
            # Single document lookup
            result_data = self._find_document_by_id(data, document_id)
            if result_data is None:
                if use_envelope:
                    return DocumentResult(
                        success=False,
                        document_id=document_id,
                        error="Document not found"
                    ).to_dict()
                return None
            
            # Store ID for envelope
            result_id = document_id
            is_collection = False
        else:
            # Collection-level operation
            result_data = data
            
            # Apply query filtering if provided
            if query:
                filtered_result = self._apply_document_query(result_data, query)
                result_data = filtered_result.get("data", result_data)
                is_collection = filtered_result.get("is_collection", True)
            else:
                is_collection = True
            
            # Use collection name or file path as ID
            result_id = os.path.basename(collection)
        
        # Apply path extraction if needed
        if path:
            result_data = self._apply_path(result_data, path)
            if result_data is None:
                if use_envelope:
                    return DocumentResult(
                        success=False,
                        path=path,
                        error="Path not found"
                    ).to_dict()
                return None
            
            # If we extracted by path, the ID should reflect this
            if document_id:
                # Keep the document ID as is
                pass
            else:
                # Append the path to the collection ID
                result_id = f"{result_id}.{path}"
            
            # Path extraction typically returns a non-collection result
            is_collection = isinstance(result_data, list)
        
        # Return raw data if envelope not requested
        if not use_envelope:
            return result_data
        
        # Wrap in envelope format
        return DocumentResult(
            success=True,
            document_id=result_id,
            data=result_data,
            is_collection=is_collection
        ).to_dict()
        
    def _find_document_by_id(self, data: Any, document_id: str) -> Optional[Dict]:
        """
        Find a document by ID in different data structures.
        
        Args:
            data: JSON data structure
            document_id: Document ID to find
            
        Returns:
            Document data or None if not found
        """
        if not data:
            return None
            
        if isinstance(data, dict):
            # Direct key lookup
            return data.get(document_id)
        
        elif isinstance(data, list):
            # Find in array by id field
            for item in data:
                if isinstance(item, dict) and item.get("id") == document_id:
                    return item
        
        return None