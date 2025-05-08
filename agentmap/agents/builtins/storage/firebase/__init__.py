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
