# agentmap/agents/builtins/storage/firebase/__init__.py
"""
Firebase document storage agents for AgentMap.

This module provides agents for reading from and writing to Firebase databases,
supporting both Firestore and Realtime Database.
"""

from agentmap.agents.builtins.storage.firebase.firebase_document_agent import FirebaseDocumentAgent
from agentmap.agents.builtins.storage.firebase.firebase_document_reader_agent import FirebaseDocumentReaderAgent
from agentmap.agents.builtins.storage.firebase.firebase_document_writer_agent import FirebaseDocumentWriterAgent
from agentmap.agents.builtins.storage.firebase.firebase_utilities import (
    get_firebase_config,
    initialize_firebase_app,
    resolve_firebase_collection,
    convert_firebase_error,
    format_document_snapshot,
    format_query_results
)

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