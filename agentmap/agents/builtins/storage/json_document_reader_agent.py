# agentmap/agents/builtins/storage/json_document_reader_agent.py

import functools
import os

from typing import Any, Dict, Optional

from agentmap.agents.builtins.storage.document_reader_agent import \
    DocumentReaderAgent
from agentmap.agents.builtins.storage.json_document_agent import \
    JSONDocumentAgent
from agentmap.logging import get_logger

logger = get_logger(__name__)


def log_operation(func):
    """Decorator to log document operations."""
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        logger.debug(f"[{self.__class__.__name__}] Starting {func.__name__}")
        try:
            result = func(self, *args, **kwargs)
            logger.debug(f"[{self.__class__.__name__}] Completed {func.__name__}")
            return result
        except Exception as e:
            logger.error(f"[{self.__class__.__name__}] Error in {func.__name__}: {str(e)}")
            raise
    return wrapper


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
        data = self._read_json_file(collection)
        if data is None:
            return None
        
        # Process the data based on parameters
        if document_id:
            # Single document lookup
            result_data = self._find_document_by_id(data, document_id)
            if result_data is None:
                return None
            
            # Store ID for envelope
            result_id = document_id
        else:
            # Collection-level operation
            result_data = data
            
            # Apply query filtering if provided
            if query:
                result_data = self._apply_document_query(result_data, query)
            
            # Use collection name or file path as ID
            result_id = os.path.basename(collection)
        
        # Apply path extraction if needed
        if path:
            result_data = self._apply_path(result_data, path)
            if result_data is None:
                return None
            
            # If we extracted by path, the ID should reflect this
            result_id = f"{result_id}.{path}"
        
        # Return raw data if envelope not requested
        if not use_envelope:
            return result_data
        
        # Determine if result is a collection
        is_collection = isinstance(result_data, list)
        
        # Wrap in envelope format
        return {
            "id": result_id,
            "data": result_data,
            "is_collection": is_collection
        }
        
    def _find_document_by_id(self, data: Any, document_id: str) -> Optional[Dict]:
        """Find a document by ID without modifying it."""
        if isinstance(data, dict):
            # Direct key lookup
            if document_id in data:
                return data[document_id]
        
        elif isinstance(data, list):
            # Find in array by id field
            for item in data:
                if isinstance(item, dict) and item.get("id") == document_id:
                    return item
        
        return None