"""
JSON document storage agents for AgentMap.

This module provides agents for reading from and writing to JSON files.
"""

from agentmap.agents.builtins.storage.json.base_agent import JSONDocumentAgent
from agentmap.agents.builtins.storage.json.reader import JSONDocumentReaderAgent
from agentmap.agents.builtins.storage.json.writer import JSONDocumentWriterAgent
from agentmap.agents.builtins.storage.json.operations import JSONDocumentOperations

# Import utilities if they exist
try:
    from agentmap.agents.builtins.storage.json.utils import (
        read_json_file, write_json_file, find_document_by_id, add_document_to_structure,
        create_initial_structure, ensure_id_in_document
    )
    _utils_available = True
except ImportError:
    _utils_available = False

__all__ = [
    'JSONDocumentAgent',
    'JSONDocumentReaderAgent',
    'JSONDocumentWriterAgent',
    'JSONDocumentOperations',
]

# Add utils to __all__ if available
if _utils_available:
    __all__.extend([
        'read_json_file',
        'write_json_file',
        'find_document_by_id',
        'add_document_to_structure',
        'create_initial_structure',
        'ensure_id_in_document',
    ])
