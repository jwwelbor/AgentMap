"""
Firebase document storage agents for AgentMap.

This module provides agents for reading from and writing to Firebase databases,
supporting both Firestore and Realtime Database.
"""

from agentmap.agents.builtins.storage.firebase.base_agent import FirebaseDocumentAgent
from agentmap.agents.builtins.storage.firebase.reader import FirebaseDocumentReaderAgent
from agentmap.agents.builtins.storage.firebase.writer import FirebaseDocumentWriterAgent
from agentmap.agents.builtins.storage.firebase.utils import (
    get_firebase_config,
    initialize_firebase_app,
    resolve_firebase_collection,
    convert_firebase_error,
    format_document_snapshot,
    format_query_results
)

# Register agents with the registry when available
try:
    from agentmap.agents.registry import register_agent
    
    # Register the Firebase agents
    register_agent("firebase_reader", FirebaseDocumentReaderAgent)
    register_agent("firebase_writer", FirebaseDocumentWriterAgent)
    
    _registry_available = True
except ImportError:
    _registry_available = False

__all__ = [
    'FirebaseDocumentAgent',
    'FirebaseDocumentReaderAgent',
    'FirebaseDocumentWriterAgent',
    'get_firebase_config',
    'initialize_firebase_app',
    'resolve_firebase_collection',
    'convert_firebase_error',
    'format_document_snapshot',
    'format_query_results'
]