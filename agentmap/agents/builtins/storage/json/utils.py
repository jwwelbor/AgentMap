"""
JSON utilities for document storage operations.

This module provides common utilities for working with JSON files,
including reading, writing, and document manipulation.
"""
from __future__ import annotations

import contextlib
import json
import os
from collections.abc import Generator
from pathlib import Path
from typing import Any, Dict, List, Optional, TextIO, Union

from agentmap.logging import get_logger

logger = get_logger(__name__)


@contextlib.contextmanager
def open_json_file(file_path: str, mode: str = 'r') -> Generator[TextIO, None, None]:
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


def read_json_file(file_path: str) -> Any:
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
        with open_json_file(file_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        logger.debug(f"JSON file not found: {file_path}")
        raise FileNotFoundError(f"File not found: {file_path}")
    except json.JSONDecodeError as e:
        error_msg = f"Invalid JSON in {file_path}: {str(e)}"
        logger.error(error_msg)
        raise ValueError(error_msg)


def write_json_file(file_path: str, data: Any, indent: int = 2) -> None:
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
        with open_json_file(file_path, 'w') as f:
            json.dump(data, f, indent=indent)
        logger.debug(f"Successfully wrote to {file_path}")
    except TypeError as e:
        error_msg = f"Cannot serialize to JSON: {str(e)}"
        logger.error(error_msg)
        raise ValueError(error_msg)


def find_document_by_id(data: Any, document_id: str) -> Optional[Dict]:
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


def ensure_id_in_document(data: Any, document_id: str) -> dict:
    """
    Ensure the document has the correct ID field.
    
    Args:
        data: Document data
        document_id: Document ID
        
    Returns:
        Document with ID field
    """
    if not isinstance(data, dict):
        return {"id": document_id, "value": data}
    
    result = data.copy()
    result["id"] = document_id
    return result


def create_initial_structure(data: Any, document_id: str) -> Any:
    """
    Create an initial data structure for a document.
    
    Args:
        data: Document data
        document_id: Document ID
        
    Returns:
        New data structure
    """
    if isinstance(data, dict):
        # For dict data, create a list with ID field
        doc_with_id = data.copy()
        doc_with_id["id"] = document_id
        return [doc_with_id]
    else:
        # For other data, use a dict with document ID as key
        return {document_id: data}


def add_document_to_structure(
    data: Any, 
    doc_data: Any, 
    document_id: str
) -> Any:
    """
    Add a document to an existing data structure.
    
    Args:
        data: Current data structure
        doc_data: Document data
        document_id: Document ID
        
    Returns:
        Updated data structure
    """
    if isinstance(data, dict):
        # Add to dictionary
        data[document_id] = doc_data
        return data
    
    elif isinstance(data, list):
        # Add to list with ID
        if isinstance(doc_data, dict):
            # Make sure document has ID
            doc_with_id = doc_data.copy()
            doc_with_id["id"] = document_id
            data.append(doc_with_id)
        else:
            # Wrap non-dict data
            data.append({"id": document_id, "value": doc_data})
        return data
    
    else:
        # Create new structure
        return create_initial_structure(doc_data, document_id)