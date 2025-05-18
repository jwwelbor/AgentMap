"""
Vector reader agent implementation.

This module provides an agent for searching vector databases with similarity search,
using LangChain integrations and standardized result formatting.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

from agentmap.agents.builtins.storage.base_storage_agent import (
    DocumentResult, log_operation)
from agentmap.agents.builtins.storage.mixins import ReaderOperationsMixin
from agentmap.agents.builtins.storage.vector.base_agent import VectorAgent
from agentmap.logging import get_logger

logger = get_logger(__name__)


class VectorReaderAgent(VectorAgent, ReaderOperationsMixin):
    """
    Agent for searching vector databases with similarity search.
    
    Implements vector-based similarity search using LangChain integrations,
    with standardized input validation and result formatting.
    """
    
    def __init__(self, name: str, prompt: str, context: Optional[Dict[str, Any]] = None):
        """
        Initialize the vector reader agent.
        
        Args:
            name: Name of the agent node
            prompt: Prompt or instruction
            context: Additional context including:
                - k: Number of results to return (default: 4)
                - input_fields: Input fields to use (default: ["query"])
                - output_field: Output field to return results in (default: "result")
        """
        super().__init__(name, prompt, context)
        self.k = int(context.get("k", 4)) if context else 4
        self.metadata_keys = context.get("metadata_keys", None)
    
    def _log_operation_start(self, collection: str, inputs: Dict[str, Any]) -> None:
        """
        Log the start of a vector search operation.
        
        Args:
            collection: Collection identifier or operation name
            inputs: Input dictionary
        """
        query = inputs.get(self.input_fields[0], "")
        query_preview = query[:30] + "..." if len(query) > 30 else query
        logger.debug(f"[{self.__class__.__name__}] Starting vector search with query: {query_preview}")
    
    def _execute_operation(self, collection: str, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute vector search operation.
        
        Args:
            collection: Collection identifier (not used for vector operations)
            inputs: Input dictionary
            
        Returns:
            Search operation result
        """
        # Get vector store
        vector_store = self._get_or_create_vectorstore(inputs)
        if isinstance(vector_store, dict) and "error" in vector_store:
            return vector_store  # Return error if vector store creation failed
        
        # Get query from inputs
        query_field = self.input_fields[0]
        query = inputs.get(query_field)
        if not query:
            return self._format_vector_result(
                success=False,
                error="No query provided for vector search"
            )
            
        # Perform search
        try:
            results = vector_store.similarity_search(query, k=self.k)
            
            # Format results
            formatted_results = []
            for doc in results:
                result_item = {"content": doc.page_content}
                
                # Filter metadata keys if specified
                if hasattr(doc, "metadata"):
                    if self.metadata_keys:
                        # Only include specified keys
                        result_item["metadata"] = {
                            k: v for k, v in doc.metadata.items() 
                            if k in self.metadata_keys
                        }
                    else:
                        # Include all metadata
                        result_item["metadata"] = doc.metadata
                
                formatted_results.append(result_item)
            
            # Return formatted results
            return self._format_vector_result(
                success=True,
                query=query,
                results=formatted_results,
                count=len(formatted_results)
            )
        except Exception as e:
            logger.error(f"Vector search error: {str(e)}")
            return self._format_vector_result(
                success=False,
                query=query,
                error=f"Search failed: {str(e)}"
            )