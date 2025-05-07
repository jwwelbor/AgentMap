# agentmap/agents/builtins/storage/json_document_reader_agent.py

import functools
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
        path: Optional[str] = None
    ) -> Any:
        """
        Read document(s) from a JSON file.
        
        Args:
            collection: Path to the JSON file
            document_id: Optional document ID
            query: Optional query parameters
            path: Optional path within document
            
        Returns:
            Document data or None if not found
        """
        # Read the JSON file
        data = self._read_json_file(collection)
        if data is None:
            return None
        
        # Handle document ID lookup
        if document_id:
            data = self._find_document_by_id(data, document_id)
            if data is None:
                return None
        
        # Apply query filtering
        if query:
            data = self._apply_document_query(data, query)
        
        # Apply path extraction
        if path:
            data = self._apply_path(data, path)
        
        return data
    
    def _find_document_by_id(self, data: Any, document_id: str) -> Optional[Dict]:
        """
        Find a document by ID in different data structures.
        
        Args:
            data: JSON data structure
            document_id: Document ID to find
            
        Returns:
            Document data or None if not found
        """
        if isinstance(data, dict):
            # Direct key lookup
            if document_id in data:
                doc = data[document_id]
                # Add ID to result if not present
                if isinstance(doc, dict) and "id" not in doc:
                    doc = doc.copy()
                    doc["id"] = document_id
                return doc
        
        elif isinstance(data, list):
            # Find in array by id field
            for item in data:
                if isinstance(item, dict) and item.get("id") == document_id:
                    return item
        
        return None