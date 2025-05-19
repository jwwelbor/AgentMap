"""
Vector writer agent implementation.

This module provides an agent for storing documents in vector databases,
using LangChain integrations and standardized result formatting.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

from agentmap.agents.builtins.storage.base_storage_agent import (
    DocumentResult, log_operation)
from agentmap.agents.builtins.storage.mixins import WriterOperationsMixin
from agentmap.agents.builtins.storage.vector.base_agent import VectorAgent
from agentmap.logging import get_logger

logger = get_logger(__name__)


class VectorWriterAgent(VectorAgent, WriterOperationsMixin):
    """
    Agent for storing documents in vector databases.
    
    Implements document storage operations for vector databases using LangChain,
    with standardized input validation and result formatting.
    """
    
    def __init__(self, name: str, prompt: str, context: Optional[Dict[str, Any]] = None):
        """
        Initialize the vector writer agent.
        
        Args:
            name: Name of the agent node
            prompt: Prompt or instruction
            context: Additional context including:
                - should_persist: Whether to persist the vector store (default: True)
                - input_fields: Input fields to use (default: ["docs"])
                - output_field: Output field to return results in (default: "result")
        """
        super().__init__(name, prompt, context)
        self.should_persist = context.get("should_persist", True) if context else True
        self.input_fields = context.get("input_fields", ["docs"]) if context else ["docs"]
    
    def _log_operation_start(self, collection: str, inputs: Dict[str, Any]) -> None:
        """
        Log the start of a vector storage operation.
        
        Args:
            collection: Collection identifier or operation name
            inputs: Input dictionary
        """
        docs = inputs.get(self.input_fields[0])
        doc_count = (
            len(docs) if isinstance(docs, list) 
            else "1" if docs is not None
            else "0"
        )
        self.log_debug(f"[{self.__class__.__name__}] Starting vector storage with {doc_count} document(s)")
    
    def _validate_inputs(self, inputs: Dict[str, Any]) -> None:
        """
        Validate inputs for vector writer operations.
        
        Args:
            inputs: Input dictionary
            
        Raises:
            ValueError: If inputs are invalid
        """
        super()._validate_inputs(inputs)
        
        # Check for required input field
        input_field = self.input_fields[0]
        if inputs.get(input_field) is None:
            raise ValueError(f"No documents provided in '{input_field}' field")
    
    def _execute_operation(self, collection: str, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute vector storage operation.
        
        Args:
            collection: Collection identifier (not used for vector operations)
            inputs: Input dictionary
            
        Returns:
            Storage operation result
        """
        # Get vector store
        vector_store = self._get_or_create_vectorstore(inputs)
        if isinstance(vector_store, dict) and "error" in vector_store:
            return vector_store  # Return error if vector store creation failed
        
        # Get documents from inputs
        docs_field = self.input_fields[0]
        docs = inputs.get(docs_field)
        if not docs:
            return self._format_vector_result(
                success=False,
                error="No documents provided"
            )
        
        try:
            # Handle different document formats
            if hasattr(docs, 'page_content'):  # Single LangChain document
                ids = vector_store.add_documents([docs])
                stored_count = 1
            elif isinstance(docs, list) and docs and hasattr(docs[0], 'page_content'):
                # List of LangChain documents
                ids = vector_store.add_documents(docs)
                stored_count = len(docs)
            else:
                # Convert to text and add
                if not isinstance(docs, list):
                    docs = [docs]
                ids = vector_store.add_texts([str(doc) for doc in docs])
                stored_count = len(docs)
            
            # Persist changes
            if self.should_persist and hasattr(vector_store, "persist"):
                vector_store.persist()
                
            return self._format_vector_result(
                success=True,
                stored_count=stored_count,
                ids=ids,
                persist_directory=self.persist_directory if self.should_persist else None
            )
        except Exception as e:
            self.log_error(f"Vector storage error: {str(e)}")
            return self._format_vector_result(
                success=False,
                error=f"Failed to store documents: {str(e)}"
            )