"""
JSON document storage agents for AgentMap.

This module provides agents for reading from and writing to JSON files,
with support for local files and cloud storage providers.
"""

from agentmap.agents.builtins.storage.json.base_agent import JSONDocumentAgent
from agentmap.agents.builtins.storage.json.reader import JSONDocumentReaderAgent
from agentmap.agents.builtins.storage.json.writer import JSONDocumentWriterAgent
from agentmap.agents.builtins.storage.json.operations import JSONDocumentOperations

# Conditionally import cloud storage support
try:
    from agentmap.agents.builtins.storage.json.cloud_agent import JSONCloudDocumentAgent
    from agentmap.agents.builtins.storage.json.cloud_reader import JSONCloudDocumentReaderAgent
    from agentmap.agents.builtins.storage.json.cloud_writer import JSONCloudDocumentWriterAgent
    _json_cloud_available = True
except ImportError:
    JSONCloudDocumentAgent = None
    JSONCloudDocumentReaderAgent = None
    JSONCloudDocumentWriterAgent = None
    _json_cloud_available = False

# Import utilities if they exist
try:
    from agentmap.agents.builtins.storage.json.utils import (
        read_json_file, write_json_file, find_document_by_id, add_document_to_structure,
        create_initial_structure, ensure_id_in_document
    )
    _utils_available = True
except ImportError:
    _utils_available = False

# Register agents with the registry when available
try:
    from agentmap.agents.registry import register_agent
    
    # Register the JSON agents
    register_agent("json_reader", JSONDocumentReaderAgent)
    register_agent("json_writer", JSONDocumentWriterAgent)
    
    # Register cloud JSON agents if available
    if _json_cloud_available:
        register_agent("json_cloudreader", JSONCloudDocumentReaderAgent)
        register_agent("json_cloud_writer", JSONCloudDocumentWriterAgent)
    
    _registry_available = True
except ImportError:
    _registry_available = False

__all__ = [
    'JSONDocumentAgent',
    'JSONDocumentReaderAgent',
    'JSONDocumentWriterAgent',
    'JSONDocumentOperations',
]

# Add cloud JSON agents if available
if _json_cloud_available:
    __all__.extend([
        'JSONCloudDocumentAgent',
        'JSONCloudDocumentReaderAgent',
        'JSONCloudDocumentWriterAgent',
    ])

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